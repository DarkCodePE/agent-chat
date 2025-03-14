# location/location_services.py
import logging
import os
import requests
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# Use the provided Mapbox key
MAPBOX_ACCESS_TOKEN = "pk.eyJ1Ijoib3JsYW5kb2t1YW4iLCJhIjoiY204ODl1NjZ1MGU4czJtb2FjdjZ0Z3pqbiJ9.QDnkyIdSffpVMt00EvfuAg"

logger = logging.getLogger(__name__)


@dataclass
class Plant:
    """Represents a plant location with all relevant details."""
    id: str
    name: str
    address: str
    phone: str
    hours: str
    coordinates: str  # Format: "lng,lat" (note: MapBox uses longitude first, unlike Google Maps)


# Complete plant database with all 14 locations (coordinates format adjusted for MapBox)
PLANTS = {
    "sjl": Plant(
        id="sjl",
        name="PLANTA SJL 2",
        address="Av. El Sol 891 (cruce con Av. Santa Rosa, a 1 cdra. del Penal Lurigancho)",
        phone="908 879 791 / 989 279 922 / 01 715 8727",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-76.9744,-12.0188"
    ),
    "trapiche": Plant(
        id="trapiche",
        name="PLANTA TRAPICHE",
        address="Av. Alfredo Mendiola Mz. E-6 Lt. 9 (Antes del cruce Panam. Norte con desvío a Trapiche)",
        phone="01 710-9245 / 01 710-9246",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-77.0603,-11.9511"
    ),
    "carabayllo": Plant(
        id="carabayllo",
        name="PLANTA CARABAYLLO",
        address="Av. Tupac Amaru km. 22 Carretera Lima - Canta (Frente al Paradero San Antonio)",
        phone="908 879 729 / 989 279 929",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-77.0344,-11.8503"
    ),
    "jicamarca": Plant(
        id="jicamarca",
        name="PLANTA JICAMARCA",
        address="Av. Mar del Norte Mz.C, Lt.4 (Antes del portón)",
        phone="946 309 951 / 989 279 922",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-76.8954,-11.9350"
    ),
    "chosica": Plant(
        id="chosica",
        name="PLANTA CHOSICA",
        address="Carretera Central Km. 37.5 (Antes del desvío a Santa Eulalia)",
        phone="989 279 927 / 989 279 922",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-76.7056,-11.9419"
    ),
    "callao1": Plant(
        id="callao1",
        name="PLANTA CALLAO 1",
        address="Av. Néstor Gambeta #8595 (Paradero - Puente Oquendo)",
        phone="946 311 128 / 01 715-1748 / 01 715-1749",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-77.1117,-11.9167"
    ),
    "callao2": Plant(
        id="callao2",
        name="PLANTA CALLAO 2",
        address="Av. Néstor Gambeta #1160 (Antes del cruce con Morales Duárez)",
        phone="908 879 721 / 01 713-1881",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos: 8:00am - 2:00pm",
        coordinates="-77.1258,-12.0348"
    ),
    "ate": Plant(
        id="ate",
        name="PLANTA ATE",
        address="Av. Separadora Industrial #2631 (Intersección con Av. Huarochirí)",
        phone="960 159 264 / 01 715 3757 / 01 715 3756",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos: 8:00am - 2:00pm",
        coordinates="-76.9439,-12.0544"
    ),
    "ate2": Plant(
        id="ate2",
        name="PLANTA ATE 2",
        address="Av. Asturias 307 - Ate",
        phone="989 279 922 / 960 157 673",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-76.9183,-12.0262"
    ),
    "naranjal": Plant(
        id="naranjal",
        name="PLANTA NARANJAL",
        address="Las Fraguas #399 esquina con Av. Alfredo Mendiola # 4820 - Independencia",
        phone="017192871 / 908 879 592",
        hours="Lunes a Sábado de 7:00am a 9:00pm",
        coordinates="-77.0600,-11.9803"
    ),
    "sanluis": Plant(
        id="sanluis",
        name="PLANTA SAN LUIS",
        address="Av. Circunvalación #2100 (Frente al Policlínico San Luis)",
        phone="908 879 601 / 989 279 922 / 01 715 6912",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos de 8:00am a 2:00pm",
        coordinates="-76.9765,-12.0786"
    ),
    "atocongo": Plant(
        id="atocongo",
        name="PLANTA ATOCONGO",
        address="Carretera Panamericana Sur km. 11.3 (Frente al Mall del Sur)",
        phone="908 879 597 / 01 714 1183 / 01 714 1182",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos de 8:00am a 2:00pm",
        coordinates="-76.9814,-12.1554"
    ),
    "surco": Plant(
        id="surco",
        name="PLANTA SURCO",
        address="Jr. Catalino Miranda #137 (Frente a la Peña del Carajo)",
        phone="989 279 921 / 01 715 8325 / 01 715 8326",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos de 8:00am a 2:00pm",
        coordinates="-76.9966,-12.1383"
    ),
    "villamaria": Plant(
        id="villamaria",
        name="PLANTA VILLA MARIA DEL TRIUNFO",
        address="Jose Pardo 385, Villa María del Triunfo (a la altura del paradero Ícaros)",
        phone="908 879 787 / 01 717 3010 / 01 717 3011",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos de 8:00am a 2:00pm",
        coordinates="-76.9420,-12.1661"
    ),
    "lurin": Plant(
        id="lurin",
        name="PLANTA LURIN",
        address="Av. Panamericana Sur - Sub Lt. 4 Mz. U - Huertos de Lurín (con calle Los Laureles)",
        phone="989 860 137 / 989 279 922",
        hours="Lunes a Sábado de 7:00am a 9:00pm, Domingos: 8:00am - 2:00pm",
        coordinates="-76.8971,-12.2524"
    )
}


def get_district_coordinates(location: str) -> Tuple[float, float]:
    """
    Get coordinates (longitude, latitude) for a location using Mapbox Geocoding API.

    Args:
        location: A string representing a location (address, district, etc.)

    Returns:
        Tuple of (longitude, latitude) as floats
    """
    try:
        # Append ", Lima, Peru" to ensure we get locations in Lima
        search_location = f"{location}, Lima, Peru"

        # URL encode the search text
        encoded_location = requests.utils.quote(search_location)

        # Call Mapbox Geocoding API
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_location}.json?access_token={MAPBOX_ACCESS_TOKEN}&country=pe&limit=1"
        response = requests.get(url)
        data = response.json()

        # Check if we got valid results
        if "features" in data and data["features"]:
            # Get the first result's coordinates (longitude, latitude)
            coordinates = data["features"][0]["geometry"]["coordinates"]
            lng, lat = coordinates[0], coordinates[1]

            logger.info(f"Found coordinates for '{location}': {lng}, {lat}")
            return (lng, lat)
        else:
            logger.warning(f"Could not geocode location '{location}'.")
            # Default to central Lima coordinates
            return (-77.0428, -12.0464)

    except Exception as e:
        logger.error(f"Error geocoding location '{location}': {str(e)}")
        # Default to central Lima coordinates as fallback
        return (-77.0428, -12.0464)


def calculate_distances(origin_lng: float, origin_lat: float, plants: List[Plant]) -> List[Dict[str, Any]]:
    """
    Calculate distances from origin to multiple plants using Mapbox Directions API.

    Args:
        origin_lng: Longitude of origin point
        origin_lat: Latitude of origin point
        plants: List of Plant objects

    Returns:
        List of dictionaries with plant information and distances
    """
    results = []

    try:
        # Process each plant individually to avoid exceeding request limits
        for plant in plants:
            try:
                # Extract coordinates
                plant_coords = plant.coordinates.split(',')
                plant_lng, plant_lat = float(plant_coords[0]), float(plant_coords[1])

                # Format coordinates for Mapbox (longitude,latitude format)
                # Note: Mapbox directions API can take multiple waypoints but we'll query individually for simplicity
                coordinates = f"{origin_lng},{origin_lat};{plant_lng},{plant_lat}"

                # Call Mapbox Directions API
                url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coordinates}?access_token={MAPBOX_ACCESS_TOKEN}&geometries=geojson&language=es&overview=false"
                response = requests.get(url)
                data = response.json()

                if "routes" in data and data["routes"]:
                    # Get distance in meters and duration in seconds
                    route = data["routes"][0]
                    distance_m = route["distance"]  # in meters
                    duration_s = route["duration"]  # in seconds

                    # Convert to kilometers and minutes
                    distance_km = distance_m / 1000
                    duration_min = duration_s / 60

                    # Format for display
                    if distance_km < 1:
                        distance_text = f"{int(distance_m)} metros"
                    else:
                        distance_text = f"{distance_km:.1f} km"

                    if duration_min < 60:
                        duration_text = f"{int(duration_min)} minutos"
                    else:
                        hours = int(duration_min // 60)
                        mins = int(duration_min % 60)
                        duration_text = f"{hours} hora{'s' if hours > 1 else ''}"
                        if mins > 0:
                            duration_text += f" {mins} minutos"

                    results.append({
                        "id": plant.id,
                        "name": plant.name,
                        "address": plant.address,
                        "phone": plant.phone,
                        "hours": plant.hours,
                        "distance_km": distance_km,
                        "duration_min": duration_min,
                        "distance_text": distance_text,
                        "duration_text": duration_text
                    })
                else:
                    # If no route is found, add plant with placeholder distance
                    logger.warning(f"No route found for plant {plant.name}")
                    results.append({
                        "id": plant.id,
                        "name": plant.name,
                        "address": plant.address,
                        "phone": plant.phone,
                        "hours": plant.hours,
                        "distance_km": 999,
                        "duration_min": 999,
                        "distance_text": "No disponible",
                        "duration_text": "No disponible"
                    })
            except Exception as e:
                logger.error(f"Error calculating distance to plant {plant.name}: {str(e)}")
                # Add plant with placeholder distance
                results.append({
                    "id": plant.id,
                    "name": plant.name,
                    "address": plant.address,
                    "phone": plant.phone,
                    "hours": plant.hours,
                    "distance_km": 999,
                    "duration_min": 999,
                    "distance_text": "No disponible",
                    "duration_text": "No disponible"
                })

        # Sort results by distance
        results.sort(key=lambda x: x["distance_km"])
        return results

    except Exception as e:
        logger.error(f"Error calculating distances: {str(e)}")
        # Fallback - just return the plants without distance info
        return [
            {
                "id": plant.id,
                "name": plant.name,
                "address": plant.address,
                "phone": plant.phone,
                "hours": plant.hours,
                "distance_km": 999,
                "duration_min": 999,
                "distance_text": "No disponible",
                "duration_text": "No disponible"
            }
            for plant in plants
        ]


def extract_location_from_message(message: str) -> str:
    """
    Attempt to extract a location from the user's message.

    Args:
        message: The user's message text

    Returns:
        Extracted location or empty string if none found
    """
    message = message.lower()

    # Check for specific districts or areas in the message
    districts = {
        "san juan de lurigancho": "san juan de lurigancho",
        "sjl": "san juan de lurigancho",
        "lurigancho": "san juan de lurigancho",
        "trapiche": "trapiche",
        "carabayllo": "carabayllo",
        "comas": "carabayllo",
        "jicamarca": "jicamarca",
        "chosica": "chosica",
        "santa eulalia": "chosica",
        "callao": "callao",
        "ate": "ate",
        "huaycán": "ate",
        "naranjal": "naranjal",
        "independencia": "naranjal",
        "san luis": "san luis",
        "atocongo": "atocongo",
        "san juan de miraflores": "atocongo",
        "surco": "surco",
        "santiago de surco": "surco",
        "villa maria": "villa maria del triunfo",
        "villa maría": "villa maria del triunfo",
        "vmt": "villa maria del triunfo",
        "lurin": "lurin",
        "lurín": "lurin"
    }

    # Check each district name
    for keyword, district in districts.items():
        if keyword in message:
            return district

    # If no district is found, check for generic location phrases
    location_phrases = [
        "cerca de", "en", "por", "próximo a", "proximo a", "cercano a"
    ]

    for phrase in location_phrases:
        if phrase in message:
            # Find the phrase and get what comes after it
            start_idx = message.find(phrase) + len(phrase)
            end_idx = min(start_idx + 30, len(message))  # Limit to 30 chars after the phrase
            location_text = message[start_idx:end_idx].strip()

            # Remove common filler words
            for filler in ["mi", "la", "el", "los", "las", "ubicación", "ubicacion"]:
                location_text = location_text.replace(f" {filler} ", " ")

            # If we have a reasonably long string, return it
            if len(location_text) > 3:
                return location_text

    # If no location is found, return empty string
    return ""