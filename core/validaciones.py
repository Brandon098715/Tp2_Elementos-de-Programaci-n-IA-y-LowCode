"""
Normalización y validaciones de negocio.

Todas las funciones validar_* reciben un diccionario "crudo" (como llega del
usuario), lo revisan y devuelven un diccionario limpio y normalizado.
Si algo está mal lanzan ValidacionError con un mensaje claro en español.
"""

import re
import unicodedata

from core.excepciones import ValidacionError

# --- Valores permitidos ---
MODALIDADES = ("presencial", "remota", "hibrida")
TIPOS_REQUISITO = ("obligatoria", "deseable")
ESTADOS_OFERTA = ("abierta", "cerrada")
ESTADOS_RECOMENDACION = ("pendiente_revision", "aprobada", "rechazada")
NIVEL_MINIMO = 1
NIVEL_MAXIMO = 5
ANIO_MINIMO = 1
ANIO_MAXIMO = 6

# Variantes que aceptamos y a qué modalidad corresponden.
_ALIAS_MODALIDAD = {
    "remoto": "remota",
    "hibrido": "hibrida",
}

# Email simple: algo@algo.algo (sin espacios). No pretende ser perfecto.
_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------

def quitar_tildes(texto: str) -> str:
    """'Estadística' -> 'Estadistica'. También convierte 'ñ' en 'n'."""
    # NFD separa cada letra de su tilde; después descartamos las tildes (categoría 'Mn').
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio entre palabras.

    '  Machine   Learning ' -> 'machine learning'
    """
    sin_tildes = quitar_tildes(str(texto))
    return " ".join(sin_tildes.lower().split())


def normalizar_skill(skill: str) -> str:
    """Normaliza el nombre de una competencia para poder compararla."""
    return normalizar_texto(skill)


def normalizar_modalidad(valor: str) -> str:
    """Devuelve 'presencial', 'remota' o 'hibrida'. Acepta 'Híbrido', 'REMOTO', etc."""
    modalidad = normalizar_texto(valor)
    modalidad = _ALIAS_MODALIDAD.get(modalidad, modalidad)
    if modalidad not in MODALIDADES:
        raise ValidacionError(
            f"Modalidad '{valor}' inválida. Opciones: {', '.join(MODALIDADES)}."
        )
    return modalidad


# ---------------------------------------------------------------------------
# Validaciones de campos sueltos
# ---------------------------------------------------------------------------

def validar_texto_obligatorio(valor, campo: str) -> str:
    """El campo debe ser texto no vacío. Devuelve el texto sin espacios de los costados."""
    if not isinstance(valor, str) or valor.strip() == "":
        raise ValidacionError(f"El campo '{campo}' es obligatorio.")
    return valor.strip()


def validar_entero_en_rango(valor, campo: str, minimo: int, maximo: int) -> int:
    """El valor debe ser un entero entre minimo y maximo (inclusive)."""
    # bool es subclase de int en Python: lo excluimos a propósito (True no es un nivel).
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise ValidacionError(f"El campo '{campo}' debe ser un número entero.")
    if valor < minimo or valor > maximo:
        raise ValidacionError(f"El campo '{campo}' debe estar entre {minimo} y {maximo}.")
    return valor


def validar_email(email) -> str:
    """Devuelve el email en minúsculas si tiene formato válido."""
    texto = validar_texto_obligatorio(email, "email").lower()
    if not _PATRON_EMAIL.match(texto):
        raise ValidacionError(f"El email '{email}' no tiene un formato válido.")
    return texto


def validar_estado_oferta(estado) -> str:
    estado_normalizado = normalizar_texto(estado or "")
    if estado_normalizado not in ESTADOS_OFERTA:
        raise ValidacionError(
            f"Estado '{estado}' inválido. Opciones: {', '.join(ESTADOS_OFERTA)}."
        )
    return estado_normalizado


# ---------------------------------------------------------------------------
# Validaciones de entidades completas
# ---------------------------------------------------------------------------

def validar_competencias(competencias) -> list[dict]:
    """Lista de {skill, nivel}. Al menos una, sin skills repetidas."""
    if not isinstance(competencias, list) or len(competencias) == 0:
        raise ValidacionError("El estudiante debe tener al menos una competencia.")

    resultado = []
    vistas = set()  # para detectar repetidas
    for comp in competencias:
        skill = normalizar_skill(validar_texto_obligatorio(comp.get("skill"), "skill"))
        nivel = validar_entero_en_rango(comp.get("nivel"), "nivel", NIVEL_MINIMO, NIVEL_MAXIMO)
        if skill in vistas:
            raise ValidacionError(f"La competencia '{skill}' está repetida.")
        vistas.add(skill)
        resultado.append({"skill": skill, "nivel": nivel})
    return resultado


def validar_estudiante(datos: dict) -> dict:
    """Valida y normaliza los datos de un estudiante (alta o modificación)."""
    return {
        "nombre": validar_texto_obligatorio(datos.get("nombre"), "nombre"),
        "email": validar_email(datos.get("email")),
        "carrera": validar_texto_obligatorio(datos.get("carrera"), "carrera"),
        "anio_cursada": validar_entero_en_rango(
            datos.get("anio_cursada"), "anio_cursada", ANIO_MINIMO, ANIO_MAXIMO
        ),
        "modalidad_preferida": normalizar_modalidad(
            validar_texto_obligatorio(datos.get("modalidad_preferida"), "modalidad_preferida")
        ),
        "competencias": validar_competencias(datos.get("competencias")),
    }


def validar_requisitos(requisitos) -> list[dict]:
    """Lista de {skill, nivel_minimo, tipo}. Al menos uno, sin skills repetidas."""
    if not isinstance(requisitos, list) or len(requisitos) == 0:
        raise ValidacionError("La oferta debe tener al menos un requisito.")

    resultado = []
    vistas = set()
    for req in requisitos:
        skill = normalizar_skill(validar_texto_obligatorio(req.get("skill"), "skill"))
        nivel_minimo = validar_entero_en_rango(
            req.get("nivel_minimo"), "nivel_minimo", NIVEL_MINIMO, NIVEL_MAXIMO
        )
        tipo = normalizar_texto(req.get("tipo") or "")
        if tipo not in TIPOS_REQUISITO:
            raise ValidacionError(
                f"Tipo de requisito '{req.get('tipo')}' inválido. "
                f"Opciones: {', '.join(TIPOS_REQUISITO)}."
            )
        if skill in vistas:
            raise ValidacionError(f"El requisito '{skill}' está repetido.")
        vistas.add(skill)
        resultado.append({"skill": skill, "nivel_minimo": nivel_minimo, "tipo": tipo})
    return resultado


def validar_oferta(datos: dict) -> dict:
    """Valida y normaliza los datos de una oferta laboral."""
    descripcion = datos.get("descripcion") or ""
    if not isinstance(descripcion, str):
        raise ValidacionError("El campo 'descripcion' debe ser texto.")

    return {
        "titulo": validar_texto_obligatorio(datos.get("titulo"), "titulo"),
        "empresa": validar_texto_obligatorio(datos.get("empresa"), "empresa"),
        "modalidad": normalizar_modalidad(
            validar_texto_obligatorio(datos.get("modalidad"), "modalidad")
        ),
        "descripcion": descripcion.strip(),
        "requisitos": validar_requisitos(datos.get("requisitos")),
    }
