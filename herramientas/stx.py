"""Lector/escritor de archivos STX (tablas de texto de Danganronpa V3).

Uso:
    python stx.py volcar <archivo.stx>
"""
import struct
import sys

MAGIA = b"STXT"


def leer(datos):
    """Devuelve (idioma, desconocido, [(id, texto), ...])."""
    if datos[:4] != MAGIA:
        raise ValueError("No es un STX")
    idioma = datos[4:8]
    ntablas, off_tabla, desconocido, cuenta = struct.unpack_from("<IIII", datos, 8)
    if ntablas != 1:
        raise ValueError("Se esperaba una sola tabla, hay %d" % ntablas)
    cadenas = []
    for i in range(cuenta):
        id_cadena, off = struct.unpack_from("<II", datos, off_tabla + i * 8)
        fin = off
        while datos[fin:fin + 2] != b"\0\0":
            fin += 2
        cadenas.append((id_cadena, datos[off:fin].decode("utf-16-le")))
    return idioma, desconocido, cadenas


def escribir(idioma, desconocido, cadenas):
    """Construye un STX. Las cadenas repetidas comparten offset, igual que el original."""
    cab = bytearray(MAGIA + idioma)
    cab += struct.pack("<IIII", 1, 0x20, desconocido, len(cadenas))
    cab += b"\0" * (0x20 - len(cab))
    tabla = bytearray()
    cuerpo = bytearray()
    base = 0x20 + len(cadenas) * 8
    vistas = {}
    for id_cadena, texto in cadenas:
        if texto not in vistas:
            vistas[texto] = base + len(cuerpo)
            cuerpo += texto.encode("utf-16-le") + b"\0\0"
        tabla += struct.pack("<II", id_cadena, vistas[texto])
    return bytes(cab + tabla + cuerpo)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    with open(sys.argv[2], "rb") as f:
        idioma, _, cadenas = leer(f.read())
    for id_cadena, texto in cadenas:
        print("[%d] %r" % (id_cadena, texto))


if __name__ == "__main__":
    main()
