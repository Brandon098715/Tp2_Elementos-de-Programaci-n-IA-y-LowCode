"""
Servicio de IA: genera recomendaciones de formación con un modelo local (Ollama).

Flujo:
  1. Las REGLAS (core/scoring.py) ya calcularon el score y las faltantes.
  2. Armamos un prompt en español con el perfil, la oferta y esas faltantes.
     La IA NO calcula el score: solo redacta recomendaciones.
  3. Llamamos a Ollama: POST {OLLAMA_URL}/api/generate con format="json".
  4. Validamos la respuesta con Pydantic. Si no es válida, reintentamos 1 vez.
  5. Revisamos el contenido (¿habla de las competencias faltantes?) y anotamos
     advertencias para el revisor humano.
  6. Se guarda con estado 'pendiente_revision': solo una persona la aprueba.

Errores:
  - Ollama apagado, timeout o modelo no instalado -> IANoDisponibleError (503)
  - Respuesta inválida dos veces seguidas        -> IAError (502)
"""

import json
from typing import Literal

import requests
from pydantic import BaseModel, Field, ValidationError, field_validator

from core import config, database
from core.excepciones import EstadoInvalidoError, IAError, IANoDisponibleError
from core.validaciones import normalizar_skill

# Cantidad total de intentos cuando la respuesta no es válida (1 intento + 1 reintento).
INTENTOS = 2


# ---------------------------------------------------------------------------
# Forma esperada de la respuesta de la IA (se valida con Pydantic)
# ---------------------------------------------------------------------------

class RecomendacionIA(BaseModel):
    competencia: str = Field(min_length=1)
    accion: str = Field(min_length=1)
    recurso_sugerido: str = Field(min_length=1)
    prioridad: Literal["alta", "media", "baja"]

    @field_validator("prioridad", mode="before")
    @classmethod
    def prioridad_en_minusculas(cls, valor):
        # El modelo a veces responde "Alta" o "ALTA": lo aceptamos normalizado.
        return normalizar_skill(valor) if isinstance(valor, str) else valor


class RespuestaIA(BaseModel):
    resumen: str = Field(min_length=1)
    recomendaciones: list[RecomendacionIA] = Field(min_length=1)
    mejoras_perfil: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def armar_prompt(estudiante: dict, oferta: dict, resultado: dict) -> str:
    """Arma el prompt en español. No incluye nombre ni email del estudiante
    (no hacen falta para recomendar y así minimizamos datos personales)."""
    competencias = ", ".join(f"{c['skill']} (nivel {c['nivel']})" for c in estudiante["competencias"])

    lineas_faltantes = []
    for f in resultado["faltantes"]:
        if f["nivel_actual"] == 0:
            situacion = "no la tiene"
        else:
            situacion = f"tiene nivel {f['nivel_actual']}"
        lineas_faltantes.append(
            f"- {f['skill']}: {situacion}, se requiere nivel {f['nivel_requerido']} ({f['tipo']})"
        )

    return f"""Sos un orientador de carrera para estudiantes universitarios de Argentina.
Tu tarea es recomendar cómo mejorar el perfil de un estudiante para una oferta laboral.

PERFIL DEL ESTUDIANTE
- Carrera: {estudiante['carrera']} (año {estudiante['anio_cursada']})
- Modalidad preferida: {estudiante['modalidad_preferida']}
- Competencias (nivel de 1 a 5): {competencias}

OFERTA
- Puesto: {oferta['titulo']} en {oferta['empresa']}
- Modalidad: {oferta['modalidad']}
- Descripción: {oferta['descripcion'] or 'sin descripción'}

RESULTADO CALCULADO POR REGLAS (no lo modifiques ni lo recalcules)
- Score de compatibilidad: {resultado['score']} de 100 ({resultado['clasificacion']})
- Competencias faltantes:
{chr(10).join(lineas_faltantes)}

INSTRUCCIONES
- Escribí en español, de forma breve y concreta.
- Hacé exactamente una recomendación por cada competencia faltante de la lista.
- En "competencia" usá el mismo nombre que aparece en la lista de faltantes.
- Prioridad: "alta" para obligatorias, "media" o "baja" para deseables.
- En "recurso_sugerido" indicá un TIPO de recurso gratuito (documentación oficial,
  curso online gratuito, proyecto práctico, ejercicios). NO inventes URLs.
- En "mejoras_perfil" sugerí de 1 a 3 mejoras generales del perfil.

Respondé SOLO con un JSON con esta forma exacta:
{{"resumen": "...", "recomendaciones": [{{"competencia": "...", "accion": "...", "recurso_sugerido": "...", "prioridad": "alta|media|baja"}}], "mejoras_perfil": ["..."]}}"""


# ---------------------------------------------------------------------------
# Llamada a Ollama
# ---------------------------------------------------------------------------

def ollama_disponible() -> bool:
    """True si Ollama responde en OLLAMA_URL (lo usa /health)."""
    try:
        respuesta = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        return respuesta.status_code == 200
    except requests.RequestException:
        return False


def _llamar_ollama(prompt: str) -> str:
    """Envía el prompt a Ollama y devuelve el texto generado (debería ser JSON)."""
    cuerpo = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",     # le pide a Ollama que la salida sea JSON
        "stream": False,      # respuesta completa de una sola vez
        "options": {"temperature": 0.3},  # poca "creatividad": respuestas más estables
    }
    try:
        respuesta = requests.post(
            f"{config.OLLAMA_URL}/api/generate", json=cuerpo, timeout=config.OLLAMA_TIMEOUT
        )
    except requests.ConnectionError:
        raise IANoDisponibleError(
            f"Servicio de IA no disponible: no se pudo conectar con Ollama en {config.OLLAMA_URL}."
        )
    except requests.Timeout:
        raise IANoDisponibleError(
            f"Servicio de IA no disponible: el modelo no respondió en {config.OLLAMA_TIMEOUT} segundos."
        )

    if respuesta.status_code == 404:
        raise IANoDisponibleError(
            f"Servicio de IA no disponible: el modelo '{config.OLLAMA_MODEL}' no está instalado. "
            f"Ejecutá: ollama pull {config.OLLAMA_MODEL}"
        )
    if respuesta.status_code != 200:
        raise IAError(f"Ollama respondió con error {respuesta.status_code}.")

    return respuesta.json().get("response", "")


def _interpretar_respuesta(texto: str) -> RespuestaIA:
    """Convierte el texto de la IA en un objeto validado.
    Lanza ValueError (JSON roto) o ValidationError (forma incorrecta)."""
    datos = json.loads(texto)
    return RespuestaIA.model_validate(datos)


# ---------------------------------------------------------------------------
# Validación del contenido (además del formato)
# ---------------------------------------------------------------------------

def _se_refiere_a(competencia_ia: str, skill_faltante: str) -> bool:
    """True si el texto de la IA menciona la skill faltante ('SQL avanzado' -> 'sql')."""
    a = normalizar_skill(competencia_ia)
    b = normalizar_skill(skill_faltante)
    return a == b or b in a or a in b


def revisar_contenido(respuesta: RespuestaIA, faltantes: list[dict]) -> list[str]:
    """Compara lo que respondió la IA con las faltantes calculadas por reglas.
    Devuelve advertencias para que el revisor humano les preste atención."""
    advertencias = []
    skills_faltantes = [f["skill"] for f in faltantes]

    for reco in respuesta.recomendaciones:
        if not any(_se_refiere_a(reco.competencia, s) for s in skills_faltantes):
            advertencias.append(
                f"La IA recomendó '{reco.competencia}', que no está entre las competencias faltantes."
            )

    for skill in skills_faltantes:
        if not any(_se_refiere_a(r.competencia, skill) for r in respuesta.recomendaciones):
            advertencias.append(f"La IA no incluyó ninguna recomendación para '{skill}'.")

    for reco in respuesta.recomendaciones:
        if "http" in reco.recurso_sugerido.lower() or "www." in reco.recurso_sugerido.lower():
            advertencias.append(
                f"El recurso para '{reco.competencia}' incluye un enlace: verificar que exista."
            )

    return advertencias


# ---------------------------------------------------------------------------
# Funciones principales
# ---------------------------------------------------------------------------

def generar_recomendacion(estudiante: dict, oferta: dict, resultado: dict) -> dict:
    """Pide la recomendación a la IA, la valida y devuelve el contenido como dict.

    Si la respuesta no es válida reintenta una vez; si vuelve a fallar -> IAError.
    """
    prompt = armar_prompt(estudiante, oferta, resultado)
    ultimo_error = ""

    for intento in range(1, INTENTOS + 1):
        texto = _llamar_ollama(prompt)  # si Ollama está caído, la excepción sale directo
        try:
            respuesta = _interpretar_respuesta(texto)
        except (ValueError, ValidationError) as error:
            ultimo_error = str(error).splitlines()[0]
            print(f"[IA] Intento {intento}: respuesta inválida ({ultimo_error})")
            continue  # reintentar

        contenido = respuesta.model_dump()
        contenido["advertencias"] = revisar_contenido(respuesta, resultado["faltantes"])
        return contenido

    raise IAError(
        f"La IA devolvió una respuesta inválida {INTENTOS} veces seguidas. "
        f"Último error: {ultimo_error}"
    )


def generar_y_guardar(resultado_id: int) -> dict:
    """Genera la recomendación para un resultado de matching y la guarda
    como 'pendiente_revision'. Es lo que llama el endpoint POST /recomendaciones/{id}.

    - NoEncontradoError si el resultado no existe.
    - EstadoInvalidoError si el resultado no tiene competencias faltantes.
    """
    resultado = database.obtener_resultado(resultado_id)
    if not resultado["faltantes"]:
        raise EstadoInvalidoError(
            f"El resultado {resultado_id} no tiene competencias faltantes: no hay nada que recomendar."
        )

    estudiante = database.obtener_estudiante(resultado["estudiante_id"])
    oferta = database.obtener_oferta(resultado["oferta_id"])

    contenido = generar_recomendacion(estudiante, oferta, resultado)
    return database.crear_recomendacion(resultado_id, contenido, config.OLLAMA_MODEL)
