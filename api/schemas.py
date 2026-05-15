from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ── Transformaciones ─────────────────────────────────────────────────
class TransformacionItem(BaseModel):
    id_transformacion: int
    orden: int = 1
    parametros: Optional[dict] = {}


# ── Crear solicitud ──────────────────────────────────────────────────
class CrearSolicitudResponse(BaseModel):
    id_solicitud: int
    mensaje: str
    total_imagenes: int


# ── Estado de solicitud ──────────────────────────────────────────────
class ImagenEstado(BaseModel):
    id_imagen: int
    nombre_archivo: str
    estado_procesamiento: str
    fecha_procesamiento: Optional[datetime] = None

    class Config:
        from_attributes = True


class EstadoSolicitudResponse(BaseModel):
    id_solicitud: int
    estado: str
    total_imagenes: int
    fecha_solicitud: datetime
    fecha_fin: Optional[datetime] = None
    progreso: str
    imagenes: List[ImagenEstado]

    class Config:
        from_attributes = True


# ── Resultados ───────────────────────────────────────────────────────
class ResultadoItem(BaseModel):
    id_imagen: int
    nombre_archivo: str
    estado_procesamiento: str
    ruta_salida: Optional[str] = None
    tipo_formato: Optional[str] = None
    tamanio_archivo: Optional[int] = None
    fecha_generacion: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResultadosSolicitudResponse(BaseModel):
    id_solicitud: int
    estado: str
    resultados: List[ResultadoItem]


# ── Nodos worker ─────────────────────────────────────────────────────
class NodoWorkerResponse(BaseModel):
    id_nodo: int
    direccion_ip: str
    estado: str
    capacidad: int
    ultima_actividad: datetime

    class Config:
        from_attributes = True


# ── Logs ─────────────────────────────────────────────────────────────
class LogItem(BaseModel):
    id_log: int
    id_imagen: Optional[int] = None
    id_nodo: Optional[int] = None
    mensaje: str
    nivel: str
    fecha: datetime

    class Config:
        from_attributes = True


# ── Transformaciones disponibles ─────────────────────────────────────
class TransformacionResponse(BaseModel):
    id_transformacion: int
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True