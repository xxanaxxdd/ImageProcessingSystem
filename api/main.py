import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from api.routes import router
from api.database import Base, engine, SessionLocal
from models.models import Transformacion
from models.models import Usuario
from api.auth import hash_password


def seed_transformaciones(db):
    """Inserta las transformaciones disponibles si la tabla está vacía."""
    if db.query(Transformacion).count() > 0:
        return
    defaults = [
        Transformacion(nombre="escala_grises",      descripcion="Convierte la imagen a escala de grises"),
        Transformacion(nombre="redimensionar",       descripcion="Cambia el tamaño. Params: ancho, alto"),
        Transformacion(nombre="rotar",               descripcion="Rota la imagen. Params: angulo (grados)"),
        Transformacion(nombre="voltear_horizontal",  descripcion="Voltea la imagen horizontalmente"),
        Transformacion(nombre="voltear_vertical",    descripcion="Voltea la imagen verticalmente"),
        Transformacion(nombre="recortar",            descripcion="Recorta la imagen. Params: izquierda, superior, derecha, inferior"),
        Transformacion(nombre="brillo",              descripcion="Ajusta el brillo. Params: factor (default 1.5)"),
        Transformacion(nombre="contraste",           descripcion="Ajusta el contraste. Params: factor (default 1.5)"),
        Transformacion(nombre="nitidez",             descripcion="Aumenta la nitidez. Params: factor (default 2.0)"),
        Transformacion(nombre="desenfoque",          descripcion="Aplica desenfoque gaussiano. Params: radio (default 2.0)"),
        Transformacion(nombre="convertir_formato",   descripcion="Cambia el formato de salida. Params: formato (JPEG, PNG, WEBP)"),
        Transformacion(nombre="marca_agua", descripcion="Inserta texto como marca de agua. Params: texto, posicion"),    
    ]
    for t in defaults:
        db.add(t)
    db.commit()

def seed_usuario(db):
    """Crea usuario admin si no existe."""
    
    usuario = (
        db.query(Usuario)
        .filter(Usuario.username == "admin")
        .first()
    )

    if usuario:
        return

    nuevo_usuario = Usuario(
        username="admin",
        password=hash_password("1234")
    )

    db.add(nuevo_usuario)
    db.commit()


def _migrar_columnas():
    """Añade columnas nuevas a tablas existentes sin romper datos previos."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE nodo_worker ADD COLUMN nombre VARCHAR(100)"))
            conn.commit()
        except Exception:
            pass  # columna ya existe


@asynccontextmanager
async def lifespan(app: FastAPI):
    for intento in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as e:
            print(f"[DB] Intento {intento + 1}/10 fallido: {e}")
            time.sleep(3)
    _migrar_columnas()
    db = SessionLocal()
    try:
        seed_transformaciones(db)
        #seed_usuario(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Sistema Distribuido de Procesamiento de Imágenes",
    description="API para enviar lotes de imágenes con transformaciones configurables distribuidas entre workers Celery.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return RedirectResponse(url="/ui/login.html")


app.mount("/ui", StaticFiles(directory="frontend", html=True), name="frontend")