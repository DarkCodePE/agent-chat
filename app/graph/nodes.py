import logging
from typing import Dict, Any, Literal

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_qdrant import Qdrant
from numpy.f2py.crackfortran import previous_context
from qdrant_client import QdrantClient

from app.graph.state import State, AmbiguityClassification, VehicleInfo, PlantInfo, LocationInfo
from app.config.settings import LLM_MODEL, QDRANT_URL, QDRANT_API_KEY

from app.services.document_service import DocumentService
from app.services.location_services_map_box import get_district_coordinates, PLANTS, calculate_distances
from app.tools.location_tools import setup_llm_with_tools

from app.util.prompt import ASSISTANT_PROMPT, AMBIGUITY_CLASSIFIER_PROMPT, AMBIGUITY_CLASSIFIER_PROMPT_v2, \
    AMBIGUITY_CLASSIFIER_PROMPT_v4, AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT, AMBIGUITY_CLASSIFIER_PROMPT_PLANT, \
    AMBIGUITY_CLASSIFIER_PROMPT_WELCOME, AMBIGUITY_CLASSIFIER_PROMPT_LOCATION, IMPORTANT_INFO_PROMPT

logger = logging.getLogger(__name__)


# ========== IMPLEMENTACIÓN DE ENRUTAMIENTO SEMÁNTICO INTEGRADA ==========

class SimpleSemanticRouter:
    """
    Versión simplificada de enrutamiento semántico para clasificación de consultas.
    No requiere dependencias externas, usa LangChain directamente.
    """

    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.welcome_examples = [
            "Hola",
            "Buenos días",
            "Buenas tardes",
            "Buenas noches",
            "Hola, ¿cómo estás?",
            "Hola, mucho gusto",
        ]
        self.requirements_examples = [
            "¿Qué documentos necesito para la revisión técnica?",
            "¿Cuáles son los requisitos para pasar la revisión?",
            "¿Qué papeles debo llevar para mi carro?",
            "¿Qué necesito para llevar mi vehículo a la revisión?",
            "¿Qué documentación debo presentar para mi auto?",
            "¿Qué certificados necesito para llevar mi vehículo?",
            "¿Cuáles son los requisitos para la revisión técnica de mi camioneta?",
            "¿Qué necesito presentar para la inspección de mi auto?",
            "¿Qué papeles tengo que llevar para la revisión técnica?",
            "¿Qué documentos se requieren para la inspección vehicular?",
            "toyota", "hyundai", "kia", "nissan", "chevrolet", "suzuki",
            "mitsubishi", "volkswagen", "honda", "ford", "mazda", "bmw",
            "mercedes", "audi", "renault", "peugeot", "citroën", "fiat",
            "jeep", "subaru", "volvo", "lexus", "changan", "jac", "mg",
            "geely", "great wall", "byd", "dfsk", "ssangyong", "haval"
        ]

        self.plant_tariff_examples = [
            "¿Dónde puedo hacer la revisión técnica?",
            "¿Cuánto cuesta la revisión técnica?",
            "¿Qué plantas hay cerca de mi ubicación?",
            "¿Cuál es el horario de atención de las plantas?",
            "¿Cuáles son las tarifas para la revisión técnica?",
            "¿Tienen planta en San Juan de Lurigancho?",
            "¿Cuánto me cuesta la revisión para mi taxi?",
            "¿Qué precio tiene la inspección para una moto?",
            "¿A qué hora abren las plantas de revisión?",
            "¿Cuál es la dirección de la planta más cercana?"
            "¿Cuanto es el costo?"
            "¿Cuanto me va salir eso?"
            "¿Cual es costo total?"
        ]

        # Nueva categoría: ejemplos de ubicación
        self.location_examples = [
            "Estoy en San Juan de Lurigancho",
            "Vivo en El Agustino",
            "Me encuentro en Comas",
            "Estoy cerca de Carabayllo",
            "Mi ubicación es Ate",
            "¿Cuál es la planta más cercana a Villa El Salvador?",
            "Me gustaría ir a la planta más cercana a mi casa en San Martín",
            "¿Hay alguna planta cerca de Los Olivos?",
            "Necesito la dirección de la planta más cercana a Independencia"
        ]

        # Pre-calcular embeddings para todas las categorías
        self.welcome_embeddings = None
        self.requirements_embeddings = None
        self.plant_tariff_embeddings = None
        self.location_embeddings = None
        self._initialize_embeddings()

        logger.info("Router semántico simplificado inicializado")

    def _initialize_embeddings(self):
        try:
            # Generar embeddings para ejemplos de bienvenida
            self.welcome_embeddings = self.embeddings.embed_documents(self.welcome_examples)

            # Generar embeddings para ejemplos de requisitos
            self.requirements_embeddings = self.embeddings.embed_documents(self.requirements_examples)

            # Generar embeddings para ejemplos de planta/tarifas
            self.plant_tariff_embeddings = self.embeddings.embed_documents(self.plant_tariff_examples)

            self.location_embeddings = self.embeddings.embed_documents(self.location_examples)

            logger.info("Embeddings inicializados para router semántico")
        except Exception as e:
            logger.error(f"Error inicializando embeddings: {str(e)}")

    def route_query(self, query: str) -> Literal["welcome", "requirements", "plant_tariff", "location"]:
        """
        Enruta una consulta del usuario a la ruta más semánticamente similar.

        Args:
            query: La consulta del usuario

        Returns:
            Nombre de la ruta: "welcome", "requirements" o "plant_tariff"
        """
        try:
            # Si no se han inicializado los embeddings, hacerlo ahora
            if self.welcome_embeddings is None or self.requirements_embeddings is None or self.plant_tariff_embeddings is None:
                self._initialize_embeddings()

            # Generar embedding para la consulta
            query_embedding = self.embeddings.embed_query(query)

            # Calcular similitud con embeddings de bienvenida
            welcome_similarities = self._calculate_similarities(query_embedding, self.welcome_embeddings)
            max_welcome_similarity = max(welcome_similarities)

            # Calcular similitud con embeddings de requirements
            req_similarities = self._calculate_similarities(query_embedding, self.requirements_embeddings)
            max_req_similarity = max(req_similarities)

            # Calcular similitud con embeddings de plant_tariff
            plant_similarities = self._calculate_similarities(query_embedding, self.plant_tariff_embeddings)
            max_plant_similarity = max(plant_similarities)

            # Calcular similitud con embeddings de ubicación
            location_similarities = self._calculate_similarities(query_embedding, self.location_embeddings)
            max_location_similarity = max(location_similarities)

            # Determinar la ruta con mayor similitud
            max_similarity = max(max_welcome_similarity, max_req_similarity, max_plant_similarity, max_location_similarity)

            if max_similarity == max_welcome_similarity:
                #logger.info(f"Consulta: '{query}' enrutada a 'welcome' (similitud: {max_welcome_similarity:.3f})")
                return "welcome"
            elif max_similarity == max_req_similarity:
                #logger.info(f"Consulta: '{query}' enrutada a 'requirements' (similitud: {max_req_similarity:.3f})")
                return "requirements"
            elif max_similarity == max_location_similarity:
                #logger.info(f"Consulta: '{query}' enrutada a 'plant_tariff' (similitud: {max_plant_similarity:.3f})")
                return "location"
            else:
                #logger.info(f"Consulta: '{query}' enrutada a 'plant_tariff' (similitud: {max_plant_similarity:.3f})")
                return "plant_tariff"
        except Exception as e:
            # En caso de error, enrutar por defecto a requisitos
            logger.error(f"Error en enrutamiento semántico: {str(e)}")
            return "requirements"

    def _calculate_similarities(self, query_embedding, document_embeddings):
        """Calcula similitud coseno entre consulta y documentos."""
        from numpy import dot
        from numpy.linalg import norm

        # Calcular similitud coseno entre la consulta y cada documento
        similarities = []
        for doc_embedding in document_embeddings:
            similarity = dot(query_embedding, doc_embedding) / (norm(query_embedding) * norm(doc_embedding))
            similarities.append(similarity)

        return similarities

    def get_prompt_template(self, query: str) -> str:
        """
        Devuelve la plantilla de prompt adecuada según la clasificación semántica.

        Args:
            query: La consulta del usuario

        Returns:
            La plantilla de prompt apropiada
        """
        route_name = self.route_query(query)

        if route_name == "welcome":
            # Podemos usar una plantilla específica para saludos o la más genérica
            # Por ahora, usando la de requisitos como default para saludos
            return AMBIGUITY_CLASSIFIER_PROMPT_WELCOME
        elif route_name == "requirements":
            return AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT
        elif route_name == "location":
            return AMBIGUITY_CLASSIFIER_PROMPT_LOCATION
        else:
            return AMBIGUITY_CLASSIFIER_PROMPT_PLANT


# Crear instancia de router semántico
ambiguity_router = SimpleSemanticRouter()

# ========== FIN DE IMPLEMENTACIÓN DE ENRUTAMIENTO SEMÁNTICO ==========

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
    #logger.info(f"messages: {messages}")
    question = state["input"]
    previous_questions = state["previous_questions"]

    system_instructions = IMPORTANT_INFO_PROMPT.format(
        question=question,
        messages=messages,
        previous_questions=previous_questions
    )

    # Configuramos el LLM para obtener salida estructurada
    structured_llm = llm.with_structured_output(VehicleInfo)

    # Invocamos el modelo
    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Extrae los puntos clave de la conversación")
    ])
    if state["plant_location"] is None:
        plant_location = result["plant_location"]
    else:
        plant_location = state["plant_location"]

    print("vehicle_type: ", result["vehicle_type"])
    print("location: ", result["location"])
    print("model: ", result["model"])
    print("annual: ", result["annual"])
    print("plant_location: ", plant_location)
    # Con reducers, simplemente devolvemos los resultados
    # La función reducer se encargará de preservar los valores existentes
    return {
        "vehicle_type": result["vehicle_type"],
        "location": result["location"],
        "plant_location": plant_location,
        "model": result["model"],
        "annual": result["annual"]
    }


def capture_important_info_old(state: State) -> dict:
    """
    Analiza la conversación para extraer y almacenar información importante
    sobre el vehículo y las necesidades del usuario.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    # Obtenemos los mensajes recientes para analizar
    messages = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]
    # logger.info(f"messages: {messages}")
    question = state["input"]
    # Prompt para extraer la información clave
    system_prompt = f"""
    Eres un asistente experto en analizar conversaciones para extraer información importante.

    A continuación, se te proporciona el historial de una conversación con un usuario sobre revisiones técnicas vehiculares.

    Tu tarea es extraer los siguientes detalles si están presentes:
    - Tipo de vehículo: tienes una lista de opciones para elegir ("taxi", "transporte particular", "transporte  escolar, "transporte de trabajadores", "transporte turístico", "transporte mercancia general", "transporte mercancia peligrosa"), si te brindan un tipo de vehículo diferente, entonces clasificalo dentro de la lista de opciones proporcionadas.
   - Ubicación del usuario: Extrae cualquier referencia a una ubicación donde se encuentra el usuario. Presta especial atención a frases como "estoy en", "vivo en", "me encuentro en", "cerca de", "mi ubicación es", "mi casa en", "estoy cerca de" seguidas de un nombre de distrito, zona o dirección en Lima. Incluye el nombre completo del distrito o zona mencionada.
      Ejemplos:
      - "Estoy en San Juan de Lurigancho" → "San Juan de Lurigancho"
      - "Vivo en El Agustino" → "El Agustino"
      - "estoy cerca del agustino" → "El Agustino"
      - "Me encuentro en Comas" → "Comas"
      - "¿Hay alguna planta cerca de Los Olivos?" → "Los Olivos"
      - "av. los alamos 123"
      - ""jr. los claveles 456"
    - Ubicación de la planta (Ejemplo: "sjl", "trapiche", "carabayllo")
    - Modelo del vehículo (Ejemplo: "toyota yaris", "hyundai accent", "kia rio")
    - Año de fabricación del vehículo (Ejemplo: "2010", "2015", "2020")

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
        HumanMessage(content="Extrae los puntos clave de la conversación")
    ])
    if state.get("plant_location") is None:
        plant_location = result["plant_location"]
    else:
        plant_location = state["plant_location"]
    # Con reducers, simplemente devolvemos los resultados
    # La función reducer se encargará de preservar los valores existentes
    return {
        "vehicle_type": result["vehicle_type"],
        "plant_location": plant_location,
        "location": result["location"],
        "model": result["model"],
        "annual": result["annual"]
    }


def classify_ambiguity(state: State) -> dict:
    """
    Determina si la consulta del usuario es ambigua y requiere clarificación.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    user_query = state["input"]
    context = state["context"]
    vehicle_type = state["vehicle_type"]
    location = state["location"]
    model = state["model"]
    annual = state["annual"]
    plant_location = state["plant_location"]
    previous_questions = state["previous_questions"]
    previous_categories = state["previous_categories"]
    current_topic = state["current_topic"]
    print("vehicle_type: ", vehicle_type)
    print("location: ", location)
    print("model: ", model)
    print("annual: ", annual)
    print("plant_location: ", plant_location)
    print("previous_questions: ", previous_questions)
    print("current_topic: ", current_topic)
    # Preparar historial de conversación en formato legible
    conversation_history = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]

    # Si hay un resumen, incluirlo también
    summary = state["summary"]

    # Utilizar el enrutador semántico para elegir el prompt adecuadoc
    if current_topic == "requirements":
        prompt_template = AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT
    elif current_topic == "plant_tariff":
        prompt_template = AMBIGUITY_CLASSIFIER_PROMPT_PLANT
    elif current_topic == "welcome":
        prompt_template = AMBIGUITY_CLASSIFIER_PROMPT_WELCOME
    else:
        # Default prompt para casos no manejados
        prompt_template = AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT

    #logger.info(f"Prompt template: {prompt_template}")
    recent_messages = state["messages"][-7:] if len(state["messages"]) > 7 else state["messages"]
    # Configurar el modelo para salida estructurada
    structured_llm = llm.with_structured_output(AmbiguityClassification)

    # Preparar el prompt con los datos actuales
    system_instructions = prompt_template.format(
        user_query=user_query,
        retrieved_context=context,
        previous_questions=previous_questions,
        previous_categories=previous_categories,
        vehicle_type=vehicle_type,
        location=location,
        plant_location=plant_location,
        model=model,
        annual=annual,
        recent_messages=recent_messages,
    )
    # print("system_instructions: ", system_instructions)
    # Invocar el modelo
    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Analiza esta consulta sobre revisiones técnicas vehiculares y determina si es ambigua.")
    ])

    return {"ambiguity_classification": result}


def route_desired_info(state: State) -> dict[str, Literal["requirements", "plant_tariff", "welcome","location"]]:
    """
    Route the user query to the desired information based on the context.

    Args:
        state: The current state

    Returns:
        The desired information to retrieve: "requirements" or "plant_tariff"
    """
    # Use the semantic router to determine the most semantically similar route
    user_query = state["input"]
    # Log de qué ruta se ha utilizado
    route_name = ambiguity_router.route_query(user_query)
    logger.info(f"Consulta '{user_query}' clasificada como '{route_name}'")
    return {"current_topic": route_name}


def ask_clarification(state: State) -> dict:
    """Genera una pregunta de clarificación al usuario."""
    # Obtener la información de ambigüedad
    clarification_question = state["ambiguity_classification"]["clarification_question"]
    ambiguity_category = state["ambiguity_classification"]["ambiguity_category"]
    # print("clarification_question: ", clarification_question)
    # print("ambiguity_category: ", ambiguity_category)
    # Construir respuesta amigable
    mensaje = f"Para ayudarte mejor, necesito más información. {clarification_question}"
    #messages = state["messages"] + [AIMessage(content=mensaje)]
    print("state ask current_topic: ", state["current_topic"])
    print("state ask vehicle_type: ", state["vehicle_type"])
    print("state ask location: ", state["location"])
    return {
        "answer": mensaje,
        "messages": [AIMessage(content=mensaje)],  # AIMessage porque es el asistente quien habla
        "previous_questions": [clarification_question],  # CORREGIDO: ahora es lista
        "previous_categories": [ambiguity_category]  # CORREGIDO: ahora es lista
    }


def process_location_node(state: State) -> Dict[str, Any]:
    """
    Process a location-based query using the find_nearest_plant tool.

    Args:
        state: The current state including user input and previously captured location.

    Returns:
        Updated state with the results of the location tool call.
    """
    # Get the user's query
    user_query = state["input"]

    # Get the location from state if available, otherwise extract from query
    location = state.get("location")

    # Configure LLM with tools
    llm_with_tools = setup_llm_with_tools()

    # Create a prompt that instructs the LLM to use the location tool
    system_message = """
         Eres un asistente experto en ayudar a los usuarios a encontrar plantas de revisión técnica en Perú.

         IMPORTANTE: Usa SIEMPRE la herramienta find_nearest_plant para encontrar las plantas más cercanas a la ubicación
         proporcionada. No inventes información ni respondas sin usar la herramienta.

         Después de obtener los resultados:
         - Sé conversacional y amigable en tu respuesta
         - Enfatiza las plantas más cercanas a la ubicación del usuario
         - Incluye la información completa de dirección, distancia, teléfono y horario que proporciona la herramienta
         - Si la herramienta devuelve un error, explica con amabilidad el problema y sugiere que proporcione otra ubicación
         """

    # Invoke the LLM with the tool
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_query}
    ]

    response = llm_with_tools.invoke(messages)

    # Update state with messages and the plant location if found
    state["answer"] = response
    state["messages"] += [
        HumanMessage(content=state["input"]),
        AIMessage(content=response)
    ]
    #logger.info(f"Processed location query with result plant ID: {state.get('plant_location')}")
    #logger.info(f"response location: {response}")
    print("state process current_topic: ", state["current_topic"])
    print("state process vehicle_type: ", state["vehicle_type"])
    print("state process location: ", state["location"])
    #logger.info(f"updated_messages: {updated_messages}")
    return state


def process_location_node_v2(state: State) -> Dict[str, Any]:
    """
    Process a location-based query directly, without using tools.

    Args:
        state: The current state including user input and previously captured location.

    Returns:
        Updated state with the results of the location query.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    # Get the user's query
    user_query = state["input"]

    # Get the location from state if available, otherwise extract from query
    user_query = state["input"]
    context = state["context"]
    vehicle_type = state["vehicle_type"]
    location = state["location"]
    model = state["model"]
    annual = state["annual"]
    plant_location = state["plant_location"]
    previous_questions = state["previous_questions"]
    previous_categories = state["previous_categories"]
    #current_topic = state["current_topic"]

    # Get coordinates for the user's location
    user_lat, user_lng = get_district_coordinates(location)

    # Get all plants
    all_plants = list(PLANTS.values())

    # Calculate distances from user location to all plants
    plants_with_distances = calculate_distances(user_lat, user_lng, all_plants)

    # Sort plants by distance
    sorted_plants = sorted(plants_with_distances, key=lambda x: x["distance_km"])

    # Get the 3 nearest plants
    nearest_plants = sorted_plants[:3]

    # Limitar la cantidad de mensajes en el historial
    recent_messages = state["messages"][-7:] if len(state["messages"]) > 7 else state["messages"]

    system_instructions = AMBIGUITY_CLASSIFIER_PROMPT_LOCATION.format(
        user_query=user_query,
        retrieved_context=context,
        previous_questions=previous_questions,
        previous_categories=previous_categories,
        vehicle_type=vehicle_type,
        location=location,
        nearest_plants=nearest_plants,
        plant_location=plant_location,
        model=model,
        annual=annual,
        recent_messages=recent_messages
    )
    # Save the plant_location for future reference
    plant_location = nearest_plants[0]["id"] if nearest_plants else None

    human_message = f"Usando la información de las plantas cercanas a {location}, formula una respuesta amigable y detallada que ayude al usuario a encontrar la planta más conveniente."

    structured_llm = llm.with_structured_output(LocationInfo)

    result = structured_llm.invoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=human_message)
    ])
    #logger.info(f"Este es el resultado '{result}'")
    print("Este es el resultado: ", result)
    print("location -> node: ", location)
    print("vehicle_type -> node: ", vehicle_type)
    print("plant_location -> node: ", plant_location)
    # Update state
    updated_messages = state.get("messages", []) + [
        HumanMessage(content=user_query),
        AIMessage(content=result["answer"])
    ]

    return {
        "answer": result["answer"],
        "messages": updated_messages,
        "current_topic": result["current_topic"],
        "nearest_plants": result["nearest_plants"],
    }

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


def route_by_semantic(state: State) -> dict:
    """
    Determine the route based on semantic classification of the input.

    This router decides whether to process a location-based query or go through
    the regular ambiguity classification flow.

    Args:
        state: Current state with input and context

    Returns:
        Next node to execute: either "process_location" or "classify_ambiguity"
    """

    # Get the user query
    user_query = state["input"]

    # Use the semantic router to determine the route type
    route_name = ambiguity_router.route_query(user_query)
    return {"current_topic": route_name}


def route_by_semantic_type(state: State) -> str:
    """
    Determine the route based on semantic classification of the input.

    This router decides whether to process a location-based query or go through
    the regular ambiguity classification flow.

    Args:
        state: Current state with input and context

    Returns:
        Next node to execute: either "process_location" or "classify_ambiguity"
    """
    current_topic = state["current_topic"]
    #logger.info("current_topic: ", current_topic)
    print("current_topicxxx: ", current_topic)
    # Special handling for location route
    if current_topic == "location":
        return "process_location"
    print("state route_by_semantic_type current_topic: ", state["current_topic"])
    print("state route_by_semantic_type vehicle_type: ", state["vehicle_type"])
    print("state route_by_semantic_type location: ", state["location"])
    # All other routes go to the regular flow
    return "classify_ambiguity"


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
        vehicle_type = state["vehicle_type"]
        location = state["location"]
        plant_location = state["plant_location"]
        user_query = state["input"]
        previous_questions = state["previous_questions"]
        # Limitar la cantidad de mensajes en el historial
        recent_messages = state["messages"][-7:] if len(state["messages"]) > 7 else state["messages"]

        # Construir el mensaje del sistema con el contexto y resumen
        system_message = ASSISTANT_PROMPT.format(
            context=context,
            chat_history=summary,
            vehicle_type=vehicle_type,
            location=location,
            plant_location=plant_location,
            user_query=user_query,
            previous_questions=previous_questions,
            recent_messages=recent_messages
        )

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
        # state["answer"] = response
        # state["messages"] += [
        #     HumanMessage(content=state["input"]),
        #     AIMessage(content=response)
        # ]
        updated_messages = state.get("messages", []) + [
            HumanMessage(content=state["input"]),
            AIMessage(content=response)
        ]
        logger.info(f"Generated response for input: {state['input'][:50]}...")
        print("state generate current_topic: ", state["current_topic"])
        print("state generate vehicle_type: ", state["vehicle_type"])
        print("state generate location: ", state["location"])
        return {
            "answer": response,
            "messages": updated_messages,
        }

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
