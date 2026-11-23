"""Completa los diacriticos de las fuentes independientes de juicios y minijuegos."""
import struct
import numpy as np

from spc import SPC
from fuente import Fuente, crear_glifos_juicio


def es_fuente(ruta):
    return ruta.endswith('_US.spc') and ruta.startswith(('trial_font/', 'minigame/rsc/font/'))


def preparar(datos, referencia):
    """Devuelve el SPC corregido y la cantidad de glifos agregados."""
    spc = SPC(datos)
    entrada = next(e for e in spc.entradas if e.nombre.endswith('.stx'))
    textura = spc.buscar(entrada.nombre[:-4] + '.srdv')
    original = Fuente(entrada.datos, textura.datos)
    nuevos = crear_glifos_juicio(original, referencia)
    if not nuevos:
        return datos, 0
    # Cuatro niveles de alfa conservan suavizado y permiten comprimir las letras
    # escaladas. Solo se cuantizan los glifos nuevos, nunca los originales.
    nuevos = {c: ((np.rint(img.astype(float) / 85) * 85).astype(np.uint8), izq, der, y)
              for c, (img, izq, der, y) in nuevos.items()}
    # Primero se intenta usar el atlas original. Si esta lleno, se agrega una fila.
    for extra in (0, 100, 200, 300, 400):
        f = Fuente(entrada.datos, textura.datos)
        if extra:
            f.alto = (f.alto + extra + 3) // 4 * 4
            tam = f.ancho * f.alto // 2
            f.srdv.extend(b'\x01\x00\x49\x92\x24\x49\x92\x24' * ((tam - len(f.srdv)) // 8))
            struct.pack_into('<H', f.srd, 0x28, f.alto)
            struct.pack_into('<I', f.srd, 0x54, tam)
        try:
            f.agregar_en_huecos(nuevos)
        except ValueError:
            continue
        entrada.datos, textura.datos = f.serializar()
        return spc.a_bytes(recomprimir=True), len(nuevos)
    raise ValueError('No hay espacio para los diacriticos de juicio')
