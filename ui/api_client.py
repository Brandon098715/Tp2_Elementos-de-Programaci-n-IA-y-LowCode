"""
Cliente HTTP de la API. TODAS las llamadas de la interfaz pasan por acá.

La interfaz nunca accede a la base de datos: solo habla con la API.

Si algo sale mal (API apagada, timeout, error 4xx/5xx) se lanza ErrorAPI con
un mensaje en español listo para mostrar al usuario.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Lee el .env de la raíz del proyecto (si existe). En Docker la variable
# API_URL viene directamente del compose.yaml.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 15        # segundos para pedidos normales
# La generación con IA puede tardar bastante más: la API puede hacer 2 intentos
# de hasta OLLAMA_TIMEOUT (120 s) cada uno, así que esperamos un poco más que eso.
TIMEOUT_IA = 300


class ErrorAPI(Exception):
    """Error al hablar con la API. 'codigo' es el código HTTP (None si no hubo respuesta)."""

    def __init__(self, mensaje: str, codigo: int | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def _pedir(metodo: str, ruta: str, timeout: int = TIMEOUT, **kwargs):
    """Hace el pedido HTTP y devuelve el JSON de la respuesta.

    kwargs se pasa tal cual a requests (por ejemplo json=... o params=...).
    """
    url = f"{API_URL}{ruta}"
    try:
        respuesta = requests.request(metodo, url, timeout=timeout, **kwargs)
    except requests.ConnectionError:
        raise ErrorAPI(
            f"No se pudo conectar con la API en {API_URL}. "
            "¿Está corriendo el servidor o el contenedor?"
        )
    except requests.Timeout:
        raise ErrorAPI("La API tardó demasiado en responder. Probá de nuevo en un momento.")

    if respuesta.status_code == 204:  # sin contenido (por ejemplo, al borrar)
        return None

    try:
        datos = respuesta.json()
    except ValueError:
        datos = None

    if respuesta.status_code >= 400:
        # La API siempre manda {"detalle": "..."} en los errores.
        if isinstance(datos, dict) and "detalle" in datos:
            mensaje = datos["detalle"]
        else:
            mensaje = f"Error inesperado de la API (código {respuesta.status_code})."
        raise ErrorAPI(mensaje, respuesta.status_code)

    return datos


def _sin_vacios(parametros: dict) -> dict:
    """Quita los filtros vacíos para no mandarlos en la URL."""
    return {k: v for k, v in parametros.items() if v not in (None, "")}


# --- Sistema ---

def obtener_salud() -> dict:
    return _pedir("GET", "/health", timeout=5)


# --- Estudiantes ---

def listar_estudiantes(skill: str = "", carrera: str = "") -> list[dict]:
    return _pedir("GET", "/estudiantes", params=_sin_vacios({"skill": skill, "carrera": carrera}))


def crear_estudiante(datos: dict) -> dict:
    return _pedir("POST", "/estudiantes", json=datos)


def actualizar_estudiante(estudiante_id: int, datos: dict) -> dict:
    return _pedir("PUT", f"/estudiantes/{estudiante_id}", json=datos)


def eliminar_estudiante(estudiante_id: int) -> None:
    _pedir("DELETE", f"/estudiantes/{estudiante_id}")


# --- Ofertas ---

def listar_ofertas(estado: str = "") -> list[dict]:
    return _pedir("GET", "/ofertas", params=_sin_vacios({"estado": estado}))


def crear_oferta(datos: dict) -> dict:
    return _pedir("POST", "/ofertas", json=datos)


def cambiar_estado_oferta(oferta_id: int, estado: str) -> dict:
    return _pedir("PATCH", f"/ofertas/{oferta_id}/estado", json={"estado": estado})


# --- Matching ---

def calcular_matching(oferta_id: int) -> dict:
    return _pedir("POST", f"/matching/ofertas/{oferta_id}")


def listar_resultados(oferta_id=None, estudiante_id=None, min_score=None) -> list[dict]:
    parametros = {"oferta_id": oferta_id, "estudiante_id": estudiante_id, "min_score": min_score}
    return _pedir("GET", "/matching/resultados", params=_sin_vacios(parametros))


# --- Recomendaciones de IA ---

def generar_recomendacion(resultado_id: int) -> dict:
    return _pedir("POST", f"/recomendaciones/{resultado_id}", timeout=TIMEOUT_IA)


def listar_recomendaciones(estado: str = "") -> list[dict]:
    return _pedir("GET", "/recomendaciones", params=_sin_vacios({"estado": estado}))


def revisar_recomendacion(recomendacion_id: int, estado: str, comentario: str) -> dict:
    return _pedir(
        "PATCH",
        f"/recomendaciones/{recomendacion_id}/revision",
        json={"estado": estado, "comentario": comentario or None},
    )


# --- Reportes ---

def obtener_resumen() -> dict:
    return _pedir("GET", "/reportes/resumen")
