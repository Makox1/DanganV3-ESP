"""Instalador de la traduccion para jugadores (ventana con Instalar y Desinstalar).

Uso:
    python instalador.py                          Abre la ventana
    python instalador.py aplicar <carpeta juego>  Sin ventana (pruebas)
    python instalador.py revertir <carpeta juego>

Se empaqueta en un .exe con PyInstaller (ver instalador.spec). Las rutas llegan a
config.py por variables de entorno antes de importar parchear; por eso, tras instalar
o desinstalar, la carpeta del juego ya no se puede cambiar sin reabrir el programa.
El respaldo se guarda dentro de la carpeta del juego (DanganV3Esp_respaldo) y se
borra al desinstalar, cuando los CPK ya son los originales.
"""
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import traceback

NOMBRE = "Danganronpa V3 en español latino"
CARPETA_STEAM = os.path.join("steamapps", "common", "Danganronpa V3 Killing Harmony")
CARPETA_RESPALDO = "DanganV3Esp_respaldo"
EJECUTABLES = ("Dangan3Win.exe", "V3Launcher.exe")
# Tamanos de los CPK de Steam; el parche nunca los cambia
TAMANOS = {"partition_data_win_us.cpk": 8525629320, "partition_resident_win.cpk": 2298785400}


class Aviso(Exception):
    """Problema previsto que el jugador puede resolver; se muestra sin traceback."""


def raiz_datos():
    """Carpeta con traduccion/ e imagenes/ (dentro del .exe o la del proyecto)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta_steam():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as clave:
            return winreg.QueryValueEx(clave, "SteamPath")[0]
    except OSError:
        return ""


def buscar_juego():
    """Busca el juego en las bibliotecas de Steam; devuelve "" si no lo encuentra."""
    steam = ruta_steam()
    if not steam:
        return ""
    bibliotecas = [steam]
    try:
        with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as f:
            bibliotecas += [r.replace("\\\\", "\\") for r in re.findall(r'"path"\s+"(.+?)"', f.read())]
    except OSError:
        pass
    for biblioteca in bibliotecas:
        ruta = os.path.normpath(os.path.join(biblioteca, CARPETA_STEAM))
        if os.path.exists(os.path.join(ruta, "data", "win", "partition_data_win_us.cpk")):
            return ruta
    return ""


def juego_abierto():
    salida = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
    return any(nombre.lower() in salida for nombre in EJECUTABLES)


def comprobar(juego):
    """Devuelve un mensaje de error, o "" si se puede parchear."""
    for nombre, tam in TAMANOS.items():
        ruta = os.path.join(juego, "data", "win", nombre)
        if not os.path.exists(ruta):
            return "No se encuentra %s.\nElige la carpeta donde está instalado el juego." % nombre
        if os.path.getsize(ruta) != tam:
            return ("%s no tiene el tamaño de la versión de Steam.\nUsa en Steam \"Verificar integridad "
                    "de los archivos del juego\" y vuelve a intentarlo." % nombre)
    if juego_abierto():
        return "El juego está abierto. Ciérralo y vuelve a intentarlo."
    return ""


def bajar_prioridad():
    """El parche ocupa un nucleo entero ~2 minutos; con prioridad baja el PC sigue respondiendo."""
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        # Sin tipos, ctypes corta el pseudohandle (-1) a 32 bits y la llamada falla en 64 bits
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    except (AttributeError, OSError):
        pass


def preparar_entorno(juego):
    bajar_prioridad()
    # numpy no debe repartir calculos en mas hilos
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(variable, "1")
    raiz = raiz_datos()
    os.environ["DRV3_JUEGO"] = juego
    os.environ["DRV3_RAIZ"] = raiz
    os.environ["DRV3_RESPALDO"] = os.path.join(juego, CARPETA_RESPALDO)
    os.environ["DRV3_PREGENERADAS"] = os.path.join(raiz, "imagenes", "pregeneradas")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def traducido_sin_respaldo():
    """True si el juego ya tiene la traduccion pero sin el respaldo de este instalador.

    Pasa si se parcheo desde el proyecto u otra copia: tomaria lo traducido como
    original y desinstalar no devolveria el juego en ingles.
    """
    import stx
    from cpk import CPK
    from spc import SPC
    from config import CPK_RESIDENTE, SPC_RESIDENTE, RESPALDO
    from parchear import cargar_traducciones
    if os.path.exists(RESPALDO):
        return False
    tabla = cargar_traducciones().get("residente", {})
    cpk = CPK(CPK_RESIDENTE)
    archivo = next(a for a in cpk.archivos if a["nombre"] == SPC_RESIDENTE)
    ingles = espanol = 0
    for e in SPC(cpk.leer(archivo)).entradas:
        traducciones = tabla.get(e.nombre)
        if not traducciones:
            continue
        for i, texto in stx.leer(e.datos)[2]:
            par = traducciones.get(i)
            if par and par[0] != par[1]:
                ingles += texto == par[0]
                espanol += texto == par[1]
    return espanol > ingles


def instalar(juego):
    preparar_entorno(juego)
    import parchear
    if traducido_sin_respaldo():
        raise Aviso("El juego ya tiene una traducción aplicada sin respaldo de este instalador.\n"
                           "Usa en Steam \"Verificar integridad de los archivos del juego\" y vuelve a "
                           "instalar.")
    parchear.aplicar()


def desinstalar(juego):
    preparar_entorno(juego)
    import parchear
    from config import RESPALDO
    if not os.path.exists(RESPALDO):
        print("No hay respaldo de este instalador: el juego no se modificó con él.")
        return
    parchear.revertir()
    shutil.rmtree(RESPALDO)
    print("Respaldo borrado.")


class Salida:
    """Lleva lo que imprime parchear a la ventana."""

    def __init__(self, cola):
        self.cola = cola

    def write(self, texto):
        self.cola.put(("texto", texto))

    def flush(self):
        pass


# Colores de la ventana: rosa de la saga sobre negro
FONDO = "#121016"
PANEL = "#1f1b25"
ROSA = "#e5007e"
ROSA_CLARO = "#ff2f9b"
TEXTO = "#f2eef5"
TENUE = "#9a93a3"
ROJO = "#ff5c6c"
ANCHO_BANNER, ALTO_BANNER = 760, 250
# Segundos que tardan las fuentes de juicio, que no imprimen nada hasta el final
SEGUNDOS_FUENTES = 20
# Segundos de la fase residente (fuente, menus y avisos de inicio comprimidos al minimo)
SEGUNDOS_RESIDENTE = 42


def imagenes_steam():
    """Banner y logo del juego desde la cache de Steam del propio jugador (no se distribuyen)."""
    steam = ruta_steam()
    encontradas = {}
    if steam:
        for actual, _, archivos in os.walk(os.path.join(steam, "appcache", "librarycache", "567640")):
            for nombre in sorted(archivos):
                for clave in ("library_hero", "logo"):
                    if nombre.startswith(clave) and "blur" not in nombre and clave not in encontradas:
                        encontradas[clave] = os.path.join(actual, nombre)
    return encontradas.get("library_hero"), encontradas.get("logo")


def fuente_windows(nombre, tam):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", nombre), tam)
    except OSError:
        return ImageFont.load_default(tam)


def crear_banner():
    """Banner de la ventana; sin la cache de Steam, franjas rosas y el titulo en texto."""
    from PIL import Image, ImageChops, ImageDraw
    heroe, logo = imagenes_steam()
    if heroe:
        with Image.open(heroe) as archivo:
            img = archivo.convert("RGB")
        img = img.resize((ANCHO_BANNER, round(img.height * ANCHO_BANNER / img.width)), Image.LANCZOS)
        arriba = max(0, (img.height - ALTO_BANNER) // 2)
        img = img.crop((0, arriba, ANCHO_BANNER, arriba + ALTO_BANNER)).convert("RGBA")
    else:
        img = Image.new("RGBA", (ANCHO_BANNER, ALTO_BANNER), FONDO)
        dib = ImageDraw.Draw(img)
        for x in range(-ALTO_BANNER, ANCHO_BANNER, 70):
            dib.polygon([(x, ALTO_BANNER), (x + 30, ALTO_BANNER), (x + 30 + ALTO_BANNER, 0),
                         (x + ALTO_BANNER, 0)], fill="#2a0a1c")
    # Degradado oscuro abajo, para que el texto se lea sobre cualquier imagen
    alfa = Image.linear_gradient("L").resize((ANCHO_BANNER, ALTO_BANNER))
    alfa = alfa.point(lambda v: max(0, min(255, int((v - 90) * 1.6))))
    # y a la izquierda, detras del logo
    lateral = Image.linear_gradient("L").rotate(90, expand=True).resize((ANCHO_BANNER, ALTO_BANNER))
    lateral = lateral.point(lambda v: max(0, min(255, int((v - 105) * 1.5))))
    sombra = Image.new("RGBA", img.size, FONDO)
    sombra.putalpha(ImageChops.lighter(alfa, lateral))
    img.alpha_composite(sombra)
    dib = ImageDraw.Draw(img)
    if logo:
        with Image.open(logo) as archivo:
            marca = archivo.convert("RGBA")
        marca.thumbnail((240, 120), Image.LANCZOS)
        img.alpha_composite(marca, (14, ALTO_BANNER - 72 - marca.height))
    else:
        dib.text((24, 24), "DANGANRONPA V3", font=fuente_windows("impact.ttf", 46), fill=TEXTO)
        dib.text((26, 80), "KILLING HARMONY", font=fuente_windows("impact.ttf", 24), fill=ROSA)
    dib.text((24, ALTO_BANNER - 66), "Traducción al español latino", font=fuente_windows("segoeuib.ttf", 28),
             fill=TEXTO)
    dib.text((26, ALTO_BANNER - 28), "HECHA POR FANS  ·  NO OFICIAL", font=fuente_windows("segoeuib.ttf", 13),
             fill=ROSA_CLARO)
    return img


class Avance:
    """Estima el porcentaje con lo que imprime parchear.

    Pesos medidos en una instalacion: menus, fuente y avisos de inicio 28 %, dialogos 41 %,
    imagenes 18 %, fuentes de juicio 12 %. La primera y la ultima fase avanzan por tiempo
    porque imprimen poco.
    """

    def __init__(self):
        import json
        import time
        self.time = time
        carpeta = os.path.join(raiz_datos(), "traduccion")
        capitulos = [n for n in os.listdir(carpeta) if n.endswith(".json")
                     and n[:-5] not in ("residente", "imagenes", "variantes", "objetos")]
        # Cada capitulo se parchea en las 5 versiones de guiones; objetos, una vez
        self.total_textos = len(capitulos) * 5 + 1
        with open(os.path.join(carpeta, "imagenes.json"), encoding="utf-8") as f:
            # Los avisos de flash/caution se aplican en la fase residente (ver parchear.py)
            self.total_imagenes = len([n for n in json.load(f) if not n.startswith("flash/caution/")])
        self.inicio = time.time()
        self.residente = False
        self.textos = self.imagenes = 0
        self.inicio_fuentes = None
        self.pendiente = ""

    def leer(self, texto):
        self.pendiente += texto
        *lineas, self.pendiente = self.pendiente.split("\n")
        for linea in lineas:
            if linea.startswith("boot/") or linea.startswith("game_resident"):
                continue
            elif " cadenas (" in linea:
                self.residente = True
                self.textos += 1
            elif " imagenes (" in linea:
                self.imagenes += 1
                if self.imagenes >= self.total_imagenes:
                    self.inicio_fuentes = self.time.time()

    def porcentaje(self):
        if self.residente:
            p = 0.28
        else:
            p = 0.28 * min(1, (self.time.time() - self.inicio) / SEGUNDOS_RESIDENTE)
        p += 0.41 * min(1, self.textos / self.total_textos)
        p += 0.18 * min(1, self.imagenes / self.total_imagenes)
        if self.inicio_fuentes:
            p += 0.12 * min(1, (self.time.time() - self.inicio_fuentes) / SEGUNDOS_FUENTES)
        return min(p, 0.99)

    def estado(self):
        if self.inicio_fuentes:
            return "Añadiendo letras con tilde a los juicios..."
        if self.imagenes:
            return "Traduciendo imágenes y menús (%d de %d)..." % (self.imagenes, self.total_imagenes)
        if self.residente:
            return "Traduciendo diálogos (%d de %d)..." % (self.textos, self.total_textos)
        return "Preparando la fuente con tildes, los menús y los avisos de inicio..."


def ventana():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
    from PIL import ImageTk

    raiz = tk.Tk()
    raiz.title(NOMBRE)
    raiz.configure(bg=FONDO)
    raiz.resizable(False, False)
    cola = queue.Queue()
    sys.stdout = sys.stderr = Salida(cola)

    banner = ImageTk.PhotoImage(crear_banner())
    tk.Label(raiz, image=banner, bd=0, bg=FONDO).pack()
    cuerpo = tk.Frame(raiz, bg=FONDO, padx=24, pady=16)
    cuerpo.pack(fill="x")

    tk.Label(cuerpo, text="CARPETA DEL JUEGO", font=("Segoe UI", 8, "bold"), fg=TENUE, bg=FONDO).pack(anchor="w")
    fila = tk.Frame(cuerpo, bg=FONDO)
    fila.pack(fill="x", pady=(2, 16))
    carpeta = tk.StringVar(value=buscar_juego())
    entrada = tk.Entry(fila, textvariable=carpeta, font=("Segoe UI", 10), bg=PANEL, fg=TEXTO, relief="flat",
                       insertbackground=TEXTO, disabledbackground=PANEL, disabledforeground=TENUE)
    entrada.pack(side="left", fill="x", expand=True, ipady=6)

    def elegir():
        ruta = filedialog.askdirectory(title="Carpeta de Danganronpa V3 Killing Harmony")
        if ruta:
            carpeta.set(os.path.normpath(ruta))

    def boton(padre, texto, orden, fondo, activo, fuente=("Segoe UI", 10), **extra):
        return tk.Button(padre, text=texto, command=orden, font=fuente, bg=fondo, fg=TEXTO, relief="flat",
                         bd=0, activebackground=activo, activeforeground=TEXTO, cursor="hand2",
                         disabledforeground=TENUE, **extra)

    boton_buscar = boton(fila, "Cambiar", elegir, PANEL, "#2c2734", padx=14)
    boton_buscar.pack(side="left", fill="y", padx=(6, 0))

    botones = tk.Frame(cuerpo, bg=FONDO)
    botones.pack(fill="x")
    boton_instalar = boton(botones, "INSTALAR TRADUCCIÓN", lambda: ejecutar(instalar), ROSA, ROSA_CLARO,
                           ("Segoe UI", 13, "bold"), padx=28, pady=10)
    boton_instalar.pack(side="left")
    boton_desinstalar = boton(botones, "Desinstalar", lambda: ejecutar(desinstalar), PANEL, "#2c2734",
                              padx=18, pady=10)
    boton_desinstalar.pack(side="left", padx=(10, 0), fill="y")

    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    estilo.configure("Rosa.Horizontal.TProgressbar", troughcolor=PANEL, background=ROSA, bordercolor=FONDO,
                     lightcolor=ROSA, darkcolor=ROSA, thickness=12)
    zona = tk.Frame(cuerpo, bg=FONDO)
    zona.pack(fill="x", pady=(20, 0))
    barra = ttk.Progressbar(zona, style="Rosa.Horizontal.TProgressbar", maximum=100)
    barra.pack(side="left", fill="x", expand=True)
    porcentaje = tk.Label(zona, text="", width=5, anchor="e", font=("Segoe UI", 16, "bold"), fg=TEXTO, bg=FONDO)
    porcentaje.pack(side="left", padx=(12, 0))
    estado = tk.Label(cuerpo, text="Cierra el juego antes de instalar o desinstalar.", font=("Segoe UI", 10),
                      fg=TENUE, bg=FONDO, anchor="w")
    estado.pack(fill="x", pady=(6, 0))

    registro = scrolledtext.ScrolledText(cuerpo, height=10, font=("Consolas", 9), bg="#0b0a0e", fg=TENUE,
                                         relief="flat", state="disabled")

    def alternar_detalles():
        if registro.winfo_ismapped():
            registro.pack_forget()
            boton_detalles.config(text="Ver detalles ▸")
        else:
            registro.pack(fill="x", pady=(8, 0), before=pie)
            boton_detalles.config(text="Ocultar detalles ▾")

    boton_detalles = tk.Button(cuerpo, text="Ver detalles ▸", command=alternar_detalles, font=("Segoe UI", 9),
                               fg=TENUE, bg=FONDO, activebackground=FONDO, activeforeground=TEXTO, relief="flat",
                               bd=0, cursor="hand2")
    boton_detalles.pack(anchor="w", pady=(10, 0))
    pie = tk.Label(cuerpo, text="Proyecto sin ánimo de lucro. Danganronpa pertenece a Spike Chunsoft.",
                   font=("Segoe UI", 8), fg="#5f5867", bg=FONDO)
    pie.pack(anchor="w", pady=(12, 0))

    trabajo_actual = {}

    def ejecutar(tarea):
        juego = carpeta.get().strip()
        error = comprobar(juego)
        if error:
            messagebox.showerror(NOMBRE, error)
            return
        # Las rutas quedan fijas al importar parchear (ver docstring)
        for control in (boton_instalar, boton_desinstalar, boton_buscar, entrada):
            control.config(state="disabled")
        trabajo_actual["avance"] = Avance() if tarea is instalar else None
        if tarea is desinstalar:
            estado.config(text="Restaurando el juego original...", fg=TEXTO)
            barra.config(mode="indeterminate")
            barra.start(12)

        def trabajo():
            try:
                tarea(juego)
                cola.put(("fin", "instalar" if tarea is instalar else "desinstalar"))
            except Aviso as e:
                # Avisos previstos (juego ya traducido): sin traceback
                print(e)
                cola.put(("error", str(e)))
            except Exception as e:
                traceback.print_exc()
                cola.put(("error", str(e)))

        threading.Thread(target=trabajo, daemon=True).start()

    def terminar(texto, color, valor):
        barra.stop()
        barra.config(mode="determinate", value=valor)
        porcentaje.config(text="%d%%" % valor if valor else "")
        estado.config(text=texto, fg=color)
        trabajo_actual["avance"] = None
        for control in (boton_instalar, boton_desinstalar):
            control.config(state="normal")

    def revisar_cola():
        while not cola.empty():
            tipo, texto = cola.get()
            if tipo == "texto":
                registro.config(state="normal")
                registro.insert("end", texto)
                registro.see("end")
                registro.config(state="disabled")
                if trabajo_actual.get("avance"):
                    trabajo_actual["avance"].leer(texto)
            elif tipo == "fin" and texto == "instalar":
                terminar("¡Traducción instalada! Ya puedes abrir el juego.", ROSA_CLARO, 100)
            elif tipo == "fin":
                terminar("Juego restaurado al inglés original.", TEXTO, 100)
            else:
                terminar("No se pudo completar. Revisa los detalles.", ROJO, 0)
                messagebox.showerror(NOMBRE, "No se pudo completar:\n\n" + texto)
        avance = trabajo_actual.get("avance")
        if avance:
            valor = avance.porcentaje() * 100
            barra.config(value=valor)
            porcentaje.config(text="%d%%" % valor)
            estado.config(text=avance.estado(), fg=TEXTO)
        raiz.after(100, revisar_cola)

    if not carpeta.get():
        estado.config(text="No se encontró el juego en Steam. Elige su carpeta con \"Cambiar\".", fg=ROJO)
    revisar_cola()
    raiz.mainloop()


def main():
    if len(sys.argv) > 2 and sys.argv[1] in ("aplicar", "revertir"):
        juego = sys.argv[2]
        if getattr(sys, "frozen", False):
            # .exe sin consola: la salida va a un archivo junto al programa
            sys.stdout = sys.stderr = open(os.path.join(os.path.dirname(sys.executable), "instalador.log"),
                                           "w", encoding="utf-8", buffering=1)
        error = comprobar(juego)
        if error:
            print(error)
            sys.exit(1)
        (instalar if sys.argv[1] == "aplicar" else desinstalar)(juego)
    elif len(sys.argv) > 1:
        print(__doc__)
    else:
        ventana()


if __name__ == "__main__":
    main()
