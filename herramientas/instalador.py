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


def raiz_datos():
    """Carpeta con traduccion/ e imagenes/ (dentro del .exe o la del proyecto)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def buscar_juego():
    """Busca el juego en las bibliotecas de Steam; devuelve "" si no lo encuentra."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as clave:
            steam = winreg.QueryValueEx(clave, "SteamPath")[0]
    except OSError:
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


def preparar_entorno(juego):
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
        raise RuntimeError("El juego ya tiene una traducción aplicada sin respaldo de este instalador.\n"
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


def ventana():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    raiz = tk.Tk()
    raiz.title(NOMBRE)
    raiz.geometry("640x460")
    cola = queue.Queue()
    sys.stdout = sys.stderr = Salida(cola)

    tk.Label(raiz, text=NOMBRE, font=("Segoe UI", 14, "bold")).pack(pady=(12, 2))
    tk.Label(raiz, text="Traducción hecha por fans. Cierra el juego antes de instalar o desinstalar.").pack()

    marco = tk.Frame(raiz)
    marco.pack(fill="x", padx=12, pady=10)
    tk.Label(marco, text="Carpeta del juego:").pack(side="left")
    carpeta = tk.StringVar(value=buscar_juego())
    entrada = tk.Entry(marco, textvariable=carpeta)
    entrada.pack(side="left", fill="x", expand=True, padx=6)

    def elegir():
        ruta = filedialog.askdirectory(title="Carpeta de Danganronpa V3 Killing Harmony")
        if ruta:
            carpeta.set(os.path.normpath(ruta))

    boton_buscar = tk.Button(marco, text="Buscar...", command=elegir)
    boton_buscar.pack(side="left")

    botones = tk.Frame(raiz)
    botones.pack(pady=4)
    registro = scrolledtext.ScrolledText(raiz, height=16, font=("Consolas", 9), state="disabled")
    registro.pack(fill="both", expand=True, padx=12, pady=(6, 12))

    def ejecutar(tarea, titulo):
        juego = carpeta.get().strip()
        error = comprobar(juego)
        if error:
            messagebox.showerror(NOMBRE, error)
            return
        # Las rutas quedan fijas al importar parchear (ver docstring)
        for control in (boton_instalar, boton_desinstalar, boton_buscar, entrada):
            control.config(state="disabled")
        cola.put(("texto", "%s... esto puede tardar varios minutos.\n" % titulo))

        def trabajo():
            try:
                tarea(juego)
                cola.put(("fin", ""))
            except Exception as e:
                traceback.print_exc()
                cola.put(("error", str(e)))

        threading.Thread(target=trabajo, daemon=True).start()

    def revisar_cola():
        while not cola.empty():
            tipo, texto = cola.get()
            if tipo == "texto":
                registro.config(state="normal")
                registro.insert("end", texto)
                registro.see("end")
                registro.config(state="disabled")
                continue
            for control in (boton_instalar, boton_desinstalar):
                control.config(state="normal")
            if tipo == "fin":
                messagebox.showinfo(NOMBRE, "Listo.")
            else:
                messagebox.showerror(NOMBRE, "No se pudo completar:\n\n" + texto)
        raiz.after(100, revisar_cola)

    boton_instalar = tk.Button(botones, text="Instalar traducción", width=20,
                               command=lambda: ejecutar(instalar, "Instalando"))
    boton_instalar.pack(side="left", padx=6)
    boton_desinstalar = tk.Button(botones, text="Desinstalar", width=20,
                                  command=lambda: ejecutar(desinstalar, "Desinstalando"))
    boton_desinstalar.pack(side="left", padx=6)
    if not carpeta.get():
        cola.put(("texto", "No se encontró el juego en Steam. Elige su carpeta con \"Buscar...\".\n"))
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
