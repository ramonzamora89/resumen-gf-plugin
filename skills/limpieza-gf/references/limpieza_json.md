# Formato de `limpieza.json`

Un archivo por sesión, en la carpeta de la sesión. Guarda **todas** las decisiones de la limpieza; el
motor (`limpiar.py`) las aplica desde cero cada vez. Las rutas son relativas a la carpeta de la sesión.
Ejemplo ficticio:

```json
{
  "sesion": "GF3",
  "nombre": "GF3",
  "base":   {"whisperx": "gf3_2/gf3_2_whisperx.json", "audio": "../audios/GF3_2.m4a"},
  "cotejo": {"whisperx": "gf3_1/gf3_1_whisperx.json", "audio": "../audios/GF3_1.mp3"},
  "desfase": 1.67,
  "moderador": "SPEAKER_02",
  "borrador": "merged.json",
  "perfiles": [["P1", "F", "29", "Vendedora"], ["P2", "M", "31", "Maestro"]],
  "voces": {"respuestas": "respuestas_v2.txt", "letras": "AB"},
  "pistas": [["me siento tranquilo", 6, 8, "«Me siento tranquilo…»"]],
  "contraste": {"tsv": "contraste.tsv", "respuestas": "respuestas_contraste_v1.txt",
                "pagina": "clips_contraste/contraste.json", "largo": 8, "ajustes": {}},
  "oido": [[1225.3, 1227.4, "Ya viene.", "FONDO", "comentario al fondo de alguien que no participa"]],
  "cortes": [["00:14:34", "está | su familia?", "Mod", "«¿Cómo está su familia?»"],
             ["00:20:15", "soluciona? | No lo soluciona.", "P2", "respuesta del participante; el cotejo coincide"]],
  "casos_cortes": [["00:29:37", 1770, 1786, "«…¿Me repite? Se diría que…»", "«¿Me repite?» quedó con P2.",
                    [["A", "Lo dice el moderador"], ["B", "Lo dice P2"], ["C", "Otra cosa (escribir)"]]]],
  "oido_cortes": [["00:29:37", "¿Me repite?", "Mod", "A: lo dice el moderador"]],
  "reubicar": [{"ts": "00:48:39", "frase": "La verdad me gustó.", "voz": "P2", "antes": "P1",
                "t_nuevo": 2933.0, "despues_de": {"ts": "00:48:51", "frase": "eso es lo que pienso."},
                "motivo": "la base desordenó la frase; orden y hora del cotejo"}],
  "insertar": [{"ts": "00:20:17", "antes_de": "realmente... | Entonces,", "texto": "Así es.", "voz": "P1",
                "motivo": "se oye y ningún aparato lo transcribió"}],
  "reemplazar_palabra": [["Fulana,", "[PARTICIPANTE],", "nombre de participante dicho en voz alta"]],
  "regla_gracias_companera": true,
  "texto": [["00:24:50", "a ver tender,", "a vender,", "cotejo «a vender»; antes dijo que vende tortillas"],
            ["00:44:01", "por bolimer,", "[dudoso: por bolimer],", "los dos aparatos igual, sentido no claro"]],
  "instituciones": ["estado", "educación", "gobernación"],
  "minusculas": true,
  "nota_participantes": "Quién habla lo identificó el equipo de oído. Los nombres de personas dichos en voz alta se reemplazaron por [PARTICIPANTE].",
  "cfg": {"hablantes": "Moderador y 2 participantes (P1 y P2), identificados de oído",
          "estado": "LIMPIA (fecha): contraste, cortes y texto revisados de oído por el equipo"}
}
```

| Campo | Qué es |
|---|---|
| `base`, `cotejo` | JSON de WhisperX (palabras con tiempo y voz) y audio de cada aparato. La base tiene la sesión completa. |
| `desfase` | Segundos que el cotejo va detrás de la base (`contraste.py contrastar` lo mide). |
| `moderador` | Voz (`SPEAKER_xx`) del moderador en la separación de la base. |
| `borrador` | `merged.json` de la base (sale de `build_turns.py`); cada turno es un tramo seguido de sus palabras. |
| `perfiles` | `[código, sexo, edad, ocupación]` en el orden de la hoja. Sin nombres. La fila 1 es la letra A de `voces.py`. |
| `voces` | Respuestas vigentes de `voces.py` (`voz:SPEAKER_xx = LETRA`) y las letras usadas. |
| `pistas` | `[frase, segundos antes, segundos después, texto para la página(, inicio de la palabra siguiente)]`. |
| `contraste` | Respuestas de la página de contraste. `ajustes` cambia una decisión al aplicarla (p. ej. una O que se pasa a «oido»). |
| `oido` | `[inicio, fin (s de la base), texto, voz, motivo]`: reemplaza lo que empieza en ese rango. Voz `FONDO` = no participa. |
| `cortes` | `[marca, frase, voz destino, motivo]` decididos leyendo. `contexto | frase`: el contexto no se mueve. |
| `casos_cortes` | Cortes dudosos para la página: `[marca, inicio s, fin s, frase, cómo quedó, opciones]`. |
| `oido_cortes` | Igual que `cortes`, con lo que respondió el equipo; la regla de fragmentos no los toca. |
| `reubicar` | Una frase que la base metió en otro lugar: pasa detrás de `despues_de`, con la hora del cotejo. |
| `insertar` | Algo que se oye y ningún aparato transcribió, antes de la frase indicada. |
| `reemplazar_palabra` | Palabra exacta → reemplazo, en todo el texto (nombres dichos en voz alta). |
| `texto` | `[marca, frase, reemplazo, motivo]`. El reemplazo puede llevar `[dudoso: …]` o `[inaudible]`. |
| `instituciones` | Palabras que no pasan a minúscula a mitad de frase. |
| `cfg` | Campos que se escriben en `limpia/cfg.json` (estado, hablantes, criterio de edición). |

Voces que se pueden usar en los campos: `Mod`, los códigos `P1`, `P2`… (según `voces`), `FONDO`,
`SINID` (participante sin identificar: queda «R» y va a pendientes) o un `SPEAKER_xx` directo.

Marcas de tiempo: `HH:MM:SS` aproximada (la frase se busca a ±90 s); `HH:MM:S` con un solo dígito en los
segundos significa «en esa decena de segundos». Si la frase aparece dos veces cerca, el motor se detiene y
pide contexto.

## Respuestas de las páginas

```
contraste:00:09:50 = T
contraste:00:57:01 = O  # lo que se oye
# notas tuyas, siempre en líneas aparte
corte:00:33:28 = C  # lo que dijo el equipo
dudoso:00:15:18 = H
```
