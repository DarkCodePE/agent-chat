# Define State structure
# LangChain imports
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.documents import Document
from typing import List, Optional, TypedDict, Annotated

from langgraph.graph import add_messages


class State(TypedDict):
    input: str
    chat_history: Annotated[List[BaseMessage], add_messages]
    context: str
    answer: str
    documents: Optional[List[Document]]  # For storing retrieved documents
    web_search: Optional[str]  # For deciding whether to perform a web search
    summary: Optional[str]  # For storing the summary of the conversation

