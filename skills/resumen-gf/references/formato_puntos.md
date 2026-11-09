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

Se acepta también el formato anterior, con `cita`, `hablante` y `ts` sueltos en el punto. Cuenta
como una sola cita, así que no pasa el mínimo de 2 salvo que se ponga `"citas_min": 1`.

## Formatos de transcripción que lee el script

- **`turns_ts.json`**: lista de turnos `{"label": "...", "ts": "HH:MM:SS", "text": "..."}`.
- **`merged.json`**: `{"turnos": [...]}` con los mismos campos, más `start` (segundos) y
  `baja_confianza` (palabras con baja confianza del reconocimiento de voz).
- **`.docx`**: un párrafo por turno, `Hablante [HH:MM:SS]:  texto`. Es el formato que producen
  los plugins de transcripción del equipo. Los párrafos sin marca se suman al turno anterior.
