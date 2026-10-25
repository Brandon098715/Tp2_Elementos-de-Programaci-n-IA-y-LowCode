"""Endpoints de reportes e indicadores."""

from fastapi import APIRouter

from core import reportes

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/resumen", summary="Indicadores generales del sistema")
def resumen():
    """Totales, score promedio por oferta, competencias más faltantes
    y recomendaciones de IA pendientes de revisión."""
    return reportes.resumen()
