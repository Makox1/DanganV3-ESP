"""Rutas y parametros comunes del proyecto."""
import os

# El instalador (instalador.py) fija estas rutas con variables de entorno
JUEGO = os.environ.get("DRV3_JUEGO", r"D:\SteamLibrary\steamapps\common\Danganronpa V3 Killing Harmony")
CPK_US = os.path.join(JUEGO, "data", "win", "partition_data_win_us.cpk")
CPK_RESIDENTE = os.path.join(JUEGO, "data", "win", "partition_resident_win.cpk")
SPC_RESIDENTE = "game_resident/game_resident_US.spc"
SPC_OBJETOS = "wrd_data/map_obj_name_text_US.SPC"

RAIZ = os.environ.get("DRV3_RAIZ", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESPALDO = os.environ.get("DRV3_RESPALDO", os.path.join(RAIZ, "respaldo"))



def respaldo_cabecera(ruta_cpk):
    """Ruta del respaldo de cabecera+TOC original de un CPK."""
    nombre = os.path.splitext(os.path.basename(ruta_cpk))[0]
    return os.path.join(RESPALDO, nombre + "_cabecera.bin")


# El juego trae varias versiones de los guiones (003-007); se parchean todas
VERSIONES = ["003", "004", "005", "006", "007"]
VERSION_REFERENCIA = "007"
