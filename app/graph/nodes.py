import logging
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient

from app.graph.state import State, AmbiguityClassification, VehicleInfo
from app.config.settings import LLM_MODEL, QDRANT_URL, QDRANT_API_KEY
from app.services.document_service import DocumentService
from app.util.prompt import ASSISTANT_PROMPT, AMBIGUITY_CLASSIFIER_PROMPT, AMBIGUITY_CLASSIFIER_PROMPT_v2

logger = logging.getLogger(__name__)

# Singleton document service
_document_service = None


def get_document_service() -> DocumentService:
    """Get or create a DocumentService singleton."""
    global _document_service
    if _document_service is None:
        try:
            _document_service = DocumentService()
        except Exception as e:
            logger.error(f"Error initializing document service: {str(e)}")
            raise
    return _document_service


# Nodo para capturar información importante
def capture_important_info(state: State) -> dict:
    """
    Analiza la conversación para extraer y almacenar información importante
    sobre el vehículo y las necesidades del usuario.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    # Obtenemos los mensajes recientes para analizar
    messages = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]
    logger.info(f"messages: {messages}")
    question = state["input"]
    # Prompt para extraer la información clave
    system_prompt = f"""
    Eres un asistente experto en analizar conversaciones para extraer información importante.

    A continuación, se te proporciona el historial de una conversación con un usuario sobre revisiones técnicas vehiculares.

    Tu tarea es extraer los siguientes detalles si están presentes:
    - Tipo de vehículo (Ejemplo: "taxi", "particular", "transporte de mercancías")
    - Ubicación de la planta (Ejemplo: "sjl", "trapiche", "carabayllo")
    - Tipo de servicio (Ejemplo: "primera vez", "renovación")
    - Categoría tarifaria (Ejemplo: "M1", "N1")

    Si algún dato no está disponible en la conversación, devuelve null para ese campo.
    
    pregunta: 
    {question}
    Conversación:
    {messages}

    Importante: 
    1. No inventes información que no esté explícitamente mencionada en la conversación
    2. Presta especial atención a las respuestas del usuario
    """

    # Configuramos el LLM para obtener salida estructurada
    structured_llm = llm.with_structured_output(VehicleInfo)

    # Invocamos el modelo
    result = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content="Extrae la información vehicular de esta conversación")
    ])

    # Actualizamos el estado con la información extraída
    return {"vehicle_info": result}


def classify_ambiguity(state: State) -> dict:
    """
    Determina si la consulta del usuario es ambigua y requiere clarificación.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    user_query = state["input"]
    context = state["context"]

    # Preparar historial de conversación en formato legible
    conversation_history = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]

    # Si hay un resumen, incluirlo también
    summary = state["summary"]
    vehicle_info = state["vehicle_info"]

    # Configurar el modelo para salida estructurada
    structured_llm = llm.with_structured_output(AmbiguityClassification)

    # Preparar el prompt con los datos actuales
    system_instructions = AMBIGUITY_CLASSIFIER_PROMPT_v2.format(
        user_query=user_query,
        retrieved_context=context,
        conversation_history=conversation_history,
        summary=summary,
        vehicle_info=vehicle_info
    )

    # Invocar el modelo
    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Analiza esta consulta sobre revisiones técnicas vehiculares")
    ])

    return {"ambiguity_classification": result}


def ask_clarification(state: State) -> dict:
    """Genera una pregunta de clarificación al usuario."""
    # Obtener la información de ambigüedad
    clarification_question = state["ambiguity_classification"]["clarification_question"]

    # Construir respuesta amigable
    mensaje = f"Para ayudarte mejor, necesito más información. {clarification_question}"

    # Actualizar estado
    state["answer"] = mensaje
    state["messages"].append(AIMessage(content=mensaje))

    return {"answer": mensaje, "messages": state["messages"]}

def retrieve_context(state: State) -> dict:
    """
    Retrieve relevant context based on the user's input.

    In a more advanced implementation, this would use a vector store
    to retrieve relevant documents based on the user's query.

    Args:
        state: The current state

    Returns:
        The updated state with context
    """
    query_text = state["input"]

    # Get the document service
    document_service = get_document_service()

    # Search for relevant documents
    search_results = document_service.search_documents(query_text, limit=5)

    # Convert to LangChain Document objects
    documents = []
    for result in search_results:
        doc = Document(
            page_content=result["content"],
            metadata={
                **result["metadata"],
                "score": result["score"],
                "document_id": result["id"]
            }
        )
        documents.append(doc)

    # Build context text from documents
    if documents:
        context_parts = []
        for i, doc in enumerate(documents, 1):
            # Extract title or use a default
            title = doc.metadata.get("name", f"Document {i}")
            # Add source info and content
            context_parts.append(f"Document {i}: {title}\n{doc.page_content}")

        # Join all parts with clear separators
        context = "\n\n---\n\n".join(context_parts)
    else:
        context = ""

    # Update state
    state["documents"] = documents
    state["context"] = context

    logger.info(f"Retrieved {len(documents)} relevant documents for query: {query_text[:50]}...")
    return {"context": context, "documents": documents}


def generate_response(state: State) -> Dict[str, Any]:
    """
    Generate a response based on chat history, context, and summary.

    Args:
        state: The current state including user input, chat history, and context.

    Returns:
        Updated state with the generated answer.
    """
    try:
        llm = ChatOpenAI(model=LLM_MODEL)
        context = state["context"]
        summary = state["summary"]

        # Construir el mensaje del sistema con el contexto y resumen
        system_message = ASSISTANT_PROMPT.format(
            context=context,
            chat_history=summary
        )

        # Limitar la cantidad de mensajes en el historial
        recent_messages = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]

        # Construir el prompt con historial y nuevo input
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{input}")
        ])

        # Ejecutar la cadena del modelo
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "messages": recent_messages,
            "input": state["input"]
        })

        # Guardar la respuesta y actualizar el historial de chat
        state["answer"] = response
        state["messages"] += [
            HumanMessage(content=state["input"]),
            AIMessage(content=response)
        ]

        logger.info(f"Generated response for input: {state['input'][:50]}...")
        return state

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise Exception("I'm sorry, I encountered an error generating a response.")


def summarize_conversation(state: State) -> Dict[str, Any]:
    """
    Summarizes the conversation and removes old messages.

    Args:
        state: The current state including chat history.

    Returns:
        Updated state with summary and trimmed messages.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    summary = state.get("summary", "")
    summary_prompt = (
        f"This is the current summary: {summary}\nExtend it with the new messages:"
        if summary else "Create a summary of the conversation above:"
    )

    # Agregar el prompt al historial y ejecutar el resumen con el modelo
    messages = state["messages"] + [HumanMessage(content=summary_prompt)]
    response = llm.invoke(messages)

    # Eliminar todos los mensajes excepto los 2 más recientes
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]

    return {"summary": response.content, "messages": delete_messages}
