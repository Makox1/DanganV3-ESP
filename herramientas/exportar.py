"""Exporta el texto de un capitulo a JSON para traducir.

Uso:
    python exportar.py <capitulo>      (ej: chap0, chap1, residente, objetos)

Genera traduccion/<capitulo>.json. Si el JSON ya existe, conserva las
traducciones ya hechas ("es") de las cadenas cuyo ingles no cambio.
"residente" son los textos de menus, objetos, etc. de game_resident_US.spc.
"objetos" son los nombres de lo que se puede examinar en el mapa.
"""
import json
import os
import sys

from cpk import CPK
from spc import SPC
import stx
from config import (CPK_US, CPK_RESIDENTE, SPC_RESIDENTE, SPC_OBJETOS, VERSION_REFERENCIA, RAIZ,
                    respaldo_cabecera)


def origen(capitulo):
    """Devuelve (ruta_cpk, ruta_spc) de donde sale el texto de un capitulo."""
    if capitulo == "residente":
        return CPK_RESIDENTE, SPC_RESIDENTE
    if capitulo == "objetos":
        return CPK_US, SPC_OBJETOS
    return CPK_US, "wrd_script/%s/%s_text_US.SPC" % (VERSION_REFERENCIA, capitulo)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    capitulo = sys.argv[1]
    ruta_cpk, ruta_spc = origen(capitulo)
    # Siempre se lee el contenido original, aunque el juego ya este parcheado
    cpk = CPK(ruta_cpk, respaldo_cabecera(ruta_cpk))
    archivo = next(a for a in cpk.archivos if a["nombre"] == ruta_spc)
    spc = SPC(cpk.leer(archivo))

    destino = os.path.join(RAIZ, "traduccion", capitulo + ".json")
    previo = {}
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            for nombre, cadenas in json.load(f).items():
                for c in cadenas:
                    previo[(nombre, c["id"], c["en"])] = c["es"]

    salida = {}
    total = 0
    for e in spc.entradas:
        if not e.nombre.endswith(".stx") or e.datos[:4] != stx.MAGIA:
            continue
        _, _, cadenas = stx.leer(e.datos)
        salida[e.nombre] = [
            {"id": i, "en": t, "es": previo.get((e.nombre, i, t), "")}
            for i, t in cadenas
        ]
        total += len(cadenas)

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print("%s: %d archivos, %d cadenas -> %s" % (capitulo, len(salida), total, destino))


if __name__ == "__main__":
    main()
