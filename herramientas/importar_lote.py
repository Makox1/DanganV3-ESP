"""Incorpora un lote de traducciones al JSON de un capitulo.

Uso:
    python importar_lote.py <capitulo> <lote.json>
    python importar_lote.py <capitulo> <lote.json> --por-texto

El lote tiene la forma {"archivo.stx": {"id": "texto en espanol", ...}, ...}.
Con --por-texto, el lote es {"texto en ingles": "texto en espanol", ...} y se
aplica a todas las cadenas con ese ingles. Con --sobrescribir tambien reemplaza las
que ya estaban traducidas (sirve para corregir una linea repetida en muchos archivos).
Las cadenas del capitulo con el mismo texto en ingles que aun no esten
traducidas reciben la misma traduccion (memoria de traduccion).
"""
import json
import os
import sys

from config import RAIZ


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    capitulo, ruta_lote = sys.argv[1], sys.argv[2]
    ruta = os.path.join(RAIZ, "traduccion", capitulo + ".json")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    with open(ruta_lote, encoding="utf-8") as f:
        lote = json.load(f)

    memoria = {}
    importadas = 0
    if "--por-texto" in sys.argv:
        memoria = dict(lote)
        lote = {}
    for nombre, traducciones in lote.items():
        cadenas = {c["id"]: c for c in datos[nombre]}
        for id_cadena, texto in traducciones.items():
            c = cadenas[int(id_cadena)]
            c["es"] = texto
            memoria[c["en"]] = texto
            importadas += 1

    # --sobrescribir: tambien reemplaza traducciones existentes con el mismo ingles
    sobrescribir = "--sobrescribir" in sys.argv
    repetidas = 0
    for cadenas in datos.values():
        for c in cadenas:
            if (sobrescribir or not c["es"]) and c["en"] in memoria and c["es"] != memoria[c["en"]]:
                c["es"] = memoria[c["en"]]
                repetidas += 1

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print("%d cadenas importadas, %d repetidas rellenadas" % (importadas, repetidas))


if __name__ == "__main__":
    main()
