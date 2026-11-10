# Formato de `puntos.json`

```json
{
  "titulo": "Resumen de 10 puntos clave del grupo focal de mujeres de 25 a 34 años",
  "subtitulo": "Ronda 2026 · sesión de 90 minutos · ocho participantes",
  "fuente": "turns_ts.json",
  "salida": "Resumen 10 puntos - GF3 mujeres 25-34.docx",
  "estado": "revisado",
  "equipo": ["Moderador", "Asistente"],
  "citas_min": 2,
  "citas_max": 4,
  "perfiles": {
    "Participante 1": "Mujer, 29 años, vendedora",
    "Hablante 4": "Mujer, 33 años, enfermera"
  },
  "puntos": [
    {
      "titulo": "Título nominal y formal",
      "cuerpo": "De 3 a 5 frases en lenguaje llano.",
      "citas": [
        {"texto": "Cita literal.", "hablante": "Participante 1", "ts": "00:12:04"},
        {"texto": "Otra voz (…) con un corte.", "hablante": "Hablante 4", "ts": "00:13:40"}
      ]
    }
  ],
  "nota_base": "Sesión, lugar, fecha, duración, participantes, fuente de los perfiles, transcripción usada y advertencia de que no se generaliza."
}
```

| Campo | Qué es |
|---|---|
| `fuente` | `turns_ts.json` (limpia), `merged.json` (cruda) o la transcripción `.docx`. Las rutas relativas se leen desde la carpeta de `puntos.json`. |
| `salida` | El `.docx` que se escribe. Si es preliminar, el nombre termina en `(preliminar).docx`. |
| `estado` | `revisado` o `preliminar`. Con `merged.json` se fuerza a preliminar. |
| `equipo` | Etiquetas que nunca se citan: moderación, notas, logística. |
| `citas_min`, `citas_max` | Opcionales. Por defecto 2 y 4. |
| `perfiles` | Etiqueta de la transcripción → perfil impreso. Nunca nombres. |
| `puntos[].citas` | De 2 a 4 citas, cada una con `texto`, `hablante` y `ts` (HH:MM:SS del turno). |
| `puntos[].citas[].voz` | Opcional. Quién habla, cuando la transcripción rotula a todos igual (por ejemplo, «R»). Se usa para el perfil (`perfiles[voz]`) y para el aviso de una sola voz; la verificación sigue usando `hablante` y `ts`. |

Se acepta también el formato anterior, con `cita`, `hablante` y `ts` sueltos en el punto. Cuenta
como una sola cita, así que no pasa el mínimo de 2 salvo que se ponga `"citas_min": 1`.

## Formatos de transcripción que lee el script

- **`turns_ts.json`**: lista de turnos `{"label": "...", "ts": "HH:MM:SS", "text": "..."}`.
- **`merged.json`**: `{"turnos": [...]}` con los mismos campos, más `start` (segundos) y
  `baja_confianza` (palabras con baja confianza del reconocimiento de voz).
- **`.docx`**: un párrafo por turno, `Hablante [HH:MM:SS]:  texto` (el formato de los plugins de
  transcripción del equipo) o `Hablante: [HH:MM:SS] texto` (el de las transcripciones limpiadas a
  mano). Los párrafos sin marca se suman al turno anterior.

## Identificación de voces (`scripts/voces.py`)

Formato de las respuestas que copia la página (`index.html`):

```
GF3 · identificación de voces
voz:SPEAKER_08 = C
voz:SPEAKER_02 = MEZCLA · nota: al final suena otra persona
cita:00:43:54 = C
```

A mano se agregan líneas para turnos sueltos, como las presentaciones, con el motivo después de `#`:

```
turno:00:42:47 = C  # cocinera, 29 años
```

`C` es la fila de la tabla de perfiles de la transcripción limpia (o su código, si la tabla trae
columna «Código»). Otros valores: `MEZCLA`, `EQUIPO`, `NOSE`. `aplicar` escribe en cada cita
`"voz": "perfil C"` y en `perfiles` el texto de esa fila.
