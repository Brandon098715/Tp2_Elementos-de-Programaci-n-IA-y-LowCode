"""
Interfaz Streamlit — Plataforma de vinculación profesional.

Ejecutar desde la raíz del proyecto:
    streamlit run ui/app.py
Se abre en http://localhost:8501

La interfaz solo habla con la API (ui/api_client.py), nunca con la base.
Cada sección está en un archivo de ui/paginas/.
"""

import streamlit as st

import api_client as api
from api_client import ErrorAPI
from paginas import estudiantes, matching, ofertas, recomendaciones, reportes

st.set_page_config(page_title="Vinculación profesional", page_icon="🎓", layout="wide")

# Nombre que se ve en el menú -> función que dibuja la página
PAGINAS = {
    "👩‍🎓 Estudiantes": estudiantes.mostrar,
    "💼 Ofertas": ofertas.mostrar,
    "📊 Matching": matching.mostrar,
    "🤖 Recomendaciones IA": recomendaciones.mostrar,
    "📈 Reportes": reportes.mostrar,
}


def estado_del_sistema() -> bool:
    """Muestra en la barra lateral el resultado de GET /health.
    Devuelve False si la API no responde."""
    st.sidebar.subheader("Estado del sistema")
    try:
        salud = api.obtener_salud()
    except ErrorAPI as error:
        st.sidebar.error("🔴 API no disponible")
        st.sidebar.caption(error.mensaje)
        return False

    def linea(nombre: str, ok: bool, texto_ok: str = "ok", texto_mal: str = "no disponible"):
        st.sidebar.write(f"{'🟢' if ok else '🔴'} **{nombre}:** {texto_ok if ok else texto_mal}")

    linea("API", salud["api"] == "ok")
    linea("Base de datos", salud["base_datos"] == "ok", texto_mal="error")
    linea("IA (Ollama)", salud["ollama"] == "ok")
    st.sidebar.caption(f"Modelo: {salud['modelo_ia']} · API: {api.API_URL}")
    if salud["ollama"] != "ok":
        st.sidebar.warning("Sin IA se puede usar todo, salvo generar recomendaciones.")
    return True


def main() -> None:
    st.sidebar.title("🎓 Vinculación profesional")
    seleccion = st.sidebar.radio("Sección", list(PAGINAS.keys()))
    st.sidebar.divider()

    if not estado_del_sistema():
        # Sin API no hay nada que mostrar: un solo mensaje claro en lugar de errores por todos lados.
        st.error(f"🔌 No se pudo conectar con la API en {api.API_URL}.")
        st.markdown(
            "- Sin Docker: ejecutá `uvicorn api.main:app --reload` en la raíz del proyecto.\n"
            "- Con Docker: revisá que el contenedor esté levantado con `docker compose ps`.\n"
            "- Después, recargá esta página."
        )
        st.stop()

    PAGINAS[seleccion]()  # dibuja la página elegida


main()
