"""
Proceso de matching: compara TODOS los estudiantes contra una oferta,
guarda cada resultado en la base y devuelve el ranking.

Usa las reglas de core/scoring.py (origen "reglas"). La IA no interviene acá.
"""

from core import config, database
from core.excepciones import EstadoInvalidoError
from core.scoring import calcular_score


def calcular_matching_oferta(oferta_id: int) -> dict:
    """Calcula y persiste el score de cada estudiante para la oferta indicada.

    - NoEncontradoError si la oferta no existe.
    - EstadoInvalidoError si la oferta está cerrada.
    """
    oferta = database.obtener_oferta(oferta_id)
    if oferta["estado"] == "cerrada":
        raise EstadoInvalidoError(
            f"La oferta {oferta_id} está cerrada: no se puede calcular el matching."
        )

    ranking = []
    for estudiante in database.listar_estudiantes():
        calculo = calcular_score(estudiante, oferta)
        resultado = database.guardar_resultado(estudiante["id"], oferta_id, calculo)
        ranking.append(resultado)

    # Ordenamos de mayor a menor score.
    ranking.sort(key=lambda r: r["score"], reverse=True)

    return {
        "oferta_id": oferta["id"],
        "oferta_titulo": oferta["titulo"],
        "origen": "reglas",
        "umbral_ia": config.UMBRAL_IA,
        "total_estudiantes": len(ranking),
        "ranking": ranking,
    }
