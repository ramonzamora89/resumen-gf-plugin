#!/usr/bin/env python3
"""Limpieza de un grupo focal grabado con dos aparatos (base y cotejo), palabra por palabra.

Uso:  python limpiar.py CARPETA_DE_LA_SESION

Lee CARPETA/limpieza.json (formato en references/limpieza_json.md) y aplica, en este orden:

  1. Contraste de aparatos: los tramos de LARGO palabras o más en que los dos aparatos no coinciden, con la
     decisión que el equipo tomó de oído (T = base, G = cotejo, TG = los dos, O = lo que escribió, X = inaudible).
  2. Correcciones de oído con tiempo exacto («oido»).
  3. Cortes entre hablantes decididos leyendo («cortes»), frases que el aparato base desordenó («reubicar»),
     cortes decididos de oído («oido_cortes»), intervenciones que ningún aparato transcribió («insertar»).
  4. Reglas: «Gracias, compañera/o» es del moderador; un fragmento de menos de 4 palabras entre dos tramos de la
     misma persona es de esa persona (salvo que el cotejo le dé otra voz); turnos seguidos de la misma persona
     se juntan.
  5. Texto («texto»): palabras mal transcritas, [dudoso: …], nombres; mayúsculas a mitad de frase.

Cada turno del borrador (merged.json) es un tramo seguido de palabras del JSON de WhisperX del aparato base;
el script lo comprueba antes de empezar. Así cada cambio se aplica sobre palabras y los turnos se rearman sin
perder nada. Ningún aparato decide solo: el cotejo también se atrasa en los cortes.

Salida en CARPETA/limpia/: turns_ts.json, cfg.json, cambios.tsv (una fila por decisión, con su motivo) y
palabras.json (cada palabra con la voz que le da cada aparato; la usa paginas.py).
"""
import collections, difflib, itertools, json, re, subprocess, sys, unicodedata
from pathlib import Path

LARGO_DEF = 8       # tramos de contraste que se deciden de oído
MIN_PALABRAS = 4    # un turno más corto no recibe voz automáticamente (igual que voces.py)


def leer_palabras(ruta):
    return [w for s in json.loads(ruta.read_text(encoding="utf-8"))["segments"] for w in s["words"]]


def clave(w):
    t = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def hms(s):
    s = max(0, int(s))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def seg_aprox(ts):
    p = ts.split(":")
    if len(p[2]) == 1:  # «00:39:2» = en los segundos 20 a 29
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2] + "0")
    return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])


def main(carpeta):
    D = Path(carpeta).resolve()
    C = json.loads((D / "limpieza.json").read_text(encoding="utf-8"))
    OUT = D / "limpia"
    OUT.mkdir(exist_ok=True)
    DESFASE = float(C["desfase"])
    MODERADOR = C["moderador"]
    LARGO = C.get("contraste", {}).get("largo", LARGO_DEF)

    M = json.loads((D / C.get("borrador", "merged.json")).read_text(encoding="utf-8-sig"))
    WT = leer_palabras(D / C["base"]["whisperx"])
    WG = leer_palabras(D / C["cotejo"]["whisperx"])

    # ------------------------------------------------------------ palabra -> turno del borrador
    tok, k = [], 0
    for n, t in enumerate(M["turnos"]):
        m = len(t["text"].split())
        if " ".join(x["word"] for x in WT[k:k + m]).strip() != t["text"].strip():
            sys.exit(f"El turno {t.get('i', n)} del borrador no coincide con las palabras del aparato base: "
                     "el borrador tiene que salir del mismo JSON de WhisperX.")
        for x in WT[k:k + m]:
            tok.append({"w": x["word"], "spk": x.get("speaker") or t["spk"], "t": x.get("start"),
                        "fin": x.get("end"), "turno": n})
        k += m
    if k != len(WT):
        sys.exit("El borrador no cubre todas las palabras del aparato base.")

    # ------------------------------------------------------------ alineación de los dos aparatos
    A = [(clave(x["word"]), i) for i, x in enumerate(WT) if "start" in x and clave(x["word"])]
    B = [(clave(x["word"]), j) for j, x in enumerate(WG) if "start" in x and clave(x["word"])]
    ops = difflib.SequenceMatcher(None, [a[0] for a in A], [b[0] for b in B], autojunk=False).get_opcodes()
    cuenta = collections.defaultdict(collections.Counter)  # voz del cotejo -> voz de la base, por mayoría
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                cuenta[WG[B[j][1]].get("speaker")][WT[A[i][1]].get("speaker")] += 1
    VOZ_G = {g: c.most_common(1)[0][0] for g, c in cuenta.items() if g}
    for tag, i1, i2, j1, j2 in ops:  # segunda opinión sobre la voz de cada palabra
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                tok[A[i][1]]["spk_g"] = VOZ_G.get(WG[B[j][1]].get("speaker"))
    largos = [o for o in ops if o[0] != "equal" and max(o[2] - o[1], o[4] - o[3]) >= LARGO]

    # ------------------------------------------------------------ 1. contraste: decisiones del equipo
    cambios = []
    con = C.get("contraste", {})
    DEC = []
    if con.get("respuestas"):
        for l in (D / con["respuestas"]).read_text(encoding="utf-8").splitlines():
            mm = re.match(r"contraste:(\d\d:\d\d:\d\d) = (T|G|TG|X|O)\s*(?:#\s*(.*))?$", l.strip())
            if mm:
                DEC.append(mm.groups())
        ajustes = con.get("ajustes", {})  # p. ej. una O que se aplica en «oido» para no perder otra voz
        DEC = [(ts, ajustes.get(ts, d), txt) for ts, d, txt in DEC]
        items = json.loads((D / con.get("pagina", "clips_contraste/contraste.json")).read_text(encoding="utf-8"))
        if not (len(DEC) == len(items) == len(largos)):
            sys.exit(f"Respuestas de contraste: {len(DEC)}; tramos en la página: {len(items)}; tramos ahora: "
                     f"{len(largos)}. Tienen que ser iguales (¿cambió LARGO o la transcripción?).")
        if [d[0] for d in DEC] != [it["ts"] for it in items]:
            sys.exit("Las respuestas de contraste no siguen el orden de la página.")
    quitar, poner = set(), collections.defaultdict(list)
    for (ts, dec, txt), (tag, i1, i2, j1, j2) in zip(DEC, largos):
        ti = [A[i][1] for i in range(i1, i2)]
        gj = [B[j][1] for j in range(j1, j2)]
        ancla = A[i1][1] if i1 < len(A) else len(tok)
        tel = " ".join(WT[i]["word"] for i in ti)
        gra = " ".join(WG[j]["word"] for j in gj)
        if dec == "T":
            cambios.append((ts, "T", "queda el aparato base", tel or "—", "—"))
            continue
        if ti:
            quitar.update(range(ti[0], ti[-1] + 1))
        if dec in ("G", "TG"):
            nuevos = [{"w": WG[j]["word"], "spk": VOZ_G.get(WG[j].get("speaker")), "t": WG[j]["start"] - DESFASE,
                       "turno": None} for j in gj]
            if dec == "TG":
                quitar.difference_update(range(ti[0], ti[-1] + 1) if ti else [])
                ancla = ti[-1] + 1 if ti else ancla
            resultado = (tel + " " + gra).strip() if dec == "TG" else gra
        else:  # O o X
            texto = (txt or "").strip() if dec == "O" else "[inaudible]"
            # si lo escrito empieza antes del tramo (repite las últimas palabras de la base), también salen
            if dec == "O" and ti:
                escritas = [clave(p) for p in texto.split()]
                antes = [i for i in range(ti[0] - 1, max(-1, ti[0] - 9), -1)
                         if tok[i]["turno"] == tok[ti[0]]["turno"]][::-1]
                for kk in range(min(len(antes), len(escritas)), 0, -1):
                    a = " ".join(clave(tok[i]["w"]) for i in antes[-kk:])
                    if difflib.SequenceMatcher(None, a, " ".join(escritas[:kk])).ratio() >= 0.75:
                        ti = antes[-kk:] + ti
                        quitar.update(antes[-kk:])
                        tel = " ".join(WT[i]["word"] for i in ti)
                        break
            votos = collections.Counter(tok[i]["spk"] for i in ti) or \
                collections.Counter(VOZ_G.get(WG[j].get("speaker")) for j in gj)
            t0 = WT[ti[0]]["start"] if ti else (WG[gj[0]]["start"] - DESFASE if gj else None)
            nuevos = [{"w": p, "spk": votos.most_common(1)[0][0], "t": t0, "turno": None} for p in texto.split()]
            resultado = texto
        poner[ancla].extend(nuevos)
        cambios.append((ts, dec, {"G": "entra el cotejo", "TG": "se suman", "O": "lo que oyó el equipo",
                                  "X": "inaudible"}[dec], tel or "—", resultado))

    seq = []
    for i, x in enumerate(tok + [None]):
        seq.extend(poner.get(i, []))
        if x is not None and i not in quitar:
            seq.append(x)

    # ------------------------------------------------------------ voces y códigos
    letras = C["voces"].get("letras", "ABCDEFGHIJKLMNOP")
    RESP = {}
    for l in (D / C["voces"]["respuestas"]).read_text(encoding="utf-8").splitlines():
        mm = re.match(rf"voz:(SPEAKER_\d\d) = ([{letras}])\b", l.strip())
        if mm:
            RESP[mm.group(1)] = f"P{letras.index(mm.group(2)) + 1}"
    VOZ = {v: k for k, v in RESP.items()} | {"Mod": MODERADOR, "FONDO": "FONDO", "SINID": "SINID"}
    voz = lambda x: VOZ.get(x, x)  # «P3», «Mod», «FONDO», «SINID» o un SPEAKER_xx directo
    nombre = lambda s: RESP.get(s, "Mod" if s == MODERADOR else s)

    # ------------------------------------------------------------ 2. correcciones de oído con tiempo exacto
    for ini, fin, texto, v, motivo in C.get("oido", []):
        dentro = [i for i, x in enumerate(seq) if x["t"] is not None and ini <= x["t"] <= fin]
        if not dentro:
            sys.exit(f"oido: no hay palabras entre {ini} y {fin} s ({motivo})")
        antes_txt = " ".join(seq[i]["w"] for i in dentro)
        seq[dentro[0]:dentro[-1] + 1] = [{"w": p, "spk": voz(v), "t": seq[dentro[0]]["t"], "turno": None}
                                         for p in texto.split()]
        cambios.append((hms(ini), "oído", motivo, antes_txt, texto))

    def buscar(ts, frase):
        """Ubica la frase cerca de la marca (±90 s). «contexto | frase»: el contexto debe coincidir y no se mueve."""
        ctx = frase.split(" | ")[0].split() if " | " in frase else []
        t0, f = seg_aprox(ts), " ".join(frase.split(" | ")).split()
        hits = [i for i in range(len(seq) - len(f) + 1)
                if [x["w"] for x in seq[i:i + len(f)]] == f and seq[i]["t"] is not None and abs(seq[i]["t"] - t0) <= 90]
        if not hits:
            sys.exit(f"No encontré «{frase}» cerca de {ts}.")
        hits.sort(key=lambda i: abs(seq[i]["t"] - t0))
        if len(hits) > 1 and abs(seq[hits[1]]["t"] - t0) - abs(seq[hits[0]]["t"] - t0) < 2:
            sys.exit(f"«{frase}» aparece varias veces cerca de {ts}: agrega contexto con « | ».")
        return range(hits[0] + len(ctx), hits[0] + len(f))

    def mover(rango, destino, ts, motivo, regla="corte", fijo=False):
        antes = collections.Counter(seq[i]["spk"] for i in rango).most_common(1)[0][0]
        for i in rango:
            seq[i]["fijo"] = seq[i].get("fijo") or fijo
        if all(seq[i]["spk"] == destino for i in rango):
            return
        for i in rango:
            seq[i]["spk"], seq[i]["turno"] = destino, None
        cambios.append((ts, regla, motivo, f"{nombre(antes)}: " + " ".join(seq[i]["w"] for i in rango),
                        f"→ {RESP.get(destino, 'Mod' if destino == MODERADOR else destino)}", "paso 2"))

    # ------------------------------------------------------------ 3. cortes entre hablantes
    for ts, frase, dest, motivo in C.get("cortes", []):
        mover(buscar(ts, frase), voz(dest), ts, motivo)
    for r in C.get("reubicar", []):  # una frase que la base metió en otro lugar: pasa detrás de otra, con hora nueva
        rg = buscar(r["ts"], r["frase"])
        bloque = [seq[i] for i in rg]
        for n, x in enumerate(bloque):
            x["spk"], x["turno"], x["t"] = voz(r["voz"]), None, r["t_nuevo"] + n * 0.5
        del seq[rg.start:rg.stop]
        destino = buscar(r["despues_de"]["ts"], r["despues_de"]["frase"]).stop
        seq[destino:destino] = bloque
        cambios.append((hms(r["t_nuevo"]), "corte", r["motivo"], f"{r['antes']}: " + " ".join(x["w"] for x in bloque),
                        f"→ {r['voz']}", "paso 2"))
    for ts, frase, dest, motivo in C.get("oido_cortes", []):
        mover(buscar(ts, frase), voz(dest), ts, motivo, "oído", fijo=True)
    for r in C.get("insertar", []):  # algo que se oye y ningún aparato transcribió
        k = buscar(r["ts"], r["antes_de"]).start
        seq[k:k] = [{"w": w, "spk": voz(r["voz"]), "t": seq[k]["t"], "turno": None, "fijo": True}
                    for w in r["texto"].split()]
        cambios.append((r.get("ts_cambio", r["ts"]), "oído", r["motivo"], "—", f"{r['voz']}: {r['texto']}", "paso 2"))
    for viejo, nuevo, _motivo in C.get("reemplazar_palabra", []):  # p. ej. un nombre dicho en voz alta
        for x in seq:
            if x["w"] == viejo:
                x["w"] = nuevo

    # 4. reglas
    if C.get("regla_gracias_companera", True):
        pal = [x["w"] for x in seq]
        for i in range(len(seq) - 1):
            if seq[i]["spk"] != MODERADOR and re.fullmatch(r"[Gg]racias,?", pal[i]) and \
                    re.fullmatch(r"compañer[oa]s?[.,]?", pal[i + 1]):
                fin = i + 2
                if fin < len(seq) and re.fullmatch(r"¿[Cc]ompañer[oa]\?", pal[fin]):
                    fin += 1
                mover(range(i, fin), MODERADOR, hms(seq[i]["t"] or 0), "«Gracias, compañera/o» es del moderador", "regla")

    # las palabras nuevas toman el turno vecino si son de la misma voz; si no, abren turno propio
    for i, x in enumerate(seq):
        if x["turno"] is None:
            prev = next((seq[j] for j in range(i - 1, -1, -1) if seq[j]["turno"] is not None), None)
            if prev and prev["spk"] == x["spk"]:
                x["turno"] = prev["turno"]
    for i in range(len(seq) - 1, -1, -1):
        x = seq[i]
        if x["turno"] is None:
            nxt = next((seq[j] for j in range(i + 1, len(seq)) if seq[j]["turno"] is not None
                        and not isinstance(seq[j]["turno"], str)), None)
            x["turno"] = nxt["turno"] if nxt and nxt["spk"] == x["spk"] else f"nuevo-{x['spk']}"
    grupos = [list(g) for _, g in itertools.groupby(range(len(seq)), key=lambda i: seq[i]["turno"])]
    for a, b, c in zip(grupos, grupos[1:], grupos[2:]):
        sa, sb, sc = seq[a[0]]["spk"], seq[b[0]]["spk"], seq[c[0]]["spk"]
        if len(b) < MIN_PALABRAS and sa == sc != sb and sa != "FONDO" and not any(seq[i].get("fijo") for i in b):
            if {seq[i].get("spk_g") for i in b} - {None} <= {sa}:
                for i in b:
                    seq[i]["spk"], seq[i]["turno"] = sa, seq[a[0]]["turno"]
                cambios.append((hms(seq[b[0]]["t"] or 0), "regla", "fragmento entre dos tramos de la misma persona",
                                f"{nombre(sb)}: " + " ".join(seq[i]["w"] for i in b), f"→ {nombre(sa)}", "paso 2"))
    for i in range(1, len(seq)):
        if seq[i]["spk"] == seq[i - 1]["spk"]:
            seq[i]["turno"] = seq[i - 1]["turno"]

    # ------------------------------------------------------------ 5. texto
    for ts, frase, nuevo, motivo in C.get("texto", []):
        r = buscar(ts, frase)
        base = seq[r.start]
        seq[r.start:r.stop] = [dict(base, w=w) for w in nuevo.split()]
        cambios.append((ts, "texto", motivo, frase, nuevo, "paso 4"))
    if C.get("minusculas", True):
        inst = set(C.get("instituciones", []))
        minus = collections.Counter(re.sub(r"[^\wáéíóúñü]", "", x["w"]) for x in seq if x["w"][:1].islower())
        n_may = 0
        for i in range(1, len(seq)):
            w, prev = seq[i]["w"], seq[i - 1]["w"]
            if seq[i]["turno"] != seq[i - 1]["turno"] or re.search(r"[.?!…:\]]\W*$", prev):
                continue
            if i + 1 < len(seq) and re.match(r"[A-ZÁÉÍÓÚÑ]", seq[i + 1]["w"]):
                continue  # nombre propio de varias palabras («El Salvador»)
            m = re.match(r"([¿¡«\"]?)([A-ZÁÉÍÓÚÑ])([a-záéíóúñü]+)(.*)$", w)
            if m and (m.group(2).lower() + m.group(3)) in minus and (m.group(2).lower() + m.group(3)) not in inst:
                seq[i]["w"] = m.group(1) + m.group(2).lower() + m.group(3) + m.group(4)
                n_may += 1
        cambios.append(("—", "texto", f"{n_may} mayúsculas a mitad de frase pasan a minúscula", "—", "—", "paso 4"))

    # ------------------------------------------------------------ turnos y salida
    def etiqueta(palabras):
        v = collections.Counter(p["spk"] for p in palabras).most_common(1)[0][0]
        if v == MODERADOR:
            return "Moderador"
        if v == "FONDO":
            return "Voz al fondo"
        oido = all(p.get("fijo") for p in palabras)
        return RESP.get(v, "R") if len(palabras) >= MIN_PALABRAS or oido else "R"

    turnos = []
    for _, grupo in itertools.groupby(seq, key=lambda x: x["turno"]):
        g = list(grupo)
        t0 = next((p["t"] for p in g if p["t"] is not None), None)
        turnos.append({"i": len(turnos), "label": etiqueta(g), "ts": hms(t0),
                       "text": " ".join(p["w"] for p in g).strip()})
    pend = [f"{t['ts']}: turno corto («{t['text'][:60]}») sin hablante confiable; asignar de oído."
            for t in turnos if t["label"] == "R"]
    n_rev = sum(1 for t in M["turnos"] if t.get("revisar"))
    cambios.append(("—", "revisión", f"{n_rev} tramos sin voz en el borrador: todos asignados y revisados en contexto",
                    "—", "—", "paso 3"))

    cfg_p = D / "cfg.json"
    cfg = json.loads(cfg_p.read_text(encoding="utf-8")) if cfg_p.exists() else {}
    cfg.update(C.get("cfg", {}))
    cfg["pendientes"] = pend
    (OUT / "turns_ts.json").write_text(json.dumps(turnos, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "cambios.tsv", "w", encoding="utf-8") as f:
        f.write("paso\tts\tdecisión\tqué\tantes (base)\tdespués\n")
        for c in cambios:
            paso = c[5] if len(c) > 5 else ("oído" if c[1] == "oído" else "contraste")
            f.write(paso + "\t" + "\t".join(c[:5]) + "\n")
    (OUT / "palabras.json").write_text(json.dumps(
        [{"w": p["w"], "t": p["t"], "fin": p.get("fin"), "spk": p["spk"], "spk_g": p.get("spk_g"),
          "turno": str(p["turno"])} for p in seq], ensure_ascii=False), encoding="utf-8")
    cnt = collections.Counter(t["label"] for t in turnos)
    print(f"{len(turnos)} turnos | {dict(sorted(cnt.items()))} | decisiones: {len(cambios)} | "
          f"pendientes: {len(pend)} | palabras sin voz: {sum(1 for p in seq if p['spk'] is None)}")
    print("voz del cotejo -> voz de la base:", dict(sorted(VOZ_G.items())))
    if C.get("build_transcript"):
        subprocess.run([sys.executable, str(Path(C["build_transcript"]).expanduser()), str(OUT)], check=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no muestra ‖, «» ni tildes sin esto
    except AttributeError:
        pass
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
