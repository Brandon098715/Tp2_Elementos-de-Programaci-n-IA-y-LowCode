"""
Cálculo del score de compatibilidad estudiante-oferta (REGLAS, no IA).

Score total 0-100 = suma de tres criterios:

| Criterio     | Peso | Cómo se calcula                                               |
|--------------|------|---------------------------------------------------------------|
| Obligatorias |  60  | cada una vale 1 si nivel >= mínimo, 0.5 si la tiene con nivel |
|              |      | menor, 0 si no la tiene. Se promedia.                         |
| Deseables    |  25  | cada una vale 1 si la tiene (cualquier nivel), 0 si no.       |
| Modalidad    |  15  | 15 si coincide, 7 si alguna de las dos es híbrida, 0 si no.   |

Redistribución: si la oferta NO tiene requisitos obligatorios (o deseables),
ese criterio "no aplica" y su peso se reparte proporcionalmente entre los que
sí aplican. Ejemplo sin obligatorias: deseables 25 y modalidad 15 suman 40,
se escalan a 100 -> deseables 62.5 y modalidad 37.5.

Faltantes: toda competencia requerida que el estudiante no tiene o tiene con
nivel menor al mínimo (tanto obligatorias como deseables). Una deseable con
nivel menor suma sus puntos igual, pero se informa como faltante para que la
IA pueda recomendar mejorarla.

Este módulo es puro: recibe diccionarios y devuelve diccionarios. No toca la
base de datos ni hace llamadas HTTP, por eso es fácil de testear.
"""

from core.validaciones import normalizar_skill, normalizar_modalidad

# --- Pesos de cada criterio (suman 100) ---
PESO_OBLIGATORIAS = 60
PESO_DESEABLES = 25
PESO_MODALIDAD = 15

# Puntos de modalidad cuando no coincide pero alguna es híbrida (sobre 15).
PUNTOS_MODALIDAD_HIBRIDA = 7

# --- Clasificación ---
LIMITE_ALTA = 75   # score >= 75 -> alta
LIMITE_MEDIA = 50  # 50 <= score < 75 -> media; menos -> baja


def clasificar(score: float) -> str:
    """Devuelve 'alta', 'media' o 'baja' según el score."""
    if score >= LIMITE_ALTA:
        return "alta"
    if score >= LIMITE_MEDIA:
        return "media"
    return "baja"


def cumplimiento_modalidad(modalidad_estudiante: str, modalidad_oferta: str) -> float:
    """Proporción (0 a 1) del criterio modalidad.

    Coincide -> 1.  Alguna es híbrida -> 7/15.  Distintas -> 0.
    """
    est = normalizar_modalidad(modalidad_estudiante)
    ofe = normalizar_modalidad(modalidad_oferta)
    if est == ofe:
        return 1.0
    if est == "hibrida" or ofe == "hibrida":
        return PUNTOS_MODALIDAD_HIBRIDA / PESO_MODALIDAD
    return 0.0


def calcular_score(estudiante: dict, oferta: dict) -> dict:
    """Compara un estudiante con una oferta y devuelve score, desglose y faltantes.

    estudiante: {"modalidad_preferida": str, "competencias": [{"skill", "nivel"}]}
    oferta:     {"modalidad": str, "requisitos": [{"skill", "nivel_minimo", "tipo"}]}

    Devuelve:
    {
        "score": 72.5,
        "clasificacion": "media",
        "origen": "reglas",
        "desglose": {"obligatorias": {...}, "deseables": {...}, "modalidad": {...}},
        "faltantes": [{"skill", "nivel_requerido", "nivel_actual", "tipo"}, ...]
    }
    """
    # Diccionario skill -> nivel del estudiante, para buscar rápido.
    niveles = {
        normalizar_skill(c["skill"]): c["nivel"] for c in estudiante["competencias"]
    }

    obligatorias = [r for r in oferta["requisitos"] if r["tipo"] == "obligatoria"]
    deseables = [r for r in oferta["requisitos"] if r["tipo"] == "deseable"]
    faltantes = []

    # --- 1) Obligatorias ---
    puntos_obligatorias = 0.0
    for req in obligatorias:
        skill = normalizar_skill(req["skill"])
        nivel_actual = niveles.get(skill, 0)  # 0 = no la tiene
        if nivel_actual >= req["nivel_minimo"]:
            puntos_obligatorias += 1
        else:
            if nivel_actual > 0:
                puntos_obligatorias += 0.5  # la tiene, pero con nivel menor
            faltantes.append(_faltante(skill, req, nivel_actual))

    # --- 2) Deseables ---
    puntos_deseables = 0.0
    for req in deseables:
        skill = normalizar_skill(req["skill"])
        nivel_actual = niveles.get(skill, 0)
        if nivel_actual > 0:
            puntos_deseables += 1  # cualquier nivel suma
        if nivel_actual < req["nivel_minimo"]:
            faltantes.append(_faltante(skill, req, nivel_actual))

    # --- 3) Modalidad ---
    prop_modalidad = cumplimiento_modalidad(
        estudiante["modalidad_preferida"], oferta["modalidad"]
    )

    # Proporción de cada criterio (None = no aplica porque no hay requisitos).
    prop_obligatorias = puntos_obligatorias / len(obligatorias) if obligatorias else None
    prop_deseables = puntos_deseables / len(deseables) if deseables else None

    criterios = {
        "obligatorias": (PESO_OBLIGATORIAS, prop_obligatorias, len(obligatorias)),
        "deseables": (PESO_DESEABLES, prop_deseables, len(deseables)),
        "modalidad": (PESO_MODALIDAD, prop_modalidad, None),
    }

    # Redistribución: escalamos los pesos de los criterios que aplican a 100.
    peso_que_aplica = sum(peso for peso, prop, _ in criterios.values() if prop is not None)
    factor = 100 / peso_que_aplica

    desglose = {}
    score = 0.0
    for nombre, (peso, proporcion, cantidad) in criterios.items():
        aplica = proporcion is not None
        peso_efectivo = peso * factor if aplica else 0.0
        puntos = peso_efectivo * proporcion if aplica else 0.0
        score += puntos
        desglose[nombre] = {
            "aplica": aplica,
            "peso_base": peso,
            "peso_efectivo": round(peso_efectivo, 2),
            "cumplimiento": round(proporcion, 3) if aplica else None,
            "puntos": round(puntos, 2),
        }
        if cantidad is not None:
            desglose[nombre]["cantidad_requisitos"] = cantidad

    score = round(score, 1)
    return {
        "score": score,
        "clasificacion": clasificar(score),
        "origen": "reglas",
        "desglose": desglose,
        "faltantes": faltantes,
    }


def _faltante(skill: str, req: dict, nivel_actual: int) -> dict:
    """Arma el registro de una competencia faltante."""
    return {
        "skill": skill,
        "nivel_requerido": req["nivel_minimo"],
        "nivel_actual": nivel_actual,
        "tipo": req["tipo"],
    }
