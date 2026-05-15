from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from api.database import Base

class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)


class Solicitud(Base):
    __tablename__ = "solicitud"

    id_solicitud = Column(Integer, primary_key=True, index=True)
    fecha_solicitud = Column(DateTime, default=datetime.utcnow)
    estado = Column(String(50), default="pendiente")  # pendiente, procesando, completado, error
    total_imagenes = Column(Integer, default=0)
    fecha_fin = Column(DateTime, nullable=True)

    imagenes = relationship("Imagen", back_populates="solicitud")


class NodoWorker(Base):
    __tablename__ = "nodo_worker"

    id_nodo = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=True)
    direccion_ip = Column(String(100))
    estado = Column(String(50), default="activo")  # activo, inactivo, ocupado, error
    capacidad = Column(Integer, default=4)
    ultima_actividad = Column(DateTime, default=datetime.utcnow)

    imagenes = relationship("Imagen", back_populates="nodo")
    logs = relationship("LogProcesamiento", back_populates="nodo")


class Transformacion(Base):
    __tablename__ = "transformacion"

    id_transformacion = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    descripcion = Column(Text, nullable=True)

    imagen_transformaciones = relationship("ImagenTransformacion", back_populates="transformacion")


class Imagen(Base):
    __tablename__ = "imagen"

    id_imagen = Column(Integer, primary_key=True, index=True)
    id_solicitud = Column(Integer, ForeignKey("solicitud.id_solicitud"))
    id_nodo = Column(Integer, ForeignKey("nodo_worker.id_nodo"), nullable=True)
    nombre_archivo = Column(String(255))
    ruta_archivo = Column(String(500))
    estado_procesamiento = Column(String(50), default="pendiente")  # pendiente, procesando, completado, error
    fecha_procesamiento = Column(DateTime, nullable=True)

    solicitud = relationship("Solicitud", back_populates="imagenes")
    nodo = relationship("NodoWorker", back_populates="imagenes")
    transformaciones = relationship("ImagenTransformacion", back_populates="imagen")
    resultado = relationship("ResultadoProcesamiento", back_populates="imagen", uselist=False)
    logs = relationship("LogProcesamiento", back_populates="imagen")


class ImagenTransformacion(Base):
    __tablename__ = "imagen_transformacion"

    id = Column(Integer, primary_key=True, index=True)
    id_imagen = Column(Integer, ForeignKey("imagen.id_imagen"))
    id_transformacion = Column(Integer, ForeignKey("transformacion.id_transformacion"))
    orden = Column(Integer, default=1)
    parametros = Column(Text, nullable=True)  # JSON string con parámetros opcionales

    imagen = relationship("Imagen", back_populates="transformaciones")
    transformacion = relationship("Transformacion", back_populates="imagen_transformaciones")


class ResultadoProcesamiento(Base):
    __tablename__ = "resultado_procesamiento"

    id_resultado = Column(Integer, primary_key=True, index=True)
    id_imagen = Column(Integer, ForeignKey("imagen.id_imagen"))
    ruta_salida = Column(String(500))
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    tipo_formato = Column(String(20), default="JPEG")
    tamanio_archivo = Column(Integer, nullable=True)
    estado = Column(String(50), default="disponible")

    imagen = relationship("Imagen", back_populates="resultado")


class LogProcesamiento(Base):
    __tablename__ = "log_procesamiento"

    id_log = Column(Integer, primary_key=True, index=True)
    id_imagen = Column(Integer, ForeignKey("imagen.id_imagen"), nullable=True)
    id_nodo = Column(Integer, ForeignKey("nodo_worker.id_nodo"), nullable=True)
    mensaje = Column(Text)
    nivel = Column(String(20), default="INFO")  # INFO, WARNING, ERROR
    fecha = Column(DateTime, default=datetime.utcnow)

    imagen = relationship("Imagen", back_populates="logs")
    nodo = relationship("NodoWorker", back_populates="logs")