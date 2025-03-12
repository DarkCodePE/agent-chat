import logging
from typing import Dict, Any, List, Literal

from semantic_router import Route
from semantic_router.encoders import OpenAIEncoder
from semantic_router.routers import SemanticRouter

from app.graph.state import State
from app.config.settings import LLM_MODEL
from app.util.prompt import AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT, AMBIGUITY_CLASSIFIER_PROMPT_PLANT

logger = logging.getLogger(__name__)


class AmbiguityClassifierRouter:
    """
    Enrutador semántico para clasificar consultas de usuarios entre rutas
    de requisitos y plantas/tarifas.
    """

    def __init__(self):
        # Inicializar el encoder
        self.encoder = OpenAIEncoder()

        # Crear rutas semánticas
        self.requirement_route = Route(
            name="requirements",
            description="""
            Maneja consultas sobre requisitos para revisiones técnicas vehiculares.
            Esta ruta es para usuarios que preguntan por:
            - Documentos necesarios para la revisión
            - Requisitos específicos para su tipo de vehículo
            - Documentación obligatoria
            - Permisos o certificados previos requeridos
            - Condiciones que debe cumplir el vehículo
            Usuarios típicos son dueños de vehículos que buscan prepararse para la revisión técnica.
            """,
            utterances=[
                "¿Qué documentos necesito para la revisión técnica?",
                "¿Cuáles son los requisitos para pasar la revisión?",
                "¿Qué papeles debo llevar para mi carro?",
                "¿Qué necesito para llevar mi vehículo a la revisión?",
                "¿Qué documentación debo presentar para mi auto?",
                "¿Qué certificados necesito para llevar mi vehículo?",
                "¿Cuáles son los requisitos para la revisión técnica de mi camioneta?",
                "¿Qué necesito presentar para la inspección de mi auto?",
                "¿Qué papeles tengo que llevar para la revisión técnica?",
                "¿Qué documentos se requieren para la inspección vehicular?"
            ],
        )

        self.plant_tariff_route = Route(
            name="plant_tariff",
            description="""
            Maneja consultas sobre ubicaciones de plantas de revisión y tarifas.
            Esta ruta es para usuarios interesados en:
            - Ubicaciones de plantas de revisión técnica
            - Horarios de atención
            - Precios de las revisiones
            - Costos según tipo de vehículo
            - Formas de pago disponibles
            Usuarios típicos son personas que buscan información logística y de costos.
            """,
            utterances=[
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
            ],
        )

        # Configurar el router semántico
        self.routes = [self.requirement_route, self.plant_tariff_route]
        self.semantic_router = SemanticRouter(
            encoder=self.encoder,
            routes=self.routes,
            auto_sync="local"
        )

        logger.info("Semantic Router para clasificación de ambigüedad inicializado")

    def route_query(self, query: str) -> Literal["requirements", "plant_tariff"]:
        """
        Enruta una consulta del usuario a la ruta más semánticamente similar.

        Args:
            query: La consulta del usuario

        Returns:
            Nombre de la ruta: "requirements" o "plant_tariff"
        """
        try:
            # Usar el router para determinar la ruta más cercana
            result = self.semantic_router(query)
            logger.info(f"Consulta: '{query}' enrutada a '{result.name}'")
            return result.name
        except Exception as e:
            # En caso de error, enrutar por defecto a requisitos
            logger.error(f"Error en enrutamiento semántico: {str(e)}")
            return "requirements"

    def get_prompt_template(self, query: str) -> str:
        """
        Devuelve la plantilla de prompt adecuada según la clasificación semántica.

        Args:
            query: La consulta del usuario

        Returns:
            La plantilla de prompt apropiada
        """
        route_name = self.route_query(query)

        if route_name == "requirements":
            return AMBIGUITY_CLASSIFIER_PROMPT_REQUIREMENT
        else:
            return AMBIGUITY_CLASSIFIER_PROMPT_PLANT


# Se puede crear una instancia singleton
ambiguity_router = AmbiguityClassifierRouter()