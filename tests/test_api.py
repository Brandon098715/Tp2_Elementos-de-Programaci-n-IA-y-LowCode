"""Tests de la API FastAPI (endpoints y códigos HTTP)."""

from core import database

ESTUDIANTE = {
    "nombre": "Julia Pérez",
    "email": "julia@example.com",
    "carrera": "Licenciatura en Sistemas",
    "anio_cursada": 3,
    "modalidad_preferida": "remota",
    "competencias": [{"skill": "Python", "nivel": 4}, {"skill": "SQL", "nivel": 2}],
}

OFERTA = {
    "titulo": "Backend Jr",
    "empresa": "Empresa Ficticia",
    "modalidad": "remota",
    "requisitos": [
        {"skill": "Python", "nivel_minimo": 3, "tipo": "obligatoria"},
        {"skill": "SQL", "nivel_minimo": 3, "tipo": "obligatoria"},
        {"skill": "Docker", "nivel_minimo": 1, "tipo": "deseable"},
    ],
}


def crear_estudiante(cliente, **cambios):
    respuesta = cliente.post("/estudiantes", json={**ESTUDIANTE, **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def crear_oferta(cliente, **cambios):
    respuesta = cliente.post("/ofertas", json={**OFERTA, **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- Sistema ---

def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["base_datos"] == "ok"
    assert r.json()["ollama"] == "no disponible"  # simulado en conftest


# --- Estudiantes ---

def test_crear_y_consultar_estudiante(cliente):
    creado = crear_estudiante(cliente)
    assert creado["id"] == 1
    assert creado["competencias"] == [{"skill": "python", "nivel": 4}, {"skill": "sql", "nivel": 2}]

    assert cliente.get("/estudiantes/1").json()["nombre"] == "Julia Pérez"
    assert len(cliente.get("/estudiantes", params={"skill": "PYTHON"}).json()) == 1
    assert cliente.get("/estudiantes", params={"skill": "java"}).json() == []


def test_estudiante_inexistente_404(cliente):
    r = cliente.get("/estudiantes/999")
    assert r.status_code == 404
    assert "999" in r.json()["detalle"]


def test_estudiante_invalido_422(cliente):
    # Nivel fuera de rango (lo detecta Pydantic)
    r = cliente.post("/estudiantes", json={**ESTUDIANTE, "competencias": [{"skill": "x", "nivel": 9}]})
    assert r.status_code == 422
    assert "competencias.0.nivel" in r.json()["detalle"]

    # Falta un campo obligatorio
    sin_email = {k: v for k, v in ESTUDIANTE.items() if k != "email"}
    assert cliente.post("/estudiantes", json=sin_email).status_code == 422

    # Modalidad inexistente (lo detecta core/validaciones)
    r = cliente.post("/estudiantes", json={**ESTUDIANTE, "modalidad_preferida": "a veces"})
    assert r.status_code == 422
    assert "Modalidad" in r.json()["detalle"]


def test_email_duplicado_409(cliente):
    crear_estudiante(cliente)
    r = cliente.post("/estudiantes", json={**ESTUDIANTE, "email": "JULIA@example.com"})
    assert r.status_code == 409


def test_actualizar_y_eliminar_estudiante(cliente):
    crear_estudiante(cliente)
    r = cliente.put("/estudiantes/1", json={**ESTUDIANTE, "anio_cursada": 5})
    assert r.status_code == 200
    assert r.json()["anio_cursada"] == 5

    assert cliente.put("/estudiantes/999", json=ESTUDIANTE).status_code == 404

    assert cliente.delete("/estudiantes/1").status_code == 204
    assert cliente.get("/estudiantes/1").status_code == 404
    assert cliente.delete("/estudiantes/1").status_code == 404


# --- Ofertas ---

def test_crear_listar_y_cerrar_oferta(cliente):
    oferta = crear_oferta(cliente)
    assert oferta["estado"] == "abierta"

    r = cliente.patch(f"/ofertas/{oferta['id']}/estado", json={"estado": "cerrada"})
    assert r.status_code == 200
    assert r.json()["estado"] == "cerrada"

    assert cliente.get("/ofertas", params={"estado": "abierta"}).json() == []
    assert len(cliente.get("/ofertas", params={"estado": "cerrada"}).json()) == 1


def test_oferta_errores(cliente):
    assert cliente.post("/ofertas", json={**OFERTA, "requisitos": []}).status_code == 422
    assert cliente.patch("/ofertas/999/estado", json={"estado": "cerrada"}).status_code == 404
    oferta = crear_oferta(cliente)
    assert cliente.patch(f"/ofertas/{oferta['id']}/estado", json={"estado": "pausada"}).status_code == 422


# --- Matching ---

def test_matching_devuelve_ranking_ordenado(cliente):
    crear_estudiante(cliente)  # python 4, sql 2 -> obligatorias 1.5/2
    crear_estudiante(cliente, nombre="Experto", email="experto@example.com",
                     competencias=[{"skill": "python", "nivel": 5}, {"skill": "sql", "nivel": 5},
                                   {"skill": "docker", "nivel": 2}])
    oferta = crear_oferta(cliente)

    r = cliente.post(f"/matching/ofertas/{oferta['id']}")
    assert r.status_code == 200
    datos = r.json()
    assert datos["origen"] == "reglas"
    assert datos["total_estudiantes"] == 2

    ranking = datos["ranking"]
    assert ranking[0]["estudiante_nombre"] == "Experto"
    assert ranking[0]["score"] == 100
    assert ranking[1]["score"] == 60  # 45 obligatorias + 0 deseables + 15 modalidad
    assert ranking[1]["faltantes"][0]["skill"] == "sql"

    # Los resultados quedaron guardados y se pueden filtrar
    assert len(cliente.get("/matching/resultados", params={"min_score": 90}).json()) == 1

    # Recalcular no duplica resultados
    cliente.post(f"/matching/ofertas/{oferta['id']}")
    assert len(cliente.get("/matching/resultados").json()) == 2


def test_matching_errores(cliente):
    assert cliente.post("/matching/ofertas/999").status_code == 404

    oferta = crear_oferta(cliente)
    cliente.patch(f"/ofertas/{oferta['id']}/estado", json={"estado": "cerrada"})
    r = cliente.post(f"/matching/ofertas/{oferta['id']}")
    assert r.status_code == 409
    assert "cerrada" in r.json()["detalle"]


# --- Revisión humana de recomendaciones ---

def _crear_recomendacion_de_prueba(cliente) -> int:
    """Crea un resultado y una recomendación directamente en la base
    (la generación con IA se prueba en la Fase 4)."""
    crear_estudiante(cliente)
    oferta = crear_oferta(cliente)
    resultado = cliente.post(f"/matching/ofertas/{oferta['id']}").json()["ranking"][0]
    reco = database.crear_recomendacion(resultado["id"], {"resumen": "Prueba"}, "modelo-test")
    return reco["id"]


def test_revision_de_recomendacion(cliente):
    reco_id = _crear_recomendacion_de_prueba(cliente)

    pendientes = cliente.get("/recomendaciones", params={"estado": "pendiente_revision"}).json()
    assert len(pendientes) == 1
    assert pendientes[0]["origen"] == "ia"

    r = cliente.patch(f"/recomendaciones/{reco_id}/revision",
                      json={"estado": "rechazada", "comentario": "Recurso inventado"})
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazada"
    assert r.json()["comentario_revisor"] == "Recurso inventado"

    # Ya revisada -> 409
    r = cliente.patch(f"/recomendaciones/{reco_id}/revision", json={"estado": "aprobada"})
    assert r.status_code == 409


def test_revision_errores(cliente):
    assert cliente.patch("/recomendaciones/999/revision", json={"estado": "aprobada"}).status_code == 404
    reco_id = _crear_recomendacion_de_prueba(cliente)
    r = cliente.patch(f"/recomendaciones/{reco_id}/revision", json={"estado": "pendiente_revision"})
    assert r.status_code == 422


# --- Reportes ---

def test_reporte_resumen(cliente):
    _crear_recomendacion_de_prueba(cliente)
    r = cliente.get("/reportes/resumen")
    assert r.status_code == 200
    datos = r.json()
    assert datos["totales"]["estudiantes"] == 1
    assert datos["totales"]["ofertas_abiertas"] == 1
    assert datos["recomendaciones_pendientes"] == 1
    assert datos["score_promedio_por_oferta"][0]["score_promedio"] == 60
    skills_faltantes = [f["skill"] for f in datos["competencias_mas_faltantes"]]
    assert "sql" in skills_faltantes and "docker" in skills_faltantes
