"""Lector/escritor de archivos SPC (contenedor de Danganronpa V3).

Uso:
    python spc.py listar  <archivo.spc>
    python spc.py extraer <archivo.spc> <carpeta_salida>
"""
import os
import struct
import sys

MAGIA = b"CPS."
COMPRIMIDO = 2
SIN_COMPRIMIR = 1


def relleno(n, alineacion=0x10):
    return (alineacion - n % alineacion) % alineacion


def invertir_bits(b):
    return int("{:08b}".format(b)[::-1], 2)


INVERSO = [invertir_bits(i) for i in range(256)]


def descomprimir(datos):
    salida = bytearray()
    bandera = 1
    pos = 0
    n = len(datos)
    while pos < n:
        if bandera == 1:
            bandera = 0x100 | INVERSO[datos[pos]]
            pos += 1
            if pos >= n:
                break
        if bandera & 1:
            salida.append(datos[pos])
            pos += 1
        else:
            b = datos[pos] | (datos[pos + 1] << 8)
            pos += 2
            cuenta = (b >> 10) + 2
            desplazamiento = b & 0x3FF
            for _ in range(cuenta):
                salida.append(salida[len(salida) - 1024 + desplazamiento])
        bandera >>= 1
    return bytes(salida)


VENTANA = 1024
MIN_COPIA = 2
MAX_COPIA = 65
MAX_CANDIDATOS = 128


def comprimir(datos):
    """Inverso de descomprimir: LZ con ventana de 1024 bytes y banderas con bits invertidos."""
    salida = bytearray()
    n = len(datos)
    pos = 0
    tabla = {}
    bandera = 0
    bit = 0
    grupo = bytearray()

    def registrar(i):
        if i + 2 < n:
            tabla.setdefault(datos[i:i + 3], []).append(i)

    def buscar(p):
        mejor_largo, mejor_dist = 0, 0
        if p + 2 < n:
            candidatos = tabla.get(datos[p:p + 3], ())
            limite = min(MAX_COPIA, n - p)
            for cand in reversed(candidatos[-MAX_CANDIDATOS:]):
                dist = p - cand
                if dist > VENTANA:
                    break
                largo = 0
                while largo < limite and datos[cand + largo] == datos[p + largo]:
                    largo += 1
                if largo > mejor_largo:
                    mejor_largo, mejor_dist = largo, dist
                    if largo == limite:
                        break
        return mejor_largo, mejor_dist

    while pos < n:
        mejor_largo, mejor_dist = buscar(pos)
        if 3 <= mejor_largo < MAX_COPIA:
            # Busqueda perezosa: si empezando un byte despues hay una copia mas larga,
            # se emite este byte como literal y se usa la siguiente
            registrar(pos)
            siguiente, _ = buscar(pos + 1)
            tabla[datos[pos:pos + 3]].pop()
            if siguiente > mejor_largo + 1:
                mejor_largo = 0
        if mejor_largo >= 3:
            b = ((mejor_largo - MIN_COPIA) << 10) | (VENTANA - mejor_dist)
            grupo += bytes([b & 0xFF, b >> 8])
            for i in range(pos, pos + mejor_largo):
                registrar(i)
            pos += mejor_largo
        else:
            bandera |= 1 << bit
            grupo.append(datos[pos])
            registrar(pos)
            pos += 1
        bit += 1
        if bit == 8:
            salida.append(INVERSO[bandera])
            salida += grupo
            bandera, bit, grupo = 0, 0, bytearray()
    if bit:
        salida.append(INVERSO[bandera])
        salida += grupo
    return bytes(salida)


def comprimir_optimo(datos):
    """Como comprimir, pero elige literales y copias minimizando el tamano total
    (programacion dinamica desde el final). Ocupa ~1 % menos y tarda ~5 s por MB;
    solo se usa para archivos que no caben en su hueco."""
    n = len(datos)
    # Copia mas larga (y su distancia) que empieza en cada posicion
    largo = [0] * n
    distancia = [0] * n
    tabla = {}
    for p in range(n - 1):
        clave = datos[p:p + 2]
        candidatos = tabla.get(clave)
        if candidatos is None:
            tabla[clave] = [p]
            continue
        limite = min(MAX_COPIA, n - p)
        mejor, mejor_dist = 0, 0
        for cand in reversed(candidatos):
            dist = p - cand
            if dist > VENTANA:
                break
            # Si difiere justo donde acaba la mejor copia, no puede superarla
            if mejor and (p + mejor >= n or datos[cand + mejor] != datos[p + mejor]):
                continue
            l = MIN_COPIA
            while l < limite and datos[cand + l] == datos[p + l]:
                l += 1
            if l > mejor:
                mejor, mejor_dist = l, dist
                if l == limite:
                    break
        largo[p], distancia[p] = mejor, mejor_dist
        if len(candidatos) > 64 and p - candidatos[0] > VENTANA:
            k = 0
            while k < len(candidatos) and p - candidatos[k] > VENTANA:
                k += 1
            del candidatos[:k]
        candidatos.append(p)
    # Coste en bits hasta el final: literal 1+8, copia 1+16
    coste = [0] * (n + 1)
    eleccion = [0] * n
    for i in range(n - 1, -1, -1):
        mejor = coste[i + 1] + 9
        elegido = 0
        for l in range(MIN_COPIA, largo[i] + 1):
            c = coste[i + l] + 17
            if c < mejor:
                mejor, elegido = c, l
        coste[i] = mejor
        eleccion[i] = elegido
    salida = bytearray()
    bandera = bit = 0
    grupo = bytearray()
    i = 0
    while i < n:
        l = eleccion[i]
        if l:
            b = ((l - MIN_COPIA) << 10) | (VENTANA - distancia[i])
            grupo += bytes([b & 0xFF, b >> 8])
            i += l
        else:
            bandera |= 1 << bit
            grupo.append(datos[i])
            i += 1
        bit += 1
        if bit == 8:
            salida.append(INVERSO[bandera])
            salida += grupo
            bandera, bit, grupo = 0, 0, bytearray()
    if bit:
        salida.append(INVERSO[bandera])
        salida += grupo
    return bytes(salida)


class Entrada:
    def __init__(self, nombre, datos, bandera_desconocida=1, comprimido=None):
        self.nombre = nombre
        self.datos = datos
        self.bandera_desconocida = bandera_desconocida
        # Bloque comprimido original; se reutiliza si los datos no cambian
        self.comprimido = comprimido
        self.datos_originales = datos if comprimido is not None else None


class SPC:
    def __init__(self, datos=None):
        self.cabecera_desconocida = b"\0\0\0\0" + b"\xff" * 8 + b"\0" * 0x18
        self.desconocido2 = 4
        self.entradas = []
        if datos is not None:
            self._leer(datos)

    @classmethod
    def abrir(cls, ruta):
        with open(ruta, "rb") as f:
            return cls(f.read())

    def _leer(self, datos):
        if datos[:4] != MAGIA:
            raise ValueError("No es un SPC")
        self.cabecera_desconocida = datos[4:0x28]
        cuenta, self.desconocido2 = struct.unpack_from("<II", datos, 0x28)
        if datos[0x40:0x44] != b"Root":
            raise ValueError("Tabla Root no encontrada")
        pos = 0x50
        for _ in range(cuenta):
            comp, desc_flag, tam_act, tam_orig, largo = struct.unpack_from("<HHIII", datos, pos)
            pos += 0x20
            nombre = datos[pos:pos + largo].decode("utf-8")
            pos += largo + 1 + relleno(largo + 1)
            bruto = datos[pos:pos + tam_act]
            pos += tam_act + relleno(tam_act)
            comprimido = None
            if comp == COMPRIMIDO:
                comprimido = bruto
                bruto = descomprimir(bruto)
                if len(bruto) != tam_orig:
                    raise ValueError("Tamano descomprimido incorrecto en %s" % nombre)
            elif comp != SIN_COMPRIMIR:
                raise ValueError("Compresion %d no soportada en %s" % (comp, nombre))
            self.entradas.append(Entrada(nombre, bruto, desc_flag, comprimido))

    def buscar(self, nombre):
        for e in self.entradas:
            if e.nombre == nombre:
                return e
        return None

    def a_bytes(self, recomprimir=False, optimo=False):
        """Serializa el SPC. Las entradas que venian comprimidas se guardan comprimidas
        (reutilizando el bloque original si no cambiaron); el resto, sin comprimir.
        recomprimir: comprime de nuevo todas las entradas comprimidas; el resultado
        suele ocupar menos que el original.
        optimo: usa comprimir_optimo (mas lento, algo mas pequeno)."""
        compresor = comprimir_optimo if optimo else comprimir
        sal = bytearray(MAGIA)
        sal += self.cabecera_desconocida
        sal += struct.pack("<II", len(self.entradas), self.desconocido2)
        sal += b"\0" * 0x10
        sal += b"Root" + b"\0" * 0x0C
        for e in self.entradas:
            nombre = e.nombre.encode("utf-8")
            if e.comprimido is None:
                modo, bloque = SIN_COMPRIMIR, e.datos
            elif e.datos == e.datos_originales and not recomprimir:
                modo, bloque = COMPRIMIDO, e.comprimido
            else:
                modo, bloque = COMPRIMIDO, compresor(e.datos)
            sal += struct.pack("<HHIII", modo, e.bandera_desconocida,
                               len(bloque), len(e.datos), len(nombre))
            sal += b"\0" * 0x10
            sal += nombre + b"\0" * (1 + relleno(len(nombre) + 1))
            sal += bloque + b"\0" * relleno(len(bloque))
        return bytes(sal)

    def a_bytes_minimo(self, max_sin_cambios=4 << 20):
        """Serializa el SPC lo mas pequeno posible: cada entrada comprimida se queda
        con lo menor entre su bloque original y comprimir_optimo. Las entradas sin
        cambios de mas de max_sin_cambios bytes conservan su bloque original
        (comprimirlas tarda casi un minuto y apenas ahorra)."""
        for e in self.entradas:
            if e.comprimido is None:
                continue
            cambiada = e.datos != e.datos_originales
            if not cambiada and len(e.datos) > max_sin_cambios:
                continue
            nuevo = comprimir_optimo(e.datos)
            if cambiada or len(nuevo) < len(e.comprimido):
                e.comprimido, e.datos_originales = nuevo, e.datos
        return self.a_bytes()

    def guardar(self, ruta):
        with open(ruta, "wb") as f:
            f.write(self.a_bytes())


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    orden, ruta = sys.argv[1], sys.argv[2]
    spc = SPC.abrir(ruta)
    if orden == "listar":
        for e in spc.entradas:
            print("%8d  %s" % (len(e.datos), e.nombre))
    elif orden == "extraer":
        salida = sys.argv[3]
        os.makedirs(salida, exist_ok=True)
        for e in spc.entradas:
            with open(os.path.join(salida, e.nombre), "wb") as f:
                f.write(e.datos)


if __name__ == "__main__":
    main()
