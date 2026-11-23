"""Reemplaza una traduccion por otra en todas las cadenas de un capitulo.

Uso:
    python reemplazar_es.py <capitulo> <lote.json>

El lote es {"traduccion actual": "traduccion nueva", ...}. Sirve para corregir
una linea que la memoria de traduccion copio en muchos archivos.
"""
import json
import os
import sys

from config import RAIZ


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    ruta = os.path.join(RAIZ, "traduccion", sys.argv[1] + ".json")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        cambios = json.load(f)
    total = 0
    for cadenas in datos.values():
        for c in cadenas:
            if c["es"] in cambios:
                c["es"] = cambios[c["es"]]
                total += 1
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print("%d cadenas cambiadas" % total)


if __name__ == "__main__":
    main()
