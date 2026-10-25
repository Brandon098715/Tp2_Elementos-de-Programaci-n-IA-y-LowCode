# Arquitectura del sistema

## 1. Vista general

```mermaid
flowchart LR
    usuario([👤 Usuario / revisor])
    externo([🌐 Sistema externo<br/>que publica ofertas])

    subgraph docker [Docker Compose · red 'vinculacion']
        ui["<b>ui</b> · Streamlit<br/>:8501"]
        api["<b>api</b> · FastAPI<br/>:8000"]
        n8n["<b>n8n</b><br/>:5678"]
        mailpit["<b>mailpit</b><br/>SMTP :1025 · web :8025"]
        db[("SQLite<br/>data/vinculacion.db")]
    end

    subgraph host [Máquina local · fuera de Docker]
        ollama["<b>Ollama</b><br/>llama3.2:3b · :11434"]
    end

    usuario -- navegador --> ui
    usuario -- lee emails --> mailpit
    ui -- "HTTP/JSON<br/>http://api:8000" --> api
    externo -- "POST /webhook/nueva-oferta" --> n8n
    n8n -- "HTTP/JSON<br/>http://api:8000" --> api
    n8n -- "SMTP mailpit:1025" --> mailpit
    api -- "sqlite3<br/>(volumen ./data)" --> db
    api -- "POST /api/generate<br/>host.docker.internal:11434" --> ollama
```

**Ideas clave**

- **Una sola puerta de entrada a los datos: la API.** La interfaz y n8n nunca tocan la base;
  todo pasa por endpoints HTTP con JSON. Así las validaciones y reglas están en un solo lugar.
- **La lógica vive en `core/`**, en funciones Python puras que no conocen FastAPI ni Streamlit.
  Los routers de la API solo validan la forma del JSON y llaman a `core/`.
- **Reglas e IA están separadas.** El score se calcula con reglas (`core/scoring.py`); la IA
  (`core/ia_service.py`) solo recibe el resultado y redacta recomendaciones.
- **Ollama corre fuera de Docker** (la consigna no obliga a contenerizar el modelo y así
  aprovecha mejor los recursos de la máquina). La API lo alcanza con `host.docker.internal`.

## 2. Capas del código

```mermaid
flowchart TB
    subgraph presentacion [Presentación]
        paginas["ui/paginas/*.py<br/>formularios, tablas, gráficos"]
        cliente["ui/api_client.py<br/>llamadas HTTP + manejo de errores"]
    end
    subgraph api_capa [API]
        routers["api/routers/*.py<br/>endpoints"]
        schemas["api/schemas.py<br/>modelos Pydantic"]
        main["api/main.py<br/>errores → códigos HTTP"]
    end
    subgraph core_capa [Lógica de negocio · core/]
        validaciones["validaciones.py"]
        scoring["scoring.py"]
        matching["matching.py"]
        ia["ia_service.py"]
        reportes["reportes.py"]
        database["database.py"]
        excepciones["excepciones.py"]
    end
    paginas --> cliente -- HTTP --> routers
    routers --> schemas
    routers --> matching & ia & reportes & database
    matching --> scoring & database
    ia --> database
    scoring --> validaciones
    database --> validaciones
    core_capa -. lanza .-> excepciones
    excepciones -. traduce .-> main
```

| Capa | Responsabilidad | No hace |
|---|---|---|
| `ui/` | Mostrar datos y formularios, traducir errores a mensajes para el usuario | No accede a la base ni calcula nada |
| `api/` | Recibir/validar JSON, elegir el código HTTP, documentar en `/docs` | No tiene reglas de negocio |
| `core/` | Validar, normalizar, calcular el score, hablar con la base y con Ollama | No sabe de HTTP ni de Streamlit |

## 3. Recorrido de los datos (proceso principal)

```mermaid
sequenceDiagram
    actor U as Usuario
    participant UI as Streamlit
    participant API as FastAPI
    participant C as core/
    participant DB as SQLite
    participant IA as Ollama

    U->>UI: Matching → elegir oferta → "Calcular"
    UI->>API: POST /matching/ofertas/2
    API->>C: calcular_matching_oferta(2)
    C->>DB: oferta + requisitos, estudiantes + competencias
    C->>C: calcular_score() por cada estudiante (REGLAS)
    C->>DB: guardar resultados (origen = 'reglas')
    API-->>UI: 200 ranking con score, desglose y faltantes
    UI-->>U: tabla con colores · "Calculado por reglas"

    U->>UI: Recomendaciones → "Generar con IA"
    UI->>API: POST /recomendaciones/{resultado_id}
    API->>C: generar_y_guardar(resultado_id)
    C->>DB: resultado, estudiante, oferta
    C->>IA: prompt con faltantes (format: json)
    IA-->>C: JSON
    C->>C: validar con Pydantic (1 reintento) + advertencias
    C->>DB: guardar (origen = 'ia', estado = 'pendiente_revision')
    API-->>UI: 201 recomendación
    UI-->>U: "Generado por IA — requiere revisión"

    U->>UI: "Aprobar" + comentario
    UI->>API: PATCH /recomendaciones/{id}/revision
    API->>C: revisar_recomendacion()
    C->>DB: estado = 'aprobada', revisado_en
    API-->>UI: 200
```

## 4. Modelo de datos

```mermaid
erDiagram
    estudiantes ||--o{ competencias_estudiante : tiene
    ofertas ||--o{ requisitos_oferta : exige
    estudiantes ||--o{ resultados_matching : "se evalúa en"
    ofertas ||--o{ resultados_matching : "se evalúa en"
    resultados_matching ||--o{ recomendaciones_ia : "origina"

    estudiantes {
        int id PK
        text nombre
        text email UK
        text carrera
        int anio_cursada "1-6"
        text modalidad_preferida "presencial|remota|hibrida"
        text creado_en
        text actualizado_en
    }
    competencias_estudiante {
        int id PK
        int estudiante_id FK
        text skill "normalizada"
        int nivel "1-5"
    }
    ofertas {
        int id PK
        text titulo
        text empresa
        text modalidad
        text descripcion
        text estado "abierta|cerrada"
        text creado_en
    }
    requisitos_oferta {
        int id PK
        int oferta_id FK
        text skill
        int nivel_minimo "1-5"
        text tipo "obligatoria|deseable"
    }
    resultados_matching {
        int id PK
        int estudiante_id FK
        int oferta_id FK
        real score "0-100"
        text clasificacion "alta|media|baja"
        text detalle_json "desglose"
        text faltantes_json
        text origen "siempre 'reglas'"
        text calculado_en
    }
    recomendaciones_ia {
        int id PK
        int resultado_id FK
        text texto_json "respuesta validada"
        text modelo
        text origen "siempre 'ia'"
        text estado "pendiente_revision|aprobada|rechazada"
        text comentario_revisor
        text creado_en
        text revisado_en
    }
```

- `UNIQUE(estudiante_id, oferta_id)` en `resultados_matching`: recalcular **actualiza** la fila.
- `ON DELETE CASCADE`: al borrar un estudiante u oferta se borran sus resultados y recomendaciones.
- Las columnas `origen` tienen un `CHECK` que impide mezclar: un resultado solo puede ser
  `'reglas'` y una recomendación solo `'ia'`.
- Las skills se guardan normalizadas (minúsculas, sin tildes) para poder compararlas.

## 5. Puertos y comunicación

| Origen → Destino | Cómo | Dirección usada |
|---|---|---|
| Navegador → Interfaz | HTTP | http://localhost:8501 |
| Navegador → API (Swagger) | HTTP | http://localhost:8000/docs |
| Navegador → n8n | HTTP | http://localhost:5678 |
| Navegador → Mailpit | HTTP | http://localhost:8025 |
| Interfaz → API | HTTP/JSON (`requests`) | `http://api:8000` (Docker) · `http://localhost:8000` (local) |
| n8n → API | Nodo HTTP Request | `{{ $env.API_URL }}` = `http://api:8000` |
| n8n → Mailpit | Nodo Send Email (SMTP) | `mailpit:1025` |
| API → Ollama | HTTP/JSON (`requests`) | `http://host.docker.internal:11434` (Docker) · `http://localhost:11434` (local) |
| API → SQLite | `sqlite3` | `/app/data/vinculacion.db` = `./data/vinculacion.db` del proyecto |

Dentro de Docker los contenedores se llaman por el **nombre del servicio** (`api`, `mailpit`)
porque comparten la red `vinculacion`. Desde la máquina se usa `localhost` con el puerto publicado.

## 6. Workflows n8n

Todos usan la variable de entorno `API_URL` (definida en `compose.yaml`) para llamar a la API,
y tienen al menos un nodo **IF**.

### 01 · Ingreso de ofertas — [01_ingreso_ofertas.json](../n8n/workflows/01_ingreso_ofertas.json)

```mermaid
flowchart LR
    A[Webhook<br/>POST /webhook/nueva-oferta] --> B[Code<br/>Normalizar datos]
    B --> C{¿Datos completos?}
    C -- sí --> D[HTTP POST /ofertas]
    C -- no --> E[Responder 400<br/>lista de errores]
    D --> F{¿Oferta creada?<br/>status 201}
    F -- sí --> G[HTTP POST /matching/ofertas/id]
    F -- no --> H[Responder 422<br/>detalle de la API]
    G --> I[Responder 201<br/>top 5 del ranking]
```

| | |
|---|---|
| **Entrada** | JSON `{titulo, empresa, modalidad, descripcion?, requisitos: [{skill, nivel_minimo, tipo}]}` |
| **Normalización** | Quita espacios, pasa modalidad y tipo a minúsculas, descarta requisitos sin nombre, `tipo` por defecto `obligatoria` |
| **Condición 1** | Título, empresa, modalidad y al menos 1 requisito → si falta algo responde **400** sin llamar a la API |
| **Condición 2** | ¿La API devolvió 201? → si no (ej. nivel 9 o modalidad inválida) responde **422** con el `detalle` de la API |
| **Salida** | **201** `{mensaje, oferta_id, oferta, origen: "reglas", total_estudiantes, ranking: top 5}` |

### 02 · Matching + IA — [02_matching_ia.json](../n8n/workflows/02_matching_ia.json)

```mermaid
flowchart LR
    T1[Schedule<br/>cada 15 min] --> A
    T2[Webhook<br/>POST /webhook/procesar-ia] --> A
    A[HTTP GET /matching/resultados<br/>?min_score=UMBRAL_IA] --> L[Loop<br/>de a 1 resultado]
    L -- siguiente --> C{¿Necesita<br/>recomendación?}
    C -- sí --> D[HTTP POST /recomendaciones/id]
    C -- no --> O[Set: omitido]
    D --> E{¿Respuesta OK?<br/>status 201}
    E -- sí --> S[Set: éxito]
    E -- no --> F[Set: fallo<br/>código + detalle]
    O --> L
    S --> L
    F --> L
    L -- terminado --> R[Code<br/>Resumen del procesamiento]
```

| | |
|---|---|
| **Entrada** | Resultados de matching con score ≥ `UMBRAL_IA` (50 por defecto) |
| **Condición 1** | Necesita recomendación si **no** tiene una (`tiene_recomendacion = false`) **y** tiene faltantes |
| **Condición 2** | ¿La API devolvió 201? Si la IA está caída (503), respondió mal (502) o hubo timeout, el nodo HTTP no corta el flujo (`neverError` + `continueRegularOutput`): se registra el fallo y se sigue con el próximo resultado |
| **Salida** | `{procesados, generadas, omitidos, errores, detalle_errores}` (visible en Executions) |
| **Idempotencia** | Una segunda corrida no duplica: todo queda "omitido" |

Resultados de las pruebas: 1.ª corrida 8 generadas / 4 omitidas; 2.ª corrida 12 omitidas;
con la IA caída 8 errores registrados y la ejecución terminó correctamente.

### 03 · Reporte y notificaciones — [03_reporte_notificaciones.json](../n8n/workflows/03_reporte_notificaciones.json)

```mermaid
flowchart LR
    T1[Schedule<br/>todos los días 9:00] --> A
    T2[Webhook<br/>GET /webhook/reporte-diario] --> A
    A[HTTP GET /reportes/resumen] --> B[Code<br/>Armar email HTML]
    B --> C{¿Hay pendientes?<br/>pendientes > 0}
    C -- sí --> D[Email a revisor@example.com<br/>'N recomendaciones pendientes']
    C -- no --> E[Email a coordinacion@example.com<br/>'sin pendientes']
```

| | |
|---|---|
| **Entrada** | `GET /reportes/resumen` |
| **Proceso** | Arma un HTML con pendientes, totales, score promedio por oferta y competencias más faltantes |
| **Condición** | `recomendaciones_pendientes > 0` decide destinatario y asunto |
| **Salida** | Email vía SMTP a Mailpit (`mailpit:1025`), visible en http://localhost:8025 |

## 7. Manejo de errores de punta a punta

```mermaid
flowchart LR
    E1[core/ lanza<br/>NoEncontradoError] --> M[api/main.py<br/>manejador global]
    E2[Pydantic rechaza<br/>el JSON] --> M
    M -- "404 / 422 / 409 / 502 / 503<br/>{detalle: '...'}" --> C[ui/api_client.py<br/>ErrorAPI]
    C --> P[Página: st.error / st.warning<br/>mensaje en español]
    M -- status + detalle --> N[n8n: nodo IF<br/>rama de error]
```

| Capa | Cómo maneja los errores |
|---|---|
| `core/` | Lanza excepciones propias con mensaje en español (`excepciones.py`) |
| `api/` | Un manejador global las convierte en el código HTTP correcto; los errores de Pydantic se traducen al español |
| `ui/` | `api_client.py` convierte conexión caída, timeouts y 4xx/5xx en `ErrorAPI`; cada página muestra un mensaje según el código |
| `n8n` | Nodos HTTP con `neverError` + IF sobre `statusCode`: los errores toman otra rama en vez de cortar el workflow |

## 8. Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| SQLite con `sqlite3` | ORM (SQLAlchemy) | La consigna pide sin ORM; SQL visible y fácil de explicar |
| Score por reglas en Python | Que la IA calcule la compatibilidad | Las reglas son explicables, reproducibles y testeables; la IA puede alucinar |
| Ollama local (`llama3.2:3b`) | APIs pagas o con cuota | Gratis, privado, sin credenciales; liviano para una notebook |
| Validación de la IA con Pydantic + advertencias | Confiar en la respuesta | El modelo chico a veces no respeta el formato o inventa recursos |
| Revisión humana obligatoria | Publicar la recomendación directo | La consigna lo exige para decisiones relevantes y el modelo comete errores |
| Ollama fuera de Docker | Contenedor de Ollama | No es obligatorio y en Windows/Mac la aceleración por hardware funciona mejor en el host |
| Una página de Streamlit por archivo | Todo en `app.py` | Más fácil de repartir entre integrantes y de explicar |
| Workflows importables por CLI | Crearlos a mano en la UI | Reproducible: `importar.sh` deja todo publicado en un paso |
| Versiones fijas de n8n y Mailpit | `latest` | Evita que una actualización rompa los workflows antes de la entrega |
