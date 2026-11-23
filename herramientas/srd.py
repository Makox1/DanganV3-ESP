"""Texturas de archivos SRD/SRDV (interfaz de Danganronpa V3).

Uso:
    python srd.py listar   <texture.srd>
    python srd.py exportar <texture.srd> <texture.srdv> <carpeta> [--solo-us]

Cada bloque $TXR describe una textura y su subbloque $RSI dice donde estan
los pixeles dentro del .srdv (bit 0x40000000 = recurso externo).
Formatos soportados: 0x0F (DXT1/BC1), 0x11 (DXT5/BC3) y 0x1C (BC7).
"""
import os
import struct
import sys

import etcpak
import texture2ddecoder
from PIL import Image

FORMATOS = {0x0F: "bc1", 0x11: "bc3", 0x1C: "bc7"}
POS_FORMATO = 0x0C
EXTERNO = 0x40000000


def bloques(datos, ini=0, fin=None):
    """Recorre bloques SRD: (magia, pos_datos, largo_datos, pos_sub, largo_sub)."""
    fin = len(datos) if fin is None else fin
    pos = ini
    while pos + 0x10 <= fin:
        magia = datos[pos:pos + 4]
        largo, largo_sub = struct.unpack_from(">II", datos, pos + 4)
        pos_datos = pos + 0x10
        pos_sub = pos_datos + largo + (0x10 - largo % 0x10) % 0x10
        yield magia, pos_datos, largo, pos_sub, largo_sub
        pos = pos_sub + largo_sub + (0x10 - largo_sub % 0x10) % 0x10


class Textura:
    def __init__(self, srd, pos_txr, pos_sub, largo_sub):
        (_, self.swizzle, self.ancho, self.alto, self.scanline,
         self.formato) = struct.unpack_from("<IHHHHB", srd, pos_txr)
        self.pos_txr = pos_txr
        self.mips = []
        self.nombre = ""
        for magia, pd, ld, _, _ in bloques(srd, pos_sub, pos_sub + largo_sub):
            if magia != b"$RSI":
                continue
            externos = srd[pd + 3]
            off_cadenas = struct.unpack_from("<I", srd, pd + 0x0C)[0]
            for i in range(externos):
                direccion, tam = struct.unpack_from("<II", srd, pd + 0x10 + i * 0x10)
                self.mips.append({"pos": pd + 0x10 + i * 0x10,
                                  "offset": direccion & 0x00FFFFFF,
                                  "bandera": direccion & 0xFF000000, "tam": tam})
            fin = srd.index(b"\0", pd + off_cadenas)
            self.nombre = srd[pd + off_cadenas:fin].decode("utf-8", "replace")

    def decodificar(self, srdv):
        """Devuelve una imagen RGBA del primer mipmap."""
        if self.formato not in FORMATOS:
            raise ValueError("Formato %x no soportado" % self.formato)
        mip = self.mips[0]
        ancho = (self.ancho + 3) // 4 * 4
        alto = (self.alto + 3) // 4 * 4
        datos = bytes(srdv[mip["offset"]:mip["offset"] + mip["tam"]])
        if FORMATOS[self.formato] == "bc7":
            bgra = texture2ddecoder.decode_bc7(datos, ancho, alto)
        elif FORMATOS[self.formato] == "bc3":
            bgra = texture2ddecoder.decode_bc3(datos, ancho, alto)
        else:
            bgra = texture2ddecoder.decode_bc1(datos, ancho, alto)
        img = Image.frombytes("RGBA", (ancho, alto), bgra, "raw", "BGRA")
        return img.crop((0, 0, self.ancho, self.alto))


def texturas(srd):
    resultado = []
    for magia, pd, _, ps, ls in bloques(srd):
        if magia == b"$TXR":
            resultado.append(Textura(srd, pd, ps, ls))
    return resultado


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    orden = sys.argv[1]
    with open(sys.argv[2], "rb") as f:
        srd = f.read()
    lista = texturas(srd)
    if orden == "listar":
        for i, t in enumerate(lista):
            print("%2d %-40s %4dx%-4d fmt=%02x swz=%d mips=%d" % (
                i, t.nombre, t.ancho, t.alto, t.formato, t.swizzle, len(t.mips)))
    elif orden == "exportar":
        with open(sys.argv[3], "rb") as f:
            srdv = f.read()
        carpeta = sys.argv[4]
        os.makedirs(carpeta, exist_ok=True)
        for i, t in enumerate(lista):
            if "--solo-us" in sys.argv and "_US" not in t.nombre:
                continue
            t.decodificar(srdv).save(os.path.join(carpeta, "%02d_%s" % (i, t.nombre.replace(".tga", ".png"))))


if __name__ == "__main__":
    main()
