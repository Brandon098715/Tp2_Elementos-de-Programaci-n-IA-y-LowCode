"""
Modelos Pydantic: definen la forma del JSON que entra y sale de la API.

- Los modelos *Entrada validan lo que manda el cliente (si falla -> 422).
- Los modelos *Salida documentan lo que devuelve la API (se ven en /docs).

Las reglas de negocio más finas (normalizar skills, modalidad válida,
skills repetidas, email duplicado) se validan en core/, no acá.
"""

from typing import Literal

from pydantic import BaseModel, Field

TEXTO_MODALIDAD = "presencial, remota o hibrida (se aceptan tildes y mayúsculas)"


# ---------------------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------------------

class Competencia(BaseModel):
    skill: str = Field(min_length=1, max_length=50, examples=["Python"])
    nivel: int = Field(ge=1, le=5, description="Nivel de 1 (básico) a 5 (experto)", examples=[3])


class EstudianteEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    carrera: str = Field(min_length=1, max_length=100)
    anio_cursada: int = Field(ge=1, le=6)
    modalidad_preferida: str = Field(description=TEXTO_MODALIDAD)
    competencias: list[Competencia] = Field(min_length=1)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nombre": "Julia Pérez",
                    "email": "julia.perez@example.com",
                    "carrera": "Licenciatura en Sistemas",
                    "anio_cursada": 3,
                    "modalidad_preferida": "hibrida",
                    "competencias": [
                        {"skill": "Python", "nivel": 3},
                        {"skill": "SQL", "nivel": 2},
                    ],
                }
            ]
        }
    }


class EstudianteSalida(BaseModel):
    id: int
    nombre: str
    email: str
    carrera: str
    anio_cursada: int
    modalidad_preferida: str
    competencias: list[Competencia]
    creado_en: str
    actualizado_en: str


# ---------------------------------------------------------------------------
# Ofertas
# ---------------------------------------------------------------------------

class Requisito(BaseModel):
    skill: str = Field(min_length=1, max_length=50, examples=["Python"])
    nivel_minimo: int = Field(ge=1, le=5, examples=[3])
    tipo: Literal["obligatoria", "deseable"]


class OfertaEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    empresa: str = Field(min_length=1, max_length=100)
    modalidad: str = Field(description=TEXTO_MODALIDAD)
    descripcion: str = Field(default="", max_length=2000)
    requisitos: list[Requisito] = Field(min_length=1)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "titulo": "Desarrollador/a Python Jr",
                    "empresa": "Empresa Ficticia SA",
                    "modalidad": "remota",
                    "descripcion": "Desarrollo de APIs.",
                    "requisitos": [
                        {"skill": "Python", "nivel_minimo": 3, "tipo": "obligatoria"},
                        {"skill": "Docker", "nivel_minimo": 1, "tipo": "deseable"},
                    ],
                }
            ]
        }
    }


class OfertaSalida(BaseModel):
    id: int
    titulo: str
    empresa: str
    modalidad: str
    descripcion: str
    estado: Literal["abierta", "cerrada"]
    requisitos: list[Requisito]
    creado_en: str


class CambioEstadoOferta(BaseModel):
    estado: Literal["abierta", "cerrada"]


# ---------------------------------------------------------------------------
# Matching (origen: reglas)
# ---------------------------------------------------------------------------

class Faltante(BaseModel):
    skill: str
    nivel_requerido: int
    nivel_actual: int = Field(description="0 si el estudiante no tiene la competencia")
    tipo: Literal["obligatoria", "deseable"]


class ResultadoSalida(BaseModel):
    id: int
    estudiante_id: int
    estudiante_nombre: str
    oferta_id: int
    oferta_titulo: str
    score: float
    clasificacion: Literal["alta", "media", "baja"]
    desglose: dict = Field(description="Puntos por criterio: obligatorias, deseables, modalidad")
    faltantes: list[Faltante]
    origen: Literal["reglas"]
    calculado_en: str
    tiene_recomendacion: bool


class RankingSalida(BaseModel):
    oferta_id: int
    oferta_titulo: str
    origen: Literal["reglas"]
    umbral_ia: int
    total_estudiantes: int
    ranking: list[ResultadoSalida]


# ---------------------------------------------------------------------------
# Recomendaciones de IA (origen: ia)
# ---------------------------------------------------------------------------

class RecomendacionSalida(BaseModel):
    id: int
    resultado_id: int
    contenido: dict = Field(description="JSON generado por la IA (resumen, recomendaciones, mejoras)")
    modelo: str
    origen: Literal["ia"]
    estado: Literal["pendiente_revision", "aprobada", "rechazada"]
    comentario_revisor: str | None
    creado_en: str
    revisado_en: str | None


class RevisionEntrada(BaseModel):
    estado: Literal["aprobada", "rechazada"]
    comentario: str | None = Field(default=None, max_length=500)

    model_config = {
        "json_schema_extra": {
            "examples": [{"estado": "aprobada", "comentario": "Recursos verificados."}]
        }
    }
