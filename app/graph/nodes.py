import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage
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
    Generate a response based on chat history and context.

    Args:
        state: The current state including user input and chat history

    Returns:
        Updated state with the answer
    """
    try:
        # Initialize the LLM
        llm = ChatOpenAI(model=LLM_MODEL)

        # Define the system prompt based on context
        system_message = "You are a helpful, friendly assistant. "

        # Add retrieved documents if available
        context = ""
        if state.get("documents") and state["documents"]:
            context = "\n\n".join([doc.page_content for doc in state["documents"]])
            system_message += "Use the following context to help answer the question: "
            system_message += f"{context}\n\n"

        system_message += "Be concise and clear in your responses."

        # Define the chat prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        # Create the chain
        chain = prompt | llm | StrOutputParser()

        # Invoke the chain
        response = chain.invoke({
            "chat_history": state["chat_history"],
            "input": state["input"]
        })


        # Set the answer
        state["answer"] = response

        # Update chat history with the new exchange
        state["chat_history"] = state["chat_history"] + [
            HumanMessage(content=state["input"]),
            AIMessage(content=response)
        ]

        logger.info(f"Generated response for input: {state['input'][:50]}...")
        return state

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        error_message = "I'm sorry, I encountered an error generating a response. Please try again."
        raise Exception(error_message)
