"""Lector/parcheador de archivos CPK (CRI Middleware) usados por Danganronpa V3.

Uso:
    python cpk.py listar  <archivo.cpk> [filtro]
    python cpk.py extraer <archivo.cpk> <carpeta_salida> [filtro]
"""
import os
import struct
import sys

# Tipos de columna de las tablas @UTF
TIPOS = {
    0x0: ">B", 0x1: ">b", 0x2: ">H", 0x3: ">h",
    0x4: ">I", 0x5: ">i", 0x6: ">Q", 0x7: ">q",
    0x8: ">f", 0x9: ">d",
}
ALMACEN_CERO = 0x10
ALMACEN_CONSTANTE = 0x30
ALMACEN_FILA = 0x50


def descifrar_utf(datos):
    """Descifra una tabla @UTF cifrada con el XOR de CRI."""
    sal = bytearray(len(datos))
    m, t = 0x5F, 0x15
    for i, b in enumerate(datos):
        sal[i] = b ^ (m & 0xFF)
        m = (m * t) & 0xFFFFFFFF
    return bytes(sal)


class TablaUTF:
    """Tabla @UTF. Guarda, ademas de los valores, la posicion de cada celda por fila
    para poder parchear valores en el archivo original."""

    def __init__(self, datos, base_archivo=0):
        if datos[:4] != b"@UTF":
            datos = descifrar_utf(datos)
            self.cifrada = True
        else:
            self.cifrada = False
        if datos[:4] != b"@UTF":
            raise ValueError("No es una tabla @UTF")
        self.datos = datos
        self.base_archivo = base_archivo
        (tam, off_filas, off_cadenas, off_datos, off_nombre,
         ncols, largo_fila, nfilas) = struct.unpack_from(">IIIIIHHI", datos, 4)
        self.off_filas = off_filas + 8
        self.off_cadenas = off_cadenas + 8
        self.off_datos = off_datos + 8
        self.nombre = self._cadena(off_nombre)
        self.largo_fila = largo_fila
        self.nfilas = nfilas

        self.columnas = []
        pos = 0x20
        for _ in range(ncols):
            flags = datos[pos]
            pos += 1
            nombre = self._cadena(struct.unpack_from(">I", datos, pos)[0])
            pos += 4
            almacen = flags & 0xF0
            tipo = flags & 0x0F
            constante = None
            if almacen == ALMACEN_CONSTANTE:
                constante, pos = self._leer_valor(tipo, pos)
            self.columnas.append((nombre, almacen, tipo, constante))

        self.filas = []
        self.posiciones = []
        for f in range(nfilas):
            pos = self.off_filas + f * largo_fila
            fila, posfila = {}, {}
            for nombre, almacen, tipo, constante in self.columnas:
                if almacen == ALMACEN_FILA:
                    posfila[nombre] = (pos, tipo)
                    fila[nombre], pos = self._leer_valor(tipo, pos)
                elif almacen == ALMACEN_CONSTANTE:
                    fila[nombre] = constante
                else:
                    fila[nombre] = None
            self.filas.append(fila)
            self.posiciones.append(posfila)

    def _cadena(self, off):
        ini = self.off_cadenas + off
        fin = self.datos.index(b"\0", ini)
        return self.datos[ini:fin].decode("utf-8", "replace")

    def _leer_valor(self, tipo, pos):
        if tipo in TIPOS:
            fmt = TIPOS[tipo]
            return struct.unpack_from(fmt, self.datos, pos)[0], pos + struct.calcsize(fmt)
        if tipo == 0xA:
            off = struct.unpack_from(">I", self.datos, pos)[0]
            return self._cadena(off), pos + 4
        if tipo == 0xB:
            off, tam = struct.unpack_from(">II", self.datos, pos)
            ini = self.off_datos + off
            return self.datos[ini:ini + tam], pos + 8
        raise ValueError("Tipo de columna desconocido: %x" % tipo)


def descomprimir_crilayla(datos):
    """Descompresion CRILAYLA (algoritmo de CRI)."""
    tam_desc, tam_cab = struct.unpack_from("<II", datos, 8)
    cabecera = datos[0x10 + tam_cab:0x10 + tam_cab + 0x100]
    salida = bytearray(tam_desc + 0x100)
    salida[:0x100] = cabecera

    entrada_fin = 0x10 + tam_cab - 1
    salida_fin = 0x100 + tam_desc - 1
    bits_restantes = 0
    byte_actual = 0
    escrito = 0
    pos = entrada_fin
    long_estilos = (2, 3, 5, 8)

    def leer_bits(n):
        nonlocal bits_restantes, byte_actual, pos
        resultado = 0
        producidos = 0
        while producidos < n:
            if bits_restantes == 0:
                byte_actual = datos[pos]
                bits_restantes = 8
                pos -= 1
            tomar = min(bits_restantes, n - producidos)
            resultado <<= tomar
            resultado |= (byte_actual >> (bits_restantes - tomar)) & ((1 << tomar) - 1)
            bits_restantes -= tomar
            producidos += tomar
        return resultado

    while escrito < tam_desc:
        if leer_bits(1):
            ref = salida_fin - escrito + leer_bits(13) + 3
            largo = 3
            for i, bits in enumerate(long_estilos):
                n = leer_bits(bits)
                largo += n
                if n != (1 << bits) - 1:
                    break
            else:
                while True:
                    n = leer_bits(8)
                    largo += n
                    if n != 0xFF:
                        break
            for _ in range(largo):
                salida[salida_fin - escrito] = salida[ref]
                ref -= 1
                escrito += 1
        else:
            salida[salida_fin - escrito] = leer_bits(8)
            escrito += 1
    return bytes(salida)


class _Cabecera:
    """Lee la cabecera/TOC desde un respaldo y el resto desde el archivo real."""

    def __init__(self, ruta, cabecera):
        self.cabecera = cabecera
        self.pos = 0
        self.archivo = open(ruta, "rb")

    def seek(self, pos):
        self.pos = pos

    def read(self, n):
        if self.pos + n <= len(self.cabecera):
            datos = self.cabecera[self.pos:self.pos + n]
        else:
            self.archivo.seek(self.pos)
            datos = self.archivo.read(n)
        self.pos += n
        return datos

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.archivo.close()


class CPK:
    def __init__(self, ruta, cabecera_original=None):
        """cabecera_original: ruta a un respaldo de cabecera+TOC; si existe se usa
        en lugar de la del archivo (para leer el contenido original de un CPK parcheado)."""
        self.ruta = ruta
        # Zonas sobrescritas en sitio por el parche: {offset: ruta del respaldo}
        self.regiones = {}
        if cabecera_original:
            info = cabecera_original.replace("_cabecera.bin", "_info.json")
            if os.path.exists(info):
                import json
                with open(info, encoding="utf-8") as f:
                    self.regiones = {int(k): v for k, v in json.load(f).get("regiones", {}).items()}
        if cabecera_original and os.path.exists(cabecera_original):
            with open(cabecera_original, "rb") as f:
                lector = _Cabecera(ruta, f.read())
        else:
            lector = open(ruta, "rb")
        with lector as f:
            cab = f.read(0x10)
            if cab[:4] != b"CPK ":
                raise ValueError("No es un CPK")
            tam = struct.unpack_from("<Q", cab, 8)[0]
            self.tabla_cabecera = TablaUTF(f.read(tam), 0x10)
            self.cabecera = self.tabla_cabecera.filas[0]
            toc_off = self.cabecera["TocOffset"]
            cont_off = self.cabecera["ContentOffset"]
            f.seek(toc_off)
            cab = f.read(0x10)
            if cab[:4] != b"TOC ":
                raise ValueError("TOC no encontrado")
            tam = struct.unpack_from("<Q", cab, 8)[0]
            self.toc_pos = toc_off + 0x10
            self.toc = TablaUTF(f.read(tam), self.toc_pos)
        self.desplazamiento = min(toc_off, cont_off) if toc_off and cont_off else (toc_off or cont_off)
        self.archivos = []
        for i, fila in enumerate(self.toc.filas):
            nombre = (fila["DirName"] + "/" if fila.get("DirName") else "") + fila["FileName"]
            self.archivos.append({
                "indice": i,
                "nombre": nombre,
                "offset": fila["FileOffset"] + self.desplazamiento,
                "tam": fila["FileSize"],
                "tam_ext": fila["ExtractSize"],
            })

    def leer(self, archivo):
        respaldo = self.regiones.get(archivo["offset"])
        if respaldo:
            with open(respaldo, "rb") as f:
                datos = f.read(archivo["tam"])
        else:
            with open(self.ruta, "rb") as f:
                f.seek(archivo["offset"])
                datos = f.read(archivo["tam"])
        if datos[:8] == b"CRILAYLA":
            datos = descomprimir_crilayla(datos)
        return datos


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    orden, ruta = sys.argv[1], sys.argv[2]
    cpk = CPK(ruta)
    if orden == "listar":
        filtro = sys.argv[3] if len(sys.argv) > 3 else ""
        for a in cpk.archivos:
            if filtro in a["nombre"]:
                print("%10d %10d  %s" % (a["tam"], a["tam_ext"], a["nombre"]))
    elif orden == "extraer":
        salida = sys.argv[3]
        filtro = sys.argv[4] if len(sys.argv) > 4 else ""
        for a in cpk.archivos:
            if filtro not in a["nombre"]:
                continue
            destino = os.path.join(salida, a["nombre"])
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(cpk.leer(a))
            print(a["nombre"])


if __name__ == "__main__":
    main()
