"""Endpoints de estudiantes. Solo reciben, validan la forma y delegan en core/."""

from fastapi import APIRouter, Response, status

from api.schemas import EstudianteEntrada, EstudianteSalida
from core import database

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])


@router.post("", response_model=EstudianteSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear un perfil de estudiante con sus competencias",
             responses={409: {"description": "Email duplicado"}, 422: {"description": "Datos inválidos"}})
def crear_estudiante(datos: EstudianteEntrada):
    return database.crear_estudiante(datos.model_dump())


@router.get("", response_model=list[EstudianteSalida], summary="Listar estudiantes")
def listar_estudiantes(skill: str | None = None, carrera: str | None = None):
    """Filtros opcionales: `skill` (tiene esa competencia) y `carrera` (texto contenido)."""
    return database.listar_estudiantes(skill=skill, carrera=carrera)


@router.get("/{estudiante_id}", response_model=EstudianteSalida, summary="Detalle de un estudiante",
            responses={404: {"description": "No existe"}})
def obtener_estudiante(estudiante_id: int):
    return database.obtener_estudiante(estudiante_id)


@router.put("/{estudiante_id}", response_model=EstudianteSalida,
            summary="Actualizar perfil y competencias (reemplaza todo)",
            responses={404: {"description": "No existe"}, 409: {"description": "Email duplicado"}})
def actualizar_estudiante(estudiante_id: int, datos: EstudianteEntrada):
    return database.actualizar_estudiante(estudiante_id, datos.model_dump())


@router.delete("/{estudiante_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar un estudiante (y sus resultados)",
               responses={404: {"description": "No existe"}})
def eliminar_estudiante(estudiante_id: int):
    database.eliminar_estudiante(estudiante_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
