"""
Aplicación FastAPI.

- Crea la app y registra los routers (uno por recurso).
- Crea las tablas de la base al iniciar.
- Convierte las excepciones de core/ en respuestas HTTP {"detalle": "..."}.

Ejecutar desde la raíz del proyecto:
    uvicorn api.main:app --reload
Documentación interactiva: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routers import estudiantes, matching, ofertas, recomendaciones, reportes
from core import config, database, ia_service
from core.excepciones import (
    DuplicadoError,
    ErrorDeNegocio,
    EstadoInvalidoError,
    IAError,
    IANoDisponibleError,
    NoEncontradoError,
    ValidacionError,
)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Se ejecuta al arrancar la API: asegura que existan las tablas."""
    database.crear_tablas()
    yield


app = FastAPI(
    title="API — Plataforma de vinculación profesional",
    description=(
        "Vincula estudiantes con ofertas laborales.\n\n"
        "- **Matching** (`origen: reglas`): score 0-100 calculado con reglas explícitas en Python.\n"
        "- **Recomendaciones** (`origen: ia`): generadas por un modelo local (Ollama) y "
        "revisadas por una persona antes de considerarse válidas."
    ),
    version="1.0.0",
    lifespan=ciclo_de_vida,
)

app.include_router(estudiantes.router)
app.include_router(ofertas.router)
app.include_router(matching.router)
app.include_router(recomendaciones.router)
app.include_router(reportes.router)


# ---------------------------------------------------------------------------
# Manejo global de errores
# ---------------------------------------------------------------------------

# Qué código HTTP corresponde a cada excepción de core/.
CODIGOS_HTTP = {
    ValidacionError: 422,
    NoEncontradoError: 404,
    DuplicadoError: 409,
    EstadoInvalidoError: 409,
    IANoDisponibleError: 503,
    IAError: 502,
}


@app.exception_handler(ErrorDeNegocio)
async def manejar_error_de_negocio(request: Request, exc: ErrorDeNegocio):
    codigo = CODIGOS_HTTP.get(type(exc), 400)
    return JSONResponse(status_code=codigo, content={"detalle": exc.mensaje})


def traducir_error_pydantic(error: dict) -> str:
    """Traduce al español los errores más comunes de Pydantic.
    Si no conocemos el tipo de error, devolvemos el mensaje original (en inglés)."""
    tipo = error["type"]
    ctx = error.get("ctx", {})
    traducciones = {
        "missing": "es obligatorio",
        "int_parsing": "debe ser un número entero",
        "int_type": "debe ser un número entero",
        "float_parsing": "debe ser un número",
        "string_type": "debe ser texto",
        "list_type": "debe ser una lista",
        "greater_than_equal": f"debe ser mayor o igual a {ctx.get('ge')}",
        "less_than_equal": f"debe ser menor o igual a {ctx.get('le')}",
        "string_too_short": f"debe tener al menos {ctx.get('min_length')} caracter(es)",
        "string_too_long": f"debe tener como máximo {ctx.get('max_length')} caracteres",
        "too_short": f"debe tener al menos {ctx.get('min_length')} elemento(s)",
        "literal_error": f"valor inválido, opciones: {ctx.get('expected')}",
        "json_invalid": "el cuerpo no es un JSON válido",
    }
    return traducciones.get(tipo, error["msg"])


@app.exception_handler(RequestValidationError)
async def manejar_error_de_validacion(request: Request, exc: RequestValidationError):
    """Errores de Pydantic (tipos, rangos, campos faltantes) -> 422 con mensaje legible."""
    errores = []
    for error in exc.errors():
        # 'loc' es la ruta del campo, ej: ("body", "competencias", 0, "nivel")
        campo = ".".join(str(parte) for parte in error["loc"] if parte != "body")
        errores.append({"campo": campo, "mensaje": traducir_error_pydantic(error)})
    detalle = "Datos inválidos: " + "; ".join(f"{e['campo']}: {e['mensaje']}" for e in errores)
    return JSONResponse(status_code=422, content={"detalle": detalle, "errores": errores})


@app.exception_handler(Exception)
async def manejar_error_inesperado(request: Request, exc: Exception):
    """Cualquier otro error: 500 sin exponer detalles internos."""
    print(f"[ERROR] {request.method} {request.url.path}: {exc!r}")
    return JSONResponse(status_code=500, content={"detalle": "Error interno del servidor."})


# ---------------------------------------------------------------------------
# Salud del sistema
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"], summary="Estado de la API, la base y Ollama")
def health():
    base_ok = database.verificar_conexion()
    ollama_ok = ia_service.ollama_disponible()
    return {
        "api": "ok",
        "base_datos": "ok" if base_ok else "error",
        "ollama": "ok" if ollama_ok else "no disponible",
        "modelo_ia": config.OLLAMA_MODEL,
        "estado_general": "ok" if (base_ok and ollama_ok) else "degradado",
    }
