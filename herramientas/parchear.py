"""Aplica o revierte la traduccion sobre los CPK del juego.

Uso:
    python parchear.py aplicar      Restaura los originales y aplica traduccion/*.json + fuente
    python parchear.py aplicar residente|textos   Aplica solo una parte (la otra queda original)
    python parchear.py revertir     Deja los CPK exactamente como los originales

El parche escribe los archivos modificados en su hueco original (o al final del
CPK si no caben) y redirige sus entradas en la TOC. Antes del primer parche se
guarda en respaldo/ la cabecera + TOC original, las zonas sobrescritas y el
tamano de cada CPK, de modo que revertir es instantaneo.
Tambien aplica las texturas traducidas de traduccion/imagenes.json.
"""
import glob
import json
import os
import struct
import sys

from cpk import CPK
from spc import SPC
import stx
import fuente
import imagenes
import fuentes_juicio
from config import (CPK_US, CPK_RESIDENTE, SPC_RESIDENTE, SPC_OBJETOS, RESPALDO, RAIZ, VERSIONES,
                    respaldo_cabecera)

FUENTE = "v3_font00"


class ParcheCPK:
    """Parchea un CPK en sitio.

    Un archivo modificado se escribe sobre su hueco original si cabe (el CPK no cambia
    de tamano); si no cabe, se anade al final y el ETOC se mueve detras.
    partition_resident_win.cpk no admite crecer: el juego se cierra al arrancar.
    """

    def __init__(self, ruta, puede_crecer=True):
        self.ruta = ruta
        self.puede_crecer = puede_crecer
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        self.prefijo = os.path.join(RESPALDO, nombre)
        self.respaldo_cab = respaldo_cabecera(ruta)
        self.respaldo_info = self.prefijo + "_info.json"
        self.cpk = None
        self.archivo = None
        self.fin = 0
        self.crecio = False

    def _leer_info(self):
        with open(self.respaldo_info, encoding="utf-8") as f:
            info = json.load(f)
        info.setdefault("regiones", {})
        return info

    def _guardar_info(self, info):
        with open(self.respaldo_info, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=1)

    def crear_respaldo(self):
        if os.path.exists(self.respaldo_info):
            return
        cpk = CPK(self.ruta)
        fin_toc = cpk.toc_pos + len(cpk.toc.datos)
        tam_cab = max(cpk.cabecera["ContentOffset"], fin_toc)
        os.makedirs(RESPALDO, exist_ok=True)
        with open(self.ruta, "rb") as f:
            cab = f.read(tam_cab)
        with open(self.respaldo_cab, "wb") as f:
            f.write(cab)
        self._guardar_info({"tam_original": os.path.getsize(self.ruta), "tam_cabecera": tam_cab,
                            "regiones": {}})
        print("Respaldo creado:", self.respaldo_cab)

    def revertir(self):
        if not os.path.exists(self.respaldo_info):
            return False
        info = self._leer_info()
        with open(self.respaldo_cab, "rb") as f:
            cab = f.read()
        with open(self.ruta, "r+b") as f:
            for offset, ruta in info["regiones"].items():
                with open(ruta, "rb") as r:
                    f.seek(int(offset))
                    f.write(r.read())
            f.seek(0)
            f.write(cab)
            f.truncate(info["tam_original"])
        return True

    def __enter__(self):
        self.crear_respaldo()
        self.revertir()
        self.cpk = CPK(self.ruta)
        if self.cpk.toc.cifrada:
            raise RuntimeError("La TOC esta cifrada; el parcheo en sitio no esta soportado")
        self.por_nombre = {a["nombre"]: a for a in self.cpk.archivos}
        self.alineacion = self.cpk.cabecera["Align"]
        # Fin del hueco de cada archivo: inicio del siguiente o fin del contenido
        cab = self.cpk.cabecera
        limite = cab.get("EtocOffset") or (cab["ContentOffset"] + cab["ContentSize"])
        inicios = sorted({a["offset"] for a in self.cpk.archivos} | {limite})
        self.hueco = {}
        for a in self.cpk.archivos:
            siguiente = next(x for x in inicios if x > a["offset"])
            self.hueco[a["nombre"]] = siguiente - a["offset"]
        # Archivo que va justo despues de cada uno (para reacomodar si algo no cabe)
        orden = sorted(self.cpk.archivos, key=lambda a: a["offset"])
        self.siguiente = {a["nombre"]: (orden[i + 1]["nombre"] if i + 1 < len(orden) else None)
                          for i, a in enumerate(orden)}
        self.escritos = set()
        self.datos_escritos = {}
        self.reubicados = set()
        self.grupo_imagenes = {}
        self.archivo = open(self.ruta, "r+b")
        self.archivo.seek(0, os.SEEK_END)
        self.fin = self.archivo.tell()
        return self

    def __exit__(self, *exc):
        """Si se anadieron datos al final, mueve el ETOC detras y amplia ContentSize
        para que el contenido nuevo quede dentro de la zona declarada."""
        f = self.archivo
        cab = self.cpk.cabecera
        try:
            if exc[0] is None and self.crecio and cab.get("EtocOffset"):
                f.seek(cab["EtocOffset"])
                etoc = f.read(cab["EtocSize"])
                self.fin += (self.alineacion - self.fin % self.alineacion) % self.alineacion
                nuevo_etoc = self.fin
                f.seek(nuevo_etoc)
                f.write(etoc)
                f.truncate(nuevo_etoc + len(etoc))
                self._escribir_cabecera("EtocOffset", nuevo_etoc)
                self._escribir_cabecera("ContentSize", nuevo_etoc - cab["ContentOffset"])
        finally:
            f.close()

    def _escribir_cabecera(self, campo, valor):
        pos, tipo = self.cpk.tabla_cabecera.posiciones[0][campo]
        self.archivo.seek(self.cpk.tabla_cabecera.base_archivo + pos)
        self.archivo.write(struct.pack(">Q" if tipo == 6 else ">I", valor))

    def leer(self, nombre):
        archivo = self.por_nombre.get(nombre)
        return None if archivo is None else self.cpk.leer(archivo)

    def _respaldar_region(self, archivo):
        """Guarda el hueco original de un archivo antes de sobrescribirlo."""
        info = self._leer_info()
        clave = str(archivo["offset"])
        if clave in info["regiones"]:
            return
        ruta = "%s_region_%d.bin" % (self.prefijo, archivo["indice"])
        f = self.archivo
        f.seek(archivo["offset"])
        with open(ruta, "wb") as r:
            r.write(f.read(self.hueco[archivo["nombre"]]))
        info["regiones"][clave] = ruta
        self._guardar_info(info)

    def _alinear(self, pos):
        return pos + (self.alineacion - pos % self.alineacion) % self.alineacion

    def _plan_reacomodo(self, nombre, datos):
        """Si datos no caben, intenta recomprimir el archivo siguiente (sin cambiar
        su contenido) y correrlo hacia adelante dentro del espacio de ambos.
        Devuelve (nombre_siguiente, datos_siguiente, posicion) o None."""
        sig = self.siguiente.get(nombre)
        if not sig or sig in self.escritos or sig in self.reubicados:
            return None
        original = self.leer(sig)
        if original[:4] != b"CPS.":
            return None
        datos_sig = SPC(original).a_bytes(recomprimir=True)
        archivo = self.por_nombre[nombre]
        pos_sig = self._alinear(archivo["offset"] + len(datos))
        fin = archivo["offset"] + self.hueco[nombre] + self.hueco[sig]
        if pos_sig + len(datos_sig) > fin:
            return None
        return sig, datos_sig, pos_sig

    def cabe(self, nombre, datos):
        return len(datos) <= self.hueco[nombre] or self._plan_reacomodo(nombre, datos) is not None

    def _escribir_toc(self, archivo, destino, tam):
        pos = self.cpk.toc.posiciones[archivo["indice"]]
        for campo, fmt, valor in (("FileOffset", ">Q", destino - self.cpk.desplazamiento),
                                  ("FileSize", ">I", tam),
                                  ("ExtractSize", ">I", tam)):
            self.archivo.seek(self.cpk.toc.base_archivo + pos[campo][0])
            self.archivo.write(struct.pack(fmt, valor))

    def corrida(self, primero, ultimo):
        """Nombres de los archivos contiguos desde primero hasta ultimo (por offset)."""
        nombres = [primero]
        while nombres[-1] != ultimo:
            nombres.append(self.siguiente[nombres[-1]])
        return nombres

    def compactar(self, nombres, solo_plan=False, optimo=False):
        """Recomprime una corrida contigua de archivos y los junta al inicio de su
        zona. Devuelve el bloque libre (inicio, fin) que queda detras.

        El contenido de cada SPC no cambia; solo su compresion y su posicion. Los
        archivos ya traducidos con reemplazar() se mueven con los datos escritos.
        optimo: comprime con comprimir_optimo y conserva el original si ocupa menos.
        """
        archivos = [self.por_nombre[n] for n in nombres]
        for a, b in zip(archivos, archivos[1:]):
            if a["offset"] + self.hueco[a["nombre"]] != b["offset"]:
                raise RuntimeError("%s y %s no son contiguos" % (a["nombre"], b["nombre"]))
        if any(n in self.escritos and n not in self.datos_escritos for n in nombres):
            raise RuntimeError("La corrida incluye archivos ya modificados")
        if not hasattr(self, "_compactados"):
            self._compactados = {}
        # Se leen y recomprimen todos antes de escribir, porque las zonas se pisan.
        for n in nombres:
            if n in self.datos_escritos:
                self._compactados[n] = self.datos_escritos[n]
            elif n not in self._compactados and optimo:
                original = self.leer(n)
                nuevo = SPC(original).a_bytes(recomprimir=True, optimo=True)
                self._compactados[n] = nuevo if len(nuevo) < len(original) else original
            elif n not in self._compactados:
                self._compactados[n] = SPC(self.leer(n)).a_bytes(recomprimir=True)
        pos = archivos[0]["offset"]
        plan = []
        for a in archivos:
            plan.append((a, self._compactados[a["nombre"]], pos))
            pos = self._alinear(pos + len(self._compactados[a["nombre"]]))
        fin = archivos[-1]["offset"] + self.hueco[archivos[-1]["nombre"]]
        if pos > fin:
            raise RuntimeError("La corrida recomprimida no cabe en su zona")
        if solo_plan:
            return pos, fin
        for a in archivos:
            self._respaldar_region(a)
        for a, datos, destino in plan:
            self.archivo.seek(destino)
            self.archivo.write(datos)
            self._escribir_toc(a, destino, len(datos))
            self.reubicados.add(a["nombre"])
        inicio = self._alinear(plan[-1][2] + len(plan[-1][1]))
        self.archivo.seek(plan[0][2])
        # Se limpian los restos entre archivos y el bloque libre final.
        for (a, datos, destino), siguiente in zip(plan, [p[2] for p in plan[1:]] + [fin]):
            self.archivo.seek(destino + len(datos))
            self.archivo.write(b"\0" * (siguiente - destino - len(datos)))
        return inicio, fin

    def reemplazar_grupo(self, reemplazos, solo_plan=False, extra=()):
        """Reparte un grupo entre sus huecos y las colas libres de guiones parcheados.

        Planifica todo antes de escribir. Las colas pertenecen a regiones ya
        respaldadas; no se modifica el tamano del CPK ni se pisa otro recurso.
        extra son bloques libres (inicio, fin) dejados por compactar().
        """
        huecos = [(self.por_nombre[n]['offset'], self.por_nombre[n]['offset'] + self.hueco[n])
                  for n in reemplazos] + list(extra)
        self.archivo.flush()
        actuales = {a['nombre']: a for a in CPK(self.ruta).archivos}
        for nombre in self.escritos:
            if not nombre.startswith('wrd_script/') or nombre in self.reubicados:
                continue
            original, actual = self.por_nombre[nombre], actuales[nombre]
            if actual['offset'] != original['offset'] or self.siguiente[nombre] in self.reubicados:
                continue
            inicio = self._alinear(actual['offset'] + actual['tam'])
            fin = original['offset'] + self.hueco[nombre]
            if inicio < fin:
                huecos.append((inicio, fin))
        unidos = []
        for inicio, fin in sorted(huecos):
            if unidos and unidos[-1][1] == inicio:
                unidos[-1] = (unidos[-1][0], fin)
            else:
                unidos.append((inicio, fin))
        plan = []
        for nombre, datos in sorted(reemplazos.items(), key=lambda p: -len(p[1])):
            opciones = [(fin - inicio, i) for i, (inicio, fin) in enumerate(unidos)
                        if fin - inicio >= len(datos)]
            if not opciones:
                raise RuntimeError('No hay espacio interno para %s; no se escribio el grupo' % nombre)
            _, i = min(opciones)
            inicio, fin = unidos.pop(i)
            plan.append((nombre, datos, inicio))
            siguiente = self._alinear(inicio + len(datos))
            if siguiente < fin:
                unidos.append((siguiente, fin))
        if solo_plan:
            return plan
        for nombre in reemplazos:
            self._respaldar_region(self.por_nombre[nombre])
        for nombre, datos, destino in plan:
            self.archivo.seek(destino)
            self.archivo.write(datos)
            self._escribir_toc(self.por_nombre[nombre], destino, len(datos))
            self.escritos.add(nombre)

    def reemplazar(self, nombre, datos):
        """Escribe datos en el hueco original; si no caben, reacomoda el archivo
        siguiente (o, si el CPK puede crecer, los anade al final) y actualiza la TOC."""
        if nombre in self.reubicados:
            raise RuntimeError("%s ya se movio para hacer espacio; no se puede reemplazar" % nombre)
        self.escritos.add(nombre)
        self.datos_escritos[nombre] = datos
        archivo = self.por_nombre[nombre]
        f = self.archivo
        hueco = self.hueco[nombre]
        plan = None if len(datos) <= hueco else self._plan_reacomodo(nombre, datos)
        if plan:
            sig, datos_sig, pos_sig = plan
            archivo_sig = self.por_nombre[sig]
            self._respaldar_region(archivo)
            self._respaldar_region(archivo_sig)
            fin = archivo["offset"] + hueco + self.hueco[sig]
            f.seek(archivo["offset"])
            f.write(datos + b"\0" * (pos_sig - archivo["offset"] - len(datos)))
            f.write(datos_sig + b"\0" * (fin - pos_sig - len(datos_sig)))
            self._escribir_toc(archivo, archivo["offset"], len(datos))
            self._escribir_toc(archivo_sig, pos_sig, len(datos_sig))
            self.reubicados.add(sig)
            return "en sitio, %s reacomodado" % os.path.basename(sig)
        if len(datos) <= hueco:
            self._respaldar_region(archivo)
            destino = archivo["offset"]
            f.seek(destino)
            f.write(datos + b"\0" * (hueco - len(datos)))
        else:
            if not self.puede_crecer:
                raise RuntimeError("%s no cabe en su hueco (%d > %d bytes) y %s no puede crecer"
                                   % (nombre, len(datos), hueco, os.path.basename(self.ruta)))
            self.fin += (self.alineacion - self.fin % self.alineacion) % self.alineacion
            destino = self.fin
            f.seek(destino)
            f.write(datos)
            self.fin += len(datos)
            self.crecio = True
        self._escribir_toc(archivo, destino, len(datos))
        return "en sitio" if destino == archivo["offset"] else "al final"


RUTA_VARIANTES = os.path.join(RAIZ, "traduccion", "variantes.json")


def cargar_traducciones():
    """Devuelve {capitulo: {archivo_stx: {id: (en, es, {ingles_variante: es})}}}.

    traduccion/variantes.json ({capitulo: {archivo_stx: {id: {ingles: es}}}}) guarda las
    cadenas cuyo ingles cambia entre versiones (003-005 frente a 007); va aparte porque
    exportar.py regenera los json de capitulo."""
    variantes = {}
    if os.path.exists(RUTA_VARIANTES):
        with open(RUTA_VARIANTES, encoding="utf-8") as f:
            variantes = json.load(f)
    resultado = {}
    for ruta in sorted(glob.glob(os.path.join(RAIZ, "traduccion", "*.json"))):
        capitulo = os.path.splitext(os.path.basename(ruta))[0]
        # imagenes.json tiene otro formato y lo procesa parchear_imagenes
        if capitulo in ("imagenes", "variantes"):
            continue
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        extra = variantes.get(capitulo, {})
        resultado[capitulo] = {
            nombre: {c["id"]: (c["en"], c["es"], extra.get(nombre, {}).get(str(c["id"]), {}))
                     for c in cadenas if c["es"]}
            for nombre, cadenas in datos.items()
        }
    return resultado


RUTA_ESCRITAS = os.path.join(RESPALDO, "textos_escritos.json")


def cargar_escritas():
    """Devuelve {capitulo: {archivo_stx: {id: [textos_es_ya_escritos]}}}.

    Algunas regiones de respaldo se guardaron con textos ya traducidos, asi que tras
    revertir el "original" de esas cadenas es un espanol anterior y no el ingles.
    """
    if not os.path.exists(RUTA_ESCRITAS):
        return {}
    with open(RUTA_ESCRITAS, encoding="utf-8") as f:
        return json.load(f)


def guardar_escritas(escritas):
    with open(RUTA_ESCRITAS, "w", encoding="utf-8") as f:
        json.dump(escritas, f, ensure_ascii=False)


def traducir_spc(datos_spc, tabla, previas=None):
    """Aplica las traducciones a un SPC. Devuelve (bytes_nuevos, cadenas_cambiadas).

    previas: {archivo_stx: {id: [textos]}} con traducciones escritas antes; se amplia
    con lo que se escribe ahora."""
    if previas is None:
        previas = {}
    spc = SPC(datos_spc)
    cambios = 0
    for e in spc.entradas:
        traducciones = tabla.get(e.nombre)
        if not traducciones:
            continue
        anteriores = previas.setdefault(e.nombre, {})
        idioma, desconocido, cadenas = stx.leer(e.datos)
        nuevas = []
        for i, texto in cadenas:
            par = traducciones.get(i)
            ya_escritas = anteriores.setdefault(str(i), []) if par else []
            # Solo se reemplaza si el ingles coincide, por si las versiones difieren,
            # o si el texto es una traduccion nuestra que quedo en el respaldo
            if par and (par[0] == texto or texto in ya_escritas):
                nuevas.append((i, par[1]))
                if par[1] not in ya_escritas:
                    ya_escritas.append(par[1])
                cambios += 1
            elif par and texto in par[2]:
                # Ingles de otra version: su traduccion respeta sus etiquetas
                nuevas.append((i, par[2][texto]))
                cambios += 1
            else:
                nuevas.append((i, texto))
        e.datos = stx.escribir(idioma, desconocido, nuevas)
    return spc.a_bytes(recomprimir=True), cambios


def parchear_textos():
    traducciones = cargar_traducciones()
    escritas = cargar_escritas()
    with ParcheCPK(CPK_US, puede_crecer=False) as parche:
        for capitulo, tabla in traducciones.items():
            if capitulo == "residente" or not any(tabla.values()):
                continue
            if capitulo == "objetos":
                nombres = [SPC_OBJETOS]
            else:
                nombres = ["wrd_script/%s/%s_text_US.SPC" % (v, capitulo) for v in VERSIONES]
            for nombre in nombres:
                datos = parche.leer(nombre)
                if datos is None:
                    continue
                nuevos, cambios = traducir_spc(datos, tabla, escritas.setdefault(capitulo, {}))
                modo = parche.reemplazar(nombre, nuevos)
                print("%-40s %5d cadenas (%s)" % (nombre, cambios, modo))
        guardar_escritas(escritas)
        parchear_imagenes(parche)
        parchear_fuentes_juicio(parche)


def parchear_fuentes_juicio(parche):
    """Las fuentes de debate se cargan aparte de la fuente residente."""
    cpk = CPK(CPK_RESIDENTE, respaldo_cabecera(CPK_RESIDENTE))
    archivo = next(a for a in cpk.archivos if a['nombre'] == SPC_RESIDENTE)
    spc = SPC(cpk.leer(archivo))
    referencia = fuente.Fuente(spc.buscar(FUENTE + '.stx').datos, spc.buscar(FUENTE + '.srdv').datos)
    reemplazos = {}
    cuentas = {}
    for nombre in parche.por_nombre:
        if fuentes_juicio.es_fuente(nombre):
            datos, cantidad = fuentes_juicio.preparar(parche.leer(nombre), referencia)
            if cantidad:
                reemplazos[nombre] = datos
                cuentas[nombre] = cantidad
    # Texturas traducidas que no cupieron en su hueco (ver parchear_imagenes)
    reemplazos.update(parche.grupo_imagenes)
    # Las fuentes completas no caben en sus huecos: se compactan los guiones de
    # chap2-6 (sin cambiar su contenido) para dejar bloques libres contiguos.
    corridas, bloques = reservar_espacio_fuentes(parche, reemplazos)
    for nombres, optimo in corridas:
        parche.compactar(nombres, optimo=optimo)
        print('%-40s compactado (%d archivos)' % (os.path.dirname(nombres[0]), len(nombres)))
    parche.reemplazar_grupo(reemplazos, extra=bloques)
    for nombre, cantidad in cuentas.items():
        print('%-40s %5d glifos de juicio (dentro del CPK)' % (nombre, cantidad))


# Avisos de inicio: juntos les faltan ~25 KB. Los cuatro archivos del casino que los
# preceden (sin traducir), con compresion optima, dejan ~28 KB libres pegados a ellos.
CORRIDAS_PREVIAS = {
    "flash/caution/caution_download_US.spc": ("flash/casino/casino_keihin_US.spc", "flash/casino/casino_top_US.spc"),
}


def reservar_espacio_fuentes(parche, reemplazos):
    """Elige cuantas versiones de guiones compactar para que quepan las fuentes.

    Las texturas grandes que no caben (CORRIDAS_PREVIAS) se compactan primero sus
    vecinos anteriores, para que el bloque libre quede pegado a su hueco.
    Devuelve (corridas, bloques) sin escribir nada; corridas es [(nombres, optimo)].
    """
    corridas, bloques = [], []
    candidatas = [(CORRIDAS_PREVIAS[n], True) for n in reemplazos if n in CORRIDAS_PREVIAS]
    candidatas += [(('wrd_script/%s/chap2_text_US.SPC' % v, 'wrd_script/%s/chap6_US.SPC' % v), False)
                   for v in VERSIONES]
    for candidata in candidatas + [None]:
        try:
            parche.reemplazar_grupo(reemplazos, solo_plan=True, extra=bloques)
            return corridas, bloques
        except RuntimeError:
            if candidata is None:
                raise
        (primero, ultimo), optimo = candidata
        nombres = parche.corrida(primero, ultimo)
        bloques.append(parche.compactar(nombres, solo_plan=True, optimo=optimo))
        corridas.append((nombres, optimo))


def parchear_imagenes(parche):
    """Texturas con texto (traduccion/imagenes.json), en el mismo CPK que los textos."""
    for nombre, traducciones in imagenes.cargar_config().items():
        spc = SPC(parche.leer(nombre))
        e_srd = spc.buscar("texture.srd")
        e_srdv = spc.buscar("texture.srdv")
        srd_original, srdv_original = e_srd.datos, e_srdv.datos
        e_srd.datos, e_srdv.datos, hechas = imagenes.traducir_texturas(
            srd_original, srdv_original, traducciones, nombre)
        datos = spc.a_bytes(recomprimir=True)
        if len(datos) > parche.hueco[nombre]:
            datos = spc.a_bytes(recomprimir=True, optimo=True)
        if len(datos) > parche.hueco[nombre]:
            # No se reacomoda al vecino (puede ser otra textura traducida): se reparte
            # junto con las fuentes de juicio en los bloques libres del CPK
            parche.grupo_imagenes[nombre] = datos
            print("%-40s %5d imagenes (con el grupo de fuentes)" % (nombre, len(hechas)))
            continue
        modo = parche.reemplazar(nombre, datos)
        print("%-40s %5d imagenes (%s)" % (nombre, len(hechas), modo))


def parchear_residente():
    """Fuente con glifos en espanol + textos de menus (traduccion/residente.json)."""
    tabla = cargar_traducciones().get("residente", {})
    escritas = cargar_escritas()
    with ParcheCPK(CPK_RESIDENTE, puede_crecer=False) as parche:
        datos, cambios = traducir_spc(parche.leer(SPC_RESIDENTE), tabla,
                                      escritas.setdefault("residente", {}))
        guardar_escritas(escritas)
        spc = SPC(datos)
        e_stx = spc.buscar(FUENTE + ".stx")
        e_srdv = spc.buscar(FUENTE + ".srdv")
        f = fuente.Fuente(e_stx.datos, e_srdv.datos)
        nuevos = fuente.crear_glifos_espanol(f)
        f.agregar(nuevos)
        e_stx.datos, e_srdv.datos = f.serializar()
        modo = parche.reemplazar(SPC_RESIDENTE, spc.a_bytes(recomprimir=True))
        print("%-40s %5d glifos nuevos: %s" % (SPC_RESIDENTE, len(nuevos), "".join(nuevos)))
        print("%-40s %5d cadenas (%s)" % (SPC_RESIDENTE, cambios, modo))


def aplicar(parte=""):
    if parte in ("", "residente"):
        parchear_residente()
    elif ParcheCPK(CPK_RESIDENTE).revertir():
        print("Restaurado:", os.path.basename(CPK_RESIDENTE))
    if parte in ("", "textos"):
        parchear_textos()
    elif ParcheCPK(CPK_US).revertir():
        print("Restaurado:", os.path.basename(CPK_US))
    print("Parche aplicado.")


def revertir():
    for ruta in (CPK_US, CPK_RESIDENTE):
        if ParcheCPK(ruta).revertir():
            print("Restaurado:", os.path.basename(ruta))


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "aplicar":
        aplicar(sys.argv[2] if len(sys.argv) > 2 else "")
    elif orden == "revertir":
        revertir()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
