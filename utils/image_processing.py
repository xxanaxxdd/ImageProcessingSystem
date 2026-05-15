from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont
import os
import json

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def aplicar_transformacion(img: Image.Image, nombre: str, parametros: dict) -> Image.Image:

    nombre = nombre.lower()

    if nombre == "escala_grises":
        return img.convert("L").convert("RGB")

    elif nombre == "redimensionar":
        ancho = int(parametros.get("ancho", img.width))
        alto = int(parametros.get("alto", img.height))
        return img.resize((ancho, alto), Image.LANCZOS)

    elif nombre == "rotar":
        angulo = float(parametros.get("angulo", 90))
        return img.rotate(angulo, expand=True)

    elif nombre == "voltear_horizontal":
        return img.transpose(Image.FLIP_LEFT_RIGHT)

    elif nombre == "voltear_vertical":
        return img.transpose(Image.FLIP_TOP_BOTTOM)

    elif nombre == "recortar":
        izquierda = int(parametros.get("izquierda", 0))
        superior = int(parametros.get("superior", 0))
        derecha = int(parametros.get("derecha", img.width))
        inferior = int(parametros.get("inferior", img.height))
        return img.crop((izquierda, superior, derecha, inferior))

    elif nombre == "brillo":
        factor = float(parametros.get("factor", 1.5))
        return ImageEnhance.Brightness(img).enhance(factor)

    elif nombre == "contraste":
        factor = float(parametros.get("factor", 1.5))
        return ImageEnhance.Contrast(img).enhance(factor)

    elif nombre == "nitidez":
        factor = float(parametros.get("factor", 2.0))
        return ImageEnhance.Sharpness(img).enhance(factor)

    elif nombre == "desenfoque":
        radio = float(parametros.get("radio", 2.0))
        return img.filter(ImageFilter.GaussianBlur(radius=radio))

    # =========================
    # MARCA DE AGUA MEJORADA
    # =========================

    elif nombre == "marca_agua":

        texto = parametros.get("texto", "Ana Afanador :D")
        posicion = parametros.get("posicion", "centro")

        width, height = img.size

        font_size = max(40, int(width * 0.06))

        rutas_fuente = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "arial.ttf",
        ]

        font = None
        for ruta in rutas_fuente:
            try:
                font = ImageFont.truetype(ruta, font_size)
                break
            except Exception:
                continue

        if font is None:
            font = ImageFont.load_default()

        # Crear capa transparente
        watermark = Image.new("RGBA", img.size)
        draw = ImageDraw.Draw(watermark)

        bbox = draw.textbbox((0, 0), texto, font=font)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if posicion == "centro":
            x = (width - text_width) / 2
            y = (height - text_height) / 2

        elif posicion == "arriba":
            x = (width - text_width) / 2
            y = 10

        elif posicion == "abajo":
            x = (width - text_width) / 2
            y = height - text_height - 10

        elif posicion == "izquierda":
            x = 10
            y = (height - text_height) / 2

        elif posicion == "derecha":
            x = width - text_width - 10
            y = (height - text_height) / 2

        else:
            x = (width - text_width) / 2
            y = (height - text_height) / 2

        # Texto blanco semi-transparente
        draw.text(
            (x, y),
            texto,
            font=font,
            fill=(255, 255, 255, 180)
        )

        img = img.convert("RGBA")
        img = Image.alpha_composite(img, watermark)
        img = img.convert("RGB")

        return img

    elif nombre == "convertir_formato":
        return img

    else:
        raise ValueError(f"Transformación desconocida: {nombre}")


def procesar_imagen(ruta_entrada: str, transformaciones: list, id_imagen: int = None) -> dict:

    img = Image.open(ruta_entrada).convert("RGB")

    transformaciones_ordenadas = sorted(
        transformaciones,
        key=lambda t: t.get("orden", 1)
    )

    formato_salida = "JPEG"

    for t in transformaciones_ordenadas:

        nombre = t["nombre"]
        params = t.get("parametros", {})

        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}

        if nombre.lower() == "convertir_formato":
            formato_salida = params.get(
                "formato",
                "JPEG"
            ).upper()
            continue

        img = aplicar_transformacion(
            img,
            nombre,
            params
        )

    base = os.path.splitext(
        os.path.basename(ruta_entrada)
    )[0]

    extension = (
        "jpg"
        if formato_salida == "JPEG"
        else formato_salida.lower()
    )

    prefix = (
        f"{id_imagen}_"
        if id_imagen is not None
        else ""
    )

    nombre_salida = (
        f"result_{prefix}{base}.{extension}"
    )

    ruta_salida = os.path.join(
        RESULTS_DIR,
        nombre_salida
    )

    img.save(
        ruta_salida,
        format=formato_salida
    )

    tamanio = os.path.getsize(
        ruta_salida
    )

    return {
        "ruta_salida": ruta_salida,
        "formato": formato_salida,
        "tamanio": tamanio,
    }