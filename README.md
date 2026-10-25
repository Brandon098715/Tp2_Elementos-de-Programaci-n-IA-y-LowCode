# TP2 — Plataforma de vinculación y desarrollo profesional

Trabajo Práctico 2 · **Elementos de Programación IA y LowCode** · 2.º cuatrimestre 2026 · Proyecto A

Sistema que vincula estudiantes y graduados con ofertas laborales. Calcula qué tan
compatible es cada perfil con cada oferta **usando reglas explícitas en Python**, detecta
las competencias que faltan y usa **IA local** para recomendar cómo mejorar el perfil.
Una persona revisa cada recomendación antes de darla por válida, y **n8n** automatiza
el ingreso de ofertas, el procesamiento con IA y los reportes por email.

> **Regla central:** el sistema distingue siempre lo **calculado por reglas**
> (`origen: "reglas"`) de lo **generado por IA** (`origen: "ia"`, con estado
> `pendiente_revision | aprobada | rechazada`), en la base, en la API y en la interfaz.

## Índice

1. [Proceso que resuelve](#proceso-que-resuelve)
2. [Componentes](#componentes)
3. [Requisitos](#requisitos)
4. [Inicio rápido con Docker](#inicio-rápido-con-docker)
5. [Ejecución sin Docker](#ejecución-sin-docker-desarrollo)
6. [Reglas de scoring](#reglas-de-scoring)
7. [Integración de IA](#integración-de-ia)
8. [API](#api-fastapi)
9. [Interfaz](#interfaz-streamlit)
10. [Workflows n8n](#workflows-n8n)
11. [Docker en detalle](#docker-en-detalle)
12. [Verificación y tests](#verificación-y-tests)
13. [Guion de demostración](#guion-de-demostración)
14. [Problemas frecuentes](#problemas-frecuentes)
15. [Estructura del repositorio](#estructura-del-repositorio)

Documentación complementaria: [arquitectura](docs/arquitectura.md) ·
[bitácora de IA](docs/bitacora_ia.md) · [responsabilidades](docs/responsabilidades.md)

---

## Proceso que resuelve

```
Ingreso de datos ─► Validación ─► Matching por reglas ─► Faltantes ─► Recomendación IA ─► Revisión humana ─► Reportes
 (UI o n8n)        (Pydantic +     (score 0-100,          (skill,      (Ollama local,      (aprobar /          (UI y email
                    core/)          desglose)              nivel)       JSON validado)       rechazar)           con n8n)
```

1. **Registrar** estudiantes con competencias (skill + nivel 1–5) y ofertas con requisitos
   obligatorios/deseables, nivel mínimo y modalidad.
2. **Calcular** el score de compatibilidad 0–100 de todos los estudiantes contra una oferta.
3. **Identificar** las competencias faltantes de cada estudiante.
4. **Generar con IA** recomendaciones de formación a partir de esas faltantes.
5. **Revisar**: una persona aprueba o rechaza cada recomendación con un comentario.
6. **Consultar** resultados, indicadores y recibir avisos de pendientes por email.

## Componentes

| Componente | Tecnología | Puerto | Carpeta |
|---|---|---|---|
| Lógica de negocio | Python 3.11+ (módulos puros, sin FastAPI ni Streamlit) | — | [core/](core/) |
| API | FastAPI + Pydantic v2 + Uvicorn | 8000 | [api/](api/) |
| Interfaz | Streamlit (consume **solo** la API) | 8501 | [ui/](ui/) |
| Automatización | n8n 2.44 | 5678 | [n8n/](n8n/) |
| IA | Ollama con `llama3.2:3b`, corre en la máquina (host) | 11434 | [core/ia_service.py](core/ia_service.py) |
| Persistencia | SQLite con `sqlite3` de la librería estándar (sin ORM) | — | `data/vinculacion.db` |
| Email de prueba | Mailpit (servidor SMTP falso, sin credenciales) | 1025 / 8025 | — |
| Contenedores | Docker Compose: `api`, `ui`, `n8n`, `mailpit` | — | [compose.yaml](compose.yaml) |

Diagrama y explicación de la comunicación entre componentes: [docs/arquitectura.md](docs/arquitectura.md).

## Requisitos

- **Docker Desktop** (o Docker Engine + Compose v2).
- **Ollama** instalado en la máquina ([ollama.com](https://ollama.com)) con el modelo descargado:
  ```bash
  ollama pull llama3.2:3b
  ```
- **Python 3.11+** solo si se quiere correr sin Docker o ejecutar los tests.

No se necesitan cuentas, claves ni servicios pagos.

## Inicio rápido con Docker

```bash
# 1. Configuración (opcional: sin .env se usan los valores por defecto)
cp .env.example .env                       # Windows: copy .env.example .env

# 2. Levantar todo
docker compose up -d --build

# 3. Cargar los datos de ejemplo (8 estudiantes y 5 ofertas ficticias)
docker compose exec api python scripts/seed.py --reset

# 4. Importar y publicar los workflows de n8n (una sola vez)
docker compose exec n8n sh /import/importar.sh
docker compose restart n8n
```

| Qué | Dónde |
|---|---|
| Interfaz | http://localhost:8501 |
| API (documentación interactiva) | http://localhost:8000/docs |
| n8n | http://localhost:5678 (la primera vez pide crear una cuenta **local**) |
| Bandeja de emails (Mailpit) | http://localhost:8025 |

Detener: `docker compose down` (los datos se conservan).

## Ejecución sin Docker (desarrollo)

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # si lo bloquea: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env
python scripts/seed.py --reset
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed.py --reset
```

Luego, en dos terminales (con el venv activado):

```bash
uvicorn api.main:app --reload        # API en http://localhost:8000
streamlit run ui/app.py              # Interfaz en http://localhost:8501
```

> n8n y Mailpit se usan desde Docker. Sin Docker y con Docker se comparte la misma
> base (`data/vinculacion.db`); no conviene correr las dos formas a la vez porque usan
> los mismos puertos.

### Variables de entorno ([.env.example](.env.example))

| Variable | Por defecto | Para qué |
|---|---|---|
| `DB_PATH` | `data/vinculacion.db` | Archivo SQLite |
| `API_URL` | `http://localhost:8000` | URL de la API que usa la interfaz (en Docker: `http://api:8000`) |
| `OLLAMA_URL` | `http://localhost:11434` | URL de Ollama (en Docker: `http://host.docker.internal:11434`) |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modelo de IA |
| `OLLAMA_TIMEOUT` | `120` | Segundos máximos de espera por respuesta del modelo |
| `UMBRAL_IA` | `50` | Score mínimo para que el workflow 02 genere recomendaciones |

## Reglas de scoring

Código: [core/scoring.py](core/scoring.py) · Tests: [tests/test_scoring.py](tests/test_scoring.py)

| Criterio | Peso | Cálculo |
|---|---|---|
| Competencias obligatorias | 60 | Cada una vale 1 si el nivel ≥ mínimo, **0.5** si la tiene con nivel menor, 0 si no la tiene. Se promedia. |
| Competencias deseables | 25 | Cada una vale 1 si la tiene (cualquier nivel), 0 si no. Se promedia. |
| Modalidad | 15 | 15 si coincide, 7 si alguna de las dos es híbrida, 0 si no coincide. |

- **Redistribución:** si la oferta no tiene obligatorias (o deseables), ese criterio no aplica y
  su peso se reparte proporcionalmente. Ej.: sin obligatorias → deseables 62.5 y modalidad 37.5.
- **Clasificación:** alta ≥ 75 · media 50–74.9 · baja < 50.
- **Faltantes:** cada requisito que no tiene o con nivel menor al mínimo
  (`{skill, nivel_requerido, nivel_actual, tipo}`). Una deseable con nivel menor suma
  puntos, pero se informa como faltante para que la IA pueda sugerir mejorarla.
- **Normalización:** las skills se comparan en minúsculas, sin tildes y sin espacios extra
  (`"Estadística "` = `"estadistica"`).
- **Transparencia:** cada resultado guarda el desglose por criterio (peso, cumplimiento, puntos).

**Ejemplo** — Diego vs. "Backend Python Jr" (híbrida; obligatorias python 3, sql 2, git 2):
tiene python 5 y sql 3 pero no git → obligatorias 2/3 × 60 = **40**; no tiene ninguna
deseable → **0**; él prefiere remota y la oferta es híbrida → **7**. Score = **47 (baja)**.

## Integración de IA

**Qué hace:** a partir de las competencias faltantes **ya calculadas por reglas**, un modelo
de lenguaje redacta recomendaciones de formación y mejoras del perfil. La IA **no** calcula
ni modifica el score.

**Flujo** ([core/ia_service.py](core/ia_service.py)):

1. Prompt en español con carrera, año, competencias, oferta, score y faltantes.
   **No** se envían nombre ni email (minimización de datos).
2. `POST {OLLAMA_URL}/api/generate` con `format: "json"`, `stream: false`, `temperature: 0.3`.
3. Validación con Pydantic de la forma
   `{"resumen", "recomendaciones": [{"competencia", "accion", "recurso_sugerido", "prioridad"}], "mejoras_perfil"}`.
   Si no es válida se **reintenta 1 vez**; si vuelve a fallar → **502**.
4. Validación del contenido: se agregan **advertencias** si la IA recomienda competencias que
   no estaban entre las faltantes, si deja faltantes sin cubrir o si incluye enlaces.
5. Se guarda con `origen: "ia"` y `estado: "pendiente_revision"`. **Solo una persona** la pasa a
   `aprobada` o `rechazada`, con comentario (`PATCH /recomendaciones/{id}/revision`). No se puede
   revisar dos veces (409).

Si Ollama está apagado, el modelo no está instalado o no responde a tiempo → **503**
"Servicio de IA no disponible". El resto del sistema sigue funcionando.

**Por qué Ollama + `llama3.2:3b`**

- Gratuito y local: sin cuentas, claves ni pagos.
- Privacidad: los datos de los estudiantes no salen de la máquina.
- Liviano (~2 GB): corre en una notebook sin GPU dedicada.
- Soporta salida JSON, que se puede validar automáticamente.
- Se puede cambiar de modelo con `OLLAMA_MODEL` sin tocar código.

**Límites (y por qué hay revisión humana)**

- **Inventa** recursos: en las pruebas sugirió un curso de una asociación inexistente y una
  plataforma paga, aunque el prompt pedía recursos gratuitos y sin URLs.
- Calidad variable: a veces es genérico o no respeta la prioridad pedida.
- Puede no cumplir el formato → se reintenta y, si falla, se informa (502).
- La primera llamada tarda ~30–60 s (Ollama carga el modelo en memoria); las siguientes, segundos.

## API (FastAPI)

Documentación interactiva con ejemplos: **http://localhost:8000/docs**.
Los routers ([api/routers/](api/routers/)) solo validan la forma del JSON y delegan en `core/`.

| Método | Ruta | Función | Errores |
|---|---|---|---|
| GET | `/health` | Estado de API, base y Ollama | — |
| POST | `/estudiantes` | Crear perfil con competencias | 422, 409 email duplicado |
| GET | `/estudiantes` | Listar (filtros `skill`, `carrera`) | — |
| GET | `/estudiantes/{id}` | Detalle | 404 |
| PUT | `/estudiantes/{id}` | Actualizar perfil y competencias | 404, 409, 422 |
| DELETE | `/estudiantes/{id}` | Eliminar (y sus resultados) → 204 | 404 |
| POST | `/ofertas` | Crear oferta con requisitos | 422 |
| GET | `/ofertas` | Listar (filtro `estado`) | — |
| GET | `/ofertas/{id}` | Detalle | 404 |
| PATCH | `/ofertas/{id}/estado` | Abrir / cerrar | 404, 422 |
| POST | `/matching/ofertas/{oferta_id}` | Calcular, guardar y devolver el ranking (**reglas**) | 404, 409 oferta cerrada |
| GET | `/matching/resultados` | Consultar (filtros `oferta_id`, `estudiante_id`, `min_score`) | — |
| POST | `/recomendaciones/{resultado_id}` | Generar recomendación (**IA**) → `pendiente_revision` | 404, 409 sin faltantes, 502, 503 |
| GET | `/recomendaciones` | Listar (filtro `estado`) | — |
| GET | `/recomendaciones/{id}` | Detalle | 404 |
| PATCH | `/recomendaciones/{id}/revision` | Aprobar / rechazar con comentario (**humano**) | 404, 409 ya revisada, 422 |
| GET | `/reportes/resumen` | Totales, score promedio por oferta, competencias más faltantes, pendientes | — |

Todas las respuestas de error tienen la forma `{"detalle": "mensaje en español"}`
(los 422 incluyen además `errores` con el campo exacto).

| Código | Significado | Excepción en `core/` |
|---|---|---|
| 422 | Dato inválido | `ValidacionError` o validación de Pydantic |
| 404 | No existe | `NoEncontradoError` |
| 409 | Duplicado o estado que no permite la operación | `DuplicadoError`, `EstadoInvalidoError` |
| 502 | La IA respondió algo inválido | `IAError` |
| 503 | IA no disponible | `IANoDisponibleError` |

## Interfaz (Streamlit)

http://localhost:8501 — todas las llamadas pasan por [ui/api_client.py](ui/api_client.py).

| Sección | Qué permite |
|---|---|
| 👩‍🎓 Estudiantes | Listado con filtros, alta con competencias dinámicas, edición y eliminación |
| 💼 Ofertas | Listado, alta con requisitos obligatorios/deseables, abrir/cerrar |
| 📊 Matching | Calcular el ranking, ver score con colores, desglose por criterio y faltantes — etiqueta **"Calculado por reglas"** |
| 🤖 Recomendaciones IA | Generar, ver el contenido y el JSON, advertencias, aprobar/rechazar con comentario — etiqueta **"Generado por IA — requiere revisión"** |
| 📈 Reportes | Métricas y gráficos: score promedio por oferta, competencias más faltantes, estados |

La barra lateral muestra el estado de `/health`. Si la API no responde, la interfaz muestra
un único mensaje con instrucciones; los errores 4xx/5xx se muestran en español.

## Workflows n8n

Tres workflows en [n8n/workflows/](n8n/workflows/), integrados con la API (`http://api:8000`)
y cada uno con al menos una condición IF. Detalle de entradas, salidas y nodos en
[docs/arquitectura.md](docs/arquitectura.md#workflows-n8n).

| Workflow | Disparador | Qué hace | Condiciones |
|---|---|---|---|
| **01 · Ingreso de ofertas** | `POST /webhook/nueva-oferta` | Normaliza la oferta, la crea, calcula el matching y responde con el top 5 | ¿Datos completos? (si no → 400) · ¿La API la aceptó? (si no → 422) |
| **02 · Matching + IA** | Cada 15 min o `POST /webhook/procesar-ia` | Recorre los resultados con score ≥ `UMBRAL_IA` y genera recomendación IA a los que no tienen | ¿Necesita recomendación? · ¿Respuesta OK? (si falla, registra y sigue) |
| **03 · Reporte y notificaciones** | Diario 9:00 o `GET /webhook/reporte-diario` | Arma un reporte HTML y lo envía por email (Mailpit) | ¿Hay pendientes? → aviso al revisor / informe a coordinación |

**Importar (una sola vez):**

```bash
docker compose exec n8n sh /import/importar.sh   # credencial SMTP + 3 workflows, y los publica
docker compose restart n8n
```

La credencial SMTP ([n8n/credentials/smtp_mailpit.json](n8n/credentials/smtp_mailpit.json))
no tiene usuario ni contraseña: Mailpit es un servidor de correo falso para pruebas.

**Si la importación automática falla**, hacerlo a mano en http://localhost:5678:

1. **Credentials → Add credential → SMTP**: Host `mailpit`, Port `1025`, User y Password vacíos,
   SSL/TLS desactivado, "Disable STARTTLS" activado. Nombre: `SMTP Mailpit (pruebas)`.
2. **Workflows → Import from File** y elegir cada JSON de `n8n/workflows/`.
3. En los dos nodos de email del workflow 03, elegir la credencial creada.
4. Abrir cada workflow y tocar **Publish**.

**Probarlos** (PowerShell):

```powershell
# 01 — oferta válida (responde 201 con el ranking)
$oferta = @{ titulo = "Data Engineer Jr"; empresa = "Ficticia Cloud"; modalidad = "remota"
             requisitos = @(@{ skill = "python"; nivel_minimo = 3; tipo = "obligatoria" },
                            @{ skill = "docker"; nivel_minimo = 1; tipo = "deseable" }) } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Method Post http://localhost:5678/webhook/nueva-oferta -ContentType "application/json" -Body $oferta

# 01 — oferta incompleta (responde 400 con la lista de errores)
curl.exe -i -X POST http://localhost:5678/webhook/nueva-oferta -H "Content-Type: application/json" -d "{}"

# 02 — procesar recomendaciones con IA ahora (responde al instante; sigue en segundo plano)
Invoke-RestMethod -Method Post http://localhost:5678/webhook/procesar-ia

# 03 — enviar el reporte ahora y verlo en http://localhost:8025
Invoke-RestMethod http://localhost:5678/webhook/reporte-diario
```

El detalle de cada ejecución (qué recorrió cada nodo) se ve en n8n → **Executions**.

## Docker en detalle

```bash
docker compose up -d --build     # construir e iniciar todo
docker compose ps                # estado de los servicios
docker compose logs -f api       # logs de un servicio (api, ui, n8n, mailpit)
docker compose restart api       # reiniciar un servicio
docker compose stop              # detener sin borrar los contenedores
docker compose start             # volver a iniciarlos
docker compose down              # detener y borrar los contenedores (los datos se conservan)
docker compose down -v           # además borra el volumen de n8n (workflows y credenciales)
```

| Servicio | Contenedor | Desde el navegador | Dentro de la red de Docker |
|---|---|---|---|
| API | `vinculacion-api` | http://localhost:8000 | `http://api:8000` |
| Interfaz | `vinculacion-ui` | http://localhost:8501 | `http://ui:8501` |
| n8n | `vinculacion-n8n` | http://localhost:5678 | `http://n8n:5678` |
| Mailpit web / SMTP | `vinculacion-mailpit` | http://localhost:8025 | `mailpit:1025` |
| Ollama (fuera de Docker) | — | http://localhost:11434 | `http://host.docker.internal:11434` |

- Los 4 contenedores comparten la red `vinculacion` y se llaman por el **nombre del servicio**.
- La API llega a Ollama con `host.docker.internal`. En Linux funciona gracias a
  `extra_hosts: host-gateway`, y Ollama debe escuchar en todas las interfaces (`OLLAMA_HOST=0.0.0.0`).
- La base SQLite queda en la carpeta `data/` del proyecto (`./data:/app/data`).
- n8n guarda workflows, credenciales e historial de ejecuciones en el volumen `n8n_data`.
- `ui` y `n8n` esperan a que la API esté sana (healthcheck sobre `/health`).
- Imágenes: `python:3.11-slim` para [api](api/Dockerfile) y [ui](ui/Dockerfile);
  versiones fijas de `n8nio/n8n:2.44.6` y `axllent/mailpit:v1.31.6`.

## Verificación y tests

```bash
pytest -v        # 53 tests, ~2 segundos, no necesitan Ollama ni Docker
```

| Archivo | Qué verifica |
|---|---|
| [tests/test_scoring.py](tests/test_scoring.py) | Score perfecto, cero, nivel insuficiente, sin obligatorias/deseables (redistribución), modalidad, normalización, clasificación |
| [tests/test_database.py](tests/test_database.py) | CRUD, email duplicado, validaciones, borrado en cascada, recalcular sin duplicar, revisión única |
| [tests/test_api.py](tests/test_api.py) | Endpoints y códigos 201, 204, 404, 409, 422; matching; revisión; reportes |
| [tests/test_ia.py](tests/test_ia.py) | Prompt, reintento ante JSON inválido, 502, 503, modelo no instalado, advertencias (Ollama **simulado**) |

Cada test usa una base temporal: nunca toca `data/vinculacion.db`.

Además de los tests automáticos se verificó a mano y con scripts: la interfaz completa contra
la API, la generación con el modelo real, la comunicación entre contenedores y todas las ramas
de los 3 workflows (incluida la caída simulada de la IA). El detalle está en la
[bitácora](docs/bitacora_ia.md).

## Guion de demostración

Duración estimada: 15 minutos. Antes de empezar:

- [ ] Ollama abierto (ícono en la bandeja) y `docker compose up -d` hecho.
- [ ] Datos limpios: `docker compose exec api python scripts/seed.py --reset`.
- [ ] Workflows importados y publicados en n8n.
- [ ] Generar una recomendación de prueba antes (para que el modelo ya esté cargado) y borrarla con un `--reset`.
- [ ] Pestañas abiertas: interfaz (8501), `/docs` (8000), n8n (5678), Mailpit (8025).

### Proceso completo (de ingreso a resultados)

| # | Acción | Qué mostrar / explicar |
|---|---|---|
| 1 | Interfaz → barra lateral | `/health`: API, base y Ollama en verde |
| 2 | **Estudiantes → Nuevo**: crear "Julia Pérez", remota, competencias Python 3, SQL 2, Excel 4 | Competencias dinámicas; se normalizan (minúsculas, sin tildes) |
| 3 | **n8n workflow 01**: enviar la oferta "Data Engineer Jr" (comando de arriba) | Responde 201 con el top 5. Ver la ejecución en n8n: Code → IF → HTTP → IF → HTTP → Respond |
| 4 | **Ofertas** | La oferta creada por n8n aparece en el listado |
| 5 | **Matching** → elegir "Analista de Datos Trainee" → Calcular | Etiqueta "Calculado por reglas", ranking con colores; abrir el desglose de Elena y explicar el cálculo |
| 6 | **Recomendaciones IA → Generar**: oferta 2, resultado de Elena | Etiqueta "Generado por IA — requiere revisión", estado pendiente, JSON, advertencias |
| 7 | Rechazar con comentario ("recurso inventado") o aprobar | Supervisión humana; intentar revisar de nuevo no es posible (409) |
| 8 | **n8n workflow 02**: `POST /webhook/procesar-ia` | En Executions: recorre resultados, omite los que ya tienen o no tienen faltantes, genera el resto |
| 9 | **Reportes** | Métricas, score promedio por oferta, competencias más faltantes, pendientes |
| 10 | **n8n workflow 03**: `GET /webhook/reporte-diario` → abrir Mailpit | Email al revisor con la cantidad de pendientes |
| 11 | `/docs` → `GET /matching/resultados?min_score=75` | Endpoint consultado directamente: JSON con `origen: "reglas"` |

### Casos de error

| # | Situación | Cómo provocarla | Resultado esperado |
|---|---|---|---|
| E1 | **Dato inválido** | `/docs` → `POST /estudiantes` con `"anio_cursada": 9` y `"competencias": []` | 422: "anio_cursada: debe ser menor o igual a 6; competencias: debe tener al menos 1 elemento(s)" |
| E2 | **Dato inválido por n8n** | Workflow 01 con `{}` | 400 con la lista de campos faltantes; la API ni se llama |
| E3 | **Email duplicado** | Interfaz → crear un estudiante con `ana.gomez@example.com` | Aviso 409 "Ya existe un estudiante con el email..." |
| E4 | **Recurso inexistente** | `/docs` → `GET /estudiantes/999` | 404 "No existe el estudiante con id 999." |
| E5 | **Operación no permitida** | Ofertas → cerrar una oferta; `/docs` → `POST /matching/ofertas/{id}` | 409 "La oferta está cerrada" (en la interfaz el botón queda deshabilitado) |
| E6 | **IA apagada** | Cerrar Ollama (clic derecho en el ícono → Quit) y generar una recomendación | Interfaz: "Servicio de IA no disponible" (503); la barra lateral marca IA en rojo; el resto sigue funcionando. Workflow 02 registra el fallo y continúa |
| E7 | **API caída** | `docker compose stop api` y recargar la interfaz | Mensaje único "No se pudo conectar con la API" con instrucciones. Volver con `docker compose start api` |
| E8 | **Respuesta inválida de la IA** | `pytest tests/test_ia.py -k invalida -v` | 1 reintento y después 502; no se guarda nada |

## Problemas frecuentes

| Problema | Causa probable | Solución |
|---|---|---|
| Barra lateral: "IA (Ollama): no disponible" | Ollama no está abierto | Abrir Ollama; verificar con `ollama list` |
| 503 "el modelo ... no está instalado" | Falta descargar el modelo | `ollama pull llama3.2:3b` |
| La primera recomendación tarda ~1 minuto | Ollama carga el modelo en memoria | Normal; las siguientes tardan segundos |
| Interfaz: "No se pudo conectar con la API" | La API no está corriendo | `docker compose ps` / `docker compose start api` |
| Webhook de n8n responde 404 | Workflows no importados o no publicados | Correr `importar.sh` y `docker compose restart n8n` |
| `port is already allocated` | Otro proceso usa 8000/8501 (ej. uvicorn sin Docker) | Cerrar ese proceso o `docker compose down` |
| En Linux la API no llega a Ollama | Ollama escucha solo en 127.0.0.1 | Iniciar Ollama con `OLLAMA_HOST=0.0.0.0` |
| La base quedó con datos de prueba | — | `python scripts/seed.py --reset` (o dentro del contenedor) |

## Estructura del repositorio

```
├── api/                    API FastAPI
│   ├── main.py             app, manejo global de errores, /health
│   ├── schemas.py          modelos Pydantic de entrada y salida
│   ├── routers/            estudiantes, ofertas, matching, recomendaciones, reportes
│   ├── requirements.txt
│   └── Dockerfile
├── core/                   lógica de negocio (sin FastAPI ni Streamlit)
│   ├── config.py           variables de entorno
│   ├── database.py         SQLite: tablas y CRUD
│   ├── scoring.py          reglas del score y faltantes
│   ├── matching.py         ranking de una oferta contra todos los estudiantes
│   ├── validaciones.py     normalización y reglas de negocio
│   ├── ia_service.py       Ollama: prompt, llamada, validación, advertencias
│   ├── reportes.py         indicadores
│   └── excepciones.py      errores propios
├── ui/                     interfaz Streamlit
│   ├── app.py              menú y estado del sistema
│   ├── api_client.py       todas las llamadas HTTP a la API
│   ├── componentes.py      utilidades compartidas
│   ├── paginas/            una página por sección
│   ├── requirements.txt
│   └── Dockerfile
├── n8n/
│   ├── workflows/          01_ingreso_ofertas, 02_matching_ia, 03_reporte_notificaciones (JSON)
│   ├── credentials/        credencial SMTP de Mailpit (sin secretos)
│   └── importar.sh         importa y publica todo
├── data/seed.json          datos ficticios
├── scripts/seed.py         carga los datos de ejemplo
├── tests/                  pytest
├── docs/                   arquitectura, bitácora de IA, responsabilidades, consigna
├── compose.yaml
├── requirements.txt        dependencias para desarrollo local (incluye api/ y ui/)
├── .env.example
└── CONSIGNA_PROYECTO.md    guía de trabajo usada con el asistente de IA
```

Todos los datos del repositorio son **ficticios**. No se suben contraseñas, tokens ni el archivo `.env`.
