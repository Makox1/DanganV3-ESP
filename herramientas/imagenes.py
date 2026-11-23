"""Traduccion de texturas con texto (menus, titulos de capitulo, etc.).

Uso:
    python imagenes.py vista       Genera imagenes/vista/*.png para revisar a ojo

Las traducciones y estilos estan en traduccion/imagenes.json:
    {"flash/title/title_new_load_US.spc": {
        "kanban_title_new_US.png": {"texto": "NUEVA PARTIDA", "fuente": "impact.ttf", ...}}}

Campos de estilo (todos opcionales salvo "texto"):
    fuente        archivo en C:/Windows/Fonts o "juego" (fuente del juego con tildes)
    color         [r, g, b]; por defecto, el color dominante del original
    borde         grosor del contorno en px (0 = sin contorno)
    color_borde   [r, g, b]
    alinear       "izquierda" | "centro" | "derecha" (respecto al texto original)
    inclinacion   inclinacion horizontal (cursiva), p. ej. 0.15
    rotacion      grados
    margen_alto   factor sobre el alto del texto original (1.0 = mismo alto)
    brillo        radio del halo luminoso en px (letreros de neon), 0 = sin halo
    color_brillo  [r, g, b] del halo; por defecto, el color del texto
    acabado_original mide la tinta opaca y toma los colores de tinta/halo del original
    intensidad_brillo multiplicador de alfa del halo (acabado_original; 1.25 por defecto)
    El texto puede tener varias lineas separadas por "\n" (se centran).

Carteles con dibujo (el texto forma parte del arte): ver generar_cartel.
Rotulos de varios colores: capas [{nombre, pos}] reutiliza adornos del mismo SRD;
textos [{texto, fuente, color, alto, ancho_max, pos}] coloca cada tramo encima.
"""
import json
import os
import sys

import etcpak
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import srd
from config import RAIZ

CARPETA_FUENTES = r"C:\Windows\Fonts"
RUTA_CONFIG = os.path.join(RAIZ, "traduccion", "imagenes.json")
TAM_BASE = 160
# Texturas ya generadas para el instalador: no dependen de las fuentes de Windows
# (Rockwell y Agency FB vienen con Office). GUARDAR las escribe al aplicar el parche.
CARPETA_PREGENERADAS = os.environ.get("DRV3_PREGENERADAS")
GUARDAR_PREGENERADAS = os.environ.get("DRV3_GUARDAR_PREGENERADAS")


def cargar_config():
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        return json.load(f)


def color_dominante(img):
    a = np.array(img)
    opacos = a[a[..., 3] > 200][:, :3]
    if len(opacos) == 0:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(opacos, axis=0))


def dibujar_ttf(texto, estilo, color):
    fuente = ImageFont.truetype(os.path.join(CARPETA_FUENTES, estilo.get("fuente", "arial.ttf")), TAM_BASE)
    if estilo.get("espaciado"):
        separacion = float(estilo["espaciado"])
        lineas = texto.split("\n")
        anchuras = [fuente.getlength(linea) + max(0, len(linea)-1) * separacion for linea in lineas]
        arriba = min(fuente.getbbox(linea)[1] for linea in lineas)
        abajo = max(fuente.getbbox(linea)[3] for linea in lineas)
        paso = abajo - arriba + 16
        lienzo = Image.new("RGBA", (int(np.ceil(max(anchuras)))+24, paso*len(lineas)+24))
        dib = ImageDraw.Draw(lienzo)
        for fila, (linea, ancho) in enumerate(zip(lineas, anchuras)):
            x = 12 + (max(anchuras)-ancho)/2
            for letra in linea:
                dib.text((x, 12-arriba+fila*paso), letra, font=fuente, fill=tuple(color)+(255,))
                x += fuente.getlength(letra) + separacion
        return lienzo
    borde = int(estilo.get("borde", 0)) * 4
    dib = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    caja = [int(v) for v in dib.multiline_textbbox((0, 0), texto, font=fuente, stroke_width=borde,
                                                   align="center")]
    lienzo = Image.new("RGBA", (caja[2] - caja[0] + 20, caja[3] - caja[1] + 20), (0, 0, 0, 0))
    dib = ImageDraw.Draw(lienzo)
    dib.multiline_text((10 - caja[0], 10 - caja[1]), texto, font=fuente, fill=tuple(color) + (255,),
                       stroke_width=borde, align="center",
                       stroke_fill=tuple(estilo.get("color_borde", [0, 0, 0])) + (255,))
    return lienzo


def con_brillo(texto, estilo, color):
    """Anade un halo difuso detras del texto (letreros de neon)."""
    from PIL import ImageFilter
    radio = int(estilo.get("brillo", 0))
    if not radio:
        return texto
    margen = radio * 2
    lienzo = Image.new("RGBA", (texto.width + 2 * margen, texto.height + 2 * margen), (0, 0, 0, 0))
    lienzo.alpha_composite(texto, (margen, margen))
    halo_alfa = lienzo.getchannel("A").filter(ImageFilter.GaussianBlur(radio))
    halo_alfa = halo_alfa.point(lambda v: min(255, v * 2))
    halo = Image.new("RGBA", lienzo.size, tuple(estilo.get("color_brillo", color)) + (0,))
    halo.putalpha(halo_alfa)
    halo.alpha_composite(lienzo)
    return halo


def dibujar_juego(texto, color):
    """Usa la fuente del propio juego (con los glifos en espanol)."""
    import fuente as modulo_fuente
    from revisar import cargar_fuente
    f = cargar_fuente()
    if not hasattr(dibujar_juego, "atlas"):
        # cargar_fuente solo anade metricas; aqui hacen falta los pixeles
        from cpk import CPK
        from spc import SPC
        from config import CPK_RESIDENTE, SPC_RESIDENTE, respaldo_cabecera
        cpk = CPK(CPK_RESIDENTE, respaldo_cabecera(CPK_RESIDENTE))
        archivo = next(a for a in cpk.archivos if a["nombre"] == SPC_RESIDENTE)
        spc = SPC(cpk.leer(archivo))
        f = modulo_fuente.Fuente(spc.buscar("v3_font00.stx").datos, spc.buscar("v3_font00.srdv").datos)
        f.agregar(modulo_fuente.crear_glifos_espanol(f))
        dibujar_juego.atlas = f
    mascara = modulo_fuente.renderizar(dibujar_juego.atlas, texto)
    lienzo = Image.new("RGBA", (mascara.shape[1], mascara.shape[0]), tuple(color) + (0,))
    lienzo.putalpha(Image.fromarray(mascara))
    return lienzo


def dibujar(cadena, estilo, color):
    """Dibuja una cadena con el estilo (fuente, cursiva, rotacion) recortada a su tinta."""
    if estilo.get("fuente", "").startswith("original:"):
        from rotulos_originales import renderizar
        texto = renderizar(cadena, estilo["fuente"].split(":", 1)[1], color)
    elif estilo.get("fuente") == "juego":
        texto = dibujar_juego(cadena, color)
    else:
        texto = dibujar_ttf(cadena, estilo, color)
    texto = texto.crop(texto.getchannel("A").getbbox())
    if estilo.get("inclinacion"):
        k = float(estilo["inclinacion"])
        extra = int(abs(k) * texto.height)
        texto = texto.transform((texto.width + extra, texto.height), Image.AFFINE,
                                (1, k, -extra if k > 0 else 0, 0, 1, 0), Image.BICUBIC)
    if estilo.get("rotacion"):
        texto = texto.rotate(float(estilo["rotacion"]), Image.BICUBIC, expand=True)
    return texto.crop(texto.getchannel("A").getbbox())


def borrar_texto(original, zonas, tinta, umbral, dilatar):
    """Borra el texto de un cartel reconstruyendo el fondo con inpainting de OpenCV.

    zonas: poligonos [[x, y], ...] donde esta el texto.
    tinta: "oscura" (texto mas oscuro que el fondo) o "clara".
    """
    import cv2
    a = np.array(original)
    rgb = np.ascontiguousarray(a[..., :3])
    luz = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    dentro = np.zeros(luz.shape, np.uint8)
    for zona in zonas:
        cv2.fillPoly(dentro, [np.array(zona, np.int32)], 255)
    if tinta == "clara":
        mascara = (luz > umbral).astype(np.uint8) * 255
    else:
        mascara = (luz < umbral).astype(np.uint8) * 255
    mascara &= dentro
    if dilatar:
        mascara = cv2.dilate(mascara, np.ones((2 * dilatar + 1, 2 * dilatar + 1), np.uint8))
        mascara &= dentro
    a[..., :3] = cv2.inpaint(rgb, mascara, 5, cv2.INPAINT_TELEA)
    return Image.fromarray(a)


def generar_cartel(original, estilo):
    """Cartel con dibujo: se borra el texto original y se dibujan los textos nuevos.

    Campos: borrar (poligonos), tinta, umbral, dilatar y textos, una lista de
    {texto, en, fuente, color, borde, color_borde, rotacion, inclinacion,
     centro: [x, y], alto (px del texto ingles de referencia), ancho_max}.
    """
    if estilo.get("mascara_borrar"):
        import cv2
        mascara = Image.open(os.path.join(RAIZ, estilo["mascara_borrar"])).convert("L")
        if mascara.size != original.size:
            raise ValueError("La mascara del cartel tiene otro tamano")
        a = np.array(original)
        a[..., :3] = cv2.inpaint(np.ascontiguousarray(a[..., :3]), np.array(mascara), 4, cv2.INPAINT_TELEA)
        resultado = Image.fromarray(a)
    else:
        resultado = borrar_texto(original, estilo["borrar"], estilo.get("tinta", "oscura"),
                                 int(estilo.get("umbral", 100)), int(estilo.get("dilatar", 2)))
    for t in estilo["textos"]:
        color = t.get("color", [0, 0, 0])
        # Se mide y escala sin rotar (la rotacion infla el alto de los textos largos)
        recto = {k: v for k, v in t.items() if k != "rotacion"}
        texto = dibujar(t["texto"], recto, color)
        escala = float(t["alto"]) / dibujar(t.get("en", t["texto"]), recto, color).height
        alto = max(1, int(texto.height * escala))
        ancho = max(1, int(texto.width * escala))
        if t.get("ancho_max") and ancho > t["ancho_max"]:
            if t.get("ajuste_uniforme"):
                alto = max(1, round(alto * t["ancho_max"] / ancho))
            ancho = int(t["ancho_max"])
        texto = texto.resize((ancho, alto), Image.LANCZOS)
        if t.get("rotacion"):
            texto = texto.rotate(float(t["rotacion"]), Image.BICUBIC, expand=True)
            ancho, alto = texto.size
        cx, cy = t["centro"]
        resultado.alpha_composite(texto, (int(cx - ancho / 2), int(cy - alto / 2)))
    return resultado


def generar(original, estilo):
    """Devuelve una imagen RGBA del mismo tamano que el original con el texto traducido."""
    if estilo.get("imagen_traducida"):
        with Image.open(os.path.join(RAIZ, estilo["imagen_traducida"])) as archivo:
            nueva = archivo.convert("RGBA")
        if nueva.size != original.size:
            raise ValueError("La imagen traducida tiene otro tamano: " + estilo["imagen_traducida"])
        return nueva
    if "borrar" in estilo:
        return generar_cartel(original, estilo)
    if estilo.get("acabado_original"):
        return generar_acabado_original(original, estilo)
    # Algunas texturas (DXT1) tienen fondo negro opaco: la tinta se mide por brillo
    # y el fondo negro se conserva
    fondo_negro = np.array(original.getchannel("A")).min() > 200
    if fondo_negro:
        luz = original.convert("L")
        caja = luz.point(lambda v: 255 if v > 40 else 0).getbbox()
        a = np.array(original)
        claros = a[np.array(luz) > 128][:, :3]
        color_auto = tuple(int(v) for v in np.median(claros, axis=0)) if len(claros) else (255, 255, 255)
    else:
        caja = original.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        color_auto = None
    if caja is None:
        caja = (0, 0, original.width, original.height)
    color = estilo.get("color") or color_auto or color_dominante(original)
    texto = dibujar(estilo["texto"], estilo, color)

    # Escala: la que hace coincidir el texto ingles ("en") con el original;
    # asi acentos y descendentes no cambian el tamano de letra
    alto_original = (caja[3] - caja[1]) * float(estilo.get("margen_alto", 1.0))
    if estilo.get("en"):
        escala = alto_original / dibujar(estilo["en"], estilo, color).height
    else:
        escala = alto_original / texto.height
    alto = max(1, int(texto.height * escala))
    ancho = max(1, int(texto.width * escala))
    maximo = original.width - 4 - 2 * (int(estilo.get("contorno_final", 0)) + (1 if estilo.get("contorno_final") else 0)) - 4 * int(estilo.get("sombra", 0))
    if ancho > maximo:
        if estilo.get("ajuste_uniforme"):
            alto = max(1, round(alto * maximo / ancho))
        ancho = maximo
    if alto > original.height - 4:
        # Textos rotados: se reduce todo para que no se corten arriba ni abajo
        factor = (original.height - 4) / alto
        alto, ancho = max(1, int(alto * factor)), max(1, int(ancho * factor))
    texto = texto.resize((ancho, alto), Image.Resampling.NEAREST if estilo.get("fuente") == "original:pixel" else Image.Resampling.LANCZOS)
    if estilo.get("desgaste_original") or estilo.get("contorno_final") or estilo.get("sombra"):
        from rotulos_originales import acabado
        texto = acabado(texto, original, estilo)
        ancho, alto = texto.size
    if estilo.get("brillo"):
        texto = con_brillo(texto, estilo, color)
        # El halo no debe salirse de la textura
        if texto.width > original.width or texto.height > original.height:
            factor = min(original.width / texto.width, original.height / texto.height)
            texto = texto.resize((max(1, int(texto.width * factor)), max(1, int(texto.height * factor))),
                                 Image.LANCZOS)
        ancho, alto = texto.size
        caja = (max(0, (caja[0] + caja[2] - ancho) // 2), max(0, (caja[1] + caja[3] - alto) // 2),
                min(original.width, (caja[0] + caja[2] + ancho) // 2),
                min(original.height, (caja[1] + caja[3] + alto) // 2))

    alinear = estilo.get("alinear", "centro")
    if alinear == "izquierda":
        x = caja[0]
    elif alinear == "derecha":
        x = caja[2] - ancho
    else:
        x = (caja[0] + caja[2]) // 2 - ancho // 2
    x = min(max(2, x), original.width - ancho - 2)
    y = caja[1] + (caja[3] - caja[1] - alto) // 2
    y = min(max(0, y), original.height - alto)
    resultado = Image.new("RGBA", original.size, (0, 0, 0, 255 if fondo_negro else 0))
    resultado.alpha_composite(texto, (x, y))
    return resultado


def generar_acabado_original(original, estilo):
    """Mide la tinta opaca sin confundir el halo con el cuerpo de las letras.

    Conserva la posicion y las proporciones del ingles de referencia. El halo se
    compone a resolucion final, con margen propio, sin encoger despues las letras.
    """
    from PIL import ImageFilter
    a = np.array(original)
    caja = original.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox()
    if caja is None or not estilo.get("en"):
        raise ValueError("acabado_original necesita tinta opaca y texto ingles de referencia")
    color = tuple(int(v) for v in np.median(a[a[..., 3] > 240, :3], axis=0))
    halo_pixeles = a[(a[..., 3] > 16) & (a[..., 3] < 100), :3]
    color_halo = tuple(int(v) for v in np.median(halo_pixeles, axis=0))
    referencia = dibujar(estilo["en"], estilo, color)
    texto = dibujar(estilo["texto"], estilo, color)
    escala_y = (caja[3] - caja[1]) / referencia.height
    escala_x = (caja[2] - caja[0]) / referencia.width
    radio = float(estilo.get("brillo", 4))
    margen = int(np.ceil(radio * 2))
    x = max(margen, caja[0])
    ancho = min(round(texto.width * escala_x), original.width - x - margen)
    alto = round(texto.height * escala_y)
    if alto > original.height - 2 * margen:
        raise ValueError("El texto y su halo no caben en la textura")
    alfa_texto = texto.getchannel("A").resize((max(1, ancho), max(1, alto)), Image.LANCZOS)
    texto = Image.new("RGBA", alfa_texto.size, color + (0,))
    texto.putalpha(alfa_texto)
    # Los acentos crecen hacia arriba; los descendentes conservan su linea base.
    fuente = ImageFont.truetype(os.path.join(CARPETA_FUENTES, estilo["fuente"]), TAM_BASE)
    dib = ImageDraw.Draw(Image.new("L", (1, 1)))
    arriba_en = dib.textbbox((0, 0), estilo["en"], font=fuente)[1]
    arriba_es = dib.textbbox((0, 0), estilo["texto"], font=fuente)[1]
    y = round(caja[1] + (arriba_es - arriba_en) * escala_y)
    y = max(margen, min(y, original.height - margen - alto))
    tinta = Image.new("RGBA", original.size)
    tinta.alpha_composite(texto, (x, y))
    alfa = tinta.getchannel("A").filter(ImageFilter.GaussianBlur(radio))
    fuerza = float(estilo.get("intensidad_brillo", 1.25))
    alfa = alfa.point(lambda v: min(255, round(v * fuerza)))
    resultado = Image.new("RGBA", original.size, color_halo + (0,))
    resultado.putalpha(alfa)
    resultado.alpha_composite(tinta)
    return resultado


PESOS_2BIT = (0, 21, 43, 64)


def bloque_bc7_modo5(color7, alfa, color_final=None, indices_color=None):
    """Bloque BC7 modo 5 con color constante y 16 valores de alfa (2 bits de indice).

    Con el color fijo, la mitad del bloque es identica en toda la textura y el SPC
    comprime mucho mejor que con un codificador generico.
    """
    amin, amax = int(min(alfa)), int(max(alfa))
    a0, a1 = amax, amin
    if a0 == a1:
        indices = [0] * 16
    else:
        niveles = [((64 - w) * a0 + w * a1 + 32) >> 6 for w in PESOS_2BIT]
        indices = [min(range(4), key=lambda k: abs(niveles[k] - v)) for v in alfa]
        if indices[0] >= 2:
            # El indice ancla (pixel 0) debe tener el bit alto en 0: se intercambian extremos
            a0, a1 = a1, a0
            indices = [3 - i for i in indices]
    valor = 0
    bit = 0

    def poner(v, n):
        nonlocal valor, bit
        valor |= (int(v) & ((1 << n) - 1)) << bit
        bit += n

    poner(1 << 5, 6)          # modo 5
    poner(0, 2)               # sin rotacion
    color_final = color7 if color_final is None else color_final
    indices_color = [0] * 16 if indices_color is None else list(indices_color)
    if indices_color[0] >= 2:
        color7, color_final = color_final, color7
        indices_color = [3 - i for i in indices_color]
    for c0, c1 in zip(color7, color_final):  # R0 R1 G0 G1 B0 B1
        poner(c0, 7)
        poner(c1, 7)
    poner(a0, 8)
    poner(a1, 8)
    poner(indices_color[0], 1)
    for i in indices_color[1:]:
        poner(i, 2)
    poner(indices[0], 1)
    for i in indices[1:]:
        poner(i, 2)
    return valor.to_bytes(16, "little")


def codificar_texto_bc7(img, color):
    """Codifica una imagen de texto de un solo color en BC7 modo 5."""
    ancho = (img.width + 3) // 4 * 4
    alto = (img.height + 3) // 4 * 4
    a = np.zeros((alto, ancho), np.uint8)
    a[:img.height, :img.width] = np.array(img.getchannel("A"))
    # Alfa casi transparente u opaco se redondea: no se nota y repite mas bloques
    a[a < 16] = 0
    a[a > 239] = 255
    color7 = [c >> 1 for c in color]
    salida = bytearray()
    cache = {}
    for by in range(alto // 4):
        for bx in range(ancho // 4):
            alfa = tuple(a[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4].reshape(16).tolist())
            if alfa not in cache:
                cache[alfa] = bloque_bc7_modo5(color7, alfa)
            salida += cache[alfa]
    return bytes(salida)


def codificar_halo_bc7(img, contorno=False):
    """BC7 modo 5: paleta compartida de tinta/halo y alfa independiente.

    Repetir los extremos de color permite comprimir el SPC sin eliminar el halo.
    Los cuatro tonos intermedios y el alfa se eligen por separado en cada bloque.
    """
    ancho, alto = (img.width + 3) // 4 * 4, (img.height + 3) // 4 * 4
    a = np.zeros((alto, ancho, 4), np.uint8)
    a[:img.height, :img.width] = np.array(img)
    # Los extremos min/max incluyen el ringing del remuestreo: exagerarian los
    # colores y harian visibles bandas dentro de los trazos opacos.
    halo = np.median(a[(a[..., 3] > 16) & (a[..., 3] < 80), :3], axis=0)
    tinta = np.median(a[a[..., 3] == 255, :3], axis=0)
    if contorno:
        visibles = a[a[..., 3] > 128, :3]
        halo, tinta = visibles.min(axis=0), visibles.max(axis=0)
    extremos = np.array([halo, tinta], dtype=np.int32) >> 1
    rgb = (extremos << 1) | (extremos >> 6)
    paleta = np.array([((64-w)*rgb[0] + w*rgb[1] + 32) >> 6 for w in PESOS_2BIT])
    dist = ((a[..., :3].astype(np.int32)[..., None, :] - paleta) ** 2).sum(axis=-1)
    indices = dist.argmin(axis=-1)
    indices[a[..., 3] < 16] = 0
    alfa = a[..., 3].copy()
    alfa[alfa < 8] = 0
    alfa[alfa > 247] = 255
    salida, cache = bytearray(), {}
    for y in range(0, alto, 4):
        for x in range(0, ancho, 4):
            valores = tuple(alfa[y:y+4, x:x+4].reshape(16).tolist())
            colores = tuple(indices[y:y+4, x:x+4].reshape(16).tolist())
            clave = (valores, colores)
            if clave not in cache:
                cache[clave] = bloque_bc7_modo5(extremos[0], valores, extremos[1], colores)
            salida += cache[clave]
    return bytes(salida)


def codificar_grises_bc7(img):
    """BC7 de tinta negra y halo blanco, con alfa independiente por bloque.

    Los extremos compartidos reducen el SPC sin cambiar las formas ni la paleta
    del rotulo. No se descartan los pixeles de alfa bajo de la sombra original.
    """
    ancho, alto = (img.width + 3) // 4 * 4, (img.height + 3) // 4 * 4
    a = np.zeros((alto, ancho, 4), np.uint8)
    a[:img.height, :img.width] = np.array(img)
    gris = np.rint(a[..., :3].astype(float).mean(axis=2)).astype(np.int32)
    niveles = np.array([0, 84, 171, 255], dtype=np.int32)
    indices = np.abs(gris[..., None] - niveles).argmin(axis=-1)
    indices[a[..., 3] == 0] = 0
    salida, cache = bytearray(), {}
    for y in range(0, alto, 4):
        for x in range(0, ancho, 4):
            alfa = tuple(a[y:y+4, x:x+4, 3].reshape(16).tolist())
            colores = tuple(indices[y:y+4, x:x+4].reshape(16).tolist())
            clave = (alfa, colores)
            if clave not in cache:
                cache[clave] = bloque_bc7_modo5([0, 0, 0], alfa, [127, 127, 127], colores)
            salida += cache[clave]
    return bytes(salida)


def codificar(img, formato):
    ancho = (img.width + 3) // 4 * 4
    alto = (img.height + 3) // 4 * 4
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    lienzo.paste(img, (0, 0))
    if srd.FORMATOS[formato] == "bc3":
        # El color de los pixeles transparentes no se ve: se iguala al del texto para
        # que los bloques de color se repitan y el SPC comprima mucho mejor
        a = np.array(lienzo)
        visibles = a[..., 3] > 0
        if visibles.any():
            a[~visibles, :3] = np.median(a[visibles][:, :3], axis=0).astype(np.uint8)
        lienzo = Image.fromarray(a)
    datos = lienzo.tobytes()
    if srd.FORMATOS[formato] == "bc7":
        return etcpak.compress_bc7(datos, ancho, alto)
    if srd.FORMATOS[formato] == "bc3":
        return etcpak.compress_bc3(datos, ancho, alto)
    return etcpak.compress_bc1(datos, ancho, alto)


def bloques_iguales(a, b, tolerancia=0):
    """Dos bloques 4x4 RGBA se ven igual si el alfa coincide y el color coincide donde no es transparente.

    tolerancia: diferencia maxima por canal (0-255) que se sigue considerando igual."""
    if tolerancia:
        return int(np.abs(a.astype(int) - b.astype(int)).max()) <= tolerancia
    if not np.array_equal(a[..., 3], b[..., 3]):
        return False
    visibles = a[..., 3] > 0
    return np.array_equal(a[..., :3][visibles], b[..., :3][visibles])


def conservar_bloques(original_bc, nuevo_bc, original_img, nueva_img, formato, tolerancia=0):
    """Copia los bloques originales donde la imagen no cambio.

    El codificador genera bloques distintos aunque los pixeles sean iguales, y eso
    hace que el SPC comprima peor y no quepa en su hueco del CPK.
    tolerancia: ver bloques_iguales ("tolerancia_bloques" en imagenes.json).
    """
    tam_bloque = 16 if srd.FORMATOS[formato] == "bc7" else 8
    ancho = (nueva_img.width + 3) // 4 * 4
    alto = (nueva_img.height + 3) // 4 * 4
    a = np.zeros((alto, ancho, 4), np.uint8)
    b = np.zeros((alto, ancho, 4), np.uint8)
    a[:original_img.height, :original_img.width] = np.array(original_img)
    b[:nueva_img.height, :nueva_img.width] = np.array(nueva_img)
    resultado = bytearray(nuevo_bc)
    conservados = 0
    for by in range(alto // 4):
        for bx in range(ancho // 4):
            if bloques_iguales(a[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4], b[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4],
                               tolerancia):
                pos = (by * (ancho // 4) + bx) * tam_bloque
                resultado[pos:pos + tam_bloque] = original_bc[pos:pos + tam_bloque]
                conservados += 1
    return bytes(resultado), conservados


def generar_capas(original, estilo, texturas, datos_srdv):
    """Reutiliza adornos del mismo atlas y compone rotulos de varios colores."""
    resultado = Image.new('RGBA', original.size, (0, 0, 0, 0))
    for capa in estilo['capas']:
        img = texturas[capa['nombre']].decodificar(datos_srdv)
        resultado.alpha_composite(img, tuple(capa['pos']))
    for t in estilo['textos']:
        if t.get("letras_variables"):
            from rotulos_originales import letras_variables
            img = letras_variables(t["texto"], t)
        else:
            img = dibujar(t['texto'], t, t['color'])
        escala = t['alto'] / img.height
        ancho = min(t['ancho_max'], round(img.width * escala))
        img = img.resize((ancho, t['alto']), Image.LANCZOS)
        resultado.alpha_composite(img, tuple(t['pos']))
    return resultado


def ruta_pregenerada(carpeta, ruta_spc, nombre):
    """Mismo nombre que imagenes/vista: <spc sin extension>__<textura>."""
    return os.path.join(carpeta, os.path.basename(ruta_spc)[:-4] + "__" + nombre)


def traducir_texturas(datos_srd, datos_srdv, traducciones, ruta_spc=None):
    """Devuelve (srd nuevo, srdv nuevo, lista de (nombre, imagen nueva)).

    Las texturas de texto de un solo color (sin borde) se codifican en BC7 modo 5,
    que comprime mucho mejor dentro del SPC; el resto, con el codificador generico.
    ruta_spc: ruta del SPC en el CPK; con ella se usan o guardan las pregeneradas.
    """
    srd_nuevo = bytearray(datos_srd)
    srdv = bytearray(datos_srdv)
    hechas = []
    for t in srd.texturas(datos_srd):
        estilo = traducciones.get(t.nombre)
        if not estilo or len(t.mips) != 1:
            continue
        original = t.decodificar(srdv)
        pregenerada = None
        if CARPETA_PREGENERADAS and ruta_spc and not estilo.get("imagen_traducida"):
            pregenerada = ruta_pregenerada(CARPETA_PREGENERADAS, ruta_spc, t.nombre)
        if pregenerada and os.path.exists(pregenerada):
            with Image.open(pregenerada) as archivo:
                nueva = archivo.convert("RGBA")
        elif 'capas' in estilo:
            originales = {x.nombre: x for x in srd.texturas(datos_srd)}
            nueva = generar_capas(original, estilo, originales, datos_srdv)
        else:
            nueva = generar(original, estilo)
        if GUARDAR_PREGENERADAS and ruta_spc and not estilo.get("imagen_traducida"):
            os.makedirs(GUARDAR_PREGENERADAS, exist_ok=True)
            nueva.save(ruta_pregenerada(GUARDAR_PREGENERADAS, ruta_spc, t.nombre))
        mip = t.mips[0]
        # El modo 5 solo sirve para texto de un color sobre fondo transparente
        transparente = np.array(nueva.getchannel("A")).min() < 200
        if srd.FORMATOS[t.formato] == "bc7" and estilo.get("color_plano_nativo"):
            bloque = codificar_texto_bc7(nueva, estilo["color_plano_nativo"])
        elif srd.FORMATOS[t.formato] == "bc7" and estilo.get("grises_nativos"):
            bloque = codificar_grises_bc7(nueva)
        elif srd.FORMATOS[t.formato] == "bc7" and (estilo.get("acabado_original") or estilo.get("contorno_final")):
            bloque = codificar_halo_bc7(nueva, contorno=bool(estilo.get("contorno_final")))
        elif (srd.FORMATOS[t.formato] == "bc7" and transparente and not estilo.get("borde")
                and not estilo.get("brillo") and not estilo.get("imagen_traducida") and not estilo.get("contorno_final") and not estilo.get("acabado_original")
                and "borrar" not in estilo and 'capas' not in estilo):
            bloque = codificar_texto_bc7(nueva, color_dominante(nueva))
        else:
            bloque = codificar(nueva, t.formato)
            original_bc = bytes(srdv[mip["offset"]:mip["offset"] + mip["tam"]])
            bloque, _ = conservar_bloques(original_bc, bloque, original, nueva, t.formato,
                                          int(estilo.get("tolerancia_bloques", 0)))
        if len(bloque) != mip["tam"]:
            raise ValueError("Tamano BC distinto en %s (%d != %d)" % (t.nombre, len(bloque), mip["tam"]))
        srdv[mip["offset"]:mip["offset"] + mip["tam"]] = bloque
        hechas.append((t.nombre, t.decodificar(srdv)))
    return bytes(srd_nuevo), bytes(srdv), hechas


def vista():
    """Exporta original y traducida lado a lado para revisarlas."""
    from cpk import CPK
    from spc import SPC
    from config import CPK_US, respaldo_cabecera
    cpk = CPK(CPK_US, respaldo_cabecera(CPK_US))
    por_nombre = {a["nombre"]: a for a in cpk.archivos}
    destino = os.path.join(RAIZ, "imagenes", "vista")
    os.makedirs(destino, exist_ok=True)
    for ruta_spc, traducciones in cargar_config().items():
        spc = SPC(cpk.leer(por_nombre[ruta_spc]))
        datos_srd = spc.buscar("texture.srd").datos
        datos_srdv = spc.buscar("texture.srdv").datos
        originales = {t.nombre: t.decodificar(datos_srdv) for t in srd.texturas(datos_srd)}
        _, _, hechas = traducir_texturas(datos_srd, datos_srdv, traducciones)
        for nombre, img in hechas:
            o = originales[nombre]
            par = Image.new("RGBA", (o.width, o.height * 2 + 4), (110, 130, 110, 255))
            par.alpha_composite(o, (0, 0))
            par.alpha_composite(img, (0, o.height + 4))
            par.save(os.path.join(destino, os.path.basename(ruta_spc)[:-4] + "__" + nombre))
            print(ruta_spc, nombre)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "vista":
        vista()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
