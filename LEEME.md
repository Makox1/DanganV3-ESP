# Traducción de Danganronpa V3 al español latino

## Flujo de trabajo

Todos los comandos se ejecutan desde `herramientas/`.

```
python exportar.py chap0          # Genera/actualiza traduccion/chap0.json (conserva lo ya traducido)
python importar_lote.py chap0 lote.json   # Incorpora un lote {"archivo.stx": {"id": "texto"}}
python revisar.py chap0           # Etiquetas, glifos faltantes, ancho de línea en píxeles
python parchear.py aplicar        # Aplica fuente + todos los traduccion/*.json al juego
python parchear.py revertir       # Deja los CPK del juego exactamente como los originales
```

`parchear.py aplicar` siempre parte del original, así que se puede ejecutar cuantas veces se quiera.
El respaldo de cabeceras y de las zonas sobrescritas está en `respaldo/` (no borrar mientras el juego esté parcheado).
Si se borrara, "Verificar integridad de los archivos" en Steam restaura el juego.

Importante: ningún CPK puede cambiar de tamaño. Si crece `partition_resident_win.cpk` el juego
se cierra al arrancar; si crece `partition_data_win_us.cpk` se queda cargando para siempre.
Por eso los archivos modificados se escriben en su hueco original ("en sitio"), recomprimidos
con el compresor de `spc.py`. Si un SPC de imágenes no cabe, `parchear.py` lo omite y lo avisa:
hay que acortar el texto.

Las texturas de texto de un solo color se codifican en BC7 modo 5 (color fijo + alfa), que
comprime mucho mejor que un codificador genérico; sin eso casi nada cabe.

## Imágenes con texto

Las texturas traducidas se definen en `traduccion/imagenes.json` (texto en español, texto
inglés de referencia `en`, tipografía de `C:\Windows\Fonts` o `"juego"`, color, borde,
inclinación, rotación, alineación). `parchear.py aplicar` las genera y las aplica.

```
python srd.py listar <texture.srd>                 # Texturas de un SPC de interfaz
python srd.py exportar <srd> <srdv> <carpeta> --solo-us   # Exportar a PNG
python imagenes.py vista                           # Original vs traducida en imagenes/vista/
```

Las texturas con texto llevan `_US` en su nombre interno. Formatos: BC7 (0x1C) y DXT1 (0x0F).

## Dónde está cada cosa en el juego

| Contenido | CPK | Ruta interna |
|---|---|---|
| Diálogos | `partition_data_win_us.cpk` | `wrd_script/00X/chapN_text_US.SPC` (versiones 003-007, se parchean todas) |
| Fuente principal | `partition_resident_win.cpk` | `game_resident/game_resident_US.spc` -> `v3_font00.stx` (SpFt) + `.srdv` (BC4 4096x101) |
| Menús, objetos, balas de verdad | `partition_resident_win.cpk` | `game_resident/game_resident_US.spc` -> `A-*.stx`, `D-Menu.stx`, ... |
| Juicios y minijuegos | `partition_data_win_us.cpk` | `wrd_data/*_US.spc`, `trial_font/`, `minigame/` |

`chap0` es el prólogo. A la fuente se le añaden `á í ó ú ñ ü Á É Í Ó Ú Ñ Ü ¿ ¡`, compuestos con trazos de la propia fuente.

`fuentes_juicio.py` también añade `á é í ó ú ñ ü Á É Í Ó Ú Ñ Ü ¿ ¡` a las 29 fuentes
de texto de `trial_font/` y `minigame/rsc/font/`. Se conservan los glifos originales;
si una letra base no existe en una fuente parcial, se usa la residente escalada.
Los atlas llenos reciben una fila adicional. Las fuentes se distribuyen dentro del
CPK, usando sus huecos, colas libres de guiones y espacio obtenido al recomprimir
los SPC de capítulo 2 sin alterar su contenido. No crece ningún CPK.
La fuente `game_font01_9_US.spc`, que solo contiene espacios, se conserva intacta.

Comprobación técnica y vista de glifos (desde la raíz):
`python scratchpad/verificar_fuentes_juicio.py --aplicado`.
Comprueba glifos, métricas, píxeles originales, tablas Unicode y tamaños de CPK.

## Criterios de traducción

Ver `traduccion/glosario.md`.
