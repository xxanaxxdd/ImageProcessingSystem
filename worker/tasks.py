import json
import socket
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from worker.celery_worker import celery, WORKER_THREADS
from utils.image_processing import procesar_imagen
from api.database import SessionLocal
from models.models import (
    Imagen, ResultadoProcesamiento, LogProcesamiento,
    NodoWorker, ImagenTransformacion, Transformacion, Solicitud,
)


def _detectar_ip_red() -> str:
    ip = os.getenv("NODO_IP")
    if ip:
        return ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


def _obtener_o_crear_nodo(db) -> NodoWorker:
    hostname = socket.gethostname()
    ip = _detectar_ip_red()
    nombre = os.getenv("NODO_NOMBRE", hostname)
    nodo = db.query(NodoWorker).filter(NodoWorker.direccion_ip == ip).first()
    if not nodo:
        nodo = NodoWorker(
            nombre=nombre,
            direccion_ip=ip,
            estado="activo",
            capacidad=WORKER_THREADS,
            ultima_actividad=datetime.now(timezone.utc),
        )
        db.add(nodo)
        db.commit()
        db.refresh(nodo)
    else:
        nodo.nombre = nombre
        nodo.estado = "activo"
        nodo.ultima_actividad = datetime.now(timezone.utc)
        db.commit()
    return nodo


def _registrar_log(db, id_imagen, id_nodo, mensaje, nivel="INFO"):
    log = LogProcesamiento(
        id_imagen=id_imagen,
        id_nodo=id_nodo,
        mensaje=mensaje,
        nivel=nivel,
        fecha=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()


def _actualizar_estado_solicitud(db, id_solicitud: int):
    solicitud = db.query(Solicitud).filter(Solicitud.id_solicitud == id_solicitud).first()
    if not solicitud:
        return
    imagenes = db.query(Imagen).filter(Imagen.id_solicitud == id_solicitud).all()
    estados = [i.estado_procesamiento for i in imagenes]
    if all(e == "completado" for e in estados):
        solicitud.estado = "completado"
        solicitud.fecha_fin = datetime.now(timezone.utc)
    elif any(e == "error" for e in estados) and all(e in ("completado", "error") for e in estados):
        solicitud.estado = "completado_con_errores"
        solicitud.fecha_fin = datetime.now(timezone.utc)
    db.commit()


def _procesar_una_imagen(id_imagen: int, id_nodo: int) -> dict:
    db = SessionLocal()
    try:
        imagen = db.query(Imagen).filter(Imagen.id_imagen == id_imagen).first()
        if not imagen:
            raise ValueError(f"Imagen {id_imagen} no encontrada.")

        imagen.id_nodo = id_nodo
        imagen.estado_procesamiento = "procesando"
        imagen.fecha_procesamiento = datetime.now(timezone.utc)
        db.commit()

        _registrar_log(db, id_imagen, id_nodo, f"Iniciando: {imagen.nombre_archivo}")

        imagen_trans = (
            db.query(ImagenTransformacion)
            .filter(ImagenTransformacion.id_imagen == id_imagen)
            .order_by(ImagenTransformacion.orden)
            .all()
        )

        transformaciones = []
        for it in imagen_trans:
            t = db.query(Transformacion).filter(
                Transformacion.id_transformacion == it.id_transformacion
            ).first()
            if t:
                params = {}
                if it.parametros:
                    try:
                        params = json.loads(it.parametros)
                    except Exception:
                        params = {}
                transformaciones.append({
                    "nombre": t.nombre,
                    "orden": it.orden,
                    "parametros": params,
                })

        resultado = procesar_imagen(imagen.ruta_archivo, transformaciones, id_imagen=id_imagen)

        res = ResultadoProcesamiento(
            id_imagen=id_imagen,
            ruta_salida=resultado["ruta_salida"],
            fecha_generacion=datetime.now(timezone.utc),
            tipo_formato=resultado["formato"],
            tamanio_archivo=resultado["tamanio"],
            estado="disponible",
        )
        db.add(res)
        imagen.estado_procesamiento = "completado"
        db.commit()

        _registrar_log(db, id_imagen, id_nodo, f"Completado: {resultado['ruta_salida']}")
        return {"id_imagen": id_imagen, "status": "ok", "ruta_salida": resultado["ruta_salida"]}

    except Exception as exc:
        db.rollback()
        imagen = db.query(Imagen).filter(Imagen.id_imagen == id_imagen).first()
        if imagen:
            imagen.estado_procesamiento = "error"
            db.commit()
        _registrar_log(db, id_imagen, id_nodo, f"Error: {str(exc)}", nivel="ERROR")
        raise

    finally:
        db.close()


@celery.task(bind=True, max_retries=3)
def procesar_lote_task(self, id_solicitud: int, ids_imagen: list):
    db = SessionLocal()
    id_nodo = None
    try:
        nodo = _obtener_o_crear_nodo(db)
        nodo.estado = "ocupado"
        solicitud = db.query(Solicitud).filter(Solicitud.id_solicitud == id_solicitud).first()
        if solicitud:
            solicitud.estado = "procesando"
        db.commit()
        id_nodo = nodo.id_nodo
    finally:
        db.close()

    resultados = []
    errores = []

    try:
        with ThreadPoolExecutor(max_workers=WORKER_THREADS) as executor:
            futures = {
                executor.submit(_procesar_una_imagen, id_imagen, id_nodo): id_imagen
                for id_imagen in ids_imagen
            }
            for future in as_completed(futures):
                id_imagen = futures[future]
                try:
                    resultados.append(future.result())
                except Exception as exc:
                    errores.append({"id_imagen": id_imagen, "error": str(exc)})

        db = SessionLocal()
        try:
            _actualizar_estado_solicitud(db, id_solicitud)
        finally:
            db.close()

        return {
            "id_solicitud": id_solicitud,
            "procesadas": len(resultados),
            "errores": len(errores),
        }

    except Exception as exc:
        if id_nodo:
            db = SessionLocal()
            try:
                nodo_db = db.query(NodoWorker).filter(NodoWorker.id_nodo == id_nodo).first()
                if nodo_db:
                    nodo_db.estado = "error"
                    nodo_db.ultima_actividad = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        raise self.retry(exc=exc, countdown=5)

    finally:
        if id_nodo:
            db = SessionLocal()
            try:
                nodo_db = db.query(NodoWorker).filter(NodoWorker.id_nodo == id_nodo).first()
                if nodo_db and nodo_db.estado != "error":
                    nodo_db.estado = "activo"
                    nodo_db.ultima_actividad = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
