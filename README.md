# Sistema Distribuido de Procesamiento de Imágenes

Sistema de procesamiento de imágenes por lotes diseñado para escalar horizontalmente.
Permite enviar múltiples imágenes con transformaciones individuales configurables y procesarlas de forma concurrente mediante workers distribuidos.

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| API Backend | FastAPI + Uvicorn |
| Cola de mensajes | Redis 7 |
| Workers distribuidos | Celery (pool de hilos) |
| Base de datos | MySQL 8 (maestro/réplica) |
| Procesamiento de imágenes | Pillow |
| Autenticación | JWT (python-jose) |
| Frontend | HTML + CSS + JavaScript |
| Contenedores | Docker + Docker Compose |

---

## Arquitectura

```
Cliente
   │
   ▼
API Server (FastAPI)          ←── Frontend HTML/JS
   │
   ▼
Redis (message broker)
   │
   ├──▶ Worker 1 (N hilos)
   └──▶ Worker 2 (N hilos)
              │
              ▼
       MySQL (escritura maestro / lectura réplica)
              │
              ▼
       Storage (uploads / results)
```

Los componentes están **completamente desacoplados**: la API nunca procesa imágenes, solo encola tareas. Los workers consumen la cola y procesan en paralelo mediante hilos.

---

## Transformaciones disponibles

| Transformación | Parámetros |
|----------------|------------|
| `escala_grises` | — |
| `redimensionar` | `ancho`, `alto` |
| `rotar` | `angulo` (grados) |
| `voltear_horizontal` | — |
| `voltear_vertical` | — |
| `recortar` | `izquierda`, `superior`, `derecha`, `inferior` |
| `brillo` | `factor` (default `1.5`) |
| `contraste` | `factor` (default `1.5`) |
| `nitidez` | `factor` (default `2.0`) |
| `desenfoque` | `radio` (default `2.0`) |
| `convertir_formato` | `formato` (`JPEG`, `PNG`, `WEBP`) |
| `marca_agua` | `texto`, `posicion` |

> **Regla:** `convertir_formato` siempre debe ir al final de la lista de transformaciones.

---

## Requisitos

- [Docker](https://www.docker.com/) y Docker Compose

---

## Inicio rápido

```bash
# 1. Clonar el repositorio
git clone https://github.com/<tu-usuario>/image-processing-system.git
cd image-processing-system

# 2. Levantar todos los servicios
docker compose up --build

# 3. Abrir el frontend
# http://localhost:8000
```

La base de datos, las tablas y los datos semilla se crean automáticamente al iniciar.

**Credenciales por defecto:** `admin` / `1234`

---

## Escalar workers

Ajusta la concurrencia de cada worker con la variable `WORKER_THREADS`:

```bash
WORKER_THREADS=8 docker compose up --build
```

O levanta instancias adicionales:

```bash
docker compose up --scale worker1=3 --build
```

---

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/lote` | Enviar lote de imágenes con transformaciones |
| `GET` | `/lote/{id}` | Consultar estado y progreso del lote |
| `GET` | `/lote/{id}/resultado` | Descargar resultados como ZIP |
| `GET` | `/info` | Ver transformaciones disponibles |
| `POST` | `/login` | Autenticación JWT |

Documentación interactiva disponible en **`/docs`** (Swagger UI).

---

## Estructura del proyecto

```
├── api/                  # FastAPI — rutas, BD, autenticación
├── worker/               # Celery — tareas de procesamiento
├── models/               # Modelos SQLAlchemy
├── utils/                # Procesamiento de imágenes (Pillow)
├── frontend/             # Dashboard web (HTML/CSS/JS)
├── mysql/                # Configuración maestro/réplica MySQL
├── uploads/              # Imágenes originales (volumen compartido)
├── results/              # Imágenes procesadas (volumen compartido)
├── docker-compose.yml    # Orquestación de servicios
├── Dockerfile            # Imagen base para API y workers
└── requirements.txt      # Dependencias Python
```

---

## Flujo de procesamiento

```
POST /lote
  → Valida imágenes (JPEG, PNG, TIFF)
  → Extrae metadata (formato, resolución)
  → Guarda en uploads/{id_lote}/
  → Registra en MySQL
  → Encola tarea en Redis via Celery
  → Responde inmediatamente (200 OK)

Worker (N hilos en paralelo)
  → Recibe tarea de Redis
  → Lee transformaciones de MySQL
  → Aplica transformaciones en orden con Pillow
  → Guarda resultado en results/{id_lote}/
  → Actualiza estado en MySQL

GET /lote/{id}/resultado
  → Genera ZIP con resultados
  → Limpia results/{id_lote}/
```

---

## Licencia

MIT
