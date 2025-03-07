# Define State structure
# LangChain imports
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.documents import Document
from typing import List, Optional, TypedDict, Annotated

from langgraph.graph import add_messages
class AmbiguityClassification(TypedDict):
    is_ambiguous: Optional[bool]  # For tracking whether the user's input is ambiguous
    ambiguity_category: Optional[str]  # For storing the category of ambiguity
    clarification_question: Optional[str]

# Primero, ampliamos el State para incluir información vehicular
class VehicleInfo(TypedDict):
    vehicle_type: Optional[str]  # tipo de vehículo (taxi, particular, etc.)
    plant_location: Optional[str]  # ubicación de la planta
    service_type: Optional[str]  # tipo de servicio (primera vez, renovación)
    tariff_type: Optional[str]  # categoría tarifaria

class State(TypedDict):
    input: str
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    answer: str
    documents: Optional[List[Document]]  # For storing retrieved documents
    web_search: Optional[str]  # For deciding whether to perform a web search
    summary: Optional[str]  # For storing the summary of the conversation
    ambiguity_classification: AmbiguityClassification
    vehicle_info: VehicleInfo  # For storing the classification of ambiguity

