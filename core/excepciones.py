"""
Excepciones propias del sistema.

La lógica de core/ lanza estas excepciones y la API (Fase 2) las traduce
a códigos HTTP. Así core/ no depende de FastAPI.

    ErrorDeNegocio          (base de todas)
    ├── ValidacionError     -> 422  dato inválido
    ├── NoEncontradoError   -> 404  el recurso no existe
    ├── DuplicadoError      -> 409  ya existe (ej: email repetido)
    ├── EstadoInvalidoError -> 409  operación no permitida en el estado actual
    ├── IANoDisponibleError -> 503  Ollama apagado o sin respuesta
    └── IAError             -> 502  la IA respondió algo inválido
"""


class ErrorDeNegocio(Exception):
    """Clase base: todas las excepciones del sistema heredan de esta."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ValidacionError(ErrorDeNegocio):
    """Un dato de entrada no cumple las reglas de negocio."""


class NoEncontradoError(ErrorDeNegocio):
    """Se buscó un registro por id y no existe."""


class DuplicadoError(ErrorDeNegocio):
    """Se intentó crear algo que ya existe (por ejemplo, un email repetido)."""


class EstadoInvalidoError(ErrorDeNegocio):
    """La operación no se puede hacer en el estado actual
    (por ejemplo, calcular matching de una oferta cerrada)."""


class IANoDisponibleError(ErrorDeNegocio):
    """El servicio de IA (Ollama) no está disponible."""


class IAError(ErrorDeNegocio):
    """La IA respondió, pero la respuesta no es válida."""
