"""Página de Matching: calcular y ver el ranking de una oferta (CALCULADO POR REGLAS)."""

import pandas as pd
import streamlit as st

import api_client as api
from api_client import ErrorAPI
from componentes import (
    EMOJI_CLASIFICACION,
    avisar_y_recargar,
    competencias_a_texto,
    mostrar_aviso,
    mostrar_error,
    pintar_clasificacion,
)

NOMBRE_CRITERIO = {
    "obligatorias": "Competencias obligatorias",
    "deseables": "Competencias deseables",
    "modalidad": "Modalidad",
}


def mostrar() -> None:
    st.header("📊 Matching estudiante ↔ oferta")
    st.badge("Calculado por reglas", icon="📐", color="blue")
    st.caption(
        "Score 0-100 = obligatorias (60) + deseables (25) + modalidad (15). "
        "Alta ≥ 75 · Media 50-74 · Baja < 50. No interviene la IA."
    )
    mostrar_aviso()

    try:
        ofertas = api.listar_ofertas()
    except ErrorAPI as error:
        mostrar_error(error)
        return
    if not ofertas:
        st.info("Primero cargá alguna oferta.")
        return

    oferta = st.selectbox(
        "Oferta", ofertas,
        format_func=lambda o: f"#{o['id']} — {o['titulo']} · {o['empresa']} ({o['estado']})",
    )
    st.caption("Requisitos: " + competencias_a_texto(oferta["requisitos"], "nivel_minimo"))

    cerrada = oferta["estado"] == "cerrada"
    if cerrada:
        st.info("La oferta está cerrada: se muestran los últimos resultados, pero no se puede recalcular.")
    if st.button("Calcular matching", type="primary", disabled=cerrada):
        try:
            datos = api.calcular_matching(oferta["id"])
        except ErrorAPI as error:
            mostrar_error(error)
        else:
            avisar_y_recargar(f"Matching calculado para {datos['total_estudiantes']} estudiante(s).")

    # Siempre mostramos lo guardado en la base (GET /matching/resultados).
    try:
        resultados = api.listar_resultados(oferta_id=oferta["id"])
    except ErrorAPI as error:
        mostrar_error(error)
        return
    if not resultados:
        st.info("Todavía no se calculó el matching para esta oferta.")
        return

    _ranking(resultados)
    _detalle(resultados)


def _ranking(resultados: list[dict]) -> None:
    st.subheader("Ranking")
    tabla = pd.DataFrame(
        [
            {
                "Puesto": i,
                "Estudiante": r["estudiante_nombre"],
                "Score": r["score"],
                "Clasificación": r["clasificacion"],
                "Faltantes": len(r["faltantes"]),
                "Recomendación IA": "sí" if r["tiene_recomendacion"] else "—",
                "Calculado": r["calculado_en"].replace("T", " "),
            }
            for i, r in enumerate(resultados, start=1)
        ]
    )
    st.dataframe(
        tabla.style.map(pintar_clasificacion, subset=["Clasificación"]),
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
        },
    )


def _detalle(resultados: list[dict]) -> None:
    st.subheader("Desglose por estudiante")
    for r in resultados:
        titulo = (
            f"{EMOJI_CLASIFICACION[r['clasificacion']]} {r['estudiante_nombre']} — "
            f"{r['score']:.1f} ({r['clasificacion']})"
        )
        with st.expander(titulo):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Puntos por criterio**")
                filas = []
                for clave, c in r["desglose"].items():
                    filas.append(
                        {
                            "Criterio": NOMBRE_CRITERIO.get(clave, clave),
                            "Peso": f"{c['peso_efectivo']:g}" if c["aplica"] else "no aplica",
                            "Cumplimiento": f"{c['cumplimiento'] * 100:.0f}%" if c["aplica"] else "—",
                            "Puntos": c["puntos"],
                        }
                    )
                st.dataframe(pd.DataFrame(filas), hide_index=True)

            with col2:
                st.markdown("**Competencias faltantes**")
                if not r["faltantes"]:
                    st.success("Cumple todos los requisitos.")
                else:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Competencia": f["skill"],
                                    "Tipo": f["tipo"],
                                    "Requerido": f["nivel_requerido"],
                                    # Texto en todas las filas: una columna no puede mezclar tipos.
                                    "Actual": str(f["nivel_actual"]) if f["nivel_actual"] else "no la tiene",
                                }
                                for f in r["faltantes"]
                            ]
                        ),
                        hide_index=True,
                    )
            st.caption(f"ID de resultado: {r['id']} (se usa para generar la recomendación con IA)")
