"""Revisa las traducciones de un capitulo.

Uso:
    python revisar.py <capitulo>

Comprueba en cada cadena traducida:
  - que las etiquetas <...> sean las mismas que en ingles
  - que no haya caracteres sin glifo en la fuente (ya con los glifos en espanol)
  - que ninguna linea sea mas ancha que la linea inglesa mas ancha del capitulo
  - que no haya mas lineas que en el original (+1 de margen)
"""
import json
import os
import re
import sys

from cpk import CPK
from spc import SPC
import fuente
from config import CPK_RESIDENTE, SPC_RESIDENTE, RAIZ, respaldo_cabecera

ETIQUETA = re.compile(r"<[^>]*>")
ANCHO_ICONO = 40
LIMITE_DIALOGO = 1240
ANCHO_MENSAJE = 600
LIMITE_MENSAJE = 1400
# La ayuda de controles (OPTIONS) tiene columnas anchas: unos 1400 px libres
LIMITE_AYUDA = 1200
# Listas de una sola columna (galeria de Extras, mapa, nombres): todas sus filas comparten ancho.
# Tambien el Armamento Argumental y las opciones del Psico Taxi: cada texto sale en el mismo
# globo/boton/etiqueta que el ingles mas ancho
LISTAS_COLUMNA = {"O-Event.stx", "O-Movie.stx", "O-Shinmitsu.stx", "O-Artwork.stx",
                  "A-MapName.stx", "A-MapListNameAscii.stx", "A-CharacterName.stx",
                  "Mtb-Voice.stx", "Mtb-Answer.stx", "BrainDrive-Answer.stx"}


def cargar_fuente():
    cpk = CPK(CPK_RESIDENTE, respaldo_cabecera(CPK_RESIDENTE))
    archivo = next(a for a in cpk.archivos if a["nombre"] == SPC_RESIDENTE)
    spc = SPC(cpk.leer(archivo))
    f = fuente.Fuente(spc.buscar("v3_font00.stx").datos, spc.buscar("v3_font00.srdv").datos)
    for c, (img, izq, der, desp_y) in fuente.crear_glifos_espanol(f).items():
        f.glifos[ord(c)] = {"x": 0, "y": 0, "ancho": img.shape[1], "alto": img.shape[0],
                            "izq": izq, "der": der, "desp_y": desp_y}
    return f


def ancho_linea(f, linea, faltantes):
    total = 0
    for parte in ETIQUETA.split(linea):
        for c in parte:
            g = f.glifos.get(ord(c))
            if g is None:
                faltantes.add(c)
                continue
            total += g["izq"] + g["ancho"] + g["der"]
    total += ANCHO_ICONO * len(re.findall(r"<PAD=", linea))
    return total


def lineas(texto):
    return texto.replace("\r\n", "\n").split("\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    capitulo = sys.argv[1]
    with open(os.path.join(RAIZ, "traduccion", capitulo + ".json"), encoding="utf-8") as fh:
        datos = json.load(fh)
    f = cargar_fuente()

    basura = set()
    limite_global = max(ancho_linea(f, l, basura)
                        for cadenas in datos.values() for c in cadenas for l in lineas(c["en"]))
    # Los textos de interfaz tienen cajas de tamano propio: se compara con su ingles (+20%)
    por_cadena = capitulo == "residente"
    hechas = total = problemas = 0
    for nombre, cadenas in datos.items():
        for c in cadenas:
            total += 1
            if not c["es"]:
                continue
            hechas += 1
            avisos = []
            if sorted(ETIQUETA.findall(c["en"])) != sorted(ETIQUETA.findall(c["es"])):
                avisos.append("etiquetas distintas")
            faltantes = set()
            # Cuadro de dialogo: limite fijo, salvo que el ingles de esa cadena ya sea mas ancho
            limite = max(LIMITE_DIALOGO, max(ancho_linea(f, l, basura) for l in lineas(c["en"])))
            if por_cadena:
                ancho_en = max(ancho_linea(f, l, basura) for l in lineas(c["en"]))
                limite = int(ancho_en * 1.2)
                # Los mensajes largos van en ventanas emergentes amplias
                if ancho_en > ANCHO_MENSAJE:
                    limite = max(limite, LIMITE_MENSAJE)
                if nombre.startswith("F-Help") or nombre == "J-TutorialTitle.stx":
                    limite = max(limite, LIMITE_AYUDA)
                # Las etiquetas del tutorial se comprimen a lo ancho si no caben
                elif nombre.startswith("J-Tutorial"):
                    limite = int(ancho_en * 1.7)
                # Las listas de una columna: cabe lo que cabe su fila inglesa mas ancha
                elif nombre in LISTAS_COLUMNA:
                    limite = max(limite, max(ancho_linea(f, l, basura)
                                             for x in cadenas for l in lineas(x["en"])))
            for l in lineas(c["es"]):
                ancho = ancho_linea(f, l, faltantes)
                if ancho > limite:
                    avisos.append("linea demasiado ancha (%d > %d px): %s" % (ancho, limite, ETIQUETA.sub("", l)))
            if faltantes:
                avisos.append("caracteres sin glifo: %s" % "".join(sorted(faltantes)))
            if len(lineas(c["es"])) > len(lineas(c["en"])) + 1:
                avisos.append("demasiadas lineas")
            if ("\r\n" in c["en"]) != ("\r\n" in c["es"]):
                avisos.append("salto de linea \\r\\n distinto")
            for a in avisos:
                problemas += 1
                print("%s #%d: %s" % (nombre, c["id"], a))
    print("%s: %d/%d cadenas traducidas, %d avisos (limite %s)" % (
        capitulo, hechas, total, problemas, "ingles +20%" if por_cadena else "%d px" % limite_global))


if __name__ == "__main__":
    main()
