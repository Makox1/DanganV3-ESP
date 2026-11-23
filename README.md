# Danganronpa V3: Killing Harmony en español latino

Traducción no oficial (hecha por fans) de **Danganronpa V3: Killing Harmony** para la versión de Steam
en Windows, al español latinoamericano.

Este repositorio no contiene archivos del juego. Para usar la traducción necesitas tu propia copia
original del juego en Steam.

## Estado

| Parte | Estado |
|---|---|
| Prólogo y capítulos 1 a 6 (diálogos, juicios, tiempo libre) | Traducido |
| Epílogo final | Traducido |
| Love Suite (`ainori`) | Traducido |
| Menús, objetos, mapa, balas de verdad, minijuegos, extras | Traducido |
| Fuentes con `á é í ó ú ñ ü ¿ ¡` | Añadidas (diálogos, juicios y minijuegos) |
| Imágenes con texto (menús, títulos, carteles) | 129 texturas traducidas; quedan algunas pendientes |

Se dejan en inglés a propósito:
- Las respuestas del Hangman's Gambit, porque el juego las guarda como códigos de letras en binario.
- Los títulos de las canciones.
- Los textos de depuración que el juego no muestra.

Gran parte del juego aún no se ha probado partida en mano después del juicio del capítulo 1.
Si encuentras errores, abre un issue con el capítulo y una captura.

## Instalación con el instalador (recomendada)

1. Descarga `DanganV3Esp.exe` de la sección **Releases** de este repositorio.
2. **Cierra el juego** y abre `DanganV3Esp.exe`. No hace falta instalar Python.
3. El programa busca el juego en Steam. Si no lo encuentra, elige su carpeta con **Buscar...**.
4. Pulsa **Instalar traducción** y espera. Tarda unos 2 minutos.

Para volver al inglés, abre el mismo programa y pulsa **Desinstalar**.

El instalador guarda una copia de las partes originales en la carpeta `DanganV3Esp_respaldo`, dentro de la
carpeta del juego. No la borres mientras la traducción esté instalada; al desinstalar se borra sola.

Antes de instalar, el juego debe estar sin modificar. Si el instalador dice que el juego ya tiene una
traducción o que los archivos no tienen el tamaño correcto, usa en Steam
*Propiedades > Archivos instalados > Verificar integridad de los archivos del juego* y vuelve a intentarlo.

Windows puede mostrar un aviso de SmartScreen porque el programa no está firmado. Pulsa
*Más información > Ejecutar de todas formas*.

## Instalación con Python (para colaboradores)

Requisitos:

- Windows y **Danganronpa V3: Killing Harmony** de Steam.
- **Python 3** (probado con 3.14) y estas librerías:

```
pip install pillow numpy etcpak texture2ddecoder
```

Pasos:

1. Comprueba que el juego esté **sin modificar**. Si no estás seguro, usa en Steam
   *Propiedades > Archivos instalados > Verificar integridad de los archivos del juego*.
2. Si tu juego no está en `D:\SteamLibrary\steamapps\common\Danganronpa V3 Killing Harmony`,
   cambia la ruta `JUEGO` en `herramientas/config.py`.
3. **Cierra el juego** y ejecuta, desde la carpeta `herramientas/`:

```
python parchear.py aplicar
```

La primera vez se crea la carpeta `respaldo/` con las partes originales que el parche sobrescribe.
**No la borres** mientras el juego esté parcheado.

Para volver al juego original:

```
python parchear.py revertir
```

Si se pierde `respaldo/`, *Verificar integridad de los archivos* en Steam también deja el juego
original.

### Advertencias

- Ejecuta siempre `python parchear.py aplicar` **sin argumentos**. `aplicar textos` y
  `aplicar residente` son modos de diagnóstico que dejan la otra mitad del juego en inglés.
- El parche escribe todo en el espacio original de cada archivo. Los archivos `.cpk` del juego
  **no pueden cambiar de tamaño**: si crecen, el juego se cierra al arrancar o se queda cargando.
- No ejecutes el parche con el juego abierto.
- Una actualización del juego en Steam puede deshacer el parche. En ese caso, vuelve a aplicarlo.

## Estructura

| Carpeta | Contenido |
|---|---|
| `traduccion/` | Textos en formato JSON (`{archivo.stx: [{id, en, es}]}`) y `glosario.md` con los criterios de traducción |
| `traduccion/imagenes.json` | Definición de las texturas traducidas |
| `herramientas/` | Scripts de Python para extraer, revisar y parchear |
| `imagenes/` | Texturas ya traducidas, máscaras, atlas de letras y texturas pregeneradas para el instalador |
| `herramientas/instalador.py` | Programa del instalador; `instalador.spec` genera el `.exe` (ver [LEEME.md](LEEME.md)) |
| `respaldo/textos_escritos.json` | Registro de los textos en español que ha escrito el parche (lo usa `parchear.py`) |

Los detalles técnicos y el flujo de trabajo para traducir están en [LEEME.md](LEEME.md).
El historial de cambios y las notas de cada tanda están en [TRASPASO.md](TRASPASO.md).

## Colaborar

Antes de traducir o corregir, lee [traduccion/glosario.md](traduccion/glosario.md) (nombres, títulos
de los Definitivos, cómo habla cada personaje). Después de editar un JSON, revisa con:

```
python revisar.py chap1
python genero.py chap1
```

`revisar.py` comprueba etiquetas, letras que no existen en la fuente y el ancho de las líneas.

## Aviso legal

Proyecto sin ánimo de lucro, sin relación con Spike Chunsoft ni NIS America. Danganronpa y todos
sus personajes pertenecen a sus respectivos dueños. No se distribuyen archivos del juego.
