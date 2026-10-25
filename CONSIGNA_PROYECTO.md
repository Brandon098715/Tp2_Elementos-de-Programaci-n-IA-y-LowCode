# Consigna del proyecto — TP2 "Elementos de Programación IA y LowCode"

> Guía de trabajo para el desarrollo asistido por IA. La consigna oficial está en `docs/consigna_tp2.pdf`.

## ROL Y CONTEXTO

Sos un desarrollador senior que me ayuda a construir un trabajo práctico universitario. El equipo es de estudiantes y **cada integrante debe poder explicar y modificar cualquier parte del código en una defensa oral**. Por eso:

- Priorizá código **simple, legible y bien comentado en español** por sobre soluciones "ingeniosas".
- Nada de abstracciones innecesarias, metaprogramación ni librerías exóticas.
- Al terminar cada fase, explicame en pocas líneas **qué hiciste, qué archivos tocaste y cómo verificarlo**.
- Trabajá **por fases**. No avances a la siguiente fase sin mi confirmación.
- Sugerime mensajes de commit al final de cada fase (formato: `feat: ...`, `fix: ...`, `docs: ...`).

## EL PROYECTO

**Proyecto A — Plataforma de vinculación y desarrollo profesional.**
Una aplicación que vincula estudiantes/graduados con ofertas laborales:

1. Registrar perfiles de estudiantes con competencias (skill + nivel 1–5).
2. Registrar ofertas laborales con requisitos (competencias obligatorias, deseables, nivel mínimo, modalidad).
3. Comparar perfil vs. oferta y calcular un **score de compatibilidad (0–100) con reglas explícitas en Python**.
4. Identificar **competencias faltantes**.
5. Usar **IA** para generar recomendaciones de formación/mejora del perfil a partir de las competencias faltantes.
6. Un humano **revisa y aprueba/rechaza** cada recomendación de IA antes de que se considere válida.
7. Automatizar con **n8n** el ingreso de ofertas, el procesamiento de matching + IA y los reportes/notificaciones.

**Regla clave:** el sistema debe distinguir SIEMPRE en datos, API e interfaz lo **calculado por reglas** (`origen: "reglas"`) de lo **generado por IA** (`origen: "ia"`, con estado `pendiente_revision | aprobada | rechazada`).

## STACK OBLIGATORIO

| Componente | Tecnología | Puerto |
|---|---|---|
| Lógica de negocio | Python 3.11+ (módulos y funciones reutilizables) | — |
| API | FastAPI + Pydantic v2 + Uvicorn | 8000 |
| Interfaz | Streamlit (consume SOLO la API, nunca la base directamente) | 8501 |
| Automatización | n8n (imagen oficial `n8nio/n8n`) | 5678 |
| IA | Ollama local, modelo `llama3.2:3b` (configurable por `.env`) | 11434 (en el host) |
| Persistencia | SQLite con `sqlite3` de la librería estándar (sin ORM) | — |
| Email de prueba | Mailpit (`axllent/mailpit`) como SMTP falso, sin credenciales reales | 1025 / 8025 |
| Contenedores | Docker Compose con servicios `api`, `ui`, `n8n`, `mailpit` | — |
| Tests | pytest + `httpx`/`TestClient` | — |

- Ollama corre **en el host**, no en Docker. Desde los contenedores se accede con `http://host.docker.internal:11434` (agregar `extra_hosts: ["host.docker.internal:host-gateway"]` para que funcione en Linux).
- Toda configuración (URLs, modelo, umbral de score, ruta de la DB) va en variables de entorno leídas desde `.env`. Incluir `.env.example`. **Nunca** subir secretos.

## ESTRUCTURA DE CARPETAS ESPERADA

```
├── api/
│   ├── main.py              # crea la app FastAPI y registra routers
│   ├── routers/             # estudiantes.py, ofertas.py, matching.py, recomendaciones.py, reportes.py
│   ├── schemas.py           # modelos Pydantic (entrada/salida)
│   └── Dockerfile
├── core/                    # lógica pura en Python, SIN FastAPI ni Streamlit
│   ├── config.py            # lee variables de entorno
│   ├── database.py          # conexión SQLite, creación de tablas, funciones CRUD
│   ├── scoring.py           # cálculo del score y competencias faltantes
│   ├── validaciones.py      # normalización de skills, validaciones de negocio
│   ├── ia_service.py        # cliente de Ollama + prompt + parseo/validación de la respuesta
│   └── excepciones.py       # excepciones propias (NoEncontradoError, DuplicadoError, IAError...)
├── ui/
│   ├── app.py               # Streamlit (multipágina o con pestañas)
│   ├── api_client.py        # todas las llamadas HTTP a la API, con manejo de errores
│   └── Dockerfile
├── n8n/workflows/           # 01_ingreso_ofertas.json, 02_matching_ia.json, 03_reporte_notificaciones.json
├── data/
│   └── seed.json            # datos ficticios: 8 estudiantes, 5 ofertas
├── scripts/seed.py          # carga seed.json en la base
├── tests/                   # test_scoring.py, test_api.py
├── docs/
│   ├── arquitectura.md      # diagrama Mermaid + explicación de comunicación y puertos
│   ├── bitacora_ia.md       # herramientas IA usadas, decisiones, dificultades, correcciones
│   ├── responsabilidades.md # qué hizo cada integrante
│   └── consigna_tp2.pdf
├── compose.yaml
├── requirements.txt
├── .env.example
├── .gitignore               # .env, *.db, __pycache__, .venv, n8n_data/
└── README.md
```

## MODELO DE DATOS (SQLite)

- `estudiantes(id, nombre, email UNIQUE, carrera, anio_cursada, modalidad_preferida, creado_en, actualizado_en)`
- `competencias_estudiante(id, estudiante_id FK, skill, nivel 1-5)`
- `ofertas(id, titulo, empresa, modalidad, descripcion, estado: abierta|cerrada, creado_en)`
- `requisitos_oferta(id, oferta_id FK, skill, nivel_minimo 1-5, tipo: obligatoria|deseable)`
- `resultados_matching(id, estudiante_id, oferta_id, score, detalle_json, faltantes_json, origen='reglas', calculado_en)` — UNIQUE(estudiante_id, oferta_id); recalcular actualiza.
- `recomendaciones_ia(id, resultado_id FK, texto_json, modelo, origen='ia', estado: pendiente_revision|aprobada|rechazada, comentario_revisor, creado_en, revisado_en)`

Las skills se normalizan (minúsculas, sin espacios extra, sin tildes) para comparar.

## REGLAS DE SCORING (core/scoring.py)

Score total 0–100 = suma ponderada:

| Criterio | Peso | Cálculo |
|---|---|---|
| Competencias obligatorias | 60 | proporción de obligatorias que el estudiante tiene con nivel ≥ mínimo; si la tiene con nivel menor, cuenta la mitad |
| Competencias deseables | 25 | proporción de deseables que tiene (cualquier nivel) |
| Modalidad | 15 | 15 si coincide, 7 si alguna es "híbrida", 0 si no coincide |

- `faltantes`: lista de `{skill, nivel_requerido, nivel_actual, tipo}` para lo que falta o no alcanza el nivel.
- Clasificación: `alta` (≥75), `media` (50–74), `baja` (<50). Umbral para disparar IA configurable (`UMBRAL_IA`, por defecto 50).
- La función devuelve también el **desglose por criterio** para mostrarlo en la UI.
- Si la oferta no tiene obligatorias, ese peso se redistribuye proporcionalmente (documentarlo).

## INTEGRACIÓN DE IA (core/ia_service.py)

- Llamar a Ollama vía HTTP (`POST {OLLAMA_URL}/api/generate`, `format: "json"`, `stream: false`, timeout configurable).
- Prompt en español que reciba: perfil, oferta y competencias faltantes **ya calculadas por reglas** (la IA no calcula el score).
- Pedir salida JSON con esta forma y **validarla con Pydantic**:
  ```json
  {"resumen": "...", "recomendaciones": [{"competencia": "...", "accion": "...", "recurso_sugerido": "...", "prioridad": "alta|media|baja"}], "mejoras_perfil": ["..."]}
  ```
- Si la respuesta no es JSON válido: reintentar 1 vez; si vuelve a fallar → `IAError`, la API responde 502 con mensaje claro.
- Si Ollama no está disponible → 503 con mensaje "Servicio de IA no disponible", sin romper el resto del sistema.
- Toda recomendación se guarda con `estado = pendiente_revision`. Solo un humano la cambia.
- Documentar en el README la justificación del modelo (gratuito, local, sin enviar datos a terceros) y sus límites (alucinaciones, recursos inventados, calidad variable → por eso hay revisión humana).

## ENDPOINTS FASTAPI

| Método | Ruta | Función | Errores |
|---|---|---|---|
| GET | `/health` | estado de API, DB y Ollama | — |
| POST | `/estudiantes` | crear perfil con competencias | 422, 409 email duplicado |
| GET | `/estudiantes` | listar con filtros (`skill`, `carrera`) | — |
| GET | `/estudiantes/{id}` | detalle | 404 |
| PUT | `/estudiantes/{id}` | actualizar perfil/competencias | 404, 422 |
| DELETE | `/estudiantes/{id}` | eliminar | 404 |
| POST | `/ofertas` | crear oferta con requisitos | 422 |
| GET | `/ofertas` | listar (filtro `estado`) | — |
| PATCH | `/ofertas/{id}/estado` | abrir/cerrar oferta | 404, 422 |
| POST | `/matching/ofertas/{oferta_id}` | calcular score de todos los estudiantes, persistir y devolver ranking | 404, 409 si está cerrada |
| GET | `/matching/resultados` | consultar resultados (filtros `oferta_id`, `estudiante_id`, `min_score`) | — |
| POST | `/recomendaciones/{resultado_id}` | generar recomendación IA | 404, 503 IA caída, 502 respuesta inválida |
| GET | `/recomendaciones` | listar (filtro `estado`) | — |
| PATCH | `/recomendaciones/{id}/revision` | aprobar/rechazar con comentario | 404, 422, 409 si ya fue revisada |
| GET | `/reportes/resumen` | totales, score promedio por oferta, competencias más faltantes, pendientes | — |

- JSON en entrada y salida, códigos HTTP correctos (201 al crear, 204 al borrar, etc.).
- Manejadores de excepciones globales que conviertan las excepciones de `core/` en respuestas `{"detalle": "..."}`.
- Documentación automática en `/docs` con descripciones y ejemplos.
- Los routers solo validan y delegan: **la lógica vive en `core/`**.

## INTERFAZ STREAMLIT

1. **Estudiantes:** alta (competencias dinámicas), tabla con filtros, edición.
2. **Ofertas:** alta con requisitos, listado, cerrar oferta.
3. **Matching:** elegir oferta → calcular → ranking con score, colores, desglose y faltantes. Etiqueta **"Calculado por reglas"**.
4. **Recomendaciones IA:** generar, ver JSON formateado, etiqueta **"Generado por IA — requiere revisión"**, Aprobar/Rechazar con comentario.
5. **Reportes:** `st.metric`, `st.bar_chart`.
6. Indicador en la barra lateral del estado de `/health`.

- Todas las llamadas pasan por `ui/api_client.py`, con manejo de `ConnectionError`, timeouts y 4xx/5xx con mensajes comprensibles.
- URL de la API por variable de entorno (`API_URL`, en Docker `http://api:8000`).

## WORKFLOWS N8N (3, cada uno con al menos un IF/Switch)

1. **01_ingreso_ofertas** — Webhook `POST /webhook/nueva-oferta` → normaliza → IF datos completos y ≥1 requisito → (sí) `POST /ofertas` → `POST /matching/ofertas/{id}` → responde 201 con ranking / (no) responde 400.
2. **02_matching_ia** — Schedule o Webhook → `GET /matching/resultados?min_score=UMBRAL` → Loop → IF sin recomendación → `POST /recomendaciones/{id}` → IF OK → registrar / (error) registrar fallo sin cortar.
3. **03_reporte_notificaciones** — Schedule diario → `GET /reportes/resumen` → IF pendientes > 0 → email a Mailpit (`mailpit:1025`) / (no) nada o "sin pendientes".

- JSON importable en `n8n/workflows/`, con URLs internas (`http://api:8000`).
- Documentar en `docs/arquitectura.md` qué hace cada workflow.

## DOCKER

- `api/Dockerfile` y `ui/Dockerfile` con `python:3.11-slim`.
- `compose.yaml` con `api`, `ui`, `n8n`, `mailpit`; red común; volúmenes `./data` y `n8n_data`; `depends_on` y `healthcheck`; variables desde `.env`.
- README: iniciar, logs, detener, reiniciar servicio, puertos, comunicación.
- También debe correr **sin Docker** (venv + uvicorn + streamlit).

## VERIFICACIÓN

- `tests/test_scoring.py`: perfecto, cero, nivel insuficiente, sin obligatorias, modalidad.
- `tests/test_api.py`: crear, consultar, 404, 422, 409, matching, revisión. Mockear Ollama.
- README: **"Guion de demostración"** con proceso completo y ≥3 casos de error.

## FASES

- **Fase 0 — Esqueleto**
- **Fase 1 — Núcleo Python**
- **Fase 2 — API FastAPI**
- **Fase 3 — Streamlit**
- **Fase 4 — IA**
- **Fase 5 — Docker**
- **Fase 6 — n8n**
- **Fase 7 — Documentación**

## RESTRICCIONES

- Sin servicios pagos. Sin credenciales reales en el repo. Datos ficticios.
- Sin ORM ni frameworks frontend adicionales.
- Ante ambigüedades, preguntar antes de decidir.
- Si un comando falla, explicar la causa probable antes de cambiar de enfoque.
