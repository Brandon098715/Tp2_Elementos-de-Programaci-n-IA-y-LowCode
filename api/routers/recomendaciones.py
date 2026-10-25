"""Endpoints de recomendaciones generadas por IA (origen 'ia') y su revisión humana.

La generación (POST /recomendaciones/{resultado_id}) se agrega en la Fase 4.
"""

from typing import Literal

from fastapi import APIRouter

from api.schemas import RecomendacionSalida, RevisionEntrada
from core import database

router = APIRouter(prefix="/recomendaciones", tags=["Recomendaciones (IA)"])


@router.get("", response_model=list[RecomendacionSalida], summary="Listar recomendaciones de IA")
def listar_recomendaciones(
    estado: Literal["pendiente_revision", "aprobada", "rechazada"] | None = None,
):
    return database.listar_recomendaciones(estado=estado)


@router.get("/{recomendacion_id}", response_model=RecomendacionSalida,
            summary="Detalle de una recomendación", responses={404: {"description": "No existe"}})
def obtener_recomendacion(recomendacion_id: int):
    return database.obtener_recomendacion(recomendacion_id)


@router.patch("/{recomendacion_id}/revision", response_model=RecomendacionSalida,
              summary="Supervisión humana: aprobar o rechazar una recomendación",
              responses={404: {"description": "No existe"},
                         409: {"description": "Ya fue revisada"},
                         422: {"description": "Estado inválido"}})
def revisar_recomendacion(recomendacion_id: int, datos: RevisionEntrada):
    return database.revisar_recomendacion(recomendacion_id, datos.estado, datos.comentario)
