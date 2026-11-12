#!/usr/bin/env python3
"""Contraste entre las dos grabaciones de una misma sesión y borrador para la limpieza.

  python contraste.py contrastar BASE_whisperx.json COTEJO_whisperx.json SALIDA.tsv [--min 3]
      Alinea las palabras de los dos aparatos, mide el desfase de reloj (mediana sobre las palabras que
      coinciden, y por cuartos de la sesión, para ver si deriva) y lista los tramos en que dicen cosas
      distintas, con marca de tiempo en los dos audios. No prueba error en ninguno: dice dónde escuchar.

  python contraste.py borrador CARPETA ID "descripción" [--tsv contraste.tsv] [--largo 8]
      Arma CARPETA/turns_ts.json y CARPETA/cfg.json para build_transcript.py (plugin de transcripción) a
      partir de CARPETA/merged.json: «Hablante 1» pasa a «Moderador» (compruébalo en el primer turno) y cada
      tramo de LARGO palabras o más en que los aparatos no coinciden entra como nota en rojo en su lugar.

La base es el aparato con la sesión completa y una sola línea de tiempo (suele ser el teléfono); el
cotejo es el otro (suele ser la grabadora, con mejor señal pero cortes por límite de archivo).
"""
import difflib, json, re, statistics, sys, unicodedata
from pathlib import Path


def palabras(ruta):
    d = json.load(open(ruta, encoding="utf-8-sig"))
    out = []
    for s in d["segments"]:
        for w in s.get("words", []):
            if "start" not in w:
                continue
            t = unicodedata.normalize("NFD", w["word"].lower())
            t = re.sub(r"[^\w]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))
            if t:
                out.append((t, w["start"], w["word"].strip()))
    return out


def hms(s):
    s = max(0, int(round(s)))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def seg(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def contrastar(base, cot, sal, minimo=3):
    A, B = palabras(base), palabras(cot)
    ops = difflib.SequenceMatcher(None, [a[0] for a in A], [b[0] for b in B], autojunk=False).get_opcodes()
    pares = [(A[i][1], B[j][1] - A[i][1]) for tag, i1, i2, j1, j2 in ops if tag == "equal"
             for i, j in zip(range(i1, i2), range(j1, j2))]
    desfase = statistics.median(d for _, d in pares)
    filas = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal" or max(i2 - i1, j2 - j1) < minimo:
            continue
        ta = A[i1][1] if i1 < len(A) else A[-1][1]
        tb = B[j1][1] if j1 < len(B) else ta + desfase
        filas.append((hms(ta), hms(tb), tag, " ".join(a[2] for a in A[i1:i2]) or "—",
                      " ".join(b[2] for b in B[j1:j2]) or "—"))
    with open(sal, "w", encoding="utf-8") as f:
        f.write(f"# desfase cotejo - base: {desfase:+.2f} s (mediana sobre {len(pares)} palabras coincidentes)\n")
        f.write(f"# palabras base {len(A)}, cotejo {len(B)}; coinciden {len(pares) / len(A):.0%} de la base\n")
        f.write("ts_base\tts_cotejo\ttipo\tbase\tcotejo\n")
        for r in filas:
            f.write("\t".join(r) + "\n")
    print(f"desfase {desfase:+.2f} s | coinciden {len(pares) / len(A):.0%} | tramos distintos (>= {minimo} palabras): {len(filas)}")
    n = len(pares)
    for k in range(4):
        trozo = [d for _, d in pares[k * n // 4:(k + 1) * n // 4]]
        print(f"  cuarto {k + 1} (desde {hms(pares[k * n // 4][0])}): {statistics.median(trozo):+.2f} s")


def borrador(d, sid, desc, tsv="contraste.tsv", largo=8):
    d = Path(d)
    m = json.loads((d / "merged.json").read_text(encoding="utf-8-sig"))
    lineas = (d / tsv).read_text(encoding="utf-8").splitlines()
    desfase = lineas[0].split(":", 1)[1].strip()
    notas = []
    for tb, tg, tipo, base, cot in (l.split("\t") for l in lineas[3:]):
        nb = 0 if base == "—" else len(base.split())
        nc = 0 if cot == "—" else len(cot.split())
        if max(nb, nc) < largo:
            continue
        if tipo == "insert":
            txt = f"El cotejo registra aquí texto que la base no tiene: «{cot}»."
        elif tipo == "delete":
            txt = f"El cotejo no registra este tramo de la base: «{base}»."
        else:
            txt = f"Los aparatos no coinciden. Base: «{base}». Cotejo: «{cot}»."
        notas.append((seg(tb), {"label": f"[Contraste {tb} base / {tg} cotejo]", "ts": None,
                                "text": txt + " Escuchar ambos audios.", "note": True}))
    turns, pend, k = [], [], 0
    tt = m["turnos"]
    for n, t in enumerate(tt):
        lab = "Moderador" if t["label"] == "Hablante 1" else t["label"]
        turns.append({"i": t["i"], "label": lab, "ts": t["ts"], "text": t["text"]})
        fin = seg(tt[n + 1]["ts"]) if n + 1 < len(tt) else 10 ** 9
        while k < len(notas) and notas[k][0] < fin:
            turns.append(notas[k][1])
            k += 1
        if t.get("revisar"):
            r = t["revisar"]
            pend.append(f"{r[0][:8]}: {len(r)} palabra(s) sin hablante asignado en el turno de {lab} "
                        f"[{t['ts']}]; revisar si cambia el hablante (p. ej., el moderador da la palabra).")
    pend = [f"{len(notas)} tramos de {largo} palabras o más en que los aparatos no coinciden, marcados en rojo "
            f"en su lugar. Lista completa en {tsv}."] + pend
    hab = sorted({t["label"] for t in turns if not t.get("note") and t["label"] != "Moderador"},
                 key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 0)
    cfg = {"id": sid, "idioma": "Español", "duracion": m.get("duracion"),
           "hablantes": f"Moderador y {len(hab)} voces separadas automáticamente; sin identificar todavía",
           "estado": "BORRADOR SIN LIMPIEZA: no citar sin revisar contra el audio",
           "criterioEdicion": "Sin limpieza: salida automática del aparato base, con notas de contraste",
           "notas": f"{desc} Dos aparatos grabaron el mismo evento. Desfase: el cotejo va {desfase} respecto "
                    f"de la base (para pasar una marca de la base al cotejo, sumar ese valor). Las voces "
                    f"«Hablante N» son de la separación automática y pueden mezclar o partir personas.",
           "pendientes": pend}
    (d / "turns_ts.json").write_text(json.dumps(turns, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sid}: {len(turns) - len(notas)} turnos, {len(notas)} notas de contraste, {len(pend) - 1} pendientes de hablante")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no muestra ‖, «» ni tildes sin esto
    except AttributeError:
        pass
    a = sys.argv[1:]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    if a[:1] == ["contrastar"] and len(a) >= 4:
        contrastar(a[1], a[2], a[3], opt("--min", 3))
    elif a[:1] == ["borrador"] and len(a) >= 4:
        borrador(a[1], a[2], a[3], opt("--tsv", "contraste.tsv"), opt("--largo", 8))
    else:
        sys.exit(__doc__)
