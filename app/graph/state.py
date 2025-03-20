# Define State structure
# LangChain imports
from operator import add

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.documents import Document
from typing import List, Optional, TypedDict, Annotated

from langgraph.graph import add_messages


# Tu función reducer personalizada
def preserve_info(old_value, new_value):
    """Preserva el valor anterior si el nuevo es None"""
    if new_value is None:
        return old_value
    return new_value


class AmbiguityClassification(TypedDict):
    is_ambiguous: Optional[bool]  # For tracking whether the user's input is ambiguous
    ambiguity_category: Optional[str]  # For storing the category of ambiguity
    clarification_question: Optional[str]


class PlantInfo(TypedDict):
    nearest_plants: Optional[List[str]]
    near_plant: Optional[str]
    answer: Optional[str]

class MentionInfo(TypedDict):
    answer: Optional[str]
    message: Optional[str]

class VehicleInfo(TypedDict):
    vehicle_type: Optional[str]  # tipo de vehículo (taxi, particular, etc.)
    plant_location: Optional[str]  # ubicación de la planta
    location: Optional[str]  # ubicación del vehículo
    model: Optional[str]  # modelo del vehículo
    annual: Optional[str]  # año de fabricación del vehículo


class LocationInfo(TypedDict):
    current_topic: Optional[str]  # precio del vehículo
    answer: Optional[str]
    nearest_plants: List[str]

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
    previous_questions: Annotated[List[str], add]  # storing previous questions
    previous_categories: Annotated[List[str], add]  # storing previous categories
    vehicle_type: Optional[str]  # tipo de vehículo (taxi, particular, etc.)
    plant_location: Optional[str]  # ubicación de la planta
    location: Optional[str]  # ubicación del vehículo
    model: Optional[str]  # modelo del vehículo
    annual: Optional[str]  # año de fabricación del vehículo
    current_topic: Optional[str]
    nearest_plants: List[str]
