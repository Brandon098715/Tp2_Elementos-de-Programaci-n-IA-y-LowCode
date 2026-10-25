"""Configuración compartida de pytest."""

import pytest

from core import config, database


@pytest.fixture
def db_temporal(tmp_path, monkeypatch):
    """Usa una base SQLite nueva y vacía en una carpeta temporal para cada test.
    Así los tests nunca tocan la base real (data/vinculacion.db)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    database.crear_tablas()
    return tmp_path / "test.db"


@pytest.fixture
def cliente(db_temporal, monkeypatch):
    """Cliente HTTP de prueba para la API, con base temporal y Ollama simulado
    como 'apagado' (los tests nunca llaman al modelo real)."""
    from fastapi.testclient import TestClient

    from api.main import app
    from core import ia_service

    monkeypatch.setattr(ia_service, "ollama_disponible", lambda: False)
    with TestClient(app) as c:
        yield c
