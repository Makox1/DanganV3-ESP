"""Busca adjetivos con el genero equivocado segun quien habla cada linea.

Uso:
    python genero.py <capitulo>      p. ej. chap1

El hablante sale de los guiones .wrd (comando 0x1d = nombre en pantalla, 0x46 =
linea de texto). chara_Blank es la narracion interna de la protagonista (Kaede) y,
tras la revelacion del juicio del capitulo 1 (c01_224 en adelante), de Shuichi.
Desde el capitulo 2 la narracion es siempre de Shuichi.
Muestra candidatos para revisar a mano: muchos son descripciones de otra persona.
"""
import json
import os
import re
import struct
import sys

from cpk import CPK
from spc import SPC
from config import CPK_US, RAIZ, VERSION_REFERENCIA, respaldo_cabecera

FEMENINOS = ("Akama", "Tojo_", "Iruma", "Yonag", "Shiro", "Chaba", "Haruk", "Yumen", "Mfunn")
MASCULINOS = ("Saiha", "Momot", "Oma__", "Ki-Bo", "Monok", "Hoshi", "Gokuh", "Shing", "Amami",
              "Mtaro", "Mkid_", "Msuke", "Mdam_")
ADJETIVOS = (r"segur|cansad|list|preocupad|nervios|agotad|tranquil|content|emocionad|sorprendid|"
             r"confundid|asustad|convencid|equivocad|enojad|molest|agradecid|encantad|obligad|perdid|"
             r"aburrid|dispuest|orgullos|celos|avergonzad|decepcionad|interesad|ocupad|despiert|dormid|"
             r"muert|viv|herid|atrapad|acostumbrad|curios|tont|estúpid|sol|mism|calmad|aliviad|"
             r"impresionad|asustad|aterrad|hart|preparad|decidid|conmovid|halagad|desesperad|frustrad|"
             r"desanimad|animad|callad|quiet|escondid|encerrad|abandonad|olvidad|enamorad|furios")
PRIMERA = re.compile(r"\b(?:estoy|estaba|estuve|estaré|soy|era|fui|seré|me siento|me sentí|me quedé|"
                     r"me quedaré|quedé|me puse|ando|sigo|me veo)\s+(?:muy |tan |bastante |un poco |"
                     r"algo |más |medio |demasiado )?((?:" + ADJETIVOS + r")(?:o|a))\b", re.I)
SEGUNDA = re.compile(r"\b(?:estás|estabas|eres|eras|fuiste|te ves|pareces|te sientes|te quedaste)\s+"
                     r"(?:muy |tan |bastante |un poco |algo |más |demasiado )?((?:" + ADJETIVOS +
                     r")(?:o|a))\b", re.I)
ARTICULO = re.compile(r"\bsoy\s+(el|la)\s+(culpable|único|única|primero|primera|último|última)\b", re.I)


def leer_wrd(datos):
    """Devuelve (parametros, comandos) de un guion .wrd."""
    n_par = struct.unpack_from("<H", datos, 4)[0]
    offsets = struct.unpack_from("<IIII", datos, 0x0C)
    parametros, pos = [], offsets[3]
    for _ in range(n_par):
        largo = datos[pos]
        parametros.append(datos[pos + 1:pos + 1 + largo].decode("utf-8", "replace"))
        pos += largo + 2
    comandos, pos = [], 0x20
    while pos < offsets[0]:
        op = datos[pos + 1]
        pos += 2
        args = []
        while pos < offsets[0] and datos[pos] != 0x70:
            args.append(struct.unpack_from(">H", datos, pos)[0])
            pos += 2
        comandos.append((op, args))
    return parametros, comandos


def hablantes(capitulo):
    """{"archivo.stx#id": codigo de personaje} de la version de referencia."""
    us = CPK(CPK_US, respaldo_cabecera(CPK_US))
    general = CPK(CPK_US.replace("_us.cpk", ".cpk"))
    spc = None
    for cpk, nombre in ((us, "%s_US.SPC" % capitulo), (general, "%s.SPC" % capitulo)):
        ruta = "wrd_script/%s/%s" % (VERSION_REFERENCIA, nombre)
        archivo = next((a for a in cpk.archivos if a["nombre"] == ruta), None)
        if archivo:
            spc = SPC(cpk.leer(archivo))
            break
    resultado = {}
    for e in spc.entradas:
        if not e.nombre.endswith(".wrd"):
            continue
        parametros, comandos = leer_wrd(e.datos)
        actual = None
        for op, args in comandos:
            if op == 0x1D and args and args[0] < len(parametros):
                actual = parametros[args[0]]
            elif op == 0x46 and args:
                resultado["%s.stx#%d" % (e.nombre[:-4], args[0])] = actual
    return resultado


def genero(archivo, codigo):
    if codigo in (None, "chara_Blank"):
        m = re.match(r"c01_(\d{3})", archivo)
        if m and 224 <= int(m.group(1)) <= 302 and not 270 <= int(m.group(1)) < 280:
            return "M"
        if re.match(r"c0[01]_", archivo):
            return "F"
        return "M"
    if codigo.endswith(FEMENINOS):
        return "F"
    if codigo.endswith(MASCULINOS):
        return "M"
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    capitulo = sys.argv[1]
    mapa = hablantes(capitulo)
    with open(os.path.join(RAIZ, "traduccion", capitulo + ".json"), encoding="utf-8") as f:
        datos = json.load(f)
    for archivo, cadenas in datos.items():
        anterior = None
        for c in sorted(cadenas, key=lambda c: c["id"]):
            texto = re.sub(r"<[^>]*>", "", c["es"])
            codigo = mapa.get("%s#%d" % (archivo, c["id"]))
            g = genero(archivo, codigo)
            avisos = []
            if g:
                for m in PRIMERA.finditer(texto):
                    if ("F" if m.group(1).lower().endswith("a") else "M") != g:
                        avisos.append("1a persona: " + m.group(0))
                for m in ARTICULO.finditer(texto):
                    if ("F" if m.group(1).lower() == "la" else "M") != g:
                        avisos.append("1a persona: " + m.group(0))
            if anterior and anterior[0] != codigo:
                for m in SEGUNDA.finditer(texto):
                    if ("F" if m.group(1).lower().endswith("a") else "M") != anterior[1]:
                        avisos.append("2a persona (a %s): %s" % (anterior[0], m.group(0)))
            if avisos:
                print("%s#%d [%s] %s || %s" % (archivo, c["id"], codigo, "; ".join(avisos),
                                              texto.replace("\n", " / ")))
            if codigo and g:
                anterior = (codigo, g)


if __name__ == "__main__":
    main()
