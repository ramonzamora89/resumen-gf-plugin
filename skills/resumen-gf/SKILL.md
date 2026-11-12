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
- Si la sesión se grabó con dos aparatos y todavía no está limpia, la limpieza va primero, con el skill
  **limpieza-gf** de este plugin. Su salida `<nombre>_Limpia con participantes.docx` (turnos
  `P1: [HH:MM:SS] texto`, moderador como `MODERADOR`) es la mejor fuente para el resumen.
- **Elige la fuente**, en este orden:
  1. `turns_ts.json`: transcripción limpia.
  2. La transcripción `.docx` con párrafos `Hablante [HH:MM:SS]: texto` o
     `Hablante: [HH:MM:SS] texto`. Si su encabezado dice «para revisión» o la limpieza no está
     hecha, pon `"estado": "preliminar"`.
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
  «Hablante 4», o un nombre de pila si se dijo en la grabación). `ts` es la marca de tiempo
  **de ese turno**. Si el script dice que no hay turno, te muestra los que hay cerca.
- **Transcripciones que no distinguen a los participantes.** Si todos aparecen con la misma
  etiqueta (por ejemplo, «R»), `hablante` sigue siendo esa etiqueta y cada cita lleva además
  `voz`: quién habla. El perfil y el aviso de una sola voz usan `voz`. Solo se pone `voz` cuando
  sale de una fuente que se puede revisar, por ejemplo la separación de voces de una
  transcripción anterior de la misma sesión, alineada turno por turno; se citan solo los turnos
  donde las dos versiones coinciden, y la nota sobre la base explica cómo se asignó. Si no hay
  esa fuente, no se pone `voz`: la cita sale como «Participante» y el cuerpo no puede decir que
  hablaron personas distintas.
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

## Identificar de oído quién habla (`scripts/voces.py`)

Cuando la transcripción limpia rotula a todos los participantes igual («R») y no hay una
transcripción anterior con voces revisadas, una persona del equipo identifica las voces de oído.
Si la sesión está en limpieza (skill limpieza-gf), `paginas.py para-voces` arma la entrada y
`paginas.py pistas` las pistas cuando no hubo ronda de presentaciones grabada.
Tú preparas el material y revisas sus respuestas; nunca asignas un perfil por tu cuenta.
Necesita `ffmpeg` en el PATH y la grabación de la sesión.

1. **Separar las voces.** Si la separación que ya existe tiene menos voces que personas en la
   sala (participantes más equipo), repítela con el número correcto, con el Python del ambiente
   de WhisperX: `voces.py diarizar AUDIO WHISPERX.json DIAR.json --hablantes N`. Usa el JSON de
   WhisperX de esa misma grabación (palabras con tiempo).
2. **Alinear:** `voces.py alinear LIMPIA.docx DIAR.json ALINEACION.json`. Calcula solo el
   desfase entre la limpia y la grabación (pueden ser minutos si la limpia incluye tramos que la
   grabación no tiene). Un turno tiene voz si coincide en ≥ 60 % de sus palabras y ≥ 90 % de esas
   palabras las dice una sola voz.
3. **Clips y página:** `voces.py clips ALINEACION.json AUDIO CARPETA --limpia LIMPIA.docx
   --puntos puntos.json --presentaciones PRES.json --titulo "GF3 · identificación de voces"`.
   - **Presentaciones:** los turnos de una ronda de presentaciones duran 2 o 3 segundos y los
     tiempos de la limpia suelen quedar corridos ahí. Ubica cada presentación en las palabras
     reconocidas de la grabación (lo que dice cada una: oficio, edad), comprueba que el tramo
     contenga a la persona correcta y pasa los cortes en `PRES.json`
     (`[{"inicio": s, "fin": s, "texto": "Cocinera; 29 años"}]`). Sin ese archivo, el script
     intenta cortarlas solo y marca cada clip como «comprobar».
   - La carpeta lleva voces y nombres reales: **no se publica ni sale del equipo**. Se abre
     `index.html` con doble clic; las respuestas se copian con el botón del final.
4. **Revisar las respuestas:** guarda lo que te peguen en un `.txt` y corre
   `voces.py revisar ALINEACION.json RESPUESTAS.txt --limpia LIMPIA.docx --llega LETRA=HH:MM:SS`
   (`--llega` para quien llegó tarde, con el tiempo de la limpia). El script detecta perfiles
   repetidos en dos voces y voces que hablan antes de que llegue esa persona, y lista todo lo
   que dice cada persona. **Lee esa lista** y busca contradicciones: con quién vive («vivo sola»
   frente a «mi hija»), hijos, dónde vive, a qué se dedica, si estudia o trabaja. Contrasta
   también con la ronda de presentaciones. Devuelve a la persona las dudas concretas, con la
   evidencia; su oído decide.
5. **Aplicar:** `voces.py aplicar …` con los mismos argumentos más `--puntos puntos.json`. Solo
   escribe si no hay errores. Las voces sin respuesta o «No estoy segura» quedan como
   «Participante» (la voz sigue sirviendo para el aviso de una sola voz); «Mezcla» las deja sin
   voz. Revisa la redacción de los perfiles, que salen de la tabla tal cual, y explica el método
   en la nota sobre la base.
6. **Transcripción con participantes:** `voces.py transcripcion ALINEACION.json RESPUESTAS.txt
   --limpia LIMPIA.docx --salida "LIMPIA con participantes.docx"`. Copia la limpia (el original no
   se toca), cambia la etiqueta de cada turno identificado por el código del participante (P1, P2…
   en el orden de la tabla, o el código que ya traiga) y agrega a la tabla las columnas «Código» y
   «Turnos», con una nota que explica el método. Los turnos sin identificar siguen con su etiqueta.

**Presentaciones y turnos sueltos.** En una presentación la persona dice quién es: es mejor
evidencia que la separación de voces. Agrégalas a mano al archivo de respuestas, una línea por
turno, con el motivo: `turno:00:42:47 = C  # cocinera, 29 años`. Asigna solo las que coinciden con
una sola fila de la tabla (por oficio y edad, o porque la otra persona con ese oficio ya se
presentó). Si lo que alguien dice no coincide con la tabla (otra ocupación, otra edad), no lo
resuelvas por tu cuenta: explica la discrepancia y la lectura más probable, y espera la
confirmación del equipo. Las líneas `turno:` y `cita:` mandan sobre la separación de voces.

**Turnos cortos.** Un turno de menos de 4 palabras («Mis hijos», «Zona 18») nunca recibe voz
automáticamente: la coincidencia por texto puede caer en otra frase igual dicha cerca.

**Errores de contenido de la limpia** (una edad mal transcrita, por ejemplo) se corrigen en la
limpia, idealmente por quien la hizo; no se corrigen en silencio en las copias.

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
