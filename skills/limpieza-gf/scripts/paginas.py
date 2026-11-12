#!/usr/bin/env python3
"""Páginas locales para decidir de oído, y análisis que las preparan. Todo se lee de CARPETA/limpieza.json.

  python paginas.py para-voces CARPETA
      Escribe <nombre>_para_voces.docx, la entrada de voces.py (plugin resumen-gf): turnos de merged.json con el
      moderador como «MODERADOR» y todos los demás como «R», y la tabla de perfiles (sin nombres) en el orden de
      «perfiles». Las letras A, B, C… de voces.py son las filas de esa tabla, en ese orden.
  python paginas.py pistas-buscar CARPETA
      Lista las frases en que alguien dice algo de sí (oficio, estudios, con quién vive, de dónde es) y las
      que marcan género («me siento tranquilo», «agradecida», «nosotras»), con la voz de cada aparato. Sirve
      cuando no hubo ronda de presentaciones grabada: de aquí salen las «pistas» de limpieza.json.
  python paginas.py pistas CARPETA
      Ubica cada pista de limpieza.json en las palabras de la base y escribe pistas.json, que se pasa a
      `voces.py clips … --presentaciones pistas.json` (plugin resumen-gf).
  python paginas.py contraste CARPETA
      clips_contraste/: los tramos de LARGO palabras o más en que los aparatos no coinciden, con los dos
      audios lado a lado. Respuestas: «contraste:HH:MM:SS = T|G|TG|X|O  # texto».
  python paginas.py cortes-analisis CARPETA
      Después de un primer limpiar.py: en cada cambio de hablante, dónde corta la base y dónde cortaría el
      cotejo. La gramática decide junto con los dos aparatos; ninguno solo (el cotejo también se atrasa).
  python paginas.py cortes CARPETA
      clips_cortes/: los cortes de «casos_cortes» en limpieza.json. Respuestas: «corte:HH:MM:SS = A|B|C  # nota».
  python paginas.py dudosos CARPETA
      clips_dudosos/: cada [dudoso: …] que quedó en limpia/palabras.json. Respuestas:
      «dudoso:HH:MM:SS = H|O|X  # lo que se oye».

Las carpetas de clips llevan voces reales: no se publican ni salen del equipo. Necesita ffmpeg en el PATH.
"""
import bisect, collections, csv, html, itertools, json, re, subprocess, sys, unicodedata
from pathlib import Path

E = html.escape


def cfg(carpeta):
    D = Path(carpeta).resolve()
    return D, json.loads((D / "limpieza.json").read_text(encoding="utf-8"))


def palabras(ruta):
    return [w for s in json.loads(Path(ruta).read_text(encoding="utf-8"))["segments"]
            for w in s.get("words", []) if w.get("start") is not None]


def norm(x):
    return re.sub(r"[^\wáéíóúüñ]", "", x.lower())


def clave(w):
    t = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def hms(s):
    s = max(0, int(s))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def seg(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def cortar(audio, ini, fin, salida):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, ini):.2f}", "-to", f"{fin:.2f}",
                    "-i", str(audio), "-ac", "1", "-b:a", "64k", str(salida)], check=True, stdin=subprocess.DEVNULL)


def respuestas_voces(D, C):
    letras = C["voces"].get("letras", "ABCDEFGHIJKLMNOP")
    R = {}
    for l in (D / C["voces"]["respuestas"]).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"voz:(SPEAKER_\d\d) = ([{letras}])\b", l.strip())
        if m:
            R[m.group(1)] = f"P{letras.index(m.group(2)) + 1}"
    R[C["moderador"]] = "Mod"
    R["FONDO"] = "Fondo"
    return R


ESTILO = """
:root { --fondo:#fff; --texto:#1a1a1a; --suave:#6E828B; --acento:#0E6B7C; --borde:#d8dee1; --caja:#f4f7f8; --marca:#fbe7c6; }
@media (prefers-color-scheme: dark) { :root { --fondo:#15191b; --texto:#e8ecee; --borde:#344046; --caja:#1e2528; --acento:#4fb3c4; --marca:#5a4520; } }
body { font-family: Corbel, "Trebuchet MS", sans-serif; background:var(--fondo); color:var(--texto); max-width: 980px;
       margin: 0 auto; padding: 16px; line-height: 1.45; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.1rem; margin: 0 0 .3rem; color: var(--acento); }
h3 { font-size: .85rem; margin: 0 0 .3rem; color: var(--suave); text-transform: uppercase; letter-spacing: .04em; }
section { border: 1px solid var(--borde); border-radius: 8px; padding: 14px; margin: 14px 0; }
.dos { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; } @media (max-width: 640px) { .dos { grid-template-columns: 1fr; } }
.dos > div { background: var(--caja); border-radius: 6px; padding: 10px; } audio { width: 100%; }
.opc { display: flex; flex-direction: column; gap: 4px; margin: 10px 0 6px; }
.nota { color: #A5342A; margin: 0 0 .5rem; } .hoy { color: var(--suave); margin: .2rem 0 .6rem; }
mark { background: var(--marca); color: inherit; padding: 0 2px; }
textarea { width: 100%; box-sizing: border-box; font: inherit; background: var(--fondo); color: var(--texto);
           border: 1px solid var(--borde); border-radius: 6px; padding: 6px; }
button { font: inherit; background: var(--acento); color: #fff; border: 0; border-radius: 6px; padding: 10px 18px; cursor: pointer; }
pre { background: var(--caja); padding: 10px; border-radius: 6px; white-space: pre-wrap; }
"""


def pagina(titulo, intro, secciones, clave_resp):
    """secciones: [(ts, html_interior)]. Cada sección lleva radios name=r{n} y un textarea."""
    secs = "".join(f'<section data-ts="{ts}">{h}<textarea rows="2" placeholder="Nota o lo que se oye"></textarea></section>'
                   for ts, h in secciones)
    return f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(titulo)}</title><style>{ESTILO}</style>
<h1>{E(titulo)}</h1><p>{intro}</p><p><strong>Material de trabajo con voces reales: no sale del equipo.</strong></p>
{secs}
<p><button id="copiar">Copiar respuestas</button> <span id="ok"></span></p><pre id="salida"></pre>
<script>
document.getElementById('copiar').onclick = () => {{
  const L = [{json.dumps(titulo)}];
  document.querySelectorAll('section').forEach(s => {{
    const r = s.querySelector('input:checked'); const t = s.querySelector('textarea').value.trim().replace(/\\s+/g, ' ');
    L.push(`{clave_resp}:${{s.dataset.ts}} = ${{r ? r.value : '?'}}` + (t ? `  # ${{t}}` : ''));
  }});
  const txt = L.join('\\n'); document.getElementById('salida').textContent = txt;
  try {{ navigator.clipboard.writeText(txt).then(() => document.getElementById('ok').textContent = 'Copiado'); }} catch (e) {{}}
}};
</script></html>"""


def radios(n, opciones):
    return '<div class="opc">' + "".join(
        f'<label><input type="radio" name="r{n}" value="{v}"> <b>{v}</b>. {E(t)}</label>' for v, t in opciones) + "</div>"


def dos_audios(n, pref, textos=("", "")):
    return ('<div class="dos">' + "".join(
        f'<div><h3>{nom}</h3><audio controls preload="none" src="{pref}{n:02d}_{k}.mp3"></audio>'
        + (f'<p>{E(tx) or "<em>(no registra nada aquí)</em>"}</p>' if tx is not None else "") + "</div>"
        for k, nom, tx in (("B", "Base", textos[0]), ("C", "Cotejo", textos[1]))) + "</div>")


def clips_dos(D, C, ini, fin, carpeta, pref, n):
    d = float(C["desfase"])
    cortar(D / C["base"]["audio"], ini, fin, carpeta / f"{pref}{n:02d}_B.mp3")
    cortar(D / C["cotejo"]["audio"], ini + d, fin + d, carpeta / f"{pref}{n:02d}_C.mp3")


# ---------------------------------------------------------------- pistas
PISTA_RE = re.compile(
    r"\b(yo soy|soy (maestr|docente|profesor|estudiant|ama|comerciante|psic|técnic|madre|mamá)\w*|me dedico|estoy estudiando|"
    r"estudio|estudié|tengo \w+ años|mis hijos|mi hij[oa]|mi esposo|mi esposa|ama de casa|maestr\w*|docente|psicolog\w*|"
    r"medicina|derecho|farmacia|universidad|magisterio|profesorado|negocio|comerci\w*|tienda|emprend\w*|casad[oa]|solter[oa]|"
    r"tranquil[oa]|agradecid[oa]|content[oa]|cansad[oa]|nosotras|cómod[oa]|segur[oa]|yo mism[oa]|en mi caso|donde yo vivo)\b", re.I)


def cmd_pistas_buscar(D, C):
    W = palabras(D / C["base"]["whisperx"])
    R = respuestas_voces(D, C) if (D / C["voces"]["respuestas"]).exists() else {C["moderador"]: "Mod"}
    txt, pos, p = " ".join(w["word"] for w in W), [], 0
    for w in W:
        pos.append(p)
        p += len(w["word"]) + 1
    last = -99
    for m in PISTA_RE.finditer(txt):
        i = bisect.bisect_right(pos, m.start()) - 1
        if W[i]["start"] - last < 4:
            continue
        last = W[i]["start"]
        a, b = max(0, i - 12), min(len(W), i + 16)
        v = collections.Counter(W[k].get("speaker") for k in range(a, b)).most_common(1)[0][0]
        print(f"{hms(W[i]['start'])} {v} ({R.get(v, '?')}) | " + " ".join(W[k]["word"] for k in range(a, b)))


def cmd_pistas(D, C):
    W = palabras(D / C["base"]["whisperx"])
    pal = [norm(w["word"]) for w in W]
    out = []
    for p in C.get("pistas", []):
        frase, antes, despues, texto = p[:4]
        q = [norm(t) for t in frase.split()]
        hits = [k for k in range(len(pal) - len(q) + 1) if pal[k:k + len(q)] == q]
        if len(p) > 4:
            hits = [k for k in hits if k + len(q) < len(pal) and pal[k + len(q)].startswith(p[4])]
        if len(hits) != 1:
            print(f"!! «{frase}»: {len(hits)} apariciones, se omite (alárgala o agrega la palabra siguiente)")
            continue
        ini = W[hits[0]]["start"]
        out.append({"inicio": round(ini - antes, 2), "fin": round(ini + despues, 2), "texto": texto})
        print(f"{hms(ini)}  {texto}")
    (D / "pistas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(out), "pistas en pistas.json")


# ---------------------------------------------------------------- contraste
ALUCINACIONES = ("gracias por su atención", "gracias a todos", "su participación", "gracias por ver", "suscríbete")


def cmd_contraste(D, C):
    largo = C.get("contraste", {}).get("largo", 8)
    tsv = D / C.get("contraste", {}).get("tsv", "contraste.tsv")
    WB, WC = palabras(D / C["base"]["whisperx"]), palabras(D / C["cotejo"]["whisperx"])
    d = float(C["desfase"])

    def ubicar(W, ts, texto):
        p = [norm(x) for x in texto.split() if norm(x)]
        if not p:
            return None
        for i, w in enumerate(W):
            if abs(w["start"] - seg(ts)) <= 6 and [norm(x["word"]) for x in W[i:i + min(3, len(p))]] == p[:3]:
                f = W[min(i + len(p) - 1, len(W) - 1)]
                return w["start"], f.get("end", f["start"])
        return None

    filas = [x for x in csv.reader(open(tsv, encoding="utf-8"), delimiter="\t") if x and not x[0].startswith("#")][1:]
    filas = [x for x in filas if max(len(x[3].split()), len(x[4].split())) >= largo]
    out = D / "clips_contraste"
    out.mkdir(exist_ok=True)
    items, secs = [], []
    for n, (tsb, tsc, _tipo, tb, tc) in enumerate(filas, 1):
        tb, tc = ("" if t == "—" else t for t in (tb, tc))
        rb, rc = ubicar(WB, tsb, tb), ubicar(WC, tsc, tc)
        vt = [r for r in (rb, (rc[0] - d, rc[1] - d) if rc else None) if r]
        ini = min(r[0] for r in vt) if vt else seg(tsb)
        fin = max(r[1] for r in vt) if vt else seg(tsb) + 6
        ini, fin = ini - 3, max(fin, ini + 6) + 3
        clips_dos(D, C, ini, fin, out, "c", n)
        ts = hms(ini + 3)
        nota = "frase típica de alucinación de Whisper" if any(a in (tb + " " + tc).lower() for a in ALUCINACIONES) else ""
        items.append({"n": n, "ts": ts, "tb": tb, "tc": tc, "nota": nota})
        secs.append((ts, f"<h2>{n}. {ts}</h2>" + (f'<p class="nota">{E(nota)}</p>' if nota else "")
                     + dos_audios(n, "c", (tb, tc)) + radios(n, [
                         ("T", "Base"), ("G", "Cotejo"), ("TG", "Los dos (se suman)"), ("X", "Ninguno: inaudible"),
                         ("O", "Otro: escribo lo que se oye")])))
    titulo = f"{C.get('sesion', 'Sesión')} · contraste de aparatos"
    (out / "index.html").write_text(pagina(titulo, f"Son los {len(items)} tramos de {largo} palabras o más en que los dos aparatos "
                                           "no transcribieron lo mismo. Cada clip empieza unos 3 segundos antes. Si ninguno acierta, "
                                           "elige «Otro» y escribe lo que se oye; si no se entiende, «Ninguno».", secs, "contraste"),
                                    encoding="utf-8")
    (out / "contraste.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", out / "index.html", len(items), "tramos")


# ---------------------------------------------------------------- cortes
def cmd_cortes_analisis(D, C):
    P = json.loads((D / "limpia" / "palabras.json").read_text(encoding="utf-8"))
    R = respuestas_voces(D, C)
    lab = lambda s: R.get(s, "?") if s else "·"
    rangos, k = [], 0
    for _, g in itertools.groupby(P, key=lambda x: x["turno"]):
        n = len(list(g))
        rangos.append((k, k + n))
        k += n
    for (a0, a1), (b0, b1) in zip(rangos, rangos[1:]):
        sa, sb = P[a0]["spk"], P[b0]["spk"]
        if sa == sb:
            continue
        lo, hi = max(a0, a1 - 6), min(b1, b0 + 6)
        win = list(range(lo, hi))
        punt = lambda c: sum(1 for i in win if P[i].get("spk_g") == (sa if i < c else sb))
        mejor = max(range(lo, hi + 1), key=lambda c: (punt(c), -abs(c - b0)))
        if mejor == b0:
            continue

        def fmt(i):
            gap = (P[i]["t"] - (P[i - 1].get("fin") or P[i - 1]["t"])) if i and P[i]["t"] and P[i - 1]["t"] else 0
            return f"{'‖' if gap >= 0.5 else ''}{P[i]['w']}[{lab(P[i]['spk'])}/{lab(P[i].get('spk_g'))}]"
        movidas = " ".join(P[i]["w"] for i in range(min(mejor, b0), max(mejor, b0)))
        print(f"{hms(P[b0]['t'] or 0)} {lab(sa)}|{lab(sb)}  el cotejo mueve {abs(mejor - b0)} palabra(s) «{movidas}»")
        print("     " + " ".join(("| " if i == b0 else "") + fmt(i) for i in win))
    print("\n[voz base/voz cotejo] · ‖ = pausa de medio segundo o más · | = corte actual")


def cmd_cortes(D, C):
    out = D / "clips_cortes"
    out.mkdir(exist_ok=True)
    secs = []
    for n, (ts, ini, fin, frase, hoy, opciones) in enumerate(C.get("casos_cortes", []), 1):
        clips_dos(D, C, ini, fin, out, "k", n)
        secs.append((ts, f"<h2>{n}. {ts}</h2><p>{E(frase)}</p><p class='hoy'>Cómo quedó: {E(hoy)}</p>"
                     + dos_audios(n, "k", (None, None)) + radios(n, opciones)))
    titulo = f"{C.get('sesion', 'Sesión')} · cortes entre hablantes"
    (out / "index.html").write_text(pagina(titulo, "Lugares donde no está claro quién dice una frase. Elige la opción que "
                                           "corresponde a lo que se oye; si eliges «Otro», anota el reparto.", secs, "corte"),
                                    encoding="utf-8")
    print("ok", out / "index.html", len(secs), "casos")


# ---------------------------------------------------------------- dudosos
def cmd_dudosos(D, C):
    P = json.loads((D / "limpia" / "palabras.json").read_text(encoding="utf-8"))
    cambios = [l.split("\t") for l in (D / "limpia" / "cambios.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    motivo = {c[5]: c[3] for c in cambios if len(c) > 5 and "[dudoso" in c[5]}
    out = D / "clips_dudosos"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.mp3"):
        f.unlink()
    secs, i, n = [], 0, 0
    while i < len(P):
        if P[i]["w"].startswith("[dudoso:"):
            j = i
            while not re.search(r"\]\W*$", P[j]["w"]):
                j += 1
            marca = " ".join(x["w"] for x in P[i:j + 1])
            ctx = " ".join(x["w"] for x in P[max(0, i - 12):min(len(P), j + 12)])
            n += 1
            t = P[i]["t"]
            clips_dos(D, C, t - 5, t + 7, out, "d", n)
            mot = next((m for k, m in motivo.items() if marca.rstrip(",.") in k), "")
            secs.append((hms(t), f"<h2>{n}. {hms(t)}</h2><p>…{E(ctx).replace(E(marca), f'<mark>{E(marca)}</mark>')}…</p>"
                         f"<p class='hoy'>{E(mot)}</p>" + dos_audios(n, "d", (None, None)) + radios(n, [
                             ("H", "La hipótesis entre corchetes está bien"), ("O", "Se dice otra cosa (escribir abajo)"),
                             ("X", "No se entiende: [inaudible]")])))
            i = j + 1
        else:
            i += 1
    titulo = f"{C.get('sesion', 'Sesión')} · palabras dudosas"
    (out / "index.html").write_text(pagina(titulo, "Lugares donde ningún aparato transcribió algo claro. Lo resaltado es la "
                                           "hipótesis que quedó en la transcripción. Cada clip empieza 5 segundos antes. Si el "
                                           "audio no corresponde al texto, dilo: la base pudo haber puesto mal la hora.", secs, "dudoso"),
                                    encoding="utf-8")
    print("ok", out / "index.html", n, "marcas")


def cmd_para_voces(D, C):
    try:
        import docx
    except ImportError:
        sys.exit("Falta python-docx: python -m pip install python-docx")
    m = json.loads((D / C.get("borrador", "merged.json")).read_text(encoding="utf-8-sig"))
    d = docx.Document()
    d.add_paragraph(f"{C.get('nombre', C.get('sesion', 'Sesión'))} · transcripción para identificar voces (borrador)")
    d.add_paragraph("Perfil de participantes")
    tb = d.add_table(rows=1, cols=3)
    for c, h in zip(tb.rows[0].cells, ("Sexo", "Edad", "Ocupación")):
        c.text = h
    for _, sx, e, o in C["perfiles"]:
        for c, v in zip(tb.add_row().cells, (sx, e, o)):
            c.text = v
    for t in m["turnos"]:
        lab = "MODERADOR" if t["spk"] == C["moderador"] else "R"
        d.add_paragraph(f"{lab}: [{t['ts']}] {t['text'].strip()}")
    sal = D / f"{C.get('nombre', 'sesion')}_para_voces.docx"
    d.save(sal)
    print("ok", sal.name, len(m["turnos"]), "turnos")


CMDS = {"para-voces": cmd_para_voces, "pistas-buscar": cmd_pistas_buscar, "pistas": cmd_pistas, "contraste": cmd_contraste,
        "cortes-analisis": cmd_cortes_analisis, "cortes": cmd_cortes, "dudosos": cmd_dudosos}

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no muestra ‖, «» ni tildes sin esto
    except AttributeError:
        pass
    if len(sys.argv) != 3 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](*cfg(sys.argv[2]))
