from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException
)

from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from api.database import SessionLocal
from models.models import (
    Solicitud,
    Imagen,
    Transformacion,
    ImagenTransformacion,
    ResultadoProcesamiento,
    NodoWorker,
    LogProcesamiento,
    Usuario,
)

from worker.tasks import procesar_lote_task

from api.auth import (
    hash_password,
    verify_password,
    create_access_token
)

import os
import json
import shutil
import zipfile
import psutil


router = APIRouter()


# =========================
# CONEXION A BASE DE DATOS
# =========================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# LOGIN
# =========================

@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    usuario = (
        db.query(Usuario)
        .filter(Usuario.username == username)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuario no encontrado"
        )

    if not verify_password(
        password,
        usuario.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    token = create_access_token(
        data={"sub": username}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =========================
# SIGNUP
# =========================

@router.post("/signup")
def signup(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existente = (
        db.query(Usuario)
        .filter(Usuario.username == username)
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya existe"
        )

    nuevo_usuario = Usuario(
        username=username,
        password=hash_password(password)
    )

    db.add(nuevo_usuario)
    db.commit()

    return {"mensaje": "Usuario creado correctamente"}


# =========================
# LISTAR TRANSFORMACIONES
# =========================

@router.get("/transformaciones")
def listar_transformaciones(
    db: Session = Depends(get_db)
):

    transformaciones = (
        db.query(Transformacion)
        .all()
    )

    resultado = []

    for t in transformaciones:

        resultado.append({
            "id_transformacion": t.id_transformacion,
            "nombre": t.nombre,
            "descripcion": t.descripcion
        })

    return resultado


# =========================
# CREAR SOLICITUD
# =========================

@router.post("/solicitudes")
def crear_solicitud(
    imagenes: list[UploadFile] = File(...),
    transformaciones: str = Form(...),
    db: Session = Depends(get_db)
):

    nueva_solicitud = Solicitud()

    db.add(nueva_solicitud)
    db.commit()
    db.refresh(nueva_solicitud)

    id_solicitud = nueva_solicitud.id_solicitud

    lista_transformaciones = json.loads(
        transformaciones.encode().decode("utf-8-sig").strip()
    )

    # 🔴 IMPORTANTE
    ids_imagenes = []

    for archivo in imagenes:

        ruta = os.path.join(
            "uploads",
            archivo.filename
        )

        with open(ruta, "wb") as buffer:
            shutil.copyfileobj(
                archivo.file,
                buffer
            )

        nueva_imagen = Imagen(
            nombre_archivo=archivo.filename,
            ruta_archivo=ruta,
            id_solicitud=id_solicitud
        )

        db.add(nueva_imagen)
        db.commit()
        db.refresh(nueva_imagen)

        # 🔴 GUARDAMOS EL ID
        ids_imagenes.append(
            nueva_imagen.id_imagen
        )

        for orden, item in enumerate(lista_transformaciones, start=1):

            # Acepta tanto [1, 2, 3] como [{"id": 1, "params": {...}}, ...]
            if isinstance(item, dict):
                id_trans = item["id"]
                params = item.get("params") or {}
            else:
                id_trans = item
                params = {}

            transformacion = (
                db.query(Transformacion)
                .filter(Transformacion.id_transformacion == id_trans)
                .first()
            )

            if not transformacion:
                raise HTTPException(
                    status_code=404,
                    detail=f"Transformación {id_trans} no existe"
                )

            db.add(ImagenTransformacion(
                id_imagen=nueva_imagen.id_imagen,
                id_transformacion=id_trans,
                orden=orden,
                parametros=json.dumps(params) if params else None,
            ))

        db.commit()

    nueva_solicitud.total_imagenes = len(ids_imagenes)
    db.commit()

    # ENVIO AL WORKER
    procesar_lote_task.delay(
        id_solicitud,
        ids_imagenes
    )

    return {
        "mensaje":
        "Solicitud creada y enviada a procesamiento",
        "id_solicitud":
        id_solicitud
    }


# =========================
# LISTAR SOLICITUDES
# =========================

@router.get("/solicitudes")
def listar_solicitudes(
    db: Session = Depends(get_db)
):

    solicitudes = (
        db.query(Solicitud)
        .all()
    )

    resultado = []

    for s in solicitudes:

        resultado.append({
            "id_solicitud": s.id_solicitud,
            "fecha_solicitud": str(s.fecha_solicitud),
            "estado": s.estado,
            "total_imagenes": s.total_imagenes
        })

    return resultado


# =========================
# ESTADO DE SOLICITUD
# =========================

@router.get("/solicitudes/{id_solicitud}")
def ver_solicitud(
    id_solicitud: int,
    db: Session = Depends(get_db),
):
    solicitud = (
        db.query(Solicitud)
        .filter(Solicitud.id_solicitud == id_solicitud)
        .first()
    )

    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    imagenes = (
        db.query(Imagen)
        .filter(Imagen.id_solicitud == id_solicitud)
        .all()
    )

    completadas = sum(1 for i in imagenes if i.estado_procesamiento == "completado")
    con_error   = sum(1 for i in imagenes if i.estado_procesamiento == "error")
    en_proceso  = sum(1 for i in imagenes if i.estado_procesamiento == "procesando")
    pendientes  = sum(1 for i in imagenes if i.estado_procesamiento == "pendiente")

    detalle_imagenes = []
    for imagen in imagenes:

        nodo = (
            db.query(NodoWorker)
            .filter(NodoWorker.id_nodo == imagen.id_nodo)
            .first()
        ) if imagen.id_nodo else None

        resultado = (
            db.query(ResultadoProcesamiento)
            .filter(ResultadoProcesamiento.id_imagen == imagen.id_imagen)
            .first()
        )

        imagen_trans = (
            db.query(ImagenTransformacion)
            .filter(ImagenTransformacion.id_imagen == imagen.id_imagen)
            .order_by(ImagenTransformacion.orden)
            .all()
        )

        transformaciones = []
        for it in imagen_trans:
            t = db.query(Transformacion).filter(
                Transformacion.id_transformacion == it.id_transformacion
            ).first()
            if t:
                transformaciones.append({
                    "orden": it.orden,
                    "nombre": t.nombre,
                    "parametros": json.loads(it.parametros) if it.parametros else {},
                })

        detalle_imagenes.append({
            "id_imagen": imagen.id_imagen,
            "nombre_archivo": imagen.nombre_archivo,
            "estado": imagen.estado_procesamiento,
            "fecha_procesamiento": str(imagen.fecha_procesamiento) if imagen.fecha_procesamiento else None,
            "id_nodo": imagen.id_nodo,
            "nombre_nodo": nodo.nombre if nodo else None,
            "direccion_ip": nodo.direccion_ip if nodo else None,
            "ruta_resultado": resultado.ruta_salida if resultado else None,
            "transformaciones": transformaciones,
        })

    return {
        "id_solicitud": solicitud.id_solicitud,
        "estado": solicitud.estado,
        "total_imagenes": solicitud.total_imagenes,
        "fecha_solicitud": str(solicitud.fecha_solicitud),
        "fecha_fin": str(solicitud.fecha_fin) if solicitud.fecha_fin else None,
        "progreso": {
            "completadas": completadas,
            "con_error": con_error,
            "en_proceso": en_proceso,
            "pendientes": pendientes,
        },
        "imagenes": detalle_imagenes,
    }


# =========================
# VER RESULTADOS
# =========================

@router.get("/solicitudes/{id_solicitud}/resultados")
def ver_resultados(
    id_solicitud: int,
    db: Session = Depends(get_db),
):
    imagenes = (
        db.query(Imagen)
        .filter(Imagen.id_solicitud == id_solicitud)
        .all()
    )

    if not imagenes:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    archivos = []
    for imagen in imagenes:
        resultado = (
            db.query(ResultadoProcesamiento)
            .filter(ResultadoProcesamiento.id_imagen == imagen.id_imagen)
            .first()
        )
        if resultado and os.path.exists(resultado.ruta_salida):
            archivos.append(os.path.basename(resultado.ruta_salida))

    if not archivos:
        raise HTTPException(status_code=404, detail="Resultados aún no disponibles")

    return {"id_solicitud": id_solicitud, "archivos": archivos}


# =========================
# DESCARGAR ZIP
# =========================

@router.get("/descargar/{id_solicitud}")
def descargar_resultados(
    id_solicitud: int,
    db: Session = Depends(get_db),
):
    imagenes = (
        db.query(Imagen)
        .filter(Imagen.id_solicitud == id_solicitud)
        .all()
    )

    if not imagenes:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    rutas = []
    for imagen in imagenes:
        resultado = (
            db.query(ResultadoProcesamiento)
            .filter(ResultadoProcesamiento.id_imagen == imagen.id_imagen)
            .first()
        )
        if resultado and os.path.exists(resultado.ruta_salida):
            rutas.append(resultado.ruta_salida)

    if not rutas:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles")

    zip_ruta = os.path.join("results", f"resultados_{id_solicitud}.zip")

    with zipfile.ZipFile(zip_ruta, "w") as zipf:
        for ruta in rutas:
            zipf.write(ruta, os.path.basename(ruta))

    return FileResponse(
        zip_ruta,
        media_type="application/zip",
        filename=f"resultados_{id_solicitud}.zip",
    )


# =========================
# DESCARGAR IMAGEN INDIVIDUAL
# =========================

@router.get("/descargar_imagen/{id_imagen}")
def descargar_imagen(
    id_imagen: int,
    db: Session = Depends(get_db),
):
    resultado = (
        db.query(ResultadoProcesamiento)
        .filter(ResultadoProcesamiento.id_imagen == id_imagen)
        .first()
    )

    if not resultado or not os.path.exists(resultado.ruta_salida):
        raise HTTPException(status_code=404, detail="Imagen no disponible")

    return FileResponse(
        resultado.ruta_salida,
        filename=os.path.basename(resultado.ruta_salida),
    )


# =========================
# NODOS WORKERS
# =========================

@router.get("/nodos")
def listar_nodos(db: Session = Depends(get_db)):
    nodos = db.query(NodoWorker).order_by(NodoWorker.ultima_actividad.desc()).all()
    return [
        {
            "id_nodo": n.id_nodo,
            "nombre": n.nombre,
            "direccion_ip": n.direccion_ip,
            "estado": n.estado,
            "capacidad": n.capacidad,
            "ultima_actividad": str(n.ultima_actividad) if n.ultima_actividad else None,
        }
        for n in nodos
    ]


# =========================
# LOGS
# =========================

@router.get("/logs")
def listar_logs(
    nivel: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(LogProcesamiento)
    if nivel:
        query = query.filter(LogProcesamiento.nivel == nivel.upper())
    logs = query.order_by(LogProcesamiento.fecha.desc()).limit(200).all()
    return [
        {
            "id_log": l.id_log,
            "id_imagen": l.id_imagen,
            "id_nodo": l.id_nodo,
            "mensaje": l.mensaje,
            "nivel": l.nivel,
            "fecha": str(l.fecha),
        }
        for l in logs
    ]


@router.get("/logs/{id_solicitud}")
def listar_logs_solicitud(
    id_solicitud: int,
    db: Session = Depends(get_db),
):
    ids_imagenes = [
        i.id_imagen
        for i in db.query(Imagen.id_imagen)
        .filter(Imagen.id_solicitud == id_solicitud)
        .all()
    ]

    if not ids_imagenes:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    logs = (
        db.query(LogProcesamiento)
        .filter(LogProcesamiento.id_imagen.in_(ids_imagenes))
        .order_by(LogProcesamiento.fecha.asc())
        .all()
    )

    return [
        {
            "id_log": l.id_log,
            "id_imagen": l.id_imagen,
            "id_nodo": l.id_nodo,
            "mensaje": l.mensaje,
            "nivel": l.nivel,
            "fecha": str(l.fecha),
        }
        for l in logs
    ]


# =========================
# MÉTRICAS
# =========================

@router.get("/metricas")
def obtener_metricas(db: Session = Depends(get_db)):

    total_solicitudes = db.query(Solicitud).count()

    solicitudes_completadas = (
        db.query(Solicitud)
        .filter(Solicitud.estado.in_(["completado", "completado_con_errores"]))
        .count()
    )

    solicitudes_en_proceso = (
        db.query(Solicitud)
        .filter(Solicitud.estado == "procesando")
        .count()
    )

    solicitudes_pendientes = (
        db.query(Solicitud)
        .filter(Solicitud.estado == "pendiente")
        .count()
    )

    solicitudes_con_error = (
        db.query(Solicitud)
        .filter(Solicitud.estado == "error")
        .count()
    )

    total_imagenes = db.query(Imagen).count()

    imagenes_procesadas = (
        db.query(Imagen)
        .filter(Imagen.estado_procesamiento == "completado")
        .count()
    )

    imagenes_con_error = (
        db.query(Imagen)
        .filter(Imagen.estado_procesamiento == "error")
        .count()
    )

    imagenes_en_proceso = (
        db.query(Imagen)
        .filter(Imagen.estado_procesamiento == "procesando")
        .count()
    )

    total_nodos = db.query(NodoWorker).count()

    nodos_activos = (
        db.query(NodoWorker)
        .filter(NodoWorker.estado == "activo")
        .count()
    )

    nodos_ocupados = (
        db.query(NodoWorker)
        .filter(NodoWorker.estado == "ocupado")
        .count()
    )

    total_logs = db.query(LogProcesamiento).count()

    logs_error = (
        db.query(LogProcesamiento)
        .filter(LogProcesamiento.nivel == "ERROR")
        .count()
    )

    mem = psutil.virtual_memory()

    return {
        "solicitudes": {
            "total": total_solicitudes,
            "completadas": solicitudes_completadas,
            "en_proceso": solicitudes_en_proceso,
            "pendientes": solicitudes_pendientes,
            "con_error": solicitudes_con_error,
        },
        "imagenes": {
            "total": total_imagenes,
            "procesadas": imagenes_procesadas,
            "en_proceso": imagenes_en_proceso,
            "con_error": imagenes_con_error,
        },
        "nodos": {
            "total": total_nodos,
            "activos": nodos_activos,
            "ocupados": nodos_ocupados,
        },
        "logs": {
            "total": total_logs,
            "errores": logs_error,
        },
        "sistema": {
            "cpu_porcentaje": psutil.cpu_percent(interval=0.5),
            "memoria_total_mb": round(mem.total / 1024 / 1024),
            "memoria_usada_mb": round(mem.used  / 1024 / 1024),
            "memoria_porcentaje": mem.percent,
        },
    }