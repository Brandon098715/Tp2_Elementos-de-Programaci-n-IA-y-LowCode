"""Funciones y constantes que comparten varias páginas de la interfaz."""

import pandas as pd
import streamlit as st

from api_client import ErrorAPI

MODALIDADES = ["presencial", "remota", "hibrida"]
NOMBRE_MODALIDAD = {"presencial": "Presencial", "remota": "Remota", "hibrida": "Híbrida"}

# Color de fondo para cada clasificación del score.
COLOR_CLASIFICACION = {"alta": "#c8e6c9", "media": "#fff3c4", "baja": "#ffcdd2"}
EMOJI_CLASIFICACION = {"alta": "🟢", "media": "🟡", "baja": "🔴"}


# ---------------------------------------------------------------------------
# Mensajes
# ---------------------------------------------------------------------------

def avisar_y_recargar(mensaje: str) -> None:
    """Guarda un mensaje de éxito y recarga la página para mostrar datos actualizados.
    El mensaje se muestra después de recargar con mostrar_aviso()."""
    st.session_state["aviso"] = mensaje
    st.rerun()


def mostrar_aviso() -> None:
    """Muestra (una sola vez) el mensaje guardado por avisar_y_recargar()."""
    if "aviso" in st.session_state:
        st.success(st.session_state.pop("aviso"))


def mostrar_error(error: ErrorAPI) -> None:
    """Muestra un error de la API con un mensaje comprensible según su tipo."""
    if error.codigo is None:
        st.error(f"🔌 {error.mensaje}")
    elif error.codigo == 404:
        st.warning(f"🔎 No encontrado: {error.mensaje}")
    elif error.codigo == 409:
        st.warning(f"⚠️ Conflicto: {error.mensaje}")
    elif error.codigo == 422:
        st.error(f"✏️ Revisá los datos: {error.mensaje}")
    elif error.codigo in (502, 503):
        st.error(f"🤖 Problema con la IA: {error.mensaje}")
    else:
        st.error(f"❌ Error del servidor ({error.codigo}): {error.mensaje}")


# ---------------------------------------------------------------------------
# Conversión de datos
# ---------------------------------------------------------------------------

def competencias_a_texto(competencias: list[dict], campo_nivel: str = "nivel") -> str:
    """[{'skill': 'python', 'nivel': 4}] -> 'python (4)'"""
    return ", ".join(f"{c['skill']} ({c[campo_nivel]})" for c in competencias)


def leer_tabla_editable(tabla: pd.DataFrame, campo_nivel: str) -> list[dict]:
    """Convierte las filas de un st.data_editor en una lista de diccionarios.

    - Ignora las filas sin skill (filas vacías).
    - Lanza ValueError si una fila tiene skill pero no tiene nivel.
    """
    filas = []
    for fila in tabla.to_dict("records"):
        skill = str(fila.get("skill") or "").strip()
        if skill == "" or skill.lower() == "nan":
            continue
        nivel = fila.get(campo_nivel)
        if nivel is None or pd.isna(nivel):
            raise ValueError(f"Falta el nivel de la competencia '{skill}'.")
        fila_limpia = {"skill": skill, campo_nivel: int(nivel)}
        if "tipo" in fila:
            fila_limpia["tipo"] = fila["tipo"] or "obligatoria"
        filas.append(fila_limpia)
    return filas


def pintar_clasificacion(valor: str) -> str:
    """Estilo CSS para la celda de clasificación (se usa con DataFrame.style.map)."""
    color = COLOR_CLASIFICACION.get(valor)
    return f"background-color: {color}; color: #222" if color else ""
