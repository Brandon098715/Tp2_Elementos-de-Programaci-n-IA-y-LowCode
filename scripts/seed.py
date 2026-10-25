"""
Carga los datos de ejemplo de data/seed.json en la base SQLite.

Uso (desde la raíz del proyecto, con el venv activado):

    python scripts/seed.py           # agrega los datos (saltea emails ya cargados)
    python scripts/seed.py --reset   # borra la base y la crea de cero

Al final muestra, como prueba, el score de cada estudiante contra la primera oferta.
"""

import argparse
import json
import sys
from pathlib import Path

# Permite importar 'core' aunque el script se ejecute como 'python scripts/seed.py'.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import config, database  # noqa: E402  (import después de ajustar sys.path)
from core.excepciones import DuplicadoError  # noqa: E402
from core.scoring import calcular_score  # noqa: E402

ARCHIVO_SEED = RAIZ / "data" / "seed.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga datos de ejemplo en la base.")
    parser.add_argument("--reset", action="store_true", help="borra la base antes de cargar")
    args = parser.parse_args()

    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        print(f"Base eliminada: {config.DB_PATH}")

    database.crear_tablas()
    datos = json.loads(ARCHIVO_SEED.read_text(encoding="utf-8"))

    # --- Estudiantes ---
    creados = 0
    for estudiante in datos["estudiantes"]:
        try:
            database.crear_estudiante(estudiante)
            creados += 1
        except DuplicadoError:
            print(f"  (ya existía) {estudiante['email']}")
    print(f"Estudiantes cargados: {creados}")

    # --- Ofertas (solo si la base no tiene ninguna, para no duplicarlas) ---
    if database.listar_ofertas():
        print("Ofertas: la base ya tiene ofertas, no se cargan de nuevo.")
    else:
        for oferta in datos["ofertas"]:
            database.crear_oferta(oferta)
        print(f"Ofertas cargadas: {len(datos['ofertas'])}")

    # --- Prueba rápida del scoring (no guarda nada) ---
    oferta = database.listar_ofertas()[0]
    print(f"\nScore contra la oferta #{oferta['id']} '{oferta['titulo']}' (calculado por reglas):")
    ranking = []
    for est in database.listar_estudiantes():
        calculo = calcular_score(est, oferta)
        ranking.append((calculo["score"], calculo["clasificacion"], est["nombre"]))
    for score, clasificacion, nombre in sorted(ranking, reverse=True):
        print(f"  {score:5.1f}  {clasificacion:<6} {nombre}")

    print(f"\nBase lista en: {config.DB_PATH}")


if __name__ == "__main__":
    main()
