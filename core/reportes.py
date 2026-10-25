"""
Indicadores para el reporte resumen (lo consume la UI y el workflow 03 de n8n).
"""

import json
from collections import Counter

from core.database import conectar

# Cuántas competencias faltantes mostrar en el ranking.
TOP_FALTANTES = 10


def resumen() -> dict:
    """Devuelve totales, score promedio por oferta, competencias más faltantes
    y cantidad de recomendaciones de IA pendientes de revisión."""
    with conectar() as con:
        total_estudiantes = con.execute("SELECT COUNT(*) FROM estudiantes").fetchone()[0]

        # Ofertas por estado: {"abierta": 4, "cerrada": 1}
        ofertas = {"abierta": 0, "cerrada": 0}
        for fila in con.execute("SELECT estado, COUNT(*) AS n FROM ofertas GROUP BY estado"):
            ofertas[fila["estado"]] = fila["n"]

        # Recomendaciones de IA por estado
        recomendaciones = {"pendiente_revision": 0, "aprobada": 0, "rechazada": 0}
        for fila in con.execute(
            "SELECT estado, COUNT(*) AS n FROM recomendaciones_ia GROUP BY estado"
        ):
            recomendaciones[fila["estado"]] = fila["n"]

        # Resultados por clasificación (alta / media / baja)
        clasificaciones = {"alta": 0, "media": 0, "baja": 0}
        for fila in con.execute(
            "SELECT clasificacion, COUNT(*) AS n FROM resultados_matching GROUP BY clasificacion"
        ):
            clasificaciones[fila["clasificacion"]] = fila["n"]

        # Score promedio y máximo por oferta (LEFT JOIN: incluye ofertas sin resultados)
        score_por_oferta = [
            dict(fila)
            for fila in con.execute(
                """SELECT o.id AS oferta_id, o.titulo, o.estado,
                          COUNT(r.id) AS cantidad_resultados,
                          ROUND(AVG(r.score), 1) AS score_promedio,
                          MAX(r.score) AS score_maximo
                   FROM ofertas o
                   LEFT JOIN resultados_matching r ON r.oferta_id = o.id
                   GROUP BY o.id
                   ORDER BY o.id"""
            )
        ]

        # Competencias más faltantes: contamos en todos los resultados guardados.
        contador = Counter()
        for fila in con.execute("SELECT faltantes_json FROM resultados_matching"):
            for faltante in json.loads(fila["faltantes_json"]):
                contador[faltante["skill"]] += 1

    return {
        "totales": {
            "estudiantes": total_estudiantes,
            "ofertas_abiertas": ofertas["abierta"],
            "ofertas_cerradas": ofertas["cerrada"],
            "resultados_matching": sum(clasificaciones.values()),
            "recomendaciones": sum(recomendaciones.values()),
        },
        "resultados_por_clasificacion": clasificaciones,
        "score_promedio_por_oferta": score_por_oferta,
        "competencias_mas_faltantes": [
            {"skill": skill, "cantidad": cantidad}
            for skill, cantidad in contador.most_common(TOP_FALTANTES)
        ],
        "recomendaciones_por_estado": recomendaciones,
        "recomendaciones_pendientes": recomendaciones["pendiente_revision"],
    }
