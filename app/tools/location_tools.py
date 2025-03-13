# location/location_tools.py
import logging
from typing import Dict, List, Any, Annotated
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId

from langchain_openai import ChatOpenAI

from app.config.settings import LLM_MODEL
from app.services.location_services import get_district_coordinates, calculate_distances, PLANTS

logger = logging.getLogger(__name__)


@tool
def find_nearest_plant(
        location: str,
        tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """
    Encuentra las plantas de revisión técnica más cercanas a una ubicación utilizando Google Maps.

    Args:
        location: La ubicación del usuario (distrito, dirección, etc.). Ejemplo: "San Juan de Lurigancho", "Comas", etc.

    Returns:
        Información sobre las plantas más cercanas, incluyendo dirección, distancia, teléfono y horario
    """
    try:
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

        # Format response for user
        formatted_info = f"Las plantas más cercanas a **{location}** son:\n\n"

        for i, plant in enumerate(nearest_plants, 1):
            formatted_info += f"{i}. **{plant['name']}**\n"
            formatted_info += f"   📍 Dirección: {plant['address']}\n"

            if plant["distance_text"] != "No disponible":
                formatted_info += f"   🚗 Distancia: {plant['distance_text']} (aprox. {plant['duration_text']} en auto)\n"
            else:
                formatted_info += f"   🚗 Distancia: Información no disponible\n"

            formatted_info += f"   📞 Teléfono: {plant['phone']}\n"
            formatted_info += f"   ⏰ Horario: {plant['hours']}\n\n"

        # Add note about driving conditions
        formatted_info += "ℹ️ *Los tiempos son estimados y pueden variar según el tráfico y las condiciones de la vía.*"

        # Return tool message with the nearest plant's ID for the state
        return {
            "nearest_plants": nearest_plants,
            "message": ToolMessage(content=formatted_info, tool_call_id=tool_call_id),
            "plant_location": nearest_plants[0]["id"] if nearest_plants else None
        }

    except Exception as e:
        logger.error(f"Error finding nearest plants: {str(e)}")
        error_message = (
            f"Lo siento, tuve problemas para encontrar las plantas más cercanas a {location}. "
            f"Por favor intenta con otra ubicación o distrito específico en Lima."
        )
        return {
            "nearest_plants": [],
            "message": ToolMessage(content=error_message, tool_call_id=tool_call_id),
            "plant_location": None
        }


def setup_llm_with_tools():
    """
    Configura el LLM con las herramientas habilitadas.

    Returns:
        Instancia de LLM con herramientas configuradas
    """
    try:
        # Inicializar el modelo base con configuración específica para uso de herramientas
        llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.1  # Baja temperatura para respuestas más deterministas
        )

        # Conectar las herramientas al modelo con tool_choice="auto" para forzar el uso
        llm_with_tools = llm.bind_tools(
            tools=[find_nearest_plant],
            tool_choice="auto"  # Forzar el uso de herramientas cuando sea apropiado
        )

        logger.info("LLM configurado exitosamente con herramientas")
        return llm_with_tools
    except Exception as e:
        logger.error(f"Error configurando LLM con herramientas: {str(e)}")
        # Fallar graciosamente retornando el LLM sin herramientas
        return ChatOpenAI(model=LLM_MODEL)
