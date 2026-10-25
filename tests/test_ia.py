"""Tests del servicio de IA y del endpoint POST /recomendaciones/{resultado_id}.

Ollama se SIMULA: reemplazamos requests.post por una función falsa, así los
tests no necesitan el modelo y siempre dan el mismo resultado.
"""

import json

import pytest
import requests

from core import ia_service
from core.excepciones import IAError, IANoDisponibleError

RESPUESTA_VALIDA = {
    "resumen": "Le falta reforzar SQL.",
    "recomendaciones": [
        {"competencia": "SQL", "accion": "Practicar consultas con JOIN",
         "recurso_sugerido": "Documentación oficial", "prioridad": "Alta"},
        {"competencia": "docker", "accion": "Armar un contenedor simple",
         "recurso_sugerido": "Curso online gratuito", "prioridad": "baja"},
    ],
    "mejoras_perfil": ["Subir proyectos a GitHub"],
}


class RespuestaFalsa:
    """Imita lo mínimo de requests.Response que usa ia_service."""

    def __init__(self, texto_generado: str, status_code: int = 200):
        self.status_code = status_code
        self._texto = texto_generado

    def json(self):
        return {"response": self._texto}


def simular_ollama(monkeypatch, *respuestas):
    """Cada llamada a requests.post devuelve la siguiente respuesta de la lista.
    Si un elemento es una excepción, se lanza. Devuelve la lista de prompts recibidos."""
    pendientes = list(respuestas)
    llamadas = []

    def post_falso(url, json=None, timeout=None):
        llamadas.append(json["prompt"])
        siguiente = pendientes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    monkeypatch.setattr(ia_service.requests, "post", post_falso)
    return llamadas


def valida(contenido=RESPUESTA_VALIDA):
    return RespuestaFalsa(json.dumps(contenido))


# --- Datos de prueba ---

ESTUDIANTE = {"carrera": "Sistemas", "anio_cursada": 3, "modalidad_preferida": "remota",
              "competencias": [{"skill": "python", "nivel": 4}, {"skill": "sql", "nivel": 2}]}
OFERTA = {"titulo": "Backend Jr", "empresa": "Ficticia", "modalidad": "remota", "descripcion": ""}
RESULTADO = {
    "score": 60, "clasificacion": "media",
    "faltantes": [
        {"skill": "sql", "nivel_requerido": 3, "nivel_actual": 2, "tipo": "obligatoria"},
        {"skill": "docker", "nivel_requerido": 1, "nivel_actual": 0, "tipo": "deseable"},
    ],
}


# --- Servicio ---

def test_prompt_incluye_faltantes_y_no_datos_personales():
    prompt = ia_service.armar_prompt({**ESTUDIANTE, "nombre": "Juan", "email": "j@x.com"},
                                     OFERTA, RESULTADO)
    assert "sql: tiene nivel 2, se requiere nivel 3 (obligatoria)" in prompt
    assert "docker: no la tiene" in prompt
    assert "60 de 100" in prompt
    assert "Juan" not in prompt and "j@x.com" not in prompt


def test_respuesta_valida(monkeypatch):
    simular_ollama(monkeypatch, valida())
    contenido = ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)
    assert contenido["recomendaciones"][0]["prioridad"] == "alta"  # "Alta" se normaliza
    assert contenido["advertencias"] == []


def test_reintenta_una_vez_si_el_json_es_invalido(monkeypatch):
    llamadas = simular_ollama(monkeypatch, RespuestaFalsa("esto no es json"), valida())
    contenido = ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)
    assert len(llamadas) == 2
    assert contenido["resumen"] == "Le falta reforzar SQL."


def test_falla_dos_veces_lanza_ia_error(monkeypatch):
    sin_recomendaciones = {"resumen": "x", "recomendaciones": []}
    simular_ollama(monkeypatch, RespuestaFalsa("{roto"), valida(sin_recomendaciones))
    with pytest.raises(IAError):
        ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)


def test_ollama_apagado(monkeypatch):
    simular_ollama(monkeypatch, requests.ConnectionError())
    with pytest.raises(IANoDisponibleError, match="no disponible"):
        ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)


def test_modelo_no_instalado(monkeypatch):
    simular_ollama(monkeypatch, RespuestaFalsa("", status_code=404))
    with pytest.raises(IANoDisponibleError, match="ollama pull"):
        ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)


def test_advertencias_si_la_ia_se_desvia(monkeypatch):
    desviada = {
        "resumen": "x",
        "recomendaciones": [{"competencia": "Kubernetes", "accion": "a",
                             "recurso_sugerido": "https://inventado.com", "prioridad": "media"},
                            {"competencia": "SQL avanzado", "accion": "b",
                             "recurso_sugerido": "Ejercicios", "prioridad": "alta"}],
    }
    simular_ollama(monkeypatch, valida(desviada))
    advertencias = ia_service.generar_recomendacion(ESTUDIANTE, OFERTA, RESULTADO)["advertencias"]
    texto = " | ".join(advertencias)
    assert "Kubernetes" in texto                    # no estaba entre las faltantes
    assert "docker" in texto                        # faltante sin recomendación
    assert "enlace" in texto                        # URL posiblemente inventada
    assert "SQL avanzado" not in texto              # 'SQL avanzado' se acepta como 'sql'


# --- Endpoint ---

def _preparar_resultado(cliente, competencias):
    cliente.post("/estudiantes", json={
        "nombre": "Ana", "email": "ana@example.com", "carrera": "Sistemas", "anio_cursada": 3,
        "modalidad_preferida": "remota", "competencias": competencias})
    oferta = cliente.post("/ofertas", json={
        "titulo": "Backend Jr", "empresa": "Ficticia", "modalidad": "remota",
        "requisitos": [{"skill": "sql", "nivel_minimo": 3, "tipo": "obligatoria"},
                       {"skill": "docker", "nivel_minimo": 1, "tipo": "deseable"}]}).json()
    return cliente.post(f"/matching/ofertas/{oferta['id']}").json()["ranking"][0]["id"]


def test_endpoint_genera_recomendacion_pendiente(cliente, monkeypatch):
    resultado_id = _preparar_resultado(cliente, [{"skill": "sql", "nivel": 2}])
    simular_ollama(monkeypatch, valida())

    r = cliente.post(f"/recomendaciones/{resultado_id}")
    assert r.status_code == 201
    reco = r.json()
    assert reco["origen"] == "ia"
    assert reco["estado"] == "pendiente_revision"
    assert reco["contenido"]["recomendaciones"][0]["competencia"] == "SQL"

    resultado = cliente.get("/matching/resultados").json()[0]
    assert resultado["tiene_recomendacion"] is True


def test_endpoint_ia_caida_503_y_resto_del_sistema_sigue(cliente, monkeypatch):
    resultado_id = _preparar_resultado(cliente, [{"skill": "sql", "nivel": 2}])
    simular_ollama(monkeypatch, requests.ConnectionError())

    r = cliente.post(f"/recomendaciones/{resultado_id}")
    assert r.status_code == 503
    assert "no disponible" in r.json()["detalle"]
    assert cliente.get("/estudiantes").status_code == 200  # lo demás funciona


def test_endpoint_respuesta_invalida_502(cliente, monkeypatch):
    resultado_id = _preparar_resultado(cliente, [{"skill": "sql", "nivel": 2}])
    simular_ollama(monkeypatch, RespuestaFalsa("no"), RespuestaFalsa("tampoco"))
    r = cliente.post(f"/recomendaciones/{resultado_id}")
    assert r.status_code == 502
    assert cliente.get("/recomendaciones").json() == []  # no se guardó nada


def test_endpoint_resultado_inexistente_404(cliente):
    assert cliente.post("/recomendaciones/999").status_code == 404


def test_endpoint_sin_faltantes_409(cliente):
    resultado_id = _preparar_resultado(cliente, [{"skill": "sql", "nivel": 5}, {"skill": "docker", "nivel": 1}])
    assert cliente.post(f"/recomendaciones/{resultado_id}").status_code == 409
