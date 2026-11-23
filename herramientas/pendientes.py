"""Muestra las cadenas sin traducir de un capitulo (sin repetir textos).

Uso:
    python pendientes.py <capitulo> <archivo.stx> [<archivo.stx> ...]
"""
import json
import os
import sys

from config import RAIZ


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    with open(os.path.join(RAIZ, "traduccion", sys.argv[1] + ".json"), encoding="utf-8") as f:
        datos = json.load(f)
    vistos = set()
    for nombre in sys.argv[2:]:
        print("==", nombre)
        for c in datos[nombre]:
            if c["es"] or c["en"] in vistos:
                continue
            vistos.add(c["en"])
            print(c["id"], json.dumps(c["en"], ensure_ascii=False))


if __name__ == "__main__":
    main()
