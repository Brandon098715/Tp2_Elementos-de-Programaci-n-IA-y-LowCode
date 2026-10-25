# TP2 — Plataforma de vinculación y desarrollo profesional

Trabajo Práctico 2 de **Elementos de Programación IA y LowCode** (2.º cuatrimestre 2026).

Sistema que vincula estudiantes/graduados con ofertas laborales:

1. Registra perfiles de estudiantes con competencias (skill + nivel 1–5).
2. Registra ofertas laborales con requisitos (obligatorios, deseables, nivel mínimo, modalidad).
3. Calcula un **score de compatibilidad (0–100) con reglas explícitas en Python**.
4. Identifica las **competencias faltantes**.
5. Usa **IA local (Ollama)** para recomendar formación a partir de las faltantes.
6. Un humano **aprueba o rechaza** cada recomendación de IA.
7. Automatiza con **n8n** el ingreso de ofertas, el matching + IA y los reportes.

> El sistema distingue siempre lo **calculado por reglas** (`origen: "reglas"`) de lo
> **generado por IA** (`origen: "ia"`, estado `pendiente_revision | aprobada | rechazada`).

> 🚧 README en construcción: se completa en la Fase 7.

## Componentes

| Componente | Tecnología | Puerto |
|---|---|---|
| Lógica de negocio | Python 3.11+ (`core/`) | — |
| API | FastAPI + Pydantic v2 + Uvicorn (`api/`) | 8000 |
| Interfaz | Streamlit (`ui/`), consume solo la API | 8501 |
| Automatización | n8n | 5678 |
| IA | Ollama (`llama3.2:3b`) en el host | 11434 |
| Persistencia | SQLite (`sqlite3` de la librería estándar) | — |
| Email de prueba | Mailpit | 1025 / 8025 |

## Estructura

```
api/        API FastAPI (routers, schemas)
core/       Lógica pura: config, base de datos, scoring, validaciones, IA
ui/         Interfaz Streamlit
n8n/        Workflows exportados en JSON
data/       Datos de ejemplo (seed.json) y base SQLite
scripts/    Utilidades (carga de datos de ejemplo)
tests/      Tests con pytest
docs/       Arquitectura, bitácora de IA, responsabilidades, consigna
```

## Requisitos

- Python 3.11 o superior
- Docker Desktop (para levantar todo con Compose)
- [Ollama](https://ollama.com) instalado en la máquina, con el modelo descargado:
  `ollama pull llama3.2:3b`

## Instalación para desarrollo (sin Docker)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

> Si PowerShell bloquea la activación del venv, ejecutar una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Datos de ejemplo

```bash
python scripts/seed.py           # carga 8 estudiantes y 5 ofertas ficticias
python scripts/seed.py --reset   # borra la base y la vuelve a crear
```

## Reglas de scoring (calculado por reglas, no por IA)

| Criterio | Peso | Cálculo |
|---|---|---|
| Competencias obligatorias | 60 | 1 si nivel ≥ mínimo, 0.5 si la tiene con nivel menor, 0 si no la tiene (promedio) |
| Competencias deseables | 25 | 1 si la tiene (cualquier nivel), 0 si no (promedio) |
| Modalidad | 15 | 15 si coincide, 7 si alguna es híbrida, 0 si no coincide |

- Si la oferta no tiene obligatorias (o deseables), ese peso se reparte
  proporcionalmente entre los demás criterios (ej.: sin obligatorias → deseables 62.5 y modalidad 37.5).
- Clasificación: **alta** ≥ 75, **media** 50–74.9, **baja** < 50.
- Faltantes: competencias requeridas que no tiene o con nivel menor al mínimo.
  Una deseable con nivel menor suma puntos, pero se informa como faltante.
- Las skills se comparan normalizadas: minúsculas, sin tildes, sin espacios extra.

Código: [core/scoring.py](core/scoring.py) · Tests: [tests/test_scoring.py](tests/test_scoring.py)

## Integración de IA

**Qué hace:** a partir de las competencias faltantes **ya calculadas por reglas**,
un modelo de lenguaje redacta recomendaciones de formación y mejoras del perfil.
La IA **no** calcula ni modifica el score.

**Flujo** ([core/ia_service.py](core/ia_service.py)):

1. Se arma un prompt en español con carrera, año, competencias, la oferta y las faltantes.
   No se envían nombre ni email (no hacen falta: minimización de datos).
2. `POST {OLLAMA_URL}/api/generate` con `format: "json"`, `stream: false`, `temperature: 0.3`.
3. La respuesta se valida con Pydantic (`resumen`, `recomendaciones[]`, `mejoras_perfil[]`).
   Si no es válida se **reintenta 1 vez**; si vuelve a fallar → **502**.
4. Se revisa el contenido y se agregan **advertencias** para el revisor: competencias
   recomendadas que no estaban entre las faltantes, faltantes sin recomendación y enlaces
   (posiblemente inventados).
5. Se guarda con `origen: "ia"` y `estado: "pendiente_revision"`. Solo una persona la
   pasa a `aprobada` o `rechazada` (`PATCH /recomendaciones/{id}/revision`).

Si Ollama está apagado, el modelo no está instalado o no responde a tiempo → **503**
"Servicio de IA no disponible". El resto del sistema sigue funcionando.

**Por qué Ollama + `llama3.2:3b`:**

- Gratuito y local: no requiere cuentas, claves ni pagos.
- Los datos de los estudiantes no salen de la máquina (no se envían a terceros).
- Modelo chico (~2 GB): corre en una notebook sin GPU dedicada.
- Soporta salida en formato JSON, que podemos validar automáticamente.
- El modelo se cambia con la variable `OLLAMA_MODEL` del `.env`.

**Límites conocidos (por eso hay revisión humana):**

- Puede **inventar** cursos, instituciones o URLs. En nuestras pruebas sugirió un curso
  de una asociación inexistente y una plataforma paga.
- Calidad variable: a veces genera recomendaciones genéricas o no respeta la prioridad pedida.
- A veces la respuesta no cumple el formato → se reintenta y, si falla, se informa el error.
- La primera llamada tarda más (~30-60 s) porque Ollama carga el modelo en memoria;
  las siguientes, unos segundos.

## Ejecución

### API (FastAPI)

```bash
uvicorn api.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Estado de API, base y Ollama |
| POST / GET | `/estudiantes` | Crear / listar (filtros `skill`, `carrera`) |
| GET / PUT / DELETE | `/estudiantes/{id}` | Detalle / actualizar / eliminar |
| POST / GET | `/ofertas` | Crear / listar (filtro `estado`) |
| GET | `/ofertas/{id}` | Detalle |
| PATCH | `/ofertas/{id}/estado` | Abrir o cerrar |
| POST | `/matching/ofertas/{oferta_id}` | Calcular ranking (reglas) y guardarlo |
| GET | `/matching/resultados` | Consultar (filtros `oferta_id`, `estudiante_id`, `min_score`) |
| POST | `/recomendaciones/{resultado_id}` | Generar recomendación con IA (queda `pendiente_revision`) |
| GET | `/recomendaciones` | Listar (filtro `estado`) |
| PATCH | `/recomendaciones/{id}/revision` | Aprobar / rechazar (supervisión humana) |
| GET | `/reportes/resumen` | Indicadores generales |

Errores: todas las respuestas de error tienen la forma `{"detalle": "..."}`.
422 = dato inválido · 404 = no existe · 409 = duplicado o estado no permitido ·
503 = IA no disponible · 502 = respuesta de IA inválida.

### Interfaz (Streamlit)

Con la API corriendo, en otra terminal:

```bash
streamlit run ui/app.py
```

Se abre en http://localhost:8501. Secciones:

| Sección | Qué permite |
|---|---|
| 👩‍🎓 Estudiantes | Listado con filtros, alta con competencias dinámicas, edición y eliminación |
| 💼 Ofertas | Listado, alta con requisitos obligatorios/deseables, abrir/cerrar |
| 📊 Matching | Calcular el ranking de una oferta, ver score, clasificación por colores, desglose y faltantes — **"Calculado por reglas"** |
| 🤖 Recomendaciones IA | Ver lo generado por la IA y aprobar/rechazar con comentario — **"Generado por IA — requiere revisión"** |
| 📈 Reportes | Métricas y gráficos: score promedio, competencias más faltantes, pendientes |

La barra lateral muestra el estado de `/health` (API, base, Ollama). La interfaz
**solo** se comunica con la API ([ui/api_client.py](ui/api_client.py)); si la API
está apagada, muestra un mensaje con instrucciones en lugar de fallar.

## Ejecución con Docker Compose (todo junto)

Requisitos: Docker Desktop abierto y Ollama corriendo en la máquina con el modelo
descargado (`ollama pull llama3.2:3b`). Ollama **no** corre en Docker.

```bash
docker compose up -d --build     # construir e iniciar todo en segundo plano
docker compose ps                # estado de los servicios
docker compose logs -f api       # logs de un servicio (api, ui, n8n, mailpit)
docker compose restart api       # reiniciar un servicio
docker compose stop              # detener sin borrar los contenedores
docker compose down              # detener y borrar los contenedores (los datos se conservan)
docker compose down -v           # además borra el volumen de n8n (workflows y credenciales)
```

Si es la primera vez, cargar los datos de ejemplo dentro del contenedor:

```bash
docker compose exec api python scripts/seed.py --reset
```

### Servicios y puertos

| Servicio | Contenedor | URL desde tu navegador | Nombre dentro de Docker |
|---|---|---|---|
| API FastAPI | `vinculacion-api` | http://localhost:8000/docs | `http://api:8000` |
| Interfaz Streamlit | `vinculacion-ui` | http://localhost:8501 | `http://ui:8501` |
| n8n | `vinculacion-n8n` | http://localhost:5678 | `http://n8n:5678` |
| Mailpit (bandeja web) | `vinculacion-mailpit` | http://localhost:8025 | — |
| Mailpit (SMTP) | `vinculacion-mailpit` | — | `mailpit:1025` |
| Ollama (en el host) | — | http://localhost:11434 | `http://host.docker.internal:11434` |

### Cómo se comunican

- Los 4 contenedores están en la misma red de Docker (`vinculacion`) y se llaman por
  el **nombre del servicio**: la interfaz usa `http://api:8000`, n8n también.
- La API llega a Ollama (que corre fuera de Docker) con `host.docker.internal`.
  En Linux esto funciona gracias a `extra_hosts: host-gateway` y Ollama debe
  escuchar en todas las interfaces (`OLLAMA_HOST=0.0.0.0`).
- La base SQLite está en la carpeta `data/` del proyecto, montada en el contenedor
  (`./data:/app/data`): los datos sobreviven a `docker compose down`.
- n8n guarda sus workflows y credenciales en el volumen `n8n_data`.
- `ui` y `n8n` esperan a que la API esté sana (`healthcheck` sobre `/health`) antes de arrancar.

### Configuración

[compose.yaml](compose.yaml) toma de `.env` (si existe) `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` y
`UMBRAL_IA`. Las URLs internas (`API_URL`, `OLLAMA_URL`) se fijan en el compose porque
dentro de Docker son distintas que al correr sin Docker.

| Archivo | Para qué |
|---|---|
| [api/Dockerfile](api/Dockerfile) | Imagen de la API (`python:3.11-slim` + `core/` + `api/`) |
| [ui/Dockerfile](ui/Dockerfile) | Imagen de la interfaz (`python:3.11-slim` + `ui/`) |
| [compose.yaml](compose.yaml) | Define los 4 servicios, red, volúmenes y healthcheck |
| [.dockerignore](.dockerignore) | Excluye `.venv`, `.env`, la base y los tests de las imágenes |

> Sin Docker y con Docker se usa la **misma** base (`data/vinculacion.db`). No conviene
> correr las dos formas a la vez porque ocupan los mismos puertos (8000 y 8501).

## Automatización con n8n

Tres workflows en [n8n/workflows/](n8n/workflows/), todos integrados con la API
(`http://api:8000`, leída de la variable `API_URL`) y cada uno con al menos una condición IF:

| Workflow | Disparador | Qué hace | Condiciones |
|---|---|---|---|
| **01 · Ingreso de ofertas** | `POST /webhook/nueva-oferta` | Normaliza la oferta, la crea (`POST /ofertas`), calcula el matching y responde con el top 5 | ¿Datos completos? → 400 · ¿La API la aceptó? → 422 |
| **02 · Matching + IA** | Cada 15 min o `POST /webhook/procesar-ia` | Recorre los resultados con score ≥ `UMBRAL_IA` y genera recomendación IA a los que no tienen | ¿Necesita recomendación? · ¿Respuesta OK? (si falla, registra el error y sigue) |
| **03 · Reporte y notificaciones** | Diario 9:00 o `GET /webhook/reporte-diario` | Consulta `/reportes/resumen` y envía un email (Mailpit) | ¿Hay pendientes? → email al revisor / informe "sin pendientes" a coordinación |

### Importar los workflows (una sola vez)

Con los contenedores levantados:

```bash
docker compose exec n8n sh /import/importar.sh   # importa credencial SMTP + 3 workflows y los publica
docker compose restart n8n                        # n8n toma los workflows publicados
```

Después abrir http://localhost:5678. La primera vez n8n pide crear una cuenta de
propietario (es **local**, no se envía a ningún lado). Los workflows aparecen publicados.

> La credencial SMTP ([n8n/credentials/smtp_mailpit.json](n8n/credentials/smtp_mailpit.json))
> no tiene usuario ni contraseña: Mailpit es un servidor de correo **falso** para pruebas.

### Probarlos

```bash
# 01 — ingreso de una oferta (válida)
curl -X POST http://localhost:5678/webhook/nueva-oferta -H "Content-Type: application/json" \
  -d '{"titulo":"Data Engineer Jr","empresa":"Ficticia Cloud","modalidad":"remota","requisitos":[{"skill":"python","nivel_minimo":3,"tipo":"obligatoria"},{"skill":"docker","nivel_minimo":1,"tipo":"deseable"}]}'

# 01 — oferta incompleta (responde 400 con la lista de errores)
curl -X POST http://localhost:5678/webhook/nueva-oferta -H "Content-Type: application/json" -d '{"titulo":"Sin empresa"}'

# 02 — procesar recomendaciones con IA ahora (responde al instante y sigue en segundo plano)
curl -X POST http://localhost:5678/webhook/procesar-ia

# 03 — enviar el reporte ahora; ver el email en http://localhost:8025
curl http://localhost:5678/webhook/reporte-diario
```

En PowerShell usar `curl.exe` en lugar de `curl`. El detalle de cada ejecución se ve en
n8n → **Executions**.

### Si la importación automática falla

1. En n8n: **Credentials → Add credential → SMTP**: Host `mailpit`, Port `1025`, User y
   Password vacíos, SSL/TLS desactivado, "Disable STARTTLS" activado. Nombre: `SMTP Mailpit (pruebas)`.
2. **Workflows → Import from File** y elegir cada JSON de `n8n/workflows/`.
3. En los nodos de email del workflow 03, seleccionar la credencial creada.
4. Abrir cada workflow y tocar **Publish**.

## Tests

```bash
pytest
```
