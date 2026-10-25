"""Endpoints de ofertas laborales."""

from typing import Literal

from fastapi import APIRouter, status

from api.schemas import CambioEstadoOferta, OfertaEntrada, OfertaSalida
from core import database

router = APIRouter(prefix="/ofertas", tags=["Ofertas"])


@router.post("", response_model=OfertaSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear una oferta con requisitos (nace 'abierta')",
             responses={422: {"description": "Datos inválidos"}})
def crear_oferta(datos: OfertaEntrada):
    return database.crear_oferta(datos.model_dump())


@router.get("", response_model=list[OfertaSalida], summary="Listar ofertas")
def listar_ofertas(estado: Literal["abierta", "cerrada"] | None = None):
    return database.listar_ofertas(estado=estado)


@router.get("/{oferta_id}", response_model=OfertaSalida, summary="Detalle de una oferta",
            responses={404: {"description": "No existe"}})
def obtener_oferta(oferta_id: int):
    return database.obtener_oferta(oferta_id)


@router.patch("/{oferta_id}/estado", response_model=OfertaSalida, summary="Abrir o cerrar una oferta",
              responses={404: {"description": "No existe"}, 422: {"description": "Estado inválido"}})
def cambiar_estado(oferta_id: int, datos: CambioEstadoOferta):
    return database.cambiar_estado_oferta(oferta_id, datos.estado)
