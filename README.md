# resumen-gf

Plugin de [Claude Code](https://claude.com/claude-code) para hacer el **resumen de 10 puntos de
un grupo focal**. Cada punto lleva un título formal, un párrafo en lenguaje llano y **de 2 a 4
citas textuales**, con el perfil de quien habla y la marca de tiempo. Sale en `.docx` con
Corbel y con todo el texto en negro.

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

## Qué incluye

- `skills/resumen-gf/SKILL.md`: reglas de redacción, de selección de citas y de atribución.
- `skills/resumen-gf/scripts/generar_resumen.py`: verificación de citas y maquetación.
- `skills/resumen-gf/scripts/voces.py`: identificación de voces de oído cuando la transcripción
  rotula a todos igual (clips, página para elegir perfiles y revisión de las respuestas).
  Necesita `ffmpeg`.
- `skills/resumen-gf/references/formato_puntos.md`: formato de `puntos.json` y de las
  transcripciones que acepta.
- `skills/resumen-gf/ejemplo/`: una transcripción y un resumen **ficticios** para probar la
  instalación.

No incluye transcripciones, perfiles ni datos de ninguna sesión real. Esos se quedan en la
carpeta del proyecto, y el `.gitignore` excluye los `.docx` generados.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
