"""Fuente SPFT de Danganronpa V3 (v3_font00.stx + v3_font00.srdv).

La textura es BC4 (un canal) sin swizzle. Cada glifo ocupa 8 bytes:
    x (12 bits), y (12 bits), ancho, alto, margen_izq, margen_der, desplazamiento_y

Uso:
    python fuente.py volcar <font.stx> <font.srdv> <salida.png>
"""
import struct
import sys

import numpy as np
from PIL import Image

# Desplazamientos dentro del bloque SpFt
OFF_MAX_CHAR = 0x08
OFF_NOMBRE = 0x10
OFF_CUENTA = 0x14
OFF_GLIFOS = 0x18
OFF_MAPA = 0x1C
OFF_RANGOS = 0x20
OFF_PUNTEROS = 0x28
NUM_PUNTEROS = 4
CARACTERES_JUICIO = ''.join(chr(c) for c in range(32, 127)) + 'áéíóúñüÁÉÍÓÚÑÜ¿¡—■▲●　'


# ---------------------------------------------------------------- BC4

def decodificar_bloque_bc4(bloque):
    r0, r1 = int(bloque[0]), int(bloque[1])
    if r0 > r1:
        paleta = [r0, r1] + [((7 - i) * r0 + i * r1) // 7 for i in range(1, 7)]
    else:
        paleta = [r0, r1] + [((5 - i) * r0 + i * r1) // 5 for i in range(1, 5)] + [0, 255]
    indices = int.from_bytes(bloque[2:8], "little")
    return np.array([paleta[(indices >> (3 * i)) & 7] for i in range(16)], np.uint8).reshape(4, 4)


def codificar_bloque_bc4(px):
    """Codifica un bloque 4x4 (modo de 8 valores con r0 > r1)."""
    px = px.astype(np.int32).reshape(16)
    mx, mn = int(px.max()), int(px.min())
    if mx == mn:
        # Bloque plano: r0 > r1 obligatorio; usar el indice 0 o 1 segun el valor
        if mx == 0:
            return bytes([1, 0]) + (0x249249249249).to_bytes(6, "little")  # todo indice 1 = 0
        return bytes([mx, mx - 1]) + bytes(6)
    paleta = [mx, mn] + [((7 - i) * mx + i * mn) // 7 for i in range(1, 7)]
    paleta = np.array(paleta, np.int32)
    indices = np.abs(px[:, None] - paleta[None, :]).argmin(axis=1)
    valor = 0
    for i, ind in enumerate(indices):
        valor |= int(ind) << (3 * i)
    return bytes([mx, mn]) + valor.to_bytes(6, "little")


def decodificar_bc4(datos, ancho, alto):
    bx, by = ancho // 4, (alto + 3) // 4
    img = np.zeros((by * 4, bx * 4), np.uint8)
    arr = np.frombuffer(datos[:bx * by * 8], np.uint8).reshape(by, bx, 8)
    for y in range(by):
        for x in range(bx):
            img[y * 4:y * 4 + 4, x * 4:x * 4 + 4] = decodificar_bloque_bc4(arr[y, x])
    return img[:alto]


# ---------------------------------------------------------------- SRD / SPFT

class Fuente:
    def __init__(self, datos_stx, datos_srdv):
        self.srd = bytearray(datos_stx)
        self.srdv = bytearray(datos_srdv)
        # Bloque $TXR en 0x10, datos en 0x20
        _, _, self.ancho, self.alto, _, formato = struct.unpack_from("<IHHHHB", self.srd, 0x20)
        if formato != 0x16:
            raise ValueError("Formato de textura no soportado: %x" % formato)
        self.spft = self.srd.index(b"SpFt")
        b = self.spft
        self.max_char = struct.unpack_from("<I", self.srd, b + OFF_MAX_CHAR)[0]
        cuenta = struct.unpack_from("<I", self.srd, b + OFF_CUENTA)[0]
        off_glifos = struct.unpack_from("<I", self.srd, b + OFF_GLIFOS)[0]
        off_mapa = struct.unpack_from("<I", self.srd, b + OFF_MAPA)[0]
        mapa = self.srd[b + off_mapa:b + off_mapa + (self.max_char + 8) // 8]
        caracteres = [c for c in range(self.max_char + 1) if mapa[c >> 3] >> (c & 7) & 1]
        if len(caracteres) != cuenta:
            raise ValueError("El mapa de bits no coincide con la cuenta de glifos")
        self.glifos = {}
        for i, c in enumerate(caracteres):
            e = self.srd[b + off_glifos + i * 8:b + off_glifos + i * 8 + 8]
            pos = e[0] | (e[1] << 8) | (e[2] << 16)
            self.glifos[c] = {
                "x": pos & 0xFFF, "y": pos >> 12, "ancho": e[3], "alto": e[4],
                "izq": struct.unpack("b", e[5:6])[0], "der": struct.unpack("b", e[6:7])[0],
                "desp_y": struct.unpack("b", e[7:8])[0],
            }

    def imagen(self):
        if not hasattr(self, "_imagen"):
            self._imagen = decodificar_bc4(self.srdv, self.ancho, self.alto)
        return self._imagen

    def recortar(self, c):
        g = self.glifos[ord(c)]
        return self.imagen()[g["y"]:g["y"] + g["alto"], g["x"]:g["x"] + g["ancho"]].copy()

    def agregar(self, nuevos, separacion=2):
        """Anade glifos al final de la ultima fila del atlas.

        nuevos: {caracter: (imagen_uint8, izq, der, desp_y)}
        Solo se recodifican los bloques BC4 nuevos; el resto queda intacto.
        """
        fila_y = max(g["y"] for g in self.glifos.values())
        x = max(g["x"] + g["ancho"] for g in self.glifos.values() if g["y"] == fila_y)
        x = (x + 3) // 4 * 4
        y0 = fila_y // 4 * 4
        lienzo = np.zeros((self.alto + 3) // 4 * 4 - y0, np.uint8)
        lienzo = np.zeros((lienzo.shape[0], self.ancho), np.uint8)
        x_ini = x
        for c, (img, izq, der, desp_y) in nuevos.items():
            alto, ancho = img.shape
            if fila_y + alto > self.alto:
                raise ValueError("El glifo %r no cabe en la fila (alto %d)" % (c, alto))
            if x + ancho > self.ancho:
                raise ValueError("No queda espacio horizontal en el atlas")
            lienzo[fila_y - y0:fila_y - y0 + alto, x:x + ancho] = img
            self.glifos[ord(c)] = {"x": x, "y": fila_y, "ancho": ancho, "alto": alto,
                                   "izq": izq, "der": der, "desp_y": desp_y}
            x += ancho + separacion

        # Recodificar los bloques tocados (desde x_ini, filas de bloque desde y0)
        bloques_x = self.ancho // 4
        for by in range(lienzo.shape[0] // 4):
            for bx in range(x_ini // 4, (x + 3) // 4):
                bloque = lienzo[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4]
                pos = ((y0 // 4 + by) * bloques_x + bx) * 8
                self.srdv[pos:pos + 8] = codificar_bloque_bc4(bloque)
        if hasattr(self, "_imagen"):
            del self._imagen

    def serializar(self):
        """Devuelve (stx, srdv) con la tabla de glifos reconstruida."""
        b = self.spft
        srd = self.srd
        off_nombre_ant, cuenta_ant, off_glifos = struct.unpack_from("<III", srd, b + OFF_NOMBRE)
        off_mapa, off_rangos = struct.unpack_from("<II", srd, b + OFF_MAPA)
        off_punteros = struct.unpack_from("<I", srd, b + OFF_PUNTEROS)[0]
        caracteres = sorted(self.glifos)
        extra = (len(caracteres) - cuenta_ant) * 8

        # Mapa de bits y tabla de rangos (cuantos caracteres hay antes de cada palabra de 32 bits)
        largo_mapa_ant = off_rangos - off_mapa
        max_char = max(self.max_char, max(caracteres))
        largo_mapa = max(largo_mapa_ant, ((max_char + 32) // 32) * 4)
        extra_mapa = largo_mapa - largo_mapa_ant
        extra += extra_mapa * 2
        mapa = bytearray(largo_mapa)
        for c in caracteres:
            mapa[c >> 3] |= 1 << (c & 7)
        rangos = bytearray()
        acumulado = 0
        for palabra in range(largo_mapa // 4):
            rangos += struct.pack("<I", acumulado)
            acumulado += bin(int.from_bytes(mapa[palabra * 4:palabra * 4 + 4], "little")).count("1")
        if len(rangos) != off_glifos - off_rangos + extra_mapa:
            raise ValueError("Tamano inesperado de la tabla de rangos")

        glifos = bytearray()
        for c in caracteres:
            g = self.glifos[c]
            pos = g["x"] | (g["y"] << 12)
            glifos += bytes([pos & 0xFF, (pos >> 8) & 0xFF, pos >> 16, g["ancho"], g["alto"]])
            glifos += struct.pack("bbb", g["izq"], g["der"], g["desp_y"])

        # Punteros y nombre de la fuente se desplazan lo que crece la tabla de glifos
        punteros = bytearray()
        for i in range(NUM_PUNTEROS):
            punteros += struct.pack("<I", struct.unpack_from("<I", srd, b + off_punteros + i * 4)[0] + extra)
        cola_spft = srd[b + off_punteros + NUM_PUNTEROS * 4:b + off_nombre_ant]
        nombre_ini = b + off_nombre_ant

        # Recurso SpFt dentro del bloque $RSI: info en 0x60 (desc, offset, largo, ...)
        rsi = 0x30
        largo_spft = struct.unpack_from("<I", srd, 0x68)[0]
        fin_spft = b + largo_spft
        nombre = srd[nombre_ini:fin_spft]

        cab_spft = bytearray(srd[b:b + off_mapa])
        struct.pack_into("<I", cab_spft, OFF_MAX_CHAR, max_char)
        struct.pack_into("<I", cab_spft, OFF_RANGOS, off_rangos + extra_mapa)
        struct.pack_into("<I", cab_spft, OFF_GLIFOS, off_glifos + extra_mapa * 2)
        struct.pack_into("<II", cab_spft, OFF_NOMBRE, off_nombre_ant + extra, len(caracteres))
        struct.pack_into("<I", cab_spft, OFF_PUNTEROS, off_punteros + extra)
        spft = cab_spft + mapa + rangos + glifos + punteros + cola_spft + nombre
        if len(spft) != largo_spft + extra:
            raise ValueError("Tamano de SpFt inconsistente")

        largo_rsi = struct.unpack_from(">I", srd, rsi + 4)[0]
        datos_rsi = bytearray(srd[rsi + 0x10:b]) + spft + srd[fin_spft:rsi + 0x10 + largo_rsi]
        struct.pack_into("<I", datos_rsi, 0x0C, struct.unpack_from("<I", datos_rsi, 0x0C)[0] + extra)
        struct.pack_into("<I", datos_rsi, 0x20, struct.unpack_from("<I", datos_rsi, 0x20)[0] + extra)
        struct.pack_into("<I", datos_rsi, 0x28, largo_spft + extra)

        cab_rsi = bytearray(srd[rsi:rsi + 0x10])
        struct.pack_into(">I", cab_rsi, 4, len(datos_rsi))
        bloque_rsi = cab_rsi + datos_rsi + b"\0" * ((0x10 - len(datos_rsi) % 0x10) % 0x10)
        fin_rsi_ant = rsi + 0x10 + largo_rsi + (0x10 - largo_rsi % 0x10) % 0x10
        resto_sub = srd[fin_rsi_ant:0x30 + struct.unpack_from(">I", srd, 0x18)[0]]

        cab = bytearray(srd[:0x30])
        struct.pack_into(">I", cab, 0x18, len(bloque_rsi) + len(resto_sub))
        fin_txr = 0x30 + struct.unpack_from(">I", srd, 0x18)[0]
        nuevo = cab + bloque_rsi + resto_sub + srd[fin_txr:]
        return bytes(nuevo), bytes(self.srdv)

    def agregar_en_huecos(self, nuevos):
        """Ocupa bloques BC4 libres sin mover ni recodificar glifos existentes."""
        filas, columnas = (self.alto + 3) // 4, self.ancho // 4
        ocupado = np.zeros((filas, columnas), dtype=bool)
        for g in self.glifos.values():
            ocupado[g['y'] // 4:(g['y'] + g['alto'] + 3) // 4,
                    g['x'] // 4:(g['x'] + g['ancho'] + 3) // 4] = True
        for c, (img, izq, der, desp_y) in sorted(nuevos.items(), key=lambda p: -p[1][0].shape[0]):
            alto, ancho = img.shape
            h, w = (alto + 3) // 4, (ancho + 3) // 4
            posicion = None
            if h <= filas and w <= columnas:
                suma = np.pad(ocupado.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
                ventanas = suma[h:, w:] - suma[:-h, w:] - suma[h:, :-w] + suma[:-h, :-w]
                validas = ventanas[:(self.alto - alto) // 4 + 1] == 0
                libres = np.argwhere(validas)
                if len(libres):
                    y, x = libres[0]
                    posicion = int(x), int(y)
            if posicion is None:
                raise ValueError('No hay espacio para %r en el atlas' % c)
            x, y = posicion
            ocupado[y:y + h, x:x + w] = True
            bloque = np.zeros((h * 4, w * 4), np.uint8)
            bloque[:alto, :ancho] = img
            for by in range(h):
                for bx in range(w):
                    pos = ((y + by) * columnas + x + bx) * 8
                    self.srdv[pos:pos + 8] = codificar_bloque_bc4(
                        bloque[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4])
            self.glifos[ord(c)] = {'x': x * 4, 'y': y * 4, 'ancho': ancho, 'alto': alto,
                                   'izq': izq, 'der': der, 'desp_y': desp_y}
        if hasattr(self, '_imagen'):
            del self._imagen



# ---------------------------------------------------------------- Glifos en espanol

def caja_tinta(img, umbral=40):
    """Devuelve (y0, y1, x0, x1) de la zona con tinta."""
    filas = np.where(img.max(axis=1) > umbral)[0]
    cols = np.where(img.max(axis=0) > umbral)[0]
    return filas[0], filas[-1] + 1, cols[0], cols[-1] + 1


def escalar(img, ancho=None, alto=None):
    h, w = img.shape
    return np.array(Image.fromarray(img).resize((ancho or w, alto or h), Image.LANCZOS))


def componer(fuente, base, diacritico, gap, centro_rel=0.0, recorte_base=0):
    """Coloca un diacritico centrado sobre un glifo base.

    centro_rel: desplazamiento horizontal del diacritico respecto al centro (en px).
    recorte_base: filas superiores a quitar del glifo base (ej. el punto de la i).
    Devuelve (imagen, izq, der, desp_y).
    """
    g = fuente.glifos[ord(base)]
    img_base = fuente.recortar(base)[recorte_base:]
    bh, bw = img_base.shape
    dh, dw = diacritico.shape
    avance = g["izq"] + g["ancho"] + g["der"]

    # Coordenadas relativas al borde izquierdo del glifo base
    dx = int(round((bw - dw) / 2 + centro_rel))
    x0 = min(0, dx)
    x1 = max(bw, dx + dw)
    alto = dh + gap + bh
    lienzo = np.zeros((alto, x1 - x0), np.uint8)
    lienzo[dh + gap:, -x0:-x0 + bw] = img_base
    zona = lienzo[:dh, dx - x0:dx - x0 + dw]
    np.maximum(zona, diacritico, out=zona)

    izq = g["izq"] + x0
    der = avance - izq - lienzo.shape[1]
    desp_y = g["desp_y"] + recorte_base - dh - gap
    return lienzo, izq, der, desp_y


def invertir(fuente, c, desp_y):
    g = fuente.glifos[ord(c)]
    img = np.rot90(fuente.recortar(c), 2).copy()
    return img, g["der"], g["izq"], desp_y


def crear_glifos_espanol(fuente):
    """Genera los glifos que faltan reutilizando trazos de la propia fuente."""
    # Tilde aguda tomada de la e con tilde
    e, e_tilde = fuente.glifos[ord("e")], fuente.glifos[ord("é")]
    zona = fuente.recortar("é")[:e["desp_y"] - e_tilde["desp_y"]]
    y0, y1, x0, x1 = caja_tinta(zona)
    aguda = zona[y0:y1, x0:x1]
    gap = zona.shape[0] - y1
    # Desplazamiento del acento respecto al centro de la e en la fuente original
    centro_acento = (x0 + x1) / 2 - e_tilde["ancho"] / 2

    # Virgulilla a partir de "~", dieresis a partir del punto de la i
    virgulilla = fuente.recortar("~")
    vy0, vy1, vx0, vx1 = caja_tinta(virgulilla)
    virgulilla = virgulilla[vy0:vy1, vx0:vx1]
    i = fuente.recortar("i")
    py0, py1, px0, px1 = caja_tinta(i[:10])
    punto = i[py0:py1, px0:px1]
    sep = max(4, punto.shape[1])
    dieresis = np.zeros((punto.shape[0], punto.shape[1] * 2 + sep), np.uint8)
    dieresis[:, :punto.shape[1]] = punto
    dieresis[:, -punto.shape[1]:] = punto

    # Filas a quitar de la i para dejarla sin punto (arranca a la altura de la x)
    sin_punto = fuente.glifos[ord("n")]["desp_y"] - fuente.glifos[ord("i")]["desp_y"]

    # Mayusculas: diacriticos mas bajos para no salirse de la linea
    alto_may = max(4, int(aguda.shape[0] * 0.7))
    aguda_may = escalar(aguda, alto=alto_may)
    virg_n = escalar(virgulilla, ancho=int(fuente.glifos[ord("n")]["ancho"] * 0.85))
    virg_may = escalar(virgulilla, ancho=int(fuente.glifos[ord("N")]["ancho"] * 0.7),
                       alto=max(4, int(virgulilla.shape[0] * 0.8)))

    nuevos = {}
    for c, base in (("á", "a"), ("ó", "o"), ("ú", "u")):
        nuevos[c] = componer(fuente, base, aguda, gap, centro_acento)
    nuevos["í"] = componer(fuente, "i", aguda, gap, 0, recorte_base=sin_punto)
    nuevos["ñ"] = componer(fuente, "n", virg_n, gap)
    nuevos["ü"] = componer(fuente, "u", dieresis, gap)
    for c, base in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        nuevos[c] = componer(fuente, base, aguda_may, 2)
    nuevos["Ñ"] = componer(fuente, "N", virg_may, 2)
    nuevos["Ü"] = componer(fuente, "U", dieresis, 2)
    # Signos de apertura: la parte superior queda a la altura de la x
    desp = fuente.glifos[ord("n")]["desp_y"] - 2
    nuevos["¿"] = invertir(fuente, "?", desp)
    nuevos["¡"] = invertir(fuente, "!", desp)
    return {c: v for c, v in nuevos.items() if ord(c) not in fuente.glifos}


def crear_glifos_juicio(fuente, referencia):
    """Compone diacriticos sobre las letras propias de cada fuente de juicio.

    Estas fuentes son subconjuntos. Se usa la letra local cuando existe y la
    residente escalada como respaldo si falta la base, sin alterar las existentes.
    """
    if ord('a') not in fuente.glifos:
        return {}
    class Bases:
        def __init__(self):
            self.glifos = dict(fuente.glifos)
            self.imagenes = {}
            for base in ''.join(chr(c) for c in range(32, 127)) + '—■▲●　':
                if ord(base) in self.glifos:
                    continue
                modelo = next((fuente.glifos[ord(c)] for c in 'AEHIT'
                               if ord(c) in fuente.glifos), fuente.glifos[ord('a')])
                if base.islower():
                    modelo = fuente.glifos[ord('a')]
                g = referencia.glifos[ord(base)]
                patron = referencia.glifos[ord('a' if base.islower() else 'A')]
                escala = modelo['alto'] / patron['alto']
                img = escalar(referencia.recortar(base), ancho=max(1, round(g['ancho'] * escala)),
                              alto=max(1, round(g['alto'] * escala)))
                self.imagenes[base] = img
                self.glifos[ord(base)] = dict(ancho=img.shape[1], alto=img.shape[0],
                    izq=round(g['izq'] * escala), der=round(g['der'] * escala),
                    desp_y=modelo['desp_y'] + round((g['desp_y'] - patron['desp_y']) * escala))

        def recortar(self, c):
            return self.imagenes[c] if c in self.imagenes else fuente.recortar(c)

    bases = Bases()
    e, et = referencia.glifos[ord('e')], referencia.glifos[ord('é')]
    aguda = referencia.recortar('é')[:e['desp_y'] - et['desp_y']]
    y0, y1, x0, x1 = caja_tinta(aguda)
    aguda = aguda[y0:y1, x0:x1]
    virgulilla = referencia.recortar('~')
    y0, y1, x0, x1 = caja_tinta(virgulilla)
    virgulilla = virgulilla[y0:y1, x0:x1]
    nuevos = {}
    for base, img in bases.imagenes.items():
        g = bases.glifos[ord(base)]
        nuevos[base] = (img, g['izq'], g['der'], g['desp_y'])
    for c, base in zip('áéíóúñüÁÉÍÓÚÑÜ', 'aeiounuAEIOUNU'):
        if ord(c) in fuente.glifos:
            continue
        g = bases.glifos[ord(base)]
        alto = max(4, round(g['alto'] * (0.13 if base.isupper() else 0.18)))
        gap = max(2, round(g['alto'] * 0.035))
        recorte = 0
        if base == 'i':
            # Separacion real entre el punto y el asta, incluso en letras estilizadas.
            tinta = bases.recortar('i').max(axis=1) > 40
            inicio = next((j for j in range(1, len(tinta)) if tinta[j - 1] and not tinta[j]), None)
            if inicio is not None:
                recorte = next((j for j in range(inicio, len(tinta)) if tinta[j]), 0)
        if c in 'ñÑ':
            marca = escalar(virgulilla, ancho=max(5, round(g['ancho'] * 0.65)), alto=alto)
        elif c in 'üÜ':
            punto = max(3, alto // 2)
            marca = np.zeros((punto, punto * 4), np.uint8)
            marca[:, :punto] = 255
            marca[:, -punto:] = 255
        else:
            marca = escalar(aguda, ancho=max(4, round(alto * aguda.shape[1] / aguda.shape[0])), alto=alto)
        nuevos[c] = componer(bases, base, marca, gap, recorte_base=recorte)
    for c, base in [('¿', '?'), ('¡', '!')]:
        if ord(c) not in fuente.glifos:
            nuevos[c] = invertir(bases, base, fuente.glifos[ord('a')]['desp_y'])
    return nuevos


def renderizar(fuente, texto, alto_linea=47):
    """Dibuja texto con las metricas de la fuente (para revisar a ojo)."""
    lineas = texto.split("\n")
    anchos = []
    for linea in lineas:
        anchos.append(sum(fuente.glifos[ord(c)]["izq"] + fuente.glifos[ord(c)]["ancho"]
                          + fuente.glifos[ord(c)]["der"] for c in linea))
    lienzo = np.zeros((alto_linea * len(lineas) + 20, max(anchos) + 20), np.uint8)
    for n, linea in enumerate(lineas):
        x = 10
        for c in linea:
            g = fuente.glifos[ord(c)]
            img = fuente.recortar(c)
            y = 10 + n * alto_linea + g["desp_y"]
            zona = lienzo[y:y + g["alto"], x + g["izq"]:x + g["izq"] + g["ancho"]]
            np.maximum(zona, img[:zona.shape[0], :zona.shape[1]], out=zona)
            x += g["izq"] + g["ancho"] + g["der"]
    return lienzo


def main():
    if len(sys.argv) < 5 or sys.argv[1] != "volcar":
        print(__doc__)
        return
    with open(sys.argv[2], "rb") as f:
        stx = f.read()
    with open(sys.argv[3], "rb") as f:
        srdv = f.read()
    fuente = Fuente(stx, srdv)
    Image.fromarray(fuente.imagen()).save(sys.argv[4])
    print("%d glifos, textura %dx%d" % (len(fuente.glifos), fuente.ancho, fuente.alto))


if __name__ == "__main__":
    main()
