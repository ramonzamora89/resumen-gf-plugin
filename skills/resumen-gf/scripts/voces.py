#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Identificar de oído quién habla cuando la transcripción limpia no distingue a los participantes
(todos rotulados igual, por ejemplo «R»). Cinco pasos:

  1. diarizar  Re-separa las voces de la grabación con el número de personas en la sala.
               Se corre con el Python del ambiente de WhisperX (necesita whisperx y HF_TOKEN):
               python voces.py diarizar AUDIO WHISPERX.json SALIDA.json --hablantes 12
  2. alinear   Cruza, por texto, cada turno de la transcripción limpia con las palabras
               diarizadas. Calcula solo el desfase entre la limpia y la grabación.
               python voces.py alinear LIMPIA.docx DIAR.json ALINEACION.json
  3. clips     Corta muestras de cada voz, las citas sin voz de puntos.json y las presentaciones,
               y arma CARPETA/index.html con la tabla de perfiles de la limpia.
               python voces.py clips ALINEACION.json AUDIO CARPETA --limpia LIMPIA.docx
                      [--puntos puntos.json] [--presentaciones pres.json]
  4. revisar   Lee las respuestas copiadas de la página y avisa de perfiles repetidos, de voces
               que hablan antes de que llegue esa persona y lista lo que dice cada persona.
               python voces.py revisar ALINEACION.json RESPUESTAS.txt --limpia LIMPIA.docx
                      [--puntos puntos.json] [--llega LETRA=HH:MM:SS ...]
  5. aplicar   Igual que revisar y, si no hay errores, escribe «voz» y «perfiles» en puntos.json.

Criterio de confianza: un turno tiene voz si sus palabras coinciden con la grabación en al menos
el 60 % (cobertura) y al menos el 90 % de esas palabras las dice una sola voz (pureza).
"""
import argparse, collections, difflib, html, json, re, statistics, subprocess, sys
from pathlib import Path

COB, PUR = 0.6, 0.9
TURNO = re.compile(r"^\s*([^:\[\]]{1,40}?)\s*:\s*\[(\d\d:\d\d:\d\d)\]\s*(.*)$", re.S)
TURNO2 = re.compile(r"^\s*(.+?)\s*\[(\d\d:\d\d:\d\d)\]\s*:\s*(.*)$", re.S)


def seg(ts):
    h, m, s = (int(x) for x in ts.split(":"))
    return h * 3600 + m * 60 + s


def hms(x):
    x = int(round(x))
    return f"{x // 3600:02d}:{x % 3600 // 60:02d}:{x % 60:02d}"


def norm(x):
    return re.sub(r"[^\w ]", " ", x.lower()).split()


def leer_limpia(ruta):
    """Turnos y tabla de perfiles de una transcripción limpia .docx."""
    import docx
    d = docx.Document(ruta)
    tt = []
    for p in d.paragraphs:
        t = p.text.strip()
        m = TURNO.match(t) or TURNO2.match(t)
        if m:
            tt.append({"label": m.group(1), "ts": m.group(2), "text": m.group(3)})
        elif t and tt:
            tt[-1]["text"] += " " + t
    perfiles = []
    for tb in d.tables:
        filas = [[c.text.strip() for c in r.cells] for r in tb.rows]
        enc = [c.lower() for c in filas[0]]
        if not any("edad" in c for c in enc):
            continue
        col = lambda nombre: next((i for i, c in enumerate(enc) if nombre in c), None)
        ic, isx, ied, ioc = col("código"), col("sexo"), col("edad"), col("ocupaci")
        for k, f in enumerate(filas[1:]):
            if not any(f):
                continue
            perfiles.append({
                "letra": (f[ic] if ic is not None and f[ic] else chr(65 + k)).strip(),
                "sexo": f[isx].strip() if isx is not None else "",
                "edad": f[ied].strip() if ied is not None else "",
                "ocupacion": " ".join(f[ioc].split()) if ioc is not None else ""})
        break
    return tt, perfiles


def perfil_texto(p):
    sexo = {"F": "Mujer", "M": "Hombre"}.get(p["sexo"].upper()[:1], p["sexo"])
    edad = f"{p['edad']} años" if p["edad"] and p["edad"].isdigit() else p["edad"]
    oc = p["ocupacion"]
    if len(oc) > 1 and oc[0].isupper() and oc[1].islower():  # «Trabaja en…» -> «trabaja en…»; siglas intactas
        oc = oc[0].lower() + oc[1:]
    return ", ".join(x for x in (sexo, edad, oc) if x)


# ---------------------------------------------------------------- 1. diarizar
def cmd_diarizar(a):
    import os, torch, whisperx
    from whisperx.diarize import DiarizationPipeline
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = DiarizationPipeline(model_name="pyannote/speaker-diarization-community-1",
                               token=os.environ["HF_TOKEN"], device=dev)
    diar = pipe(a.audio, num_speakers=a.hablantes)
    diar = diar[0] if isinstance(diar, tuple) else diar
    res = json.load(open(a.whisperx, encoding="utf-8"))
    res = whisperx.assign_word_speakers(diar, res)
    res["_meta"] = {"num_speakers": a.hablantes, "dispositivo": dev}
    json.dump(res, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False)
    print("ok", a.salida, sorted(diar["speaker"].unique().tolist()))


# ---------------------------------------------------------------- 2. alinear
def palabras_diar(ruta):
    """(inicio, fin, palabra, voz) desde un JSON de WhisperX con palabras y hablantes."""
    d = json.load(open(ruta, encoding="utf-8-sig"))
    W = []
    if "segments" in d:
        for sg in d["segments"]:
            for w in sg.get("words", []):
                if w.get("start") is None:
                    continue
                for tok in norm(w.get("word", "")):
                    W.append((w["start"], w.get("end", w["start"]), tok, w.get("speaker", sg.get("speaker"))))
    else:  # merged.json: solo hay inicio por turno
        for t in d["turnos"]:
            st = t.get("start", seg(t["ts"]))
            for tok in norm(t["text"]):
                W.append((st, st, tok, t["label"]))
    return W


def cmd_alinear(a):
    T, _ = leer_limpia(a.limpia)
    W = palabras_diar(a.diar)
    pal = [w[2] for w in W]
    # desfase global: 5-gramas que aparecen una sola vez en la grabación
    idx = collections.defaultdict(list)
    for k in range(len(pal) - 4):
        idx[tuple(pal[k:k + 5])].append(k)
    difs = []
    for t in T:
        tw = norm(t["text"])
        for k in range(0, max(0, len(tw) - 4), 3):
            hit = idx.get(tuple(tw[k:k + 5]))
            if hit and len(hit) == 1:
                difs.append(seg(t["ts"]) - W[hit[0]][0])
    if not difs:
        sys.exit("No encontré frases comunes entre la limpia y la grabación.")
    off = statistics.median(difs)
    print(f"Desfase limpia - grabación: {off:+.1f} s ({len(difs)} anclas)")
    out = []
    for t in T:
        tw = norm(t["text"])
        r = dict(t, cov=0.0, pure=0.0, voz=None, voces={}, rec=None)
        if len(tw) >= 2:
            t0 = seg(t["ts"]) - off
            ks = [k for k, w in enumerate(W) if abs(w[0] - t0) <= 150]
            if ks:
                lo, hi = ks[0], ks[-1] + 1
                sm = difflib.SequenceMatcher(None, tw, pal[lo:hi], autojunk=False)
                bl = [x for x in sm.get_matching_blocks() if x.size >= 2]
                pos = [lo + k for x in bl for k in range(x.b, x.b + x.size)]
                if pos:
                    vs = collections.Counter(W[k][3] for k in pos)
                    voz, c = vs.most_common(1)[0]
                    r.update(cov=round(len(pos) / len(tw), 2), pure=round(c / len(pos), 2),
                             voz=voz, voces=dict(vs), rec=[W[pos[0]][0], W[pos[-1]][1]])
        out.append(r)
    json.dump({"desfase": off, "turnos": out}, open(a.salida, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    conf = [r for r in out if r["cov"] >= COB and r["pure"] >= PUR and len(norm(r["text"])) >= 8]
    largos = [r for r in out if len(norm(r["text"])) >= 8 and r["label"] == a.participantes]
    cp = [r for r in conf if r["label"] == a.participantes]
    print(f"Turnos largos de participantes con voz confiable: {len(cp)} de {len(largos)}")
    print("Voces de participantes:", dict(collections.Counter(r["voz"] for r in cp)))
    eq = collections.Counter(r["voz"] for r in conf if r["label"] != a.participantes)
    if eq:
        print("Voces en turnos del equipo:", dict(eq))


# ---------------------------------------------------------------- 3. clips
def cortar(audio, carpeta, nombre, tramos):
    tmp = []
    for k, (a, b) in enumerate(tramos):
        f = carpeta / f"_t{k}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, a):.2f}", "-to", f"{b:.2f}",
                        "-i", str(audio), "-ac", "1", "-ar", "22050", str(f)], check=True)
        tmp.append(f)
    sil = carpeta / "_sil.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                    "-t", "1", str(sil)], check=True)
    lista = carpeta / "_lista.txt"
    lineas = []
    for k, f in enumerate(tmp):
        lineas += ([f"file '{sil.name}'"] if k else []) + [f"file '{f.name}'"]
    lista.write_text("\n".join(lineas), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista.name,
                    "-c:a", "libmp3lame", "-q:a", "5", nombre], check=True, cwd=carpeta)
    for f in tmp + [sil, lista]:
        f.unlink()


def cita_turno(turnos, c):
    frag = " ".join(norm(c["texto"].split("(…)")[0]))[:30]
    for i, t in enumerate(turnos):
        if t["ts"] == c["ts"] and t["label"] == c.get("hablante", t["label"]) and frag in " ".join(norm(t["text"])):
            return i
    return None


def cmd_clips(a):
    A = json.load(open(a.alineacion, encoding="utf-8"))
    off, T = A["desfase"], A["turnos"]
    _, perfiles = leer_limpia(a.limpia)
    out = Path(a.carpeta)
    out.mkdir(parents=True, exist_ok=True)
    info = {"presentaciones": [], "voces": [], "citas": [], "perfiles": perfiles}

    def local(i):
        v = [seg(T[j]["ts"]) - T[j]["rec"][0] for j in range(max(0, i - 6), min(len(T), i + 7)) if T[j]["rec"]]
        return statistics.median(v) if v else off

    # presentaciones: cortes a mano (más fiables) o, si no hay, turnos que parecen presentaciones
    if a.presentaciones:
        for k, p in enumerate(json.load(open(a.presentaciones, encoding="utf-8")), 1):
            nombre = f"pres_{k:02d}.mp3"
            cortar(a.audio, out, nombre, [(p["inicio"] - 0.4, p["fin"] + 0.4)])
            info["presentaciones"].append({"clip": nombre, "texto": p["texto"]})
    else:
        pat = re.compile(r"(me llamo|mi nombre es|\bsoy\b).{0,80}\b(\d\d) años", re.I)
        k = 0
        for i, t in enumerate(T):
            if t["label"] == a.participantes and pat.search(t["text"]):
                k += 1
                ini = seg(t["ts"]) - local(i)
                nombre = f"pres_{k:02d}.mp3"
                cortar(a.audio, out, nombre, [(ini - 1, ini + 9)])
                info["presentaciones"].append({"clip": nombre, "texto": re.sub(r"\[[A-ZÁÉÍÓÚ ]+\]", "…", t["text"])[:120],
                                               "aviso": "corte automático: comprobar que suene la persona correcta"})

    por_voz = collections.defaultdict(list)
    etiquetas = collections.defaultdict(collections.Counter)  # voz -> etiquetas de la limpia
    for t in T:
        if t["rec"] and t["cov"] >= COB and t["pure"] >= PUR:
            etiquetas[t["voz"]][t["label"] == a.participantes] += 1
        if t["label"] == a.participantes and t["rec"] and t["cov"] >= COB and t["pure"] >= 0.95 and t["rec"][1] - t["rec"][0] >= 8:
            por_voz[t["voz"]].append(t)
    for voz in list(por_voz):
        c = etiquetas[voz]
        if c[False] > c[True]:
            print(f"{voz} se omite: dice sobre todo turnos del equipo ({c[False]} contra {c[True]})")
            del por_voz[voz]
    for voz in sorted(por_voz):
        ts = sorted(por_voz[voz], key=lambda t: t["rec"][0])
        if len(ts) > 4:
            ts = [ts[round(j * (len(ts) - 1) / 3)] for j in range(4)]
        nombre = f"voz_{voz}.mp3"
        cortar(a.audio, out, nombre, [(t["rec"][0] + 0.3, min(t["rec"][0] + 10.5, t["rec"][1])) for t in ts])
        info["voces"].append({"clip": nombre, "voz": voz, "turnos": len(por_voz[voz]),
                              "muestras": [{"ts": t["ts"], "texto": t["text"][:140]} for t in ts]})

    if a.puntos:
        P = json.load(open(a.puntos, encoding="utf-8"))
        k = 0
        for np_, p in enumerate(P["puntos"], 1):
            for c in p["citas"]:
                i = cita_turno(T, c)
                if i is not None and T[i]["cov"] >= COB and T[i]["pure"] >= PUR:
                    continue
                t = T[i] if i is not None else {"ts": c["ts"], "rec": None}
                ini, fin = (t["rec"] if t["rec"] else (seg(c["ts"]) - (local(i) if i is not None else off),) * 2)
                k += 1
                nombre = f"cita_{k:02d}.mp3"
                cortar(a.audio, out, nombre, [(ini - 0.5, max(ini + 6, min(fin, ini + 20)) + 0.5)])
                info["citas"].append({"clip": nombre, "punto": np_, "ts": c["ts"], "texto": c["texto"]})

    json.dump(info, open(out / "clips.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    (out / "index.html").write_text(pagina(info, a.titulo), encoding="utf-8")
    print(f"ok {out / 'index.html'}: {len(info['presentaciones'])} presentaciones, "
          f"{len(info['voces'])} voces, {len(info['citas'])} citas sin voz")


def pagina(info, titulo):
    e = html.escape
    P = info["perfiles"]
    letras = [p["letra"] for p in P]

    def selector(clave, num=None):
        ops = ['<option value="">— elegir —</option>']
        for p in P:
            t = e(f"{p['letra']} · {p['edad']} años · {p['ocupacion']}")
            ops.append(f'<option value="{e(p["letra"])}" data-t="{t}">{t}</option>')
        ops += ['<option value="MEZCLA">Mezcla: suenan dos o más personas</option>',
                '<option value="EQUIPO">Es del equipo</option>', '<option value="NOSE">No estoy segura</option>']
        tipo = f' data-voz="{num}"' if num else ' data-cita="1"'
        return (f'<select data-k="{e(clave)}"{tipo}>{"".join(ops)}</select>'
                f'<input type="text" data-n="{e(clave)}" placeholder="Nota (opcional)">')

    filas = "".join(f'<tr><td><b>{e(p["letra"])}</b></td><td>{e(p["sexo"])}</td><td>{e(p["edad"])}</td>'
                    f'<td>{e(p["ocupacion"])}</td><td class="asig" data-l="{e(p["letra"])}">—</td></tr>' for p in P)
    pres = "".join(f'<div class="clip"><div class="t">{k}. {e(p["texto"])}'
                   f'{"<br><small>" + e(p["aviso"]) + "</small>" if p.get("aviso") else ""}</div>'
                   f'<audio controls preload="none" src="{p["clip"]}"></audio></div>'
                   for k, p in enumerate(info["presentaciones"], 1)) or "<p>Sin presentaciones.</p>"
    voces = "".join(
        f'<div class="card"><h3>Voz {k}</h3><div class="meta">{len(v["muestras"])} fragmento(s) de unos 10 s, '
        f'de distintos momentos · {v["turnos"]} turno(s) largos</div>'
        f'<audio controls preload="none" src="{v["clip"]}"></audio><ol>'
        + "".join(f'<li><span class="ts">{m["ts"]}</span> {e(m["texto"])}…</li>' for m in v["muestras"])
        + f'</ol>{selector("voz:" + v["voz"], k)}</div>' for k, v in enumerate(info["voces"], 1))
    citas = "".join(
        f'<div class="card"><h3>Cita {k} · punto {c["punto"]} · {c["ts"]}</h3>'
        f'<audio controls preload="none" src="{c["clip"]}"></audio><p class="cita">“{e(c["texto"])}”</p>'
        f'{selector("cita:" + c["ts"])}</div>' for k, c in enumerate(info["citas"], 1)) or "<p>Todas las citas tienen voz.</p>"
    clave_ls = "voces_" + re.sub(r"\W", "_", titulo)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(titulo)}</title><style>
:root{{--fg:#111;--bg:#fff;--mut:#555;--line:#ddd;--acc:#0E6B7C;--card:#f6f7f7}}
@media (prefers-color-scheme:dark){{:root{{--fg:#eee;--bg:#161818;--mut:#aaa;--line:#333;--acc:#5fb3c2;--card:#1f2222}}}}
body{{font-family:Corbel,'Trebuchet MS',sans-serif;color:var(--fg);background:var(--bg);max-width:900px;margin:0 auto;padding:16px;line-height:1.45}}
h2{{border-bottom:2px solid var(--acc);padding-bottom:4px;margin-top:1.6em}} table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left}}
.clip{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:6px 0}}
.clip .t{{flex:1 1 300px}} audio{{max-width:100%;width:340px}} .card{{background:var(--card);border-radius:8px;padding:12px 14px;margin:12px 0}}
.card h3{{margin:0 0 4px}} .meta{{color:var(--mut);font-size:.9em}} li{{margin:3px 0;font-size:.95em}} .ts{{color:var(--mut)}}
select,input{{font:inherit;padding:5px;margin:6px 6px 0 0;max-width:100%}} input{{width:260px}} .cita{{font-style:italic}}
button{{font:inherit;background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer}}
textarea{{width:100%;height:220px;font-family:Consolas,monospace;font-size:.85em;margin-top:8px;background:var(--card);color:var(--fg);border:1px solid var(--line)}}
.aviso{{border-left:4px solid #A5342A;padding:6px 10px;background:var(--card)}}
</style></head><body><h1>{e(titulo)}</h1>
<p class="aviso">Uso interno. Los clips tienen voces y nombres reales; esta carpeta no sale del equipo.</p>
<p><b>Qué hay que hacer:</b> escucha las presentaciones (paso 1) y luego cada voz (paso 2), y elige su perfil.
Cada clip de voz junta fragmentos de distintos momentos: si suenan dos personas, elige «Mezcla». Si eliges un perfil que ya
tiene otra voz, se mueve: la otra queda vacía. Al final pulsa «Copiar respuestas» y pégalas en el chat.</p>
<h2>Perfiles (tabla de la transcripción limpia)</h2>
<table><tr><th></th><th>Sexo</th><th>Edad</th><th>Ocupación</th><th>Asignada a</th></tr>{filas}</table>
<h2>Paso 1. Presentaciones</h2>{pres}<h2>Paso 2. Voces</h2>{voces}
<h2>Paso 3. Citas que no se pudieron ligar a una voz</h2>{citas}
<h2>Respuestas</h2><button id="copiar">Copiar respuestas</button><textarea id="salida" readonly></textarea>
<script>
const K={json.dumps(clave_ls)}, L={json.dumps(letras)};
let g={{}}; try{{g=JSON.parse(localStorage.getItem(K)||'{{}}')}}catch(e){{}}
document.querySelectorAll('[data-k],[data-n]').forEach(el=>{{const k=el.dataset.k||('nota|'+el.dataset.n);
 if(g[k]) el.value=g[k]; el.addEventListener('input',()=>{{
  if(el.dataset.voz&&L.includes(el.value)) document.querySelectorAll('select[data-voz]').forEach(s=>{{
   if(s!==el&&s.value===el.value){{s.value='';g[s.dataset.k]='';av(s,'Se quitó '+el.value+' de esta voz: ahora está en la Voz '+el.dataset.voz+'.')}}}});
  g[k]=el.value;try{{localStorage.setItem(K,JSON.stringify(g))}}catch(e){{}};act();txt();}});}});
function av(s,m){{let a=s.parentNode.querySelector('.movido');if(!a){{a=document.createElement('div');a.className='movido';
 a.style.cssText='color:#A5342A;margin-top:4px';s.parentNode.appendChild(a)}}a.textContent=m}}
function act(){{const a={{}};
 document.querySelectorAll('select[data-voz]').forEach(s=>{{if(L.includes(s.value))(a[s.value]=a[s.value]||[]).push(s.dataset.voz)}});
 document.querySelectorAll('select[data-voz]').forEach(s=>s.querySelectorAll('option[data-t]').forEach(o=>{{
  const ot=(a[o.value]||[]).filter(v=>v!==s.dataset.voz); o.textContent=o.dataset.t+(ot.length?' · ya en Voz '+ot.join(' y ')+' (se moverá aquí)':'');}}));
 document.querySelectorAll('select[data-cita] option[data-t]').forEach(o=>{{const v=a[o.value];o.textContent=o.dataset.t+(v?' · ya en Voz '+v.join(' y '):'')}});
 document.querySelectorAll('td.asig').forEach(td=>{{const v=a[td.dataset.l];td.textContent=v?'Voz '+v.join(' y Voz ')+(v.length>1?' ⚠ repetida':''):'—';td.style.color=v&&v.length>1?'#A5342A':''}});}}
function txt(){{const l=[{json.dumps(titulo)}];document.querySelectorAll('select[data-k]').forEach(s=>{{
 const n=document.querySelector('input[data-n="'+s.dataset.k+'"]');l.push(s.dataset.k+' = '+(s.value||'(sin elegir)')+(n&&n.value?' · nota: '+n.value:''))}});
 document.getElementById('salida').value=l.join('\\n');}}
document.getElementById('copiar').onclick=()=>{{txt();const t=document.getElementById('salida');t.select();
 try{{navigator.clipboard.writeText(t.value)}}catch(e){{document.execCommand('copy')}}}};
act();txt();
</script></body></html>"""


# ---------------------------------------------------------------- 4 y 5. revisar / aplicar
def leer_respuestas(ruta):
    r = {}
    for linea in Path(ruta).read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^\s*((?:voz|cita):[^=]+?)\s*=\s*([^·]+?)\s*(?:·\s*nota:\s*(.*))?$", linea)
        if m and m.group(2) != "(sin elegir)":
            r[m.group(1)] = (m.group(2).strip(), (m.group(3) or "").strip())
    return r


def cmd_revisar(a, aplicar=False):
    A = json.load(open(a.alineacion, encoding="utf-8"))
    T = A["turnos"]
    _, perfiles = leer_limpia(a.limpia)
    por_letra = {p["letra"]: p for p in perfiles}
    R = leer_respuestas(a.respuestas)
    errores, avisos = [], []
    llega = {}
    for x in a.llega or []:
        l, ts = x.split("=")
        llega[l.strip()] = ts.strip()

    voz_a = {k[4:]: v[0] for k, v in R.items() if k.startswith("voz:")}
    cita_a = {k[5:]: v[0] for k, v in R.items() if k.startswith("cita:")}
    for v, l in list(voz_a.items()) + list(cita_a.items()):
        if l not in por_letra and l not in ("MEZCLA", "EQUIPO", "NOSE"):
            errores.append(f"«{l}» no es una fila de la tabla de perfiles")
    rep = collections.defaultdict(list)
    for v, l in voz_a.items():
        if l in por_letra:
            rep[l].append(v)
    for l, vs in rep.items():
        if len(vs) > 1:
            errores.append(f"el perfil {l} está en {len(vs)} voces: {', '.join(vs)}. Una persona no puede tener dos "
                           f"voces salvo que la separación la haya partido; si es así, decirlo en la nota")

    conf = [t for t in T if t["label"] == a.participantes and t["cov"] >= COB and t["pure"] >= PUR and len(norm(t["text"])) >= 4]
    dichos = collections.defaultdict(list)  # letra -> turnos
    for t in conf:
        l = voz_a.get(t["voz"])
        if l in por_letra:
            dichos[l].append(t)
    for ts, l in cita_a.items():
        if l in por_letra:
            dichos[l] += [t for t in T if t["ts"] == ts and t["label"] == a.participantes][:1]
    for l, ts in llega.items():
        antes = [t for t in dichos.get(l, []) if t["ts"] < ts]
        if antes:
            errores.append(f"el perfil {l} llega en {ts}, pero se le asignan turnos anteriores: "
                           + ", ".join(sorted({t["ts"] for t in antes})))
    for l, tt in sorted(dichos.items()):
        print(f"\n== {l} · {perfil_texto(por_letra[l])}")
        for t in sorted(tt, key=lambda t: t["ts"]):
            print(f"   {t['ts']} [{t['voz'] or 'cita'}] {t['text'][:150]}")
    for l in por_letra:
        if l not in dichos:
            avisos.append(f"el perfil {l} no quedó asignado a ninguna voz ni cita")
    print()
    for x in avisos:
        print("AVISO:", x)
    for x in errores:
        print("ERROR:", x)
    print("\nRevisar también, persona por persona, que lo que cuenta sea coherente con su perfil y entre sí "
          "(hijos, con quién vive, dónde vive, a qué se dedica).")
    if not aplicar:
        return
    if errores:
        sys.exit(f"{len(errores)} errores: no se tocó puntos.json.")
    P = json.load(open(a.puntos, encoding="utf-8"))
    perf = {a.participantes: "Participante"}
    n_perf = 0
    for p in P["puntos"]:
        for c in p["citas"]:
            c.pop("voz", None)
            i = cita_turno(T, c)
            l = cita_a.get(c["ts"])
            if l is None and i is not None and T[i]["cov"] >= COB and T[i]["pure"] >= PUR:
                v = T[i]["voz"]
                l = voz_a.get(v)
                if l in ("MEZCLA", "NOSE", None):
                    if l is None:  # voz sin respuesta: sirve para distinguir personas, sin perfil
                        c["voz"] = v
                        perf[v] = "Participante"
                    continue
            if l == "EQUIPO":
                sys.exit(f"La cita de {c['ts']} es del equipo según las respuestas: quítala del resumen.")
            if l in por_letra:
                c["voz"] = "perfil " + l
                perf["perfil " + l] = perfil_texto(por_letra[l])
                n_perf += 1
    P["perfiles"] = perf
    json.dump(P, open(a.puntos, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nOK: {n_perf} citas con perfil escritas en {a.puntos}. Revisar la redacción de los perfiles "
          "(salen tal como vienen en la tabla) antes de generar el resumen.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Identificar de oído quién habla en una transcripción limpia.")
    sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("diarizar"); x.add_argument("audio"); x.add_argument("whisperx"); x.add_argument("salida")
    x.add_argument("--hablantes", type=int, required=True)
    x = sp.add_parser("alinear"); x.add_argument("limpia"); x.add_argument("diar"); x.add_argument("salida")
    x.add_argument("--participantes", default="R", help="etiqueta de los participantes en la limpia")
    x = sp.add_parser("clips"); x.add_argument("alineacion"); x.add_argument("audio"); x.add_argument("carpeta")
    x.add_argument("--limpia", required=True); x.add_argument("--puntos"); x.add_argument("--presentaciones")
    x.add_argument("--titulo", default="Identificación de voces")
    x.add_argument("--participantes", default="R", help="etiqueta de los participantes en la limpia")
    for nombre in ("revisar", "aplicar"):
        x = sp.add_parser(nombre); x.add_argument("alineacion"); x.add_argument("respuestas")
        x.add_argument("--limpia", required=True); x.add_argument("--puntos", required=(nombre == "aplicar"))
        x.add_argument("--llega", nargs="*", help="LETRA=HH:MM:SS (tiempo de la limpia) de quien llegó tarde")
        x.add_argument("--participantes", default="R", help="etiqueta de los participantes en la limpia")
    a = ap.parse_args()
    {"diarizar": cmd_diarizar, "alinear": cmd_alinear, "clips": cmd_clips,
     "revisar": cmd_revisar, "aplicar": lambda a: cmd_revisar(a, True)}[a.cmd](a)


if __name__ == "__main__":
    main()
