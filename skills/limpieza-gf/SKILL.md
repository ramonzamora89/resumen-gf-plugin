---
name: limpieza-gf
description: 'Limpia la transcripción de un grupo focal grabado con dos aparatos (teléfono y grabadora): identifica las voces de oído, contrasta los dos audios, corrige los cortes entre hablantes y las palabras mal transcritas con páginas locales para que el equipo escuche, y entrega la limpia en el formato del equipo (MODERADOR / R, Arial) lista para el resumen de 10 puntos. Úsalo cuando pidan limpiar, revisar o «dejar lista» la transcripción de una sesión de grupo focal, contrastar los dos audios, identificar quién habla, o cuando haya un merged.json y dos JSON de WhisperX de la misma sesión.'
---

# Limpieza de un grupo focal grabado con dos aparatos

La limpieza la decide el oído del equipo. Tú preparas el material, propones con evidencia, revisas
contradicciones y registras cada decisión; **nunca asignas una voz ni eliges una versión por tu cuenta**
cuando la evidencia no alcanza. Todo queda en un `limpieza.json` por sesión y el motor
(`scripts/limpiar.py`) lo vuelve a aplicar desde cero cada vez, así que nada se edita a mano en la salida.

Scripts (carpeta `scripts/` de este skill; Python 3, `python-docx`, `ffmpeg` en el PATH):

| Script | Qué hace |
|---|---|
| `contraste.py contrastar` · `borrador` | Compara los dos aparatos (desfase, tramos distintos) y arma el borrador |
| `paginas.py` | Entrada para `voces.py`, pistas, páginas de oído (contraste, cortes, dudosos) y análisis de cortes |
| `limpiar.py CARPETA` | Aplica todas las decisiones de `limpieza.json` palabra por palabra |
| `formato_limpia.py CARPETA` | Limpia en el formato del equipo: `<nombre>_Limpia.docx` y `… con participantes.docx` |

El formato de `limpieza.json`, con un ejemplo ficticio, está en `references/limpieza_json.md`.

## 0. Antes de empezar

- **Los dos aparatos no son intercambiables.** Compara duraciones: si una termina en un número redondo
  (60:00), ese aparato cortó por límite de archivo. La **base** es el que tiene la sesión completa en una
  sola línea de tiempo (suele ser el teléfono); el otro es el **cotejo** (suele tener mejor señal).
- Transcribe los dos con WhisperX (plugin de transcripción del equipo), con el número de voces = personas en
  la sala (participantes + equipo), y arma el `merged.json` de la base con `build_turns.py`.
- Pide la hoja de perfiles (sexo, edad, ocupación) y confirma quién del equipo estaba en la sala y su rol.
  Revisa la hoja: códigos repetidos o mal digitados, edades fuera del tramo del grupo. Avisa; no corrijas en
  silencio.
- `contraste.py contrastar BASE.json COTEJO.json contraste.tsv`: anota el desfase en `limpieza.json`
  («desfase»). Si los cuartos de la sesión dan valores distintos, el reloj deriva: avisa.
- `contraste.py borrador CARPETA ID "descripción" --tsv contraste.tsv`: borrador con notas en rojo.
  Comprueba en el primer turno que «Hablante 1» sea el moderador.

## 1. Identificar las voces (con `voces.py` del plugin resumen-gf)

1. `paginas.py para-voces CARPETA` → `<nombre>_para_voces.docx` (MODERADOR / R + tabla de perfiles).
2. `voces.py alinear <nombre>_para_voces.docx BASE_whisperx.json alineacion_voces.json`.
3. **Pistas.** Si hubo ronda de presentaciones, úsala (`--presentaciones`). Si no se grabó:
   `paginas.py pistas-buscar CARPETA` lista lo que cada voz dice de sí (oficio, estudios, con quién vive, de
   dónde es) y las marcas de género («me siento tranquilo», «agradecida», «nosotras»). También sirve cómo
   el moderador da la palabra («Compañera», «Y compañero, ¿cómo…?»). Elige 8 a 15 frases, ponlas en
   «pistas» de `limpieza.json` con un texto neutro (lo que se oye, no el perfil que crees) y corre
   `paginas.py pistas CARPETA` → `pistas.json`.
4. `voces.py clips alineacion_voces.json AUDIO_BASE clips_voces --limpia <nombre>_para_voces.docx
   --presentaciones pistas.json --titulo "GF3 · identificación de voces"`. La persona del equipo escucha y
   pega las respuestas; guárdalas en `respuestas_v1.txt` y corre `voces.py revisar`.
5. **Lee lo que dice cada persona** y busca contradicciones con su perfil: sexo («mi esposa»), con quién vive,
   si estudia o trabaja, edad. Contrasta cada voz con la separación del cotejo (si el cotejo también la pone
   en una sola voz, no es una mezcla). Devuelve la duda concreta con la cita y la marca de tiempo; el oído
   decide. Guarda cada versión de las respuestas (`respuestas_v2.txt`…) con el motivo del cambio en un
   comentario y pon la vigente en «voces» de `limpieza.json`.

## 2. Contraste de aparatos (paso 1 del motor)

`paginas.py contraste CARPETA` → `clips_contraste/`: los tramos de 8 palabras o más en que los aparatos no
coinciden, con los dos audios. Se responde T (base), G (cotejo), TG (los dos), X (inaudible) u O (lo que
se oye). Señala las frases típicas de alucinación de Whisper («Gracias por su atención», «Gracias a todos
por su participación») y las frases sin sentido, pero no decidas por el equipo: hay frases raras que sí se
dijeron (alguien le habla a un niño que entró a la sala).

- Guarda las respuestas tal cual en `respuestas_contraste_v1.txt`. **Las notas tuyas van en líneas
  aparte que empiezan con `#`**, nunca detrás del `#` de una línea O: lo que sigue al `#` de una O entra al
  texto.
- Si el equipo deja «?» y escribe un texto, es una O: confírmalo.
- Si una O reemplazaría un tramo que incluye otra voz (por ejemplo, el cierre del moderador), deja la
  respuesta como está, pon «ajustes»: {"HH:MM:SS": "T"} y aplica la frase en «oido» con tiempo exacto.
- Un comentario de alguien que no participa (al fondo) va en «oido» con voz `FONDO`: sale como
  «Voz al fondo», en turno propio, y no se cita.

Corre `limpiar.py CARPETA` y revisa el texto alrededor de cada cambio: si lo escrito por el equipo empieza
antes del tramo, el motor quita la repetición; si queda algo raro, pregunta.

## 3. Cortes entre hablantes (paso 2)

La separación automática corre los cortes unas palabras hacia un lado u otro, y **el cotejo también se
atrasa**: ningún aparato decide solo. `paginas.py cortes-analisis CARPETA` muestra, en cada cambio de
hablante, la voz que da cada aparato y las pausas. Decide con la gramática de la frase completa más los dos
aparatos:

- «¿Cómo está | su familia?» → la pregunta entera es del moderador; «Yo | considero que…» → todo es del
  participante que responde. La dirección cambia de un caso a otro.
- Fórmulas del moderador dentro de un turno de participante («Ok, gracias.», «¿Alguien más…?»,
  «Compañero.») pasan al moderador. «Gracias, compañera/o» es del moderador (regla automática).
- Una persona suele empezar sus turnos igual («Yo siento que…»): es evidencia.
- Lee el contexto (turno anterior y siguiente) antes de decidir.

Lo seguro va en «cortes» de `limpieza.json`, una entrada por corte con su motivo; usa `contexto | frase`
cuando la frase se repite cerca. Lo dudoso va en «casos_cortes» con 2 o 3 opciones concretas y
`paginas.py cortes CARPETA` arma la página; las respuestas van en «oido_cortes». Lo que nadie transcribió
pero se oye (un «Así es» de otra persona) va en «insertar». Si la base puso mal la hora de una frase (el clip no
coincide con el texto, o la frase aparece dentro de otra), el cotejo suele tenerla en orden: «reubicar»
con su hora.

El motor aplica además dos reglas: un fragmento de menos de 4 palabras entre dos tramos de la misma persona
es de esa persona (salvo que el cotejo diga otra cosa), y los turnos seguidos de la misma persona se juntan.
Al terminar no debe quedar ningún turno «R»; los que queden van a la página de cortes.

## 4. Texto (paso 4)

- **Lee la transcripción completa antes de cerrar.** La búsqueda automática deja pasar errores que solo se
  ven leyendo: palabras que no existen, siglas deformadas, frases que no dan sentido.
- Compara cada palabra rara con el cotejo. Se corrige **sin marca** solo cuando el cotejo y el contexto de la
  sesión coinciden (base «iba a ver tender», cotejo «iba a vender», y antes dijo que vende tortillas). Si no,
  `[dudoso: hipótesis]`; si no hay mejor hipótesis, el texto de la base. Nunca se rellena con texto plausible.
- **Términos del aviso inicial de WhisperX:** revisa cada aparición contra el cotejo. Los dos aparatos se
  transcribieron con el mismo aviso, así que coincidir no basta si el término es raro en ese contexto (un
  municipio del aviso que la grabadora oyó como otra palabra resultó ser otro municipio).
- Siglas y nombres que Whisper deforma: compáralos con el cotejo y con otras menciones de la misma sesión.
- `paginas.py dudosos CARPETA` → página con cada `[dudoso: …]`. Si el equipo dice que el audio no
  corresponde al texto, revisa la hora en los dos aparatos: la base pudo haber comprimido la frase.
- Las mayúsculas a mitad de frase pasan a minúscula solas; protege instituciones en «instituciones».

## 5. Nombres y contenido sensible

- Nombre de un participante dicho en voz alta (de esta sesión u otra) → `[PARTICIPANTE]` en la limpia
  («reemplazar_palabra» o «texto»). Los nombres de funcionarios y figuras públicas se mantienen. Los de
  terceros que no son ni una cosa ni otra: pregunta.
- Antes de que algo salga del equipo se decide explícitamente cómo se tratan los testimonios sensibles; deja
  la decisión escrita en la carpeta de la sesión.
- Las carpetas `clips_*` llevan voces reales y los archivos de trabajo (`cambios.tsv`, respuestas) pueden
  llevar nombres: no salen del equipo.

## 6. Entregar

1. `limpiar.py CARPETA`: debe terminar con 0 pendientes y 0 palabras sin voz.
2. En «cfg» de `limpieza.json` pon el estado («LIMPIA (fecha): …») y los hablantes.
3. `formato_limpia.py CARPETA` → `<nombre>_Limpia.docx` (todos «R») y `<nombre>_Limpia con
   participantes.docx` (códigos y columnas Código y Turnos). Comprueba con grep que no haya nombres de
   participantes ni del equipo, ni marcas de trabajo.
4. El resumen de 10 puntos (skill resumen-gf) se hace sobre `… con participantes.docx`.

Al entregar cada etapa di qué se aplicó, qué interpretaste de las respuestas (y cómo), qué queda para el
oído y dónde está cada página. `limpia/cambios.tsv` tiene una fila por decisión con su motivo.
