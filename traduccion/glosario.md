# Glosario y criterios

## Estilo
- Español latino neutro: "ustedes", "salón", "pizarrón", "casillero", "auto", "preparatoria", "mouse".
- Kaede narra en femenino hasta la revelación del juicio del capítulo 1 (`c01_224`); desde ahí, Shuichi narra en masculino. Las notas de relación de Kaede (`B-TechouTsushinboReport`, 75-104) siguen en femenino.
- Signos de apertura siempre: `¿...?`, `¡...!`, `¡¿...?!`.
- Mantener intactas las etiquetas `<CLT=...>` y `<PAD=...>`, y los saltos `\n` / `\r\n` tal como estén.
- Puntos suspensivos pegados como en el original: `Pero...¿por qué yo?`.
- Tutoriales del sistema: tuteo y género neutro cuando se pueda.
- No usar caracteres sin glifo (p. ej. `°`, `«»`); `revisar.py` los detecta.
- Sin asteriscos: el inglés marca énfasis con `*palabra*`; en español se quitan. Los sonidos
  (`*click*`) van sin asteriscos ("Clic", "¡Pum!") y `*sigh*` se traduce "Ay...".
- Género según quien habla y a quien se dirige: antes de aplicar, revisar los candidatos de
  `python genero.py <capitulo>` (lee el hablante de cada línea en los guiones `.wrd`).

## Términos
| Inglés | Español |
|---|---|
| locker | casillero |
| classroom | salón (de clases) |
| high school student | estudiante de preparatoria |
| 2F | Piso 2 |
| Hell yeah! (Monokid) | ¡Hell yeah! (muletilla, se deja) |
| Class Trial | Juicio Escolar |
| School Life / Daily Life / Deadly Life | Vida Escolar / Vida Diaria / Vida Mortal |
| Free Time | Tiempo Libre |
| Monocoins | Monomonedas |
| MonoMono Machine | Máquina MonoMono |
| Love Across the Universe | Amor a Través del Universo |
| Kind / Normal / Mean (dificultad) | Amable / Normal / Cruel |
| Logic / Action Difficulty | Dificultad lógica / Dificultad de acción |
| Nonstop Debate | Debate Sin Parar |
| Rebuttal Showdown | Duelo de Refutación |
| Psyche Taxi | Psico Taxi |
| Hangman's Gambit | Apuesta del Ahorcado |
| Mind Mine | Mina Mental |
| Argument Armament | Armamento Argumental |
| Debate Scrum | Debate en Equipos |
| Closing Argument | Argumento Final |
| Mass Panic Debate | Debate de Pánico Masivo |
| replay data | repetición |
| School Regulations | Reglamento escolar |
| Nighttime | horario nocturno |
| body discovery announcement | anuncio de descubrimiento de cadáver |
| motive / First Blood Perk | motivo / Bono de Primera Sangre |
| Monokuma Theater | Teatro Monokuma |
| Death Road of Despair | Camino Mortal de la Desesperación |
| Kee-boy (Kokichi a Keebo) | Kee-boy |
| Ultimate / Ultimates | Definitivo/a / los Definitivos |
| Ultimate Academy for Gifted Juveniles | Academia Definitiva para Jóvenes Superdotados |
| Ultimate Initiative / Ultimate Hunt | Iniciativa Definitiva / Cacería de Definitivos |
| Ultimate Research Lab | Laboratorio Definitivo |
| killing game / killing school semester | juego de matanza / semestre escolar de matanza |
| class trial / blackened / spotless | juicio escolar / culpable / inocentes |
| punishment / Voting Time | castigo / Hora de Votar |
| Flashback Light | Luz de Recuerdos |
| End Wall | Muro del Fin |
| Report Card | Libreta de Calificaciones |
| Monokubs, Exisals, Monopad | se dejan igual |
| cubs (de Monokuma) | oseznos |
| Monokuma "Puhuhu" / Kokichi "Nee-heehee" | "Pupupu" / "Nijiji" |
| mage / magician (Himiko) | maga / ilusionista |
| degenerate males (Tenko) | varones degenerados |
| Pianist, Detective, Cosplayer, Mage, Aikido Master, Inventor, Robot, Supreme Leader, Child Caregiver, Tennis Pro, Anthropologist, Maid, Astronaut, Entomologist, Artist | Pianista, Detective, Cosplayer, Maga/Ilusionista, Maestra de Aikido, Inventora, Robot, Líder Supremo, Cuidadora Infantil, Tenista, Antropólogo, Sirvienta, Astronauta, Entomólogo, Artista (+ Definitivo/a) |

## Voces
- Gonta habla en tercera persona con infinitivos: "Gonta querer ser caballero".
- Kirumi y Korekiyo: registro formal, tratan de "ustedes".
- Tsumugi: muletilla "simplemente" (en inglés "plain").
- Miu y Monokid: groserías fuertes; evitar modismos demasiado regionales.

## Objetos del mapa
- `traduccion/objetos.json` (nombres al examinar), cubiertos para todo el juego.

## Interfaz
- Textos de menú en `traduccion/residente.json` (archivos `D-Menu`, `S-SaveLoad`, `I-Button`, `H-Result`).
- También contiene regalos (`A-Present`, `A-PresentSetumei`), habilidades (`A-Skill`, `A-SkillSetumei`), reglamento (`B-TechouKousoku`) y perfiles (`B-TechouTsushinbo`, `B-TechouTsushinboSpecial`, `B-TechouTsushinboReport`).
- Las pruebas del primer caso son los IDs 0-17 de `A-Kotodama` y `A-KotodamaSetumei1`; sus variantes de mentira están en `A-KotodamaUso`. Los IDs 18-29 son marcadores sin contenido real.
- Los campos cortos usan abreviaturas cuando lo exige `revisar.py` (por ejemplo, `Hab.`, `Monom.`, `Def.`). En diálogos y descripciones se mantienen los términos completos.
- La pantalla de título, el menú principal y las opciones son imágenes (`flash/title/*_US.spc`, BC7/DXT1), no texto.
