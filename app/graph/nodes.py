import logging
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient

from app.graph.state import State
from app.config.settings import LLM_MODEL, QDRANT_URL, QDRANT_API_KEY
from app.services.document_service import DocumentService
from app.util.prompt import ASSISTANT_PROMPT

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


def retrieve_context(state: State) -> State:
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
    return state


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

        # # Construir el mensaje del sistema con el contexto y resumen
        # system_message = "You are a helpful, friendly assistant."
        #
        # # Agregar el contexto de documentos si existe
        # context = state.get("context", "")
        # if context:
        #     system_message += f"\n\nUse the following context to help answer the question:\n{context}\n"
        # elif state.get("documents") and state["documents"]:
        #     document_context = "\n\n".join([doc.page_content for doc in state["documents"]])
        #     system_message += f"\n\nUse the following context to help answer the question:\n{document_context}\n"
        #
        # # Agregar resumen si existe
        # summary = state.get("summary", "")
        # if summary:
        #     system_message += f"\n\nSummary of the conversation so far: {summary}\n"
        #
        # system_message += "\nBe concise and clear in your responses. If the context doesn't contain relevant information to answer the question, say so and answer based on your knowledge."

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
