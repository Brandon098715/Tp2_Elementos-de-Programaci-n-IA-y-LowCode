"""Página de Reportes: indicadores generales (GET /reportes/resumen)."""

import pandas as pd
import streamlit as st

import api_client as api
from api_client import ErrorAPI
from componentes import mostrar_error


def mostrar() -> None:
    st.header("📈 Reportes")
    if st.button("🔄 Actualizar"):
        st.rerun()

    try:
        datos = api.obtener_resumen()
    except ErrorAPI as error:
        mostrar_error(error)
        return

    totales = datos["totales"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Estudiantes", totales["estudiantes"])
    col2.metric("Ofertas abiertas", totales["ofertas_abiertas"],
                help=f"Cerradas: {totales['ofertas_cerradas']}")
    col3.metric("Resultados de matching", totales["resultados_matching"])
    col4.metric("Recomendaciones IA pendientes", datos["recomendaciones_pendientes"],
                help=f"Total de recomendaciones: {totales['recomendaciones']}")

    st.divider()
    izquierda, derecha = st.columns(2)

    with izquierda:
        st.subheader("Score promedio por oferta")
        st.caption("📐 Calculado por reglas")
        por_oferta = [o for o in datos["score_promedio_por_oferta"] if o["score_promedio"] is not None]
        if por_oferta:
            tabla = pd.DataFrame(por_oferta)
            tabla["Oferta"] = "#" + tabla["oferta_id"].astype(str) + " " + tabla["titulo"]
            st.bar_chart(tabla.set_index("Oferta")["score_promedio"], horizontal=True)
        else:
            st.info("Todavía no se calculó ningún matching.")

        st.subheader("Resultados por clasificación")
        clasif = datos["resultados_por_clasificacion"]
        st.bar_chart(pd.Series(clasif, name="cantidad"))

    with derecha:
        st.subheader("Competencias más faltantes")
        st.caption("Cuántas veces aparece cada competencia como faltante en los resultados")
        faltantes = datos["competencias_mas_faltantes"]
        if faltantes:
            st.bar_chart(pd.DataFrame(faltantes).set_index("skill")["cantidad"], horizontal=True)
        else:
            st.info("Sin datos todavía.")

        st.subheader("Recomendaciones IA por estado")
        st.bar_chart(pd.Series(datos["recomendaciones_por_estado"], name="cantidad"))
