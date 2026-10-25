# Bitácora de uso de IA en el desarrollo

> La consigna (sección 5) pide registrar las herramientas de IA usadas, las decisiones
> técnicas, las dificultades y las correcciones. Esta bitácora tiene dos partes:
> **(A)** lo registrado durante el desarrollo asistido, ya completo, y **(B)** una plantilla
> para que **cada integrante** agregue su propia experiencia.

## Herramientas utilizadas

| Herramienta | Uso | Dónde |
|---|---|---|
| **Claude Code** (asistente de programación, modelo Claude Opus) | Análisis de la consigna, diseño de arquitectura, generación y revisión de código, tests, Docker, workflows n8n y documentación | Todo el repositorio |
| **Ollama + llama3.2:3b** | IA **dentro del sistema**: genera recomendaciones de formación | `core/ia_service.py` |
| _(completar: ChatGPT, Copilot, Gemini, etc. si alguien los usó)_ | | |

**Forma de trabajo:** se le dio al asistente una guía con la consigna, el stack y las reglas
([CONSIGNA_PROYECTO.md](../CONSIGNA_PROYECTO.md)) y se trabajó **por fases**. Al cerrar cada
fase el asistente explicaba qué hizo y cómo verificarlo, y el equipo confirmaba antes de seguir.
Se pidió código simple y comentado en español para que todos puedan explicarlo en la defensa.

## (A) Registro por fase

### Fase 0 — Esqueleto
- **Hecho:** estructura de carpetas, `requirements.txt`, `.gitignore`, `.env.example`, `core/config.py`.
- **Decisión:** toda la configuración se lee de variables de entorno en un único módulo (`core/config.py`).
- **Dificultad:** Ollama estaba instalado pero sin modelos → se descargó `llama3.2:3b` (1.9 GB).

### Fase 1 — Núcleo Python
- **Hecho:** SQLite sin ORM, reglas de scoring, validaciones, excepciones, datos ficticios, 28 tests.
- **Decisiones:**
  - Deseable con nivel menor: suma puntos pero aparece en faltantes (para que la IA la recomiende).
  - Si una oferta no tiene obligatorias o deseables, el peso se redistribuye proporcionalmente.
  - Las skills se guardan normalizadas (minúsculas, sin tildes) para comparar sin errores.
  - Las funciones de alta validan antes de guardar, así cualquier camino (API, seed) queda protegido.
- **Verificación:** casos calculados a mano en los tests (ej. 45 + 25 + 15 = 85).

### Fase 2 — API FastAPI
- **Hecho:** 16 endpoints (el 17.º, generar con IA, se sumó en la Fase 4), manejador global de errores, 13 tests de API.
- **Decisión:** se agregaron `core/matching.py` y `core/reportes.py` para que los routers no tengan lógica.
- **Dificultad → corrección:** los errores de validación de Pydantic salían **en inglés**
  ("Input should be less than or equal to 6"). Se agregó una traducción de los tipos de error
  más comunes en `api/main.py`.

### Fase 3 — Interfaz Streamlit
- **Hecho:** 5 páginas, cliente HTTP único, mensajes de error por código.
- **Dificultades → correcciones:**
  - Al mostrar tablas con columnas que mezclaban números y texto ("no la tiene") Streamlit
    tiraba advertencias de conversión → se pasaron esas columnas a texto.
  - Con la API apagada aparecía el mismo error repetido en cada pestaña → se hizo que la app
    muestre **un solo** mensaje con instrucciones y se detenga.
  - La herramienta de pruebas de Streamlit (`AppTest`) no permite cargar filas en tablas
    editables → esa parte se probó por separado (la función que lee la tabla) y a mano.

### Fase 4 — Integración de IA
- **Hecho:** prompt, llamada a Ollama, validación Pydantic, reintento, advertencias de contenido, 12 tests con Ollama simulado.
- **Decisiones:**
  - El prompt **no** incluye nombre ni email (minimización de datos personales).
  - Además del formato se valida el **contenido**: si la IA habla de competencias que no
    faltaban, deja alguna sin cubrir o incluye enlaces, se agrega una advertencia para el revisor.
  - Si el resultado no tiene faltantes la API responde 409 (no hay nada que recomendar).
- **Pruebas con el modelo real (hallazgos):**
  - La primera llamada tardó ~50 s (carga del modelo); las siguientes entre 4 y 26 s.
  - La IA **inventó** un curso de una "Asociación Argentina de Comunicación" y sugirió
    Pluralsight (pago) aunque el prompt pedía recursos gratuitos y sin inventar.
  - Asignó prioridad "alta" a una competencia deseable, contra lo pedido.
  - Estos casos justifican la revisión humana obligatoria.
- **Ajuste:** el timeout de la interfaz (300 s) se dejó mayor que 2 intentos de la API (2 × 120 s).

### Fase 5 — Docker
- **Hecho:** Dockerfiles, `compose.yaml` con 4 servicios, red, volúmenes y healthcheck.
- **Decisiones:**
  - Dependencias separadas por imagen (`api/requirements.txt`, `ui/requirements.txt`): la API pesa 246 MB.
  - Versiones fijas de n8n (2.44.6) y Mailpit (v1.31.6), elegidas entre las estables recientes.
  - Healthcheck con Python porque `python:3.11-slim` no trae `curl`.
- **Dificultad:** en Git Bash (Windows) las rutas tipo `/workflows` se convierten en rutas de
  Windows al pasarlas a `docker exec` → se usó `MSYS_NO_PATHCONV=1`.

### Fase 6 — n8n
- **Hecho:** 3 workflows con condiciones IF, credencial SMTP sin secretos, script de importación.
- **Dificultades → correcciones:**
  - En n8n 2.x los workflows ya no se "activan": se **publican** (`n8n publish:workflow`) y hay
    que reiniciar n8n para que registre los webhooks.
  - Para que un error de la IA no corte el workflow 02 se combinó `neverError` (el HTTP no falla
    con 4xx/5xx) + `continueRegularOutput` (no falla con timeouts) + un IF sobre `statusCode`.
  - Para leer el historial de ejecuciones de n8n hubo que copiar también el archivo `-wal` de
    SQLite (las escrituras recientes todavía no estaban en el archivo principal).
  - Se agregó `.gitattributes` para que `importar.sh` mantenga fin de línea LF (en Windows Git
    puede convertirlo a CRLF y el script falla en Linux).
- **Verificación:** las 3 ramas del workflow 01 (201/400/422), el 02 con IA real, repetido
  (no duplica) y con IA caída simulada (registra 8 fallos y termina), y el 03 en ambas ramas.

### Fase 7 — Documentación
- README final, arquitectura con diagramas Mermaid, esta bitácora, responsabilidades y guion de demo.

## Qué NO hizo la IA / qué revisó el equipo

_(Completar por el equipo. Ejemplos de lo que conviene registrar:)_

- Partes que revisaron línea por línea antes de aceptar.
- Cambios que pidieron porque la primera propuesta no les convencía.
- Errores del asistente que detectaron ustedes.
- Partes que escribieron o modificaron a mano.

## (B) Registro individual

> Copiar este bloque una vez por integrante.

### Integrante: _Nombre Apellido_

| Fecha | Herramienta | Para qué la usé | Qué le pedí (resumen) | Qué cambié o corregí del resultado |
|---|---|---|---|---|
| | | | | |
| | | | | |

**Dificultad más importante que encontré y cómo la resolví:**

**Qué parte del sistema puedo explicar en detalle:**
