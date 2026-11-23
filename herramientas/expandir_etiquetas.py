"""Expande abreviaturas de etiquetas en un lote antes de importarlo.

Uso:
    python expandir_etiquetas.py <lote.json>

<S> -> <CLT=cltSTRONG>, <N> -> <CLT=cltNORMAL>, <M> -> <CLT=cltMIND>, <SYS> -> <CLT=cltSYSTEM>
El archivo se sobrescribe con las etiquetas completas.
"""
import json
import sys

ABREVIATURAS = {
    "<S>": "<CLT=cltSTRONG>",
    "<N>": "<CLT=cltNORMAL>",
    "<M>": "<CLT=cltMIND>",
    "<SYS>": "<CLT=cltSYSTEM>",
}


def expandir(texto):
    for corta, larga in ABREVIATURAS.items():
        texto = texto.replace(corta, larga)
    return texto


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    with open(sys.argv[1], encoding="utf-8") as f:
        lote = json.load(f)
    lote = {nombre: {i: expandir(t) for i, t in cadenas.items()} for nombre, cadenas in lote.items()}
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lote, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
