"""Página de Recomendaciones IA: ver y revisar (aprobar / rechazar) lo que generó la IA.

Todo lo de esta página es GENERADO POR IA y requiere revisión humana.
"""

import pandas as pd
import streamlit as st

import api_client as api
from api_client import ErrorAPI
from componentes import avisar_y_recargar, mostrar_aviso, mostrar_error

ESTADOS = {
    "pendiente_revision": "🕒 Pendiente de revisión",
    "aprobada": "✅ Aprobada",
    "rechazada": "❌ Rechazada",
}


def mostrar() -> None:
    st.header("🤖 Recomendaciones generadas por IA")
    st.badge("Generado por IA — requiere revisión", icon="⚠️", color="orange")
    st.caption(
        "La IA solo redacta sugerencias a partir de las competencias faltantes que ya "
        "calcularon las reglas. Una persona debe aprobarlas antes de considerarlas válidas."
    )
    mostrar_aviso()

    with st.expander("✨ Generar una nueva recomendación con IA", expanded=False):
        _generar()

    st.subheader("Recomendaciones generadas")
    filtro = st.radio(
        "Estado", ["Todas", *ESTADOS.keys()], horizontal=True,
        format_func=lambda e: ESTADOS.get(e, e),
    )
    try:
        recomendaciones = api.listar_recomendaciones(estado="" if filtro == "Todas" else filtro)
        # Para mostrar a qué estudiante y oferta corresponde cada recomendación.
        resultados = {r["id"]: r for r in api.listar_resultados()}
    except ErrorAPI as error:
        mostrar_error(error)
        return

    if not recomendaciones:
        st.info("No hay recomendaciones para mostrar.")
        return

    for reco in recomendaciones:
        _tarjeta(reco, resultados.get(reco["resultado_id"]))


def _generar() -> None:
    """Elegir un resultado de matching (con faltantes) y pedirle a la IA una recomendación."""
    try:
        ofertas = api.listar_ofertas()
    except ErrorAPI as error:
        mostrar_error(error)
        return
    if not ofertas:
        st.info("No hay ofertas cargadas.")
        return

    oferta = st.selectbox("Oferta", ofertas, key="gen_oferta",
                          format_func=lambda o: f"#{o['id']} — {o['titulo']}")
    try:
        resultados = api.listar_resultados(oferta_id=oferta["id"])
    except ErrorAPI as error:
        mostrar_error(error)
        return

    # Solo tiene sentido recomendar si hay competencias faltantes.
    con_faltantes = [r for r in resultados if r["faltantes"]]
    if not con_faltantes:
        st.info("Esta oferta no tiene resultados con competencias faltantes. "
                "¿Ya calculaste el matching en la sección Matching?")
        return

    resultado = st.selectbox(
        "Resultado de matching", con_faltantes, key="gen_resultado",
        format_func=lambda r: (
            f"{r['estudiante_nombre']} — score {r['score']:.1f} ({r['clasificacion']})"
            + (" · ya tiene recomendación" if r["tiene_recomendacion"] else "")
        ),
    )
    st.caption("Faltantes (calculadas por reglas): " + ", ".join(
        f"{f['skill']} ({f['nivel_actual']}/{f['nivel_requerido']}, {f['tipo']})"
        for f in resultado["faltantes"]
    ))

    if st.button("Generar con IA", type="primary"):
        with st.spinner("La IA está generando la recomendación… la primera vez puede tardar ~1 minuto."):
            try:
                reco = api.generar_recomendacion(resultado["id"])
            except ErrorAPI as error:
                mostrar_error(error)
                return
        avisar_y_recargar(f"Recomendación #{reco['id']} generada. Queda pendiente de revisión.")


def _tarjeta(reco: dict, resultado: dict | None) -> None:
    """Dibuja una recomendación con su contenido y, si está pendiente, el formulario de revisión."""
    with st.container(border=True):
        if resultado:
            st.markdown(
                f"#### #{reco['id']} · {resultado['estudiante_nombre']} → {resultado['oferta_titulo']}"
            )
            st.caption(f"Score por reglas: {resultado['score']:.1f} ({resultado['clasificacion']})")
        else:
            st.markdown(f"#### Recomendación #{reco['id']}")

        st.write(f"**Estado:** {ESTADOS[reco['estado']]} · **Modelo:** {reco['modelo']} · "
                 f"**Origen:** {reco['origen']}")
        if reco["estado"] == "pendiente_revision":
            st.warning("Generado por IA — requiere revisión. Verificá que los recursos existan.")

        _contenido(reco["contenido"])

        if reco["estado"] == "pendiente_revision":
            _formulario_revision(reco)
        else:
            comentario = reco["comentario_revisor"] or "sin comentario"
            st.info(f"Revisada el {reco['revisado_en'].replace('T', ' ')} — {comentario}")


def _contenido(contenido: dict) -> None:
    """Muestra el JSON de la IA de forma legible (y también crudo, en un desplegable)."""
    if contenido.get("resumen"):
        st.markdown(f"**Resumen:** {contenido['resumen']}")

    if contenido.get("recomendaciones"):
        st.markdown("**Recomendaciones de formación**")
        st.dataframe(
            pd.DataFrame(contenido["recomendaciones"]).rename(
                columns={
                    "competencia": "Competencia",
                    "accion": "Acción",
                    "recurso_sugerido": "Recurso sugerido",
                    "prioridad": "Prioridad",
                }
            ),
            hide_index=True,
        )

    if contenido.get("mejoras_perfil"):
        st.markdown("**Mejoras para el perfil**")
        for mejora in contenido["mejoras_perfil"]:
            st.markdown(f"- {mejora}")

    # Advertencias que detectó el sistema al validar el contenido de la IA.
    if contenido.get("advertencias"):
        st.markdown("**⚠️ Advertencias de la validación automática**")
        for advertencia in contenido["advertencias"]:
            st.markdown(f"- {advertencia}")

    with st.expander("Ver JSON original"):
        st.json(contenido)


def _formulario_revision(reco: dict) -> None:
    with st.form(f"revision_{reco['id']}"):
        comentario = st.text_input("Comentario del revisor", placeholder="Opcional")
        col1, col2 = st.columns(2)
        aprobar = col1.form_submit_button("✅ Aprobar", type="primary")
        rechazar = col2.form_submit_button("❌ Rechazar")

    if aprobar or rechazar:
        estado = "aprobada" if aprobar else "rechazada"
        try:
            api.revisar_recomendacion(reco["id"], estado, comentario)
        except ErrorAPI as error:
            mostrar_error(error)
        else:
            avisar_y_recargar(f"Recomendación #{reco['id']} {estado}.")
