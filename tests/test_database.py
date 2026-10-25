"""Tests de la capa de datos (core/database.py) usando una base temporal."""

import pytest

from core import database
from core.excepciones import (
    DuplicadoError,
    EstadoInvalidoError,
    NoEncontradoError,
    ValidacionError,
)
from core.scoring import calcular_score

ESTUDIANTE = {
    "nombre": "Ana Prueba",
    "email": "Ana.Prueba@Example.com",
    "carrera": "Licenciatura en Sistemas",
    "anio_cursada": 3,
    "modalidad_preferida": "Híbrida",
    "competencias": [{"skill": "Python", "nivel": 4}, {"skill": "Estadística", "nivel": 2}],
}

OFERTA = {
    "titulo": "Backend Jr",
    "empresa": "Empresa Ficticia",
    "modalidad": "remota",
    "requisitos": [
        {"skill": "python", "nivel_minimo": 3, "tipo": "obligatoria"},
        {"skill": "docker", "nivel_minimo": 1, "tipo": "deseable"},
    ],
}


def test_crear_y_obtener_estudiante_normaliza_datos(db_temporal):
    creado = database.crear_estudiante(ESTUDIANTE)
    assert creado["id"] == 1
    assert creado["email"] == "ana.prueba@example.com"
    assert creado["modalidad_preferida"] == "hibrida"
    assert {"skill": "estadistica", "nivel": 2} in creado["competencias"]
    assert database.obtener_estudiante(1)["nombre"] == "Ana Prueba"


def test_email_duplicado(db_temporal):
    database.crear_estudiante(ESTUDIANTE)
    with pytest.raises(DuplicadoError):
        database.crear_estudiante({**ESTUDIANTE, "email": "ana.prueba@example.com"})


def test_datos_invalidos(db_temporal):
    with pytest.raises(ValidacionError):
        database.crear_estudiante({**ESTUDIANTE, "competencias": [{"skill": "python", "nivel": 9}]})
    with pytest.raises(ValidacionError):
        database.crear_oferta({**OFERTA, "requisitos": []})


def test_no_encontrado(db_temporal):
    with pytest.raises(NoEncontradoError):
        database.obtener_estudiante(999)
    with pytest.raises(NoEncontradoError):
        database.eliminar_estudiante(999)


def test_filtro_por_skill_con_tilde(db_temporal):
    database.crear_estudiante(ESTUDIANTE)
    assert len(database.listar_estudiantes(skill="ESTADÍSTICA")) == 1
    assert len(database.listar_estudiantes(skill="java")) == 0
    assert len(database.listar_estudiantes(carrera="sistemas")) == 1


def test_actualizar_estudiante(db_temporal):
    database.crear_estudiante(ESTUDIANTE)
    cambios = {**ESTUDIANTE, "anio_cursada": 4, "competencias": [{"skill": "SQL", "nivel": 3}]}
    actualizado = database.actualizar_estudiante(1, cambios)
    assert actualizado["anio_cursada"] == 4
    assert actualizado["competencias"] == [{"skill": "sql", "nivel": 3}]


def test_resultado_se_actualiza_al_recalcular(db_temporal):
    est = database.crear_estudiante(ESTUDIANTE)
    ofe = database.crear_oferta(OFERTA)
    primero = database.guardar_resultado(est["id"], ofe["id"], calcular_score(est, ofe))
    segundo = database.guardar_resultado(est["id"], ofe["id"], calcular_score(est, ofe))
    assert primero["id"] == segundo["id"]  # misma fila, no se duplica
    assert segundo["origen"] == "reglas"
    assert len(database.listar_resultados(oferta_id=ofe["id"])) == 1


def test_borrar_estudiante_borra_en_cascada(db_temporal):
    est = database.crear_estudiante(ESTUDIANTE)
    ofe = database.crear_oferta(OFERTA)
    database.guardar_resultado(est["id"], ofe["id"], calcular_score(est, ofe))
    database.eliminar_estudiante(est["id"])
    assert database.listar_resultados() == []


def test_revision_humana_de_recomendacion(db_temporal):
    est = database.crear_estudiante(ESTUDIANTE)
    ofe = database.crear_oferta(OFERTA)
    res = database.guardar_resultado(est["id"], ofe["id"], calcular_score(est, ofe))

    reco = database.crear_recomendacion(res["id"], {"resumen": "texto"}, "modelo-test")
    assert reco["origen"] == "ia"
    assert reco["estado"] == "pendiente_revision"
    assert database.obtener_resultado(res["id"])["tiene_recomendacion"] is True

    revisada = database.revisar_recomendacion(reco["id"], "aprobada", "Correcta")
    assert revisada["estado"] == "aprobada"
    assert revisada["revisado_en"] is not None

    # No se puede revisar dos veces.
    with pytest.raises(EstadoInvalidoError):
        database.revisar_recomendacion(reco["id"], "rechazada", None)


def test_cerrar_oferta(db_temporal):
    ofe = database.crear_oferta(OFERTA)
    assert database.cambiar_estado_oferta(ofe["id"], "cerrada")["estado"] == "cerrada"
    assert database.listar_ofertas(estado="abierta") == []
    with pytest.raises(ValidacionError):
        database.cambiar_estado_oferta(ofe["id"], "pausada")
