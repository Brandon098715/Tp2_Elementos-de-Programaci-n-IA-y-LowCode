"""
Servicio de IA (Ollama local).

Por ahora solo verifica si Ollama está disponible (lo usa /health).
En la Fase 4 se agrega la generación de recomendaciones.
"""

import requests

from core import config


def ollama_disponible() -> bool:
    """True si Ollama responde en OLLAMA_URL."""
    try:
        respuesta = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        return respuesta.status_code == 200
    except requests.RequestException:
        return False
