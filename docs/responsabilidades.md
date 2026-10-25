# Responsabilidades del equipo

> Completar con los nombres reales. La consigna pide una breve descripción de lo que hizo
> cada integrante, y en la defensa **todos** deben poder explicar y modificar cualquier parte.
> Abajo hay una división sugerida por componente; ajústenla a lo que realmente hizo cada uno.

## Integrantes

| Integrante | Rol principal | Componentes | Archivos principales |
|---|---|---|---|
| _Nombre 1_ | Lógica de negocio y datos | Scoring, validaciones, base de datos, datos de ejemplo | `core/scoring.py`, `core/validaciones.py`, `core/database.py`, `data/seed.json`, `tests/test_scoring.py` |
| _Nombre 2_ | API | Endpoints, modelos Pydantic, manejo de errores | `api/`, `core/matching.py`, `core/reportes.py`, `tests/test_api.py` |
| _Nombre 3_ | Interfaz e IA | Streamlit, integración con Ollama, revisión humana | `ui/`, `core/ia_service.py`, `tests/test_ia.py` |
| _Nombre 4_ | Automatización e infraestructura | n8n, Docker, documentación | `n8n/`, `compose.yaml`, `*/Dockerfile`, `docs/` |

## Detalle por integrante

### _Nombre 1_
- **Qué hizo:**
- **Decisiones que tomó:**
- **Dificultades que resolvió:**
- **Commits principales:** _(hash o mensaje)_

### _Nombre 2_
- **Qué hizo:**
- **Decisiones que tomó:**
- **Dificultades que resolvió:**
- **Commits principales:**

### _Nombre 3_
- **Qué hizo:**
- **Decisiones que tomó:**
- **Dificultades que resolvió:**
- **Commits principales:**

### _Nombre 4_
- **Qué hizo:**
- **Decisiones que tomó:**
- **Dificultades que resolvió:**
- **Commits principales:**

## Preparación de la defensa

Cada integrante marca lo que ya puede explicar y modificar sin ayuda:

| Tema | _Nombre 1_ | _Nombre 2_ | _Nombre 3_ | _Nombre 4_ |
|---|---|---|---|---|
| Cálculo del score y faltantes (`core/scoring.py`) | ☐ | ☐ | ☐ | ☐ |
| Tablas y consultas SQL (`core/database.py`) | ☐ | ☐ | ☐ | ☐ |
| Endpoints y códigos de error (`api/`) | ☐ | ☐ | ☐ | ☐ |
| Cómo la interfaz llama a la API (`ui/api_client.py`) | ☐ | ☐ | ☐ | ☐ |
| Prompt, validación y reintento de la IA (`core/ia_service.py`) | ☐ | ☐ | ☐ | ☐ |
| Los 3 workflows de n8n (nodos, entradas, salidas, condiciones) | ☐ | ☐ | ☐ | ☐ |
| Docker Compose: servicios, red, volúmenes, puertos | ☐ | ☐ | ☐ | ☐ |
| Correr el guion de demostración completo | ☐ | ☐ | ☐ | ☐ |

**Ejercicios de práctica** (el docente puede pedir una modificación acotada):

1. Cambiar el peso de modalidad de 15 a 20 y ajustar los demás para que sumen 100. ¿Qué tests fallan y por qué?
2. Agregar el filtro `empresa` a `GET /ofertas`.
3. Hacer que rechazar una recomendación exija un comentario (422 si viene vacío).
4. En el workflow 02, cambiar el intervalo a 5 minutos y el umbral a 70.
5. Mostrar en la página de Matching cuántos estudiantes quedaron en cada clasificación.
