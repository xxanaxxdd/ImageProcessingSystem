# Diagrama de Comunicación — Image Processing System

## 1. Diagrama de Componentes y Mensajes

```mermaid
graph TB
    Cliente["Cliente\n(HTTP Client)"]

    subgraph API_Layer["Capa API — FastAPI (puerto 8000)"]
        Main["api/main.py\nStartup / Lifespan"]
        Routes["api/routes.py\nEndpoints REST"]
        Schemas["api/schemas.py\nPydantic Schemas"]
        DB_Conn["api/database.py\nSesión SQLAlchemy"]
    end

    subgraph Workers["Capa Worker — Celery"]
        W1["worker1\ncelery_worker.py\n(concurrency=4)"]
        W2["worker2\ncelery_worker.py\n(concurrency=4)"]
        Tasks["worker/tasks.py\nRe-exporta tarea"]
    end

    subgraph Utils["Utilidades"]
        ImgProc["utils/image_processing.py\nprocesar_imagen()\naplicar_transformacion()"]
    end

    subgraph Infra["Infraestructura"]
        Redis["Redis\n:6379\nBroker + Backend"]
        MySQL["MySQL\nimages_db\n:3306"]
    end

    subgraph FS["Sistema de Archivos"]
        Uploads["uploads/\nimágenes de entrada"]
        Results["results/\nimágenes procesadas"]
    end

    %% Cliente → API
    Cliente -->|"1  POST /solicitudes\n(archivos + transformaciones)"| Routes
    Cliente -->|"2  GET /solicitudes/{id}"| Routes
    Cliente -->|"3  GET /solicitudes/{id}/resultados"| Routes
    Cliente -->|"4  GET /imagenes/{id}/descargar"| Routes
    Cliente -->|"5  GET /transformaciones"| Routes
    Cliente -->|"6  GET /nodos  |  GET /logs"| Routes

    %% API interna
    Main -->|"Startup: create_all()\nseed transformaciones"| MySQL
    Routes -.->|"valida con"| Schemas
    Routes -.->|"abre sesión"| DB_Conn

    %% API → Infra / FS
    Routes -->|"7  INSERT Solicitud\nImagen, ImagenTransformacion"| MySQL
    Routes -->|"8  SELECT Solicitud\nImagen, Transformacion, NodoWorker, Log"| MySQL
    Routes -->|"9  Guardar archivo\nuploads/{id}_{filename}"| Uploads
    Routes -->|"10 procesar_imagen_task.delay(id_imagen)"| Redis
    Routes -->|"11 Servir archivo resultado"| Results

    %% Redis → Workers
    Redis -->|"12 Entregar tarea"| W1
    Redis -->|"12 Entregar tarea"| W2

    %% Workers → DB
    W1 -->|"13 SELECT/INSERT NodoWorker"| MySQL
    W1 -->|"14 UPDATE Imagen (procesando)"| MySQL
    W1 -->|"15 SELECT ImagenTransformacion\n+ Transformacion"| MySQL
    W1 -->|"16 INSERT ResultadoProcesamiento\nLogProcesamiento"| MySQL
    W1 -->|"17 UPDATE Imagen (completado/error)\nUPDATE Solicitud"| MySQL

    W2 -->|"13–17 (igual que W1)"| MySQL

    %% Workers → Utils
    W1 -->|"18 procesar_imagen(ruta, transformaciones)"| ImgProc
    W2 -->|"18 procesar_imagen(ruta, transformaciones)"| ImgProc

    %% Utils → FS
    ImgProc -->|"19 Leer imagen original"| Uploads
    ImgProc -->|"20 Escribir resultado\nresults/result_{base}.{ext}"| Results
```

---

## 2. Diagrama de Secuencia — Flujo Principal

```mermaid
sequenceDiagram
    actor Cliente
    participant API   as FastAPI (routes.py)
    participant DB    as MySQL (images_db)
    participant Queue as Redis (Celery Queue)
    participant WK    as Celery Worker
    participant PIL   as image_processing.py
    participant FS    as File System

    %% --- Envío de solicitud ---
    Cliente->>API: POST /solicitudes (imágenes + JSON transformaciones)
    API->>FS: Guardar archivos → uploads/{id_sol}_{nombre}
    API->>DB: INSERT Solicitud (estado='pendiente')
    loop Por cada imagen
        API->>DB: INSERT Imagen (estado='pendiente')
        API->>DB: INSERT ImagenTransformacion × N transformaciones
        API->>Queue: procesar_imagen_task.delay(id_imagen)
    end
    API->>DB: UPDATE Solicitud (estado='procesando')
    API-->>Cliente: 201 {id_solicitud, estado='procesando', total_imagenes}

    %% --- Procesamiento asíncrono ---
    Queue->>WK: Entregar procesar_imagen_task(id_imagen)
    WK->>DB: SELECT/INSERT NodoWorker (registro del nodo)
    WK->>DB: UPDATE Imagen (estado='procesando', id_nodo)
    WK->>DB: SELECT ImagenTransformacion ORDER BY orden
    WK->>DB: SELECT Transformacion (nombre, parámetros)
    WK->>PIL: procesar_imagen(ruta_archivo, lista_transformaciones)
    PIL->>FS: Leer imagen (uploads/)
    loop Por cada transformación
        PIL->>PIL: aplicar_transformacion(img, nombre, params)
    end
    PIL->>FS: Guardar resultado → results/result_{base}.{ext}
    PIL-->>WK: {ruta_salida, formato, tamaño_archivo}
    WK->>DB: INSERT ResultadoProcesamiento
    WK->>DB: UPDATE Imagen (estado='completado')
    WK->>DB: INSERT LogProcesamiento (nivel=INFO)
    WK->>DB: SELECT todas las Imágenes de la Solicitud
    WK->>DB: UPDATE Solicitud (estado='completado' | 'completado_con_errores')

    %% --- Consulta de estado ---
    Cliente->>API: GET /solicitudes/{id_solicitud}
    API->>DB: SELECT Solicitud + Imágenes
    API-->>Cliente: {estado, progreso: completadas/total}

    %% --- Descarga de resultado ---
    Cliente->>API: GET /imagenes/{id_imagen}/descargar
    API->>DB: SELECT ResultadoProcesamiento (ruta_salida)
    API->>FS: Leer archivo results/{nombre}
    API-->>Cliente: FileResponse (imagen procesada)
```

---

## 3. Tabla de Mensajes entre Componentes

| # | Emisor | Receptor | Mensaje / Operación | Protocolo |
|---|--------|----------|---------------------|-----------|
| 1–6 | Cliente | API Routes | Peticiones HTTP REST | HTTP/1.1 |
| 7 | API Routes | MySQL | INSERT/SELECT ORM (Solicitud, Imagen, etc.) | SQLAlchemy/PyMySQL |
| 8 | API Routes | File System | Guardar archivos subidos | OS I/O |
| 9 | API Routes | Redis | `procesar_imagen_task.delay(id_imagen)` | Celery/Redis protocol |
| 10 | API Routes | File System | Servir archivo resultado | OS I/O |
| 11 | Redis | Celery Worker | Entregar tarea serializada (JSON) | Celery wire format |
| 12 | Celery Worker | MySQL | SELECT/UPDATE Imagen, NodoWorker, Logs | SQLAlchemy/PyMySQL |
| 13 | Celery Worker | image_processing | `procesar_imagen(ruta, transformaciones)` | Llamada directa Python |
| 14 | image_processing | File System | Leer/escribir imágenes con PIL | PIL/OS I/O |
| 15 | Celery Worker | Redis | Resultado de tarea (éxito/error) | Celery result backend |

---

## 4. Ciclo de Estados de una Solicitud

```mermaid
stateDiagram-v2
    [*] --> pendiente : POST /solicitudes
    pendiente --> procesando : API encola tareas en Redis
    procesando --> completado : Todas las imágenes OK
    procesando --> completado_con_errores : Al menos una imagen falló
    completado --> [*]
    completado_con_errores --> [*]

    state procesando {
        [*] --> img_pendiente
        img_pendiente --> img_procesando : Worker toma la tarea
        img_procesando --> img_completado : Transformaciones OK
        img_procesando --> img_error : Excepción (retry x3)
        img_error --> img_procesando : Reintento automático
    }
```
