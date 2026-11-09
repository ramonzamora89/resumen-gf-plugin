---
name: resumen-gf
description: 'Genera el resumen de 10 puntos de un grupo focal (título, párrafo en lenguaje llano y de 2 a 4 citas textuales verificadas por punto, con hablante y marca de tiempo), en .docx con Corbel y todo en negro. Úsalo cuando pidan el resumen, los 10 puntos, los hallazgos o "una idea general" de una sesión de grupo focal, a partir de la transcripción limpia (turns_ts.json), la cruda (merged.json, sale como preliminar) o la transcripción en .docx con turnos «Hablante [HH:MM:SS]: texto».'
---

# Resumen de 10 puntos de un grupo focal

El trabajo tiene dos partes. Leer y redactar te toca a ti; verificar y maquetar lo hace el script.

1. **Tú** lees la transcripción completa y escribes `puntos.json`.
2. **`scripts/generar_resumen.py puntos.json`** comprueba cada cita contra la transcripción y,
   solo si todas pasan, arma el `.docx`: Corbel en todos los estilos (Title, Subtitle, Heading 1,
   Heading 2, Quote, Atribución), márgenes de 2 cm y todo el texto en negro.

El script está en la carpeta `scripts/` de este skill (la ruta base aparece al cargarlo).
Se corre con Python 3 y `python-docx`:

```
python -I <carpeta del skill>/scripts/generar_resumen.py <sesión>/puntos.json
```

En Mac el comando suele ser `python3`. Si falta `python-docx`, el script lo dice; se instala con
`python -m pip install python-docx`. Usa `--solo-verificar` mientras ajustas las citas.
El formato completo de `puntos.json` está en `references/formato_puntos.md`, y un ejemplo
ficticio que corre en cualquier máquina, en `ejemplo/`.

## Antes de leer

- Ubica la carpeta de la sesión (por ejemplo, `transcripciones/<sesión>/`) y su
  `cfg.json` si existe: trae los pendientes, quién es del equipo y los perfiles.
- **Elige la fuente**, en este orden:
  1. `turns_ts.json`: transcripción limpia.
  2. La transcripción `.docx` con párrafos `Hablante [HH:MM:SS]: texto`. Si su encabezado dice
     «para revisión» o la limpieza no está hecha, pon `"estado": "preliminar"`.
  3. `merged.json`: cruda, sin limpiar. El resumen sale **preliminar** automáticamente, con un
     aviso debajo del título.
- **Equipo.** El rol del equipo cambia de una sesión a otra: quien modera en una puede tomar
  notas en otra. Confírmalo en `cfg.json` o pregunta, y pon en `equipo` todas las etiquetas
  del equipo. **Nunca se citan.**
- **En la versión cruda, evita los tramos que `cfg.json` marca como alucinación**, por ejemplo
  «Gracias por ver el video». Tampoco cites voces sin identificar que puedan ser del equipo. Si
  no sabes cuál voz es de la persona del equipo, dilo en la nota sobre la base.

## Cómo se escriben los puntos

- **Diez puntos**, en el orden en que aparecen en la sesión o por tema de la guía.
- **Título nominal, descriptivo y formal**: «La policía vista como amenaza», no «Nadie nos
  cuida». No uses cifras ni conclusiones narrativas.
- **Cuerpo** de 3 a 5 frases en lenguaje llano, que pueda leer alguien de 15 años. Si aparece un
  término técnico o local, se explica en la misma frase (por ejemplo, qué es la canasta básica).
  Usa «el grupo», «varias personas», «una participante». Nunca «los jóvenes piensan» ni nada que
  generalice: un grupo focal no mide cuánta gente piensa algo.
- Si un dato del contexto corrige lo que se dijo, se aclara sin desmentir a nadie.

## Las citas: de 2 a 4 por punto

Cada punto lleva **entre 2 y 4 citas**. El script rechaza el documento si un punto tiene menos
o más. Sirven para que el lector vea el punto dicho con las palabras de quienes participaron, y
en voces distintas.

**Cómo elegirlas:**

- **Cada cita tiene que aportar algo que las otras no traen**: otra persona, otro matiz, otro
  ejemplo concreto o un desacuerdo. Dos citas que dicen lo mismo con otras palabras no suman,
  así que basta con una de ellas.
- **Prefiere voces distintas.** Si todas las citas de un punto son de la misma persona, el
  script lo avisa. Eso es aceptable solo si de verdad nadie más habló del tema, y entonces el
  cuerpo tiene que decir «una participante», no «el grupo».
- **Si hubo desacuerdo, cítalo.** Cuando una persona discrepa, su cita va en el punto, y el
  cuerpo nombra la diferencia. No se presenta un consenso que no hubo.
- **Orden:** primero la cita que mejor dice el punto y después las que lo matizan o lo
  contradicen. Si no hay una cita principal clara, van en el orden de la sesión.
- **Extensión:** de una a tres frases por cita. Si una cita necesita más, recórtala con `(…)`.
- **Si no encuentras dos citas genuinas, el punto probablemente es débil.** Fusiónalo con otro
  o cámbialo. **Nunca se rellena** con una cita que no diga el punto, y nunca con palabras del
  moderador o del equipo.
- La misma cita no se repite en dos puntos; el script lo avisa.

**Fidelidad:**

- Cada cita es literal de la transcripción. Se corrige solo la puntuación. `(…)` marca un corte
  y cada fragmento tiene que aparecer en orden.
- `hablante` es la etiqueta tal como aparece en la transcripción («Participante 3»,
  «Hablante 4», o un nombre de pila si se dijo en la grabación). `ts` es la marca de tiempo **de ese turno**. Si el script dice que no hay turno,
  te muestra los que hay cerca.
- La verificación revisa los 3 minutos que siguen al turno, porque la diarización (la
  separación automática de voces) a veces parte una frase entre dos turnos.
- **Citas cortas en el cuerpo** van así: “frase literal” (mujer, 21 años, …, 01:10:59). El script
  verifica las que tienen la marca de tiempo en los 40 caracteres que siguen a la comilla de
  cierre. Si la marca queda más lejos, verifícala tú.
- En la versión cruda, el script avisa de las palabras de la cita con baja confianza del
  reconocimiento de voz. Esas citas se escuchan en el audio antes de usarlas fuera del equipo.

## Atribución

- `perfiles` traduce cada etiqueta al perfil que se imprime: «Mujer, 31 años, ingeniera
  ambiental». El perfil sale del inventario de participantes; esa correspondencia vive en el
  `cfg.json` de la sesión y no sale del equipo. **Nunca se imprimen nombres** en el resumen.
- Una etiqueta sin perfil sale como «Participante (Hablante N en la transcripción)». No adivines
  perfiles a partir de la ronda de presentaciones; deja la hipótesis en la nota sobre la base.

## Nota sobre la base

Va siempre al final y declara:

- sesión, lugar, fecha, duración y número de participantes;
- de dónde salen los perfiles;
- qué transcripción se usó (cruda o limpia, uno o dos dispositivos);
- que cada cita lleva su marca de tiempo para verificarla contra el audio;
- que un grupo focal muestra cómo razonan y con qué palabras hablan quienes participaron, no
  cuánta gente piensa lo mismo, y que todo lo dicho se refiere solo a quienes participaron.

En la versión preliminar agrega lo que falta antes de la limpieza: voces sin identificar,
alucinaciones evitadas y la persona del equipo sin ubicar.

## Salida

- `salida`: `<carpeta de la sesión>/Resumen 10 puntos - <sesión>.docx`. Si es preliminar, el
  nombre termina en `(preliminar).docx`, para que no se confunda con el definitivo.
- Guarda `puntos.json` junto al `.docx`. Es la fuente del documento: para corregirlo se edita
  el JSON y se vuelve a correr el script, nunca el `.docx` a mano.
- Al entregar, di cuántas citas se verificaron, qué avisos dio el script y qué quedó pendiente.
- Antes de que el documento salga del equipo hay que decidir cómo se tratan los testimonios
  sensibles (violencia, muertes, salud) y los nombres de terceros que aparecen en las citas.
