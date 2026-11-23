# Genera dist/DanganV3Esp.exe. Uso, desde herramientas/:
#     python -m PyInstaller instalador.spec --noconfirm
# Antes, imagenes/pregeneradas/ debe estar al dia (ver LEEME.md, "Instalador").
import os

from PyInstaller.utils.hooks import collect_data_files

RAIZ = os.path.dirname(os.path.abspath(SPECPATH))

# etcpak detecta la CPU con archspec, que lee sus propios json al importarse
datos = collect_data_files("archspec") + [(os.path.join(RAIZ, "traduccion", "*.json"), "traduccion")]
for carpeta in ("traducidas", "mascaras", "fuentes", "pregeneradas"):
    datos.append((os.path.join(RAIZ, "imagenes", carpeta), os.path.join("imagenes", carpeta)))

a = Analysis(
    ["instalador.py"],
    pathex=[SPECPATH],
    datas=datos,
    hiddenimports=["parchear", "cpk", "spc", "stx", "srd", "fuente", "fuentes_juicio", "imagenes",
                   "revisar", "rotulos_originales", "config"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="DanganV3Esp",
    console=False,
)
