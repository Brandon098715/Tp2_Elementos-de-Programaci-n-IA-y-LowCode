"""Endpoints de matching (score calculado por REGLAS, origen 'reglas')."""

from fastapi import APIRouter, Query

from api.schemas import RankingSalida, ResultadoSalida
from core import database
from core.matching import calcular_matching_oferta

router = APIRouter(prefix="/matching", tags=["Matching (reglas)"])


@router.post("/ofertas/{oferta_id}", response_model=RankingSalida,
             summary="Calcular el score de todos los estudiantes contra una oferta",
             responses={404: {"description": "La oferta no existe"},
                        409: {"description": "La oferta está cerrada"}})
def calcular_matching(oferta_id: int):
    """Calcula, guarda (o actualiza) y devuelve el ranking ordenado por score."""
    return calcular_matching_oferta(oferta_id)


@router.get("/resultados", response_model=list[ResultadoSalida],
            summary="Consultar resultados de matching guardados")
def listar_resultados(
    oferta_id: int | None = None,
    estudiante_id: int | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
):
    return database.listar_resultados(
        oferta_id=oferta_id, estudiante_id=estudiante_id, min_score=min_score
    )
