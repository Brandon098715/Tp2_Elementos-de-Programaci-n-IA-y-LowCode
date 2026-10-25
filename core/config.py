"""
Configuración del sistema.

Lee las variables de entorno (desde el archivo .env si existe) y las expone
como constantes simples. El resto del código importa desde acá, por ejemplo:

    from core.config import DB_PATH, UMBRAL_IA

Así hay un único lugar donde se definen los valores por defecto.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carpeta raíz del proyecto (la que contiene core/, api/, ui/...).
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# Carga el .env de la raíz. Si no existe, no pasa nada: se usan los valores
# por defecto o las variables que ya estén definidas (por ejemplo en Docker).
load_dotenv(RAIZ_PROYECTO / ".env")


def _leer_entero(nombre: str, por_defecto: int) -> int:
    """Lee una variable de entorno como entero; si es inválida usa el valor por defecto."""
    valor = os.getenv(nombre)
    if valor is None or valor.strip() == "":
        return por_defecto
    try:
        return int(valor)
    except ValueError:
        print(f"[config] {nombre}='{valor}' no es un entero; se usa {por_defecto}.")
        return por_defecto


def _resolver_ruta(ruta: str) -> Path:
    """Convierte una ruta relativa en absoluta tomando como base la raíz del proyecto."""
    p = Path(ruta)
    return p if p.is_absolute() else RAIZ_PROYECTO / p


# --- Base de datos ---
DB_PATH: Path = _resolver_ruta(os.getenv("DB_PATH", "data/vinculacion.db"))

# --- API (la usa la interfaz Streamlit) ---
API_URL: str = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

# --- IA / Ollama ---
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT: int = _leer_entero("OLLAMA_TIMEOUT", 120)

# --- Matching ---
UMBRAL_IA: int = _leer_entero("UMBRAL_IA", 50)
