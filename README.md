# resumen-gf

Plugin de [Claude Code](https://claude.com/claude-code) para hacer el **resumen de 10 puntos de
un grupo focal**. Cada punto lleva un título formal, un párrafo en lenguaje llano y **de 2 a 4
citas textuales**, con el perfil de quien habla y la marca de tiempo. Sale en `.docx` con
Corbel y con todo el texto en negro.

Incluye también la **limpieza de la transcripción** cuando la sesión se grabó con dos aparatos
(skill `limpieza-gf`): identificación de voces de oído, contraste de los dos audios, cortes entre
hablantes y palabras dudosas, cada etapa con una página local para que el equipo escuche y decida.
Sale en el formato de las limpias del equipo (`MODERADOR` / `R`, Arial), lista para el resumen.

Claude lee la transcripción y redacta los puntos. Un script comprueba que **cada cita esté,
literal, en la transcripción, en el turno y la marca de tiempo indicados**, y que nadie del
equipo aparezca citado. Si una sola cita falla, no se escribe el documento.

## Manual

El paso a paso completo, con solución de problemas, está en
[`manual-instalacion.pdf`](manual-instalacion.pdf). Se regenera con
`python docs/build_manual.py` desde `docs/manual.html`.

## Instalación

Requisitos: Claude Code, Python 3 y `python-docx`.

```
python -m pip install python-docx
```

(En Mac, `python3 -m pip install python-docx`.)

Dentro de Claude Code:

```
/plugin marketplace add ramonzamora89/resumen-gf-plugin
/plugin install resumen-gf@resumen-gf
```

Sin conexión a GitHub, también se puede apuntar a una copia local de la carpeta:

```
/plugin marketplace add E:\ruta\a\resumen-gf-plugin
```

### Probar que funciona

Pídele a Claude: *«corre el ejemplo del plugin resumen-gf»*, o córrelo a mano desde la carpeta
del plugin:

```
python -I skills/resumen-gf/scripts/generar_resumen.py skills/resumen-gf/ejemplo/puntos.json
```

Debe decir `Citas verificadas: 8 en 3 puntos` y escribir
`Resumen 10 puntos - ejemplo ficticio.docx`. El aviso «hay 3 puntos, no 10» es normal: el
ejemplo es corto a propósito.

## Uso

Abre Claude Code en la carpeta del proyecto y pide, por ejemplo:

> Haz el resumen de 10 puntos del GF3 con la transcripción de `transcripciones/gf3_mujeres_25-34`.

Claude escribe `puntos.json` junto a la transcripción, corre la verificación y genera el
`.docx`. Para corregir algo se edita `puntos.json` y se vuelve a correr; el `.docx` no se toca a
mano.

Para una sesión grabada con dos aparatos que todavía no está limpia:

> Empecemos con la limpieza del GF3: las transcripciones de los dos aparatos están en
> `transcripciones/gf3` y los perfiles en la hoja de participantes.

Claude arma cada página de oído (voces, contraste, cortes, dudosos), espera las respuestas del equipo,
las registra en `limpieza.json` y al final genera `GF3_Limpia.docx` y `GF3_Limpia con participantes.docx`.

## Qué incluye

- `skills/resumen-gf/SKILL.md`: reglas de redacción, de selección de citas y de atribución.
- `skills/resumen-gf/scripts/generar_resumen.py`: verificación de citas y maquetación.
- `skills/resumen-gf/scripts/voces.py`: identificación de voces de oído cuando la transcripción
  rotula a todos igual (clips, página para elegir perfiles, revisión de las respuestas y copia de
  la transcripción con el código de cada participante).
  Necesita `ffmpeg`.
- `skills/resumen-gf/references/formato_puntos.md`: formato de `puntos.json` y de las
  transcripciones que acepta.
- `skills/resumen-gf/ejemplo/`: una transcripción y un resumen **ficticios** para probar la
  instalación.
- `skills/limpieza-gf/SKILL.md`: el proceso de limpieza con dos aparatos y sus reglas.
- `skills/limpieza-gf/scripts/`: `contraste.py` (desfase y tramos distintos entre aparatos, borrador),
  `paginas.py` (entrada para `voces.py`, pistas, páginas de contraste, cortes y dudosos, análisis de
  cortes), `limpiar.py` (aplica todas las decisiones de `limpieza.json`, palabra por palabra) y
  `formato_limpia.py` (la limpia en el formato del equipo). Necesitan `ffmpeg`.
- `skills/limpieza-gf/references/limpieza_json.md`: formato de `limpieza.json`, con un ejemplo ficticio.

No incluye transcripciones, perfiles ni datos de ninguna sesión real. Esos se quedan en la
carpeta del proyecto, y el `.gitignore` excluye los `.docx` generados.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
