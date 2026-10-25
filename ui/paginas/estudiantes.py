"""Página de Estudiantes: listado con filtros, alta y edición/eliminación."""

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
    st.header("👩‍🎓 Estudiantes")
    mostrar_aviso()
    tab_listado, tab_alta, tab_edicion = st.tabs(["Listado", "Nuevo estudiante", "Editar / eliminar"])
    with tab_listado:
        _listado()
    with tab_alta:
        _alta()
    with tab_edicion:
        _edicion()


# ---------------------------------------------------------------------------

def _listado() -> None:
    col1, col2 = st.columns(2)
    skill = col1.text_input("Filtrar por competencia", placeholder="ej: python")
    carrera = col2.text_input("Filtrar por carrera", placeholder="ej: sistemas")

    try:
        estudiantes = api.listar_estudiantes(skill=skill, carrera=carrera)
    except ErrorAPI as error:
        mostrar_error(error)
        return

    if not estudiantes:
        st.info("No hay estudiantes que coincidan con los filtros.")
        return

    tabla = pd.DataFrame(
        [
            {
                "ID": e["id"],
                "Nombre": e["nombre"],
                "Email": e["email"],
                "Carrera": e["carrera"],
                "Año": e["anio_cursada"],
                "Modalidad": NOMBRE_MODALIDAD.get(e["modalidad_preferida"]),
                "Competencias": competencias_a_texto(e["competencias"]),
            }
            for e in estudiantes
        ]
    )
    st.caption(f"{len(estudiantes)} estudiante(s)")
    st.dataframe(tabla, hide_index=True)


# ---------------------------------------------------------------------------

def _formulario(clave: str, inicial: dict, texto_boton: str) -> dict | None:
    """Dibuja el formulario de estudiante. Devuelve los datos si se envió, o None.

    'inicial' trae los valores con los que arranca el formulario (vacío para el alta).
    """
    with st.form(clave):
        col1, col2 = st.columns(2)
        nombre = col1.text_input("Nombre *", value=inicial.get("nombre", ""))
        email = col2.text_input("Email *", value=inicial.get("email", ""))
        carrera = col1.text_input("Carrera *", value=inicial.get("carrera", ""))
        anio = col2.number_input(
            "Año de cursada *", min_value=1, max_value=6, step=1,
            value=inicial.get("anio_cursada", 1),
        )
        modalidad_actual = inicial.get("modalidad_preferida", "presencial")
        modalidad = st.selectbox(
            "Modalidad preferida *", MODALIDADES,
            index=MODALIDADES.index(modalidad_actual), format_func=NOMBRE_MODALIDAD.get,
        )

        st.markdown("**Competencias** — agregá filas con el **+** de la tabla. Nivel de 1 a 5.")
        filas_iniciales = inicial.get("competencias") or [{"skill": "", "nivel": 3}]
        tabla = st.data_editor(
            pd.DataFrame(filas_iniciales, columns=["skill", "nivel"]),
            num_rows="dynamic",
            hide_index=True,
            key=f"{clave}_competencias",
            column_config={
                "skill": st.column_config.TextColumn("Competencia", required=True),
                "nivel": st.column_config.NumberColumn(
                    "Nivel", min_value=1, max_value=5, step=1, default=3, required=True
                ),
            },
        )
        enviado = st.form_submit_button(texto_boton, type="primary")

    if not enviado:
        return None

    try:
        competencias = leer_tabla_editable(tabla, "nivel")
    except ValueError as error:
        st.error(f"✏️ {error}")
        return None

    return {
        "nombre": nombre,
        "email": email,
        "carrera": carrera,
        "anio_cursada": int(anio),
        "modalidad_preferida": modalidad,
        "competencias": competencias,
    }


def _alta() -> None:
    datos = _formulario("alta_estudiante", {}, "Crear estudiante")
    if datos is None:
        return
    try:
        creado = api.crear_estudiante(datos)
    except ErrorAPI as error:
        mostrar_error(error)
        return
    avisar_y_recargar(f"Estudiante '{creado['nombre']}' creado con id {creado['id']}.")


def _edicion() -> None:
    try:
        estudiantes = api.listar_estudiantes()
    except ErrorAPI as error:
        mostrar_error(error)
        return
    if not estudiantes:
        st.info("Todavía no hay estudiantes.")
        return

    elegido = st.selectbox(
        "Elegí un estudiante", estudiantes,
        format_func=lambda e: f"#{e['id']} — {e['nombre']} ({e['email']})",
    )

    # La clave incluye el id para que el formulario se recargue al cambiar de estudiante.
    datos = _formulario(f"editar_{elegido['id']}", elegido, "Guardar cambios")
    if datos is not None:
        try:
            api.actualizar_estudiante(elegido["id"], datos)
        except ErrorAPI as error:
            mostrar_error(error)
        else:
            avisar_y_recargar(f"Estudiante '{datos['nombre']}' actualizado.")

    st.divider()
    st.markdown("**Eliminar estudiante**")
    confirmar = st.checkbox(
        f"Confirmo que quiero eliminar a {elegido['nombre']} (también se borran sus resultados)",
        key=f"confirmar_borrado_{elegido['id']}",
    )
    if st.button("Eliminar", disabled=not confirmar, type="secondary"):
        try:
            api.eliminar_estudiante(elegido["id"])
        except ErrorAPI as error:
            mostrar_error(error)
        else:
            avisar_y_recargar(f"Estudiante '{elegido['nombre']}' eliminado.")
