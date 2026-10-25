"""Página de Ofertas: listado, alta con requisitos y abrir/cerrar."""

import pandas as pd
import streamlit as st

import api_client as api
from api_client import ErrorAPI
from componentes import (
    MODALIDADES,
    NOMBRE_MODALIDAD,
    avisar_y_recargar,
    competencias_a_texto,
    leer_tabla_editable,
    mostrar_aviso,
    mostrar_error,
)


def mostrar() -> None:
    st.header("💼 Ofertas laborales")
    mostrar_aviso()
    tab_listado, tab_alta = st.tabs(["Listado", "Nueva oferta"])
    with tab_listado:
        _listado()
    with tab_alta:
        _alta()


# ---------------------------------------------------------------------------

def _listado() -> None:
    filtro = st.radio("Estado", ["Todas", "abierta", "cerrada"], horizontal=True)
    try:
        ofertas = api.listar_ofertas(estado="" if filtro == "Todas" else filtro)
    except ErrorAPI as error:
        mostrar_error(error)
        return

    if not ofertas:
        st.info("No hay ofertas para mostrar.")
        return

    filas = []
    for o in ofertas:
        obligatorias = [r for r in o["requisitos"] if r["tipo"] == "obligatoria"]
        deseables = [r for r in o["requisitos"] if r["tipo"] == "deseable"]
        filas.append(
            {
                "ID": o["id"],
                "Título": o["titulo"],
                "Empresa": o["empresa"],
                "Modalidad": NOMBRE_MODALIDAD.get(o["modalidad"]),
                "Estado": "🟢 abierta" if o["estado"] == "abierta" else "⚫ cerrada",
                "Obligatorias": competencias_a_texto(obligatorias, "nivel_minimo"),
                "Deseables": competencias_a_texto(deseables, "nivel_minimo"),
            }
        )
    st.caption(f"{len(ofertas)} oferta(s) · entre paréntesis, el nivel mínimo")
    st.dataframe(pd.DataFrame(filas), hide_index=True)

    # --- Abrir / cerrar una oferta ---
    st.subheader("Abrir o cerrar una oferta")
    elegida = st.selectbox(
        "Oferta", ofertas, format_func=lambda o: f"#{o['id']} — {o['titulo']} ({o['estado']})"
    )
    if elegida["descripcion"]:
        st.caption(elegida["descripcion"])

    nuevo_estado = "cerrada" if elegida["estado"] == "abierta" else "abierta"
    texto = "Cerrar oferta" if nuevo_estado == "cerrada" else "Reabrir oferta"
    if st.button(texto, key=f"estado_{elegida['id']}"):
        try:
            api.cambiar_estado_oferta(elegida["id"], nuevo_estado)
        except ErrorAPI as error:
            mostrar_error(error)
        else:
            avisar_y_recargar(f"Oferta #{elegida['id']} ahora está {nuevo_estado}.")


# ---------------------------------------------------------------------------

def _alta() -> None:
    with st.form("alta_oferta"):
        col1, col2 = st.columns(2)
        titulo = col1.text_input("Título *")
        empresa = col2.text_input("Empresa *")
        modalidad = st.selectbox("Modalidad *", MODALIDADES, format_func=NOMBRE_MODALIDAD.get)
        descripcion = st.text_area("Descripción")

        st.markdown(
            "**Requisitos** — agregá filas con el **+**. "
            "*Obligatoria* pesa 60 puntos, *deseable* 25."
        )
        tabla = st.data_editor(
            pd.DataFrame(
                [{"skill": "", "nivel_minimo": 2, "tipo": "obligatoria"}],
                columns=["skill", "nivel_minimo", "tipo"],
            ),
            num_rows="dynamic",
            hide_index=True,
            key="alta_oferta_requisitos",
            column_config={
                "skill": st.column_config.TextColumn("Competencia", required=True),
                "nivel_minimo": st.column_config.NumberColumn(
                    "Nivel mínimo", min_value=1, max_value=5, step=1, default=2, required=True
                ),
                "tipo": st.column_config.SelectboxColumn(
                    "Tipo", options=["obligatoria", "deseable"], default="obligatoria", required=True
                ),
            },
        )
        enviado = st.form_submit_button("Crear oferta", type="primary")

    if not enviado:
        return

    try:
        requisitos = leer_tabla_editable(tabla, "nivel_minimo")
    except ValueError as error:
        st.error(f"✏️ {error}")
        return

    datos = {
        "titulo": titulo,
        "empresa": empresa,
        "modalidad": modalidad,
        "descripcion": descripcion,
        "requisitos": requisitos,
    }
    try:
        creada = api.crear_oferta(datos)
    except ErrorAPI as error:
        mostrar_error(error)
        return
    avisar_y_recargar(f"Oferta '{creada['titulo']}' creada con id {creada['id']}.")
