"""
Acceso a la base de datos SQLite (sin ORM, usando sqlite3 de la librería estándar).

- conectar(): abre una conexión, hace commit al terminar y la cierra.
- crear_tablas(): crea las tablas si no existen.
- Funciones CRUD por entidad: estudiantes, ofertas, resultados de matching
  y recomendaciones de IA.

Las funciones de alta/modificación validan los datos (core.validaciones)
antes de guardar, y lanzan las excepciones de core.excepciones cuando
algo no existe o está duplicado. Devuelven diccionarios comunes de Python.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core import config
from core.excepciones import (
    DuplicadoError,
    EstadoInvalidoError,
    NoEncontradoError,
    ValidacionError,
)
from core.validaciones import (
    normalizar_skill,
    validar_estado_oferta,
    validar_estudiante,
    validar_oferta,
)

# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS estudiantes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT    NOT NULL,
    email               TEXT    NOT NULL UNIQUE,
    carrera             TEXT    NOT NULL,
    anio_cursada        INTEGER NOT NULL CHECK (anio_cursada BETWEEN 1 AND 6),
    modalidad_preferida TEXT    NOT NULL CHECK (modalidad_preferida IN ('presencial', 'remota', 'hibrida')),
    creado_en           TEXT    NOT NULL,
    actualizado_en      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS competencias_estudiante (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    skill         TEXT    NOT NULL,
    nivel         INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
    UNIQUE (estudiante_id, skill)
);

CREATE TABLE IF NOT EXISTS ofertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo      TEXT NOT NULL,
    empresa     TEXT NOT NULL,
    modalidad   TEXT NOT NULL CHECK (modalidad IN ('presencial', 'remota', 'hibrida')),
    descripcion TEXT NOT NULL DEFAULT '',
    estado      TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cerrada')),
    creado_en   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requisitos_oferta (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    oferta_id    INTEGER NOT NULL REFERENCES ofertas(id) ON DELETE CASCADE,
    skill        TEXT    NOT NULL,
    nivel_minimo INTEGER NOT NULL CHECK (nivel_minimo BETWEEN 1 AND 5),
    tipo         TEXT    NOT NULL CHECK (tipo IN ('obligatoria', 'deseable')),
    UNIQUE (oferta_id, skill)
);

-- Resultado calculado por REGLAS. Uno por par estudiante-oferta:
-- si se recalcula, se actualiza la misma fila.
CREATE TABLE IF NOT EXISTS resultados_matching (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id  INTEGER NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    oferta_id      INTEGER NOT NULL REFERENCES ofertas(id) ON DELETE CASCADE,
    score          REAL    NOT NULL CHECK (score BETWEEN 0 AND 100),
    clasificacion  TEXT    NOT NULL CHECK (clasificacion IN ('alta', 'media', 'baja')),
    detalle_json   TEXT    NOT NULL,
    faltantes_json TEXT    NOT NULL,
    origen         TEXT    NOT NULL DEFAULT 'reglas' CHECK (origen = 'reglas'),
    calculado_en   TEXT    NOT NULL,
    UNIQUE (estudiante_id, oferta_id)
);

-- Recomendación generada por IA. Siempre nace 'pendiente_revision'
-- y solo una persona la pasa a 'aprobada' o 'rechazada'.
CREATE TABLE IF NOT EXISTS recomendaciones_ia (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    resultado_id       INTEGER NOT NULL REFERENCES resultados_matching(id) ON DELETE CASCADE,
    texto_json         TEXT    NOT NULL,
    modelo             TEXT    NOT NULL,
    origen             TEXT    NOT NULL DEFAULT 'ia' CHECK (origen = 'ia'),
    estado             TEXT    NOT NULL DEFAULT 'pendiente_revision'
                               CHECK (estado IN ('pendiente_revision', 'aprobada', 'rechazada')),
    comentario_revisor TEXT,
    creado_en          TEXT    NOT NULL,
    revisado_en        TEXT
);
"""


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def _ahora() -> str:
    """Fecha y hora actual como texto ISO, ej: '2026-10-25T18:30:00'."""
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conectar():
    """Abre una conexión a la base. Uso:

        with conectar() as con:
            con.execute(...)

    Al salir del bloque hace commit (o rollback si hubo error) y cierra.
    """
    ruta = Path(config.DB_PATH)  # se lee en cada llamada: los tests lo cambian
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row  # permite acceder a las columnas por nombre
    con.execute("PRAGMA foreign_keys = ON")  # SQLite no activa las FK por defecto
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def crear_tablas() -> None:
    """Crea todas las tablas si todavía no existen."""
    with conectar() as con:
        con.executescript(ESQUEMA_SQL)


def verificar_conexion() -> bool:
    """True si la base responde (se usa en /health)."""
    try:
        with conectar() as con:
            con.execute("SELECT 1")
        return True
    except sqlite3.Error:
        return False


# ---------------------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------------------

def _armar_estudiante(con, fila) -> dict:
    """Convierte una fila de 'estudiantes' en dict y le agrega sus competencias."""
    estudiante = dict(fila)
    competencias = con.execute(
        "SELECT skill, nivel FROM competencias_estudiante WHERE estudiante_id = ? ORDER BY skill",
        (estudiante["id"],),
    ).fetchall()
    estudiante["competencias"] = [dict(c) for c in competencias]
    return estudiante


def _guardar_competencias(con, estudiante_id: int, competencias: list[dict]) -> None:
    """Reemplaza todas las competencias del estudiante por las recibidas."""
    con.execute("DELETE FROM competencias_estudiante WHERE estudiante_id = ?", (estudiante_id,))
    con.executemany(
        "INSERT INTO competencias_estudiante (estudiante_id, skill, nivel) VALUES (?, ?, ?)",
        [(estudiante_id, c["skill"], c["nivel"]) for c in competencias],
    )


def _email_en_uso(con, email: str, excluir_id: int | None = None) -> bool:
    """True si otro estudiante ya usa ese email."""
    fila = con.execute(
        "SELECT id FROM estudiantes WHERE email = ? AND id != ?",
        (email, excluir_id or -1),
    ).fetchone()
    return fila is not None


def crear_estudiante(datos: dict) -> dict:
    """Valida y guarda un estudiante con sus competencias. Devuelve el estudiante creado."""
    limpio = validar_estudiante(datos)
    ahora = _ahora()
    with conectar() as con:
        if _email_en_uso(con, limpio["email"]):
            raise DuplicadoError(f"Ya existe un estudiante con el email '{limpio['email']}'.")
        cursor = con.execute(
            """INSERT INTO estudiantes
               (nombre, email, carrera, anio_cursada, modalidad_preferida, creado_en, actualizado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (limpio["nombre"], limpio["email"], limpio["carrera"], limpio["anio_cursada"],
             limpio["modalidad_preferida"], ahora, ahora),
        )
        nuevo_id = cursor.lastrowid
        _guardar_competencias(con, nuevo_id, limpio["competencias"])
    return obtener_estudiante(nuevo_id)


def obtener_estudiante(estudiante_id: int) -> dict:
    """Devuelve un estudiante con sus competencias o lanza NoEncontradoError."""
    with conectar() as con:
        fila = con.execute("SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()
        if fila is None:
            raise NoEncontradoError(f"No existe el estudiante con id {estudiante_id}.")
        return _armar_estudiante(con, fila)


def listar_estudiantes(skill: str | None = None, carrera: str | None = None) -> list[dict]:
    """Lista estudiantes. Filtros opcionales:
    - skill: solo los que tienen esa competencia (se normaliza).
    - carrera: texto contenido en la carrera (sin distinguir mayúsculas).
    """
    sql = "SELECT * FROM estudiantes WHERE 1 = 1"  # '1 = 1' permite ir agregando 'AND ...'
    parametros = []
    if skill:
        sql += """ AND id IN (SELECT estudiante_id FROM competencias_estudiante WHERE skill = ?)"""
        parametros.append(normalizar_skill(skill))
    if carrera:
        sql += " AND LOWER(carrera) LIKE ?"
        parametros.append(f"%{carrera.strip().lower()}%")
    sql += " ORDER BY nombre"

    with conectar() as con:
        filas = con.execute(sql, parametros).fetchall()
        return [_armar_estudiante(con, f) for f in filas]


def actualizar_estudiante(estudiante_id: int, datos: dict) -> dict:
    """Reemplaza los datos y las competencias de un estudiante (como un PUT)."""
    limpio = validar_estudiante(datos)
    with conectar() as con:
        existe = con.execute("SELECT id FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()
        if existe is None:
            raise NoEncontradoError(f"No existe el estudiante con id {estudiante_id}.")
        if _email_en_uso(con, limpio["email"], excluir_id=estudiante_id):
            raise DuplicadoError(f"Ya existe otro estudiante con el email '{limpio['email']}'.")
        con.execute(
            """UPDATE estudiantes
               SET nombre = ?, email = ?, carrera = ?, anio_cursada = ?,
                   modalidad_preferida = ?, actualizado_en = ?
               WHERE id = ?""",
            (limpio["nombre"], limpio["email"], limpio["carrera"], limpio["anio_cursada"],
             limpio["modalidad_preferida"], _ahora(), estudiante_id),
        )
        _guardar_competencias(con, estudiante_id, limpio["competencias"])
    return obtener_estudiante(estudiante_id)


def eliminar_estudiante(estudiante_id: int) -> None:
    """Borra un estudiante. Por ON DELETE CASCADE se borran también sus
    competencias, resultados de matching y recomendaciones."""
    with conectar() as con:
        cursor = con.execute("DELETE FROM estudiantes WHERE id = ?", (estudiante_id,))
        if cursor.rowcount == 0:
            raise NoEncontradoError(f"No existe el estudiante con id {estudiante_id}.")


# ---------------------------------------------------------------------------
# Ofertas
# ---------------------------------------------------------------------------

def _armar_oferta(con, fila) -> dict:
    """Convierte una fila de 'ofertas' en dict y le agrega sus requisitos."""
    oferta = dict(fila)
    requisitos = con.execute(
        """SELECT skill, nivel_minimo, tipo FROM requisitos_oferta
           WHERE oferta_id = ? ORDER BY tipo DESC, skill""",  # obligatorias primero
        (oferta["id"],),
    ).fetchall()
    oferta["requisitos"] = [dict(r) for r in requisitos]
    return oferta


def crear_oferta(datos: dict) -> dict:
    """Valida y guarda una oferta con sus requisitos. Nace en estado 'abierta'."""
    limpio = validar_oferta(datos)
    with conectar() as con:
        cursor = con.execute(
            """INSERT INTO ofertas (titulo, empresa, modalidad, descripcion, estado, creado_en)
               VALUES (?, ?, ?, ?, 'abierta', ?)""",
            (limpio["titulo"], limpio["empresa"], limpio["modalidad"],
             limpio["descripcion"], _ahora()),
        )
        nuevo_id = cursor.lastrowid
        con.executemany(
            "INSERT INTO requisitos_oferta (oferta_id, skill, nivel_minimo, tipo) VALUES (?, ?, ?, ?)",
            [(nuevo_id, r["skill"], r["nivel_minimo"], r["tipo"]) for r in limpio["requisitos"]],
        )
    return obtener_oferta(nuevo_id)


def obtener_oferta(oferta_id: int) -> dict:
    """Devuelve una oferta con sus requisitos o lanza NoEncontradoError."""
    with conectar() as con:
        fila = con.execute("SELECT * FROM ofertas WHERE id = ?", (oferta_id,)).fetchone()
        if fila is None:
            raise NoEncontradoError(f"No existe la oferta con id {oferta_id}.")
        return _armar_oferta(con, fila)


def listar_ofertas(estado: str | None = None) -> list[dict]:
    """Lista ofertas, opcionalmente filtradas por estado ('abierta' / 'cerrada')."""
    sql = "SELECT * FROM ofertas"
    parametros = []
    if estado:
        sql += " WHERE estado = ?"
        parametros.append(validar_estado_oferta(estado))
    sql += " ORDER BY id"
    with conectar() as con:
        filas = con.execute(sql, parametros).fetchall()
        return [_armar_oferta(con, f) for f in filas]


def cambiar_estado_oferta(oferta_id: int, estado: str) -> dict:
    """Abre o cierra una oferta."""
    nuevo_estado = validar_estado_oferta(estado)
    with conectar() as con:
        cursor = con.execute("UPDATE ofertas SET estado = ? WHERE id = ?", (nuevo_estado, oferta_id))
        if cursor.rowcount == 0:
            raise NoEncontradoError(f"No existe la oferta con id {oferta_id}.")
    return obtener_oferta(oferta_id)


# ---------------------------------------------------------------------------
# Resultados de matching (origen: reglas)
# ---------------------------------------------------------------------------

# Consulta base: trae el resultado con el nombre del estudiante, el título de
# la oferta y si ya tiene alguna recomendación de IA asociada.
_SQL_RESULTADOS = """
SELECT r.*,
       e.nombre AS estudiante_nombre,
       o.titulo AS oferta_titulo,
       (SELECT COUNT(*) FROM recomendaciones_ia ri WHERE ri.resultado_id = r.id) AS cantidad_recomendaciones
FROM resultados_matching r
JOIN estudiantes e ON e.id = r.estudiante_id
JOIN ofertas o     ON o.id = r.oferta_id
"""


def _armar_resultado(fila) -> dict:
    """Convierte una fila de resultados en dict, pasando el JSON a objetos Python."""
    resultado = dict(fila)
    resultado["desglose"] = json.loads(resultado.pop("detalle_json"))
    resultado["faltantes"] = json.loads(resultado.pop("faltantes_json"))
    resultado["tiene_recomendacion"] = resultado.pop("cantidad_recomendaciones") > 0
    return resultado


def guardar_resultado(estudiante_id: int, oferta_id: int, calculo: dict) -> dict:
    """Guarda (o actualiza si ya existía) el resultado de scoring de un par
    estudiante-oferta. 'calculo' es lo que devuelve scoring.calcular_score()."""
    with conectar() as con:
        con.execute(
            """INSERT INTO resultados_matching
                   (estudiante_id, oferta_id, score, clasificacion,
                    detalle_json, faltantes_json, origen, calculado_en)
               VALUES (?, ?, ?, ?, ?, ?, 'reglas', ?)
               ON CONFLICT (estudiante_id, oferta_id) DO UPDATE SET
                   score = excluded.score,
                   clasificacion = excluded.clasificacion,
                   detalle_json = excluded.detalle_json,
                   faltantes_json = excluded.faltantes_json,
                   calculado_en = excluded.calculado_en""",
            (estudiante_id, oferta_id, calculo["score"], calculo["clasificacion"],
             json.dumps(calculo["desglose"], ensure_ascii=False),
             json.dumps(calculo["faltantes"], ensure_ascii=False),
             _ahora()),
        )
        fila = con.execute(
            _SQL_RESULTADOS + " WHERE r.estudiante_id = ? AND r.oferta_id = ?",
            (estudiante_id, oferta_id),
        ).fetchone()
        return _armar_resultado(fila)


def obtener_resultado(resultado_id: int) -> dict:
    """Devuelve un resultado de matching o lanza NoEncontradoError."""
    with conectar() as con:
        fila = con.execute(_SQL_RESULTADOS + " WHERE r.id = ?", (resultado_id,)).fetchone()
    if fila is None:
        raise NoEncontradoError(f"No existe el resultado de matching con id {resultado_id}.")
    return _armar_resultado(fila)


def listar_resultados(
    oferta_id: int | None = None,
    estudiante_id: int | None = None,
    min_score: float | None = None,
) -> list[dict]:
    """Lista resultados ordenados de mayor a menor score, con filtros opcionales."""
    sql = _SQL_RESULTADOS + " WHERE 1 = 1"
    parametros = []
    if oferta_id is not None:
        sql += " AND r.oferta_id = ?"
        parametros.append(oferta_id)
    if estudiante_id is not None:
        sql += " AND r.estudiante_id = ?"
        parametros.append(estudiante_id)
    if min_score is not None:
        sql += " AND r.score >= ?"
        parametros.append(min_score)
    sql += " ORDER BY r.score DESC, e.nombre"
    with conectar() as con:
        filas = con.execute(sql, parametros).fetchall()
    return [_armar_resultado(f) for f in filas]


# ---------------------------------------------------------------------------
# Recomendaciones de IA (origen: ia)
# ---------------------------------------------------------------------------

def _armar_recomendacion(fila) -> dict:
    recomendacion = dict(fila)
    recomendacion["contenido"] = json.loads(recomendacion.pop("texto_json"))
    return recomendacion


def crear_recomendacion(resultado_id: int, contenido: dict, modelo: str) -> dict:
    """Guarda una recomendación de IA. SIEMPRE nace como 'pendiente_revision'."""
    obtener_resultado(resultado_id)  # lanza NoEncontradoError si no existe
    with conectar() as con:
        cursor = con.execute(
            """INSERT INTO recomendaciones_ia
                   (resultado_id, texto_json, modelo, origen, estado, creado_en)
               VALUES (?, ?, ?, 'ia', 'pendiente_revision', ?)""",
            (resultado_id, json.dumps(contenido, ensure_ascii=False), modelo, _ahora()),
        )
        nuevo_id = cursor.lastrowid
    return obtener_recomendacion(nuevo_id)


def obtener_recomendacion(recomendacion_id: int) -> dict:
    with conectar() as con:
        fila = con.execute(
            "SELECT * FROM recomendaciones_ia WHERE id = ?", (recomendacion_id,)
        ).fetchone()
    if fila is None:
        raise NoEncontradoError(f"No existe la recomendación con id {recomendacion_id}.")
    return _armar_recomendacion(fila)


def listar_recomendaciones(estado: str | None = None) -> list[dict]:
    """Lista recomendaciones, opcionalmente filtradas por estado."""
    sql = "SELECT * FROM recomendaciones_ia"
    parametros = []
    if estado:
        sql += " WHERE estado = ?"
        parametros.append(estado)
    sql += " ORDER BY id DESC"
    with conectar() as con:
        filas = con.execute(sql, parametros).fetchall()
    return [_armar_recomendacion(f) for f in filas]


def revisar_recomendacion(recomendacion_id: int, estado: str, comentario: str | None) -> dict:
    """Supervisión humana: aprueba o rechaza una recomendación pendiente.

    - estado debe ser 'aprobada' o 'rechazada' (si no -> ValidacionError).
    - si ya fue revisada antes -> EstadoInvalidoError (no se puede revisar dos veces).
    """
    if estado not in ("aprobada", "rechazada"):
        raise ValidacionError("El estado de revisión debe ser 'aprobada' o 'rechazada'.")

    actual = obtener_recomendacion(recomendacion_id)  # NoEncontradoError si no existe
    if actual["estado"] != "pendiente_revision":
        raise EstadoInvalidoError(
            f"La recomendación {recomendacion_id} ya fue revisada (estado: {actual['estado']})."
        )

    with conectar() as con:
        con.execute(
            """UPDATE recomendaciones_ia
               SET estado = ?, comentario_revisor = ?, revisado_en = ?
               WHERE id = ?""",
            (estado, (comentario or "").strip() or None, _ahora(), recomendacion_id),
        )
    return obtener_recomendacion(recomendacion_id)
