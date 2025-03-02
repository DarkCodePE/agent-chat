import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from app.graph.state import State
from app.config.settings import LLM_MODEL

logger = logging.getLogger(__name__)


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
    # This is a placeholder implementation
    # In a real application, you would implement RAG here

    # For now, we're just passing through the state

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

        # Construir el mensaje del sistema con el contexto y resumen
        system_message = "You are a helpful, friendly assistant."

        # Agregar el contexto de documentos si existe
        if state.get("documents") and state["documents"]:
            context = "\n\n".join([doc.page_content for doc in state["documents"]])
            system_message += f"\nUse the following context to answer: {context}\n"

        # Agregar resumen si existe
        summary = state.get("summary", "")
        if summary:
            system_message += f"\nSummary of the conversation so far: {summary}\n"

        system_message += "\nBe concise and clear in your responses."

        # Limitar la cantidad de mensajes en el historial
        recent_messages = state["chat_history"][-5:]  # Últimos 5 mensajes

        # Construir el prompt con historial y nuevo input
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        # Ejecutar la cadena del modelo
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "chat_history": recent_messages,
            "input": state["input"]
        })

        # Guardar la respuesta y actualizar el historial de chat
        state["answer"] = response
        state["chat_history"] += [
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
    messages = state["chat_history"] + [HumanMessage(content=summary_prompt)]
    response = llm.invoke(messages)

    # Eliminar todos los mensajes excepto los 2 más recientes
    delete_messages = [RemoveMessage(id=m.id) for m in state["chat_history"][:-2]]

    return {"summary": response.content, "chat_history": delete_messages}
