"""Tests de las reglas de scoring (core/scoring.py)."""

import pytest

from core.scoring import calcular_score, clasificar


# --- Helpers para armar datos de prueba de forma corta ---

def estudiante(modalidad: str, **competencias) -> dict:
    """estudiante("remota", python=3, sql=2)"""
    return {
        "modalidad_preferida": modalidad,
        "competencias": [{"skill": s, "nivel": n} for s, n in competencias.items()],
    }


def oferta(modalidad: str, obligatorias: dict | None = None, deseables: dict | None = None) -> dict:
    """oferta("remota", obligatorias={"python": 3}, deseables={"docker": 1})"""
    requisitos = []
    for skill, nivel in (obligatorias or {}).items():
        requisitos.append({"skill": skill, "nivel_minimo": nivel, "tipo": "obligatoria"})
    for skill, nivel in (deseables or {}).items():
        requisitos.append({"skill": skill, "nivel_minimo": nivel, "tipo": "deseable"})
    return {"modalidad": modalidad, "requisitos": requisitos}


OFERTA_BASE = oferta("remota", obligatorias={"python": 3, "sql": 2}, deseables={"git": 2})


# --- Casos principales ---

def test_score_perfecto():
    est = estudiante("remota", python=5, sql=3, git=2)
    r = calcular_score(est, OFERTA_BASE)
    assert r["score"] == 100
    assert r["clasificacion"] == "alta"
    assert r["faltantes"] == []
    assert r["origen"] == "reglas"


def test_score_cero():
    est = estudiante("presencial", java=4)
    r = calcular_score(est, OFERTA_BASE)
    assert r["score"] == 0
    assert r["clasificacion"] == "baja"
    # Le faltan las 3 competencias, todas con nivel_actual 0.
    assert {f["skill"] for f in r["faltantes"]} == {"python", "sql", "git"}
    assert all(f["nivel_actual"] == 0 for f in r["faltantes"])


def test_nivel_insuficiente_cuenta_la_mitad():
    # python 2 < 3 -> vale 0.5 ; sql 3 >= 2 -> vale 1 ; obligatorias = 1.5/2 * 60 = 45
    # git 1 < 2 pero es deseable -> suma 25 igual, aunque figura como faltante
    # modalidad coincide -> 15.   Total = 45 + 25 + 15 = 85
    est = estudiante("remota", python=2, sql=3, git=1)
    r = calcular_score(est, OFERTA_BASE)
    assert r["desglose"]["obligatorias"]["puntos"] == 45
    assert r["desglose"]["deseables"]["puntos"] == 25
    assert r["score"] == 85
    assert r["faltantes"] == [
        {"skill": "python", "nivel_requerido": 3, "nivel_actual": 2, "tipo": "obligatoria"},
        {"skill": "git", "nivel_requerido": 2, "nivel_actual": 1, "tipo": "deseable"},
    ]


def test_sin_obligatorias_redistribuye_el_peso():
    # Sin obligatorias: deseables (25) y modalidad (15) se escalan a 100
    # -> deseables 62.5 y modalidad 37.5. Tiene la deseable, modalidad no coincide.
    ofe = oferta("presencial", deseables={"git": 1})
    est = estudiante("remota", git=1)
    r = calcular_score(est, ofe)
    assert r["desglose"]["obligatorias"]["aplica"] is False
    assert r["desglose"]["deseables"]["peso_efectivo"] == 62.5
    assert r["desglose"]["modalidad"]["peso_efectivo"] == 37.5
    assert r["score"] == 62.5


def test_sin_obligatorias_todo_cumplido_da_100():
    ofe = oferta("remota", deseables={"git": 1, "docker": 1})
    r = calcular_score(estudiante("remota", git=3, docker=1), ofe)
    assert r["score"] == 100


def test_sin_deseables_redistribuye_el_peso():
    # Obligatorias 60 y modalidad 15 se escalan a 100 -> 80 y 20.
    ofe = oferta("remota", obligatorias={"python": 1})
    r = calcular_score(estudiante("presencial", python=1), ofe)
    assert r["desglose"]["obligatorias"]["peso_efectivo"] == 80
    assert r["score"] == 80


# --- Modalidad ---

@pytest.mark.parametrize(
    "mod_estudiante, mod_oferta, puntos_esperados",
    [
        ("remota", "remota", 15),         # coincide
        ("hibrida", "remota", 7),         # el estudiante es híbrido
        ("presencial", "hibrida", 7),     # la oferta es híbrida
        ("presencial", "remota", 0),      # no coincide
    ],
)
def test_modalidad(mod_estudiante, mod_oferta, puntos_esperados):
    ofe = oferta(mod_oferta, obligatorias={"python": 1}, deseables={"git": 1})
    est = estudiante(mod_estudiante, python=1, git=1)
    r = calcular_score(est, ofe)
    assert r["desglose"]["modalidad"]["puntos"] == puntos_esperados
    assert r["score"] == 85 + puntos_esperados


# --- Normalización y otros ---

def test_normaliza_mayusculas_tildes_y_espacios():
    ofe = oferta("Híbrido", obligatorias={"estadistica": 2, "machine learning": 1})
    est = estudiante("HIBRIDA", **{"  Estadística ": 3, "Machine   Learning": 2})
    r = calcular_score(est, ofe)
    assert r["score"] == 100
    assert r["faltantes"] == []


def test_desglose_suma_el_score():
    est = estudiante("hibrida", python=2, git=5)
    r = calcular_score(est, OFERTA_BASE)
    suma = sum(c["puntos"] for c in r["desglose"].values())
    assert round(suma, 1) == r["score"]


@pytest.mark.parametrize(
    "score, esperado",
    [(100, "alta"), (75, "alta"), (74.9, "media"), (50, "media"), (49.9, "baja"), (0, "baja")],
)
def test_clasificacion(score, esperado):
    assert clasificar(score) == esperado
