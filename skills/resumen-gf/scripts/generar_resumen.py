#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resumen de 10 puntos de un grupo focal, con 2 a 4 citas verificadas por punto.

    python generar_resumen.py puntos.json                 # verifica citas y escribe el .docx
    python generar_resumen.py puntos.json --solo-verificar

puntos.json (ver ../references/formato_puntos.md y ../ejemplo/puntos.json):
  titulo, subtitulo, salida (.docx), fuente (turns_ts.json limpio, merged.json crudo o la
  transcripción .docx con párrafos «Hablante [HH:MM:SS]: texto»),
  estado ("preliminar" si la fuente es merged.json; se fuerza solo), equipo (etiquetas que no se
  citan nunca: Moderador y miembros del equipo), perfiles {etiqueta: "Mujer, 31 años, ..."},
  citas_min / citas_max (opcionales, 2 y 4 por defecto),
  puntos [{titulo, cuerpo, citas: [{texto, hablante, ts}, ...]}], nota_base.

Verificación, antes de escribir nada:
  1. Cada punto trae entre citas_min y citas_max citas.
  2. Cada cita debe estar, literal salvo puntuación y mayúsculas, en la transcripción a partir del
     turno con esa etiqueta y esa marca de tiempo (ventana de 3 minutos, porque la diarización
     parte frases entre turnos). «(…)» separa fragmentos que deben aparecer en orden.
  3. El hablante citado no puede ser del equipo.
  4. Las citas cortas dentro del cuerpo, “así” (…, 00:12:34), se verifican igual, en cualquier
     hablante que no sea del equipo.
Si algo falla, se detiene y no escribe el documento. Las repeticiones (misma cita dos veces,
todas las citas de un punto de la misma persona) salen como aviso.
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path

try:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt, Cm, RGBColor
except ImportError:
    sys.exit("Falta python-docx. Instálalo con:  python -m pip install python-docx")

FUENTE = "Corbel"
NEGRO = RGBColor(0, 0, 0)  # todo el documento va en negro, sin colores de tema
ACENTO = CRITICO = GRIS = NEGRO
VENTANA = 180  # segundos
OMISION = re.compile(r"\s*(?:\(…\)|\(\.\.\.\))\s*")
TS = re.compile(r"^\d\d:\d\d:\d\d$")


def seg(ts):
    h, m, s = (int(x) for x in ts.split(":"))
    return h * 3600 + m * 60 + s


def norm(s):
    s = unicodedata.normalize("NFC", s.lower())
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


TURNO_DOCX = re.compile(r"^\s*(.+?)\s*\[(\d\d:\d\d:\d\d)\]\s*:\s*(.*)$", re.S)


def turnos_docx(fuente):
    """Transcripción .docx con párrafos «Hablante [HH:MM:SS]:  texto». Un párrafo sin marca
    se suma al turno anterior."""
    tt = []
    for p in Document(fuente).paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        m = TURNO_DOCX.match(txt)
        if m:
            tt.append({"label": m.group(1), "ts": m.group(2), "text": m.group(3)})
        elif tt:
            tt[-1]["text"] += " " + txt
    if not tt:
        sys.exit(f"No encontré turnos «Hablante [HH:MM:SS]: texto» en {Path(fuente).name}.")
    return tt


def cargar_turnos(fuente):
    """Devuelve (turnos, crudo). Acepta turns_ts.json (limpia), merged.json (cruda) o .docx."""
    if Path(fuente).suffix.lower() == ".docx":
        tt = turnos_docx(fuente)
        for t in tt:
            t["_s"] = seg(t["ts"])
        return tt, False
    d = json.loads(Path(fuente).read_text(encoding="utf-8-sig"))
    crudo = isinstance(d, dict) and "turnos" in d
    tt = d["turnos"] if crudo else d
    tt = [t for t in tt if t.get("ts") and not t.get("note")]
    for t in tt:
        t["_s"] = t.get("start", seg(t["ts"]))
    return tt, crudo


def citas_de(p):
    """Lista de citas del punto. Acepta el formato anterior (cita/hablante/ts sueltos)."""
    if "citas" in p:
        return p["citas"]
    if "cita" in p:
        return [{"texto": p["cita"], "hablante": p.get("hablante"), "ts": p.get("ts")}]
    return []


def buscar(cita, tt, ts, hablante=None, excluir=()):
    """Devuelve (ok, motivo, turno_inicial)."""
    if not TS.match(ts or ""):
        return False, f"marca de tiempo inválida «{ts}» (formato HH:MM:SS)", None
    t0 = seg(ts)
    cands = [i for i, t in enumerate(tt)
             if t["ts"] == ts and (hablante is None or t["label"] == hablante)
             and t["label"] not in excluir]
    if not cands:
        cerca = [f"{t['ts']} {t['label']}" for t in tt if abs(t["_s"] - t0) <= 30][:6]
        return False, f"no hay turno de «{hablante or 'participante'}» en {ts}; cerca: {cerca}", None
    frags = [norm(f) for f in OMISION.split(cita) if norm(f)]
    if not frags:
        return False, "la cita está vacía", None
    for i in cands:
        texto = " ".join(norm(t["text"]) for t in tt[i:] if t["_s"] - tt[i]["_s"] <= VENTANA)
        pos, ok = 0, True
        for f in frags:
            j = texto.find(f, pos)
            if j < 0:
                ok = False
                break
            pos = j + len(f)
        if ok:
            return True, "", tt[i]
    return False, f"el texto no aparece literal desde {ts} (ventana {VENTANA} s): «{frags[0][:60]}…»", None


CITA_CUERPO = re.compile(r"“([^”]+)”[^“(]{0,40}\(([^()]*?)(\d\d:\d\d:\d\d)\)")


def verificar(cfg, tt, crudo):
    equipo = set(cfg.get("equipo") or ["Moderador"])
    cmin, cmax = int(cfg.get("citas_min", 2)), int(cfg.get("citas_max", 4))
    perfiles = cfg.get("perfiles") or {}
    errores, avisos = [], []
    puntos = cfg["puntos"]
    if len(puntos) != 10:
        avisos.append(f"hay {len(puntos)} puntos, no 10")
    vistas = {}  # texto normalizado -> punto donde apareció
    total = 0
    for n, p in enumerate(puntos, 1):
        citas = citas_de(p)
        if not cmin <= len(citas) <= cmax:
            errores.append(f"punto {n}: tiene {len(citas)} citas; deben ser de {cmin} a {cmax}")
        hablantes = set()
        for k, c in enumerate(citas, 1):
            total += 1
            donde = f"punto {n}, cita {k}"
            faltan = [x for x in ("texto", "hablante", "ts") if not c.get(x)]
            if faltan:
                errores.append(f"{donde}: falta {', '.join(faltan)}")
                continue
            hablantes.add(c["hablante"])
            if c["hablante"] in equipo:
                errores.append(f"{donde}: «{c['hablante']}» es del equipo y no se cita")
                continue
            clave = norm(c["texto"])
            if clave in vistas:
                avisos.append(f"{donde}: repite una cita ya usada en el punto {vistas[clave]}")
            vistas.setdefault(clave, n)
            ok, motivo, t = buscar(c["texto"], tt, c["ts"], c["hablante"], equipo)
            if not ok:
                errores.append(f"{donde}: {motivo}")
            elif crudo:
                # Solo palabras de contenido (4+ letras) que están en la cita: las funcionales
                # («de», «en», «que») casi siempre salen con baja confianza y no dicen nada.
                enc = set(norm(c["texto"]).split())
                dud = sorted({b["palabra"] for b in t.get("baja_confianza", [])
                              if len(norm(b["palabra"])) >= 4 and norm(b["palabra"]) in enc})
                if dud:
                    avisos.append(f"{donde} ({c['ts']}): palabras con baja confianza, escuchar "
                                  f"antes de citar fuera del equipo: {', '.join(dud)}")
            if c["hablante"] not in perfiles:
                avisos.append(f"{donde}: «{c['hablante']}» sin perfil; se rotula como participante")
        if len(citas) > 1 and len(hablantes) == 1:
            avisos.append(f"punto {n}: todas las citas son de «{next(iter(hablantes))}»; "
                          "si otras personas dijeron lo mismo, conviene sumar otra voz")
        for c, _, ts in CITA_CUERPO.findall(p["cuerpo"]):
            ok, motivo, _ = buscar(c, tt, ts, None, equipo)
            if not ok:
                errores.append(f"punto {n}, cita en el cuerpo: {motivo}")
    return errores, avisos, total


def estilos(doc):
    st = doc.styles

    def fija(nombre, size, bold=False, italic=False, color=None, tipo=WD_STYLE_TYPE.PARAGRAPH,
             before=0, after=6, indent=None, base="Normal"):
        try:
            s = st[nombre]
        except KeyError:
            s = st.add_style(nombre, tipo)
            s.base_style = st[base]
        f = s.font
        f.name, f.size, f.bold, f.italic = FUENTE, Pt(size), bold, italic
        rpr = s.element.get_or_add_rPr()
        for col in rpr.findall(qn("w:color")):  # quita colores de tema (themeColor)
            rpr.remove(col)
        f.color.rgb = color if color is not None else NEGRO
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = rpr.makeelement(qn("w:rFonts"), {})
            rpr.append(rf)
        for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(k), FUENTE)
        for k in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            rf.attrib.pop(qn(k), None)
        for sp in rpr.findall(qn("w:spacing")):  # Subtitle trae espaciado entre letras
            rpr.remove(sp)
        pf = s.paragraph_format
        pf.space_before, pf.space_after = Pt(before), Pt(after)
        if indent is not None:
            pf.left_indent = Cm(indent)
        return s

    # Valores por defecto del documento: Corbel y negro también fuera de los estilos.
    rpr_def = doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
    rf = rpr_def.get_or_add_rFonts()
    for k in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        rf.attrib.pop(qn(k), None)
    for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(k), FUENTE)
    rpr_def._remove_color()
    rpr_def._add_color().val = NEGRO

    # Tema: fuentes del tema en Corbel y colores de texto y acento en negro, para que cualquier
    # estilo que alguien aplique después al editar el Word tampoco cambie de fuente ni de color.
    for part in doc.part.package.iter_parts():
        if str(part.partname).startswith("/word/theme/"):
            x = part.blob.decode("utf-8")
            x = re.sub(r'(<a:(?:major|minor)Font>\s*<a:latin typeface=")[^"]*"', rf'\g<1>{FUENTE}"', x)
            x = re.sub(r'(<a:(?:dk2|accent\d|hlink|folHlink)>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}"',
                       r'\g<1>000000"', x)
            part._blob = x.encode("utf-8")

    fija("Normal", 11)
    fija("Title", 16, bold=True, color=ACENTO, after=4)
    fija("Subtitle", 10, italic=True, color=GRIS, after=14)
    fija("Heading 1", 12, bold=True, color=ACENTO, before=10, after=4)
    fija("Heading 2", 12, bold=True, color=ACENTO, before=16, after=4)
    fija("Quote", 11, italic=True, after=2, indent=0.8)
    fija("Atribución", 9, color=GRIS, after=8, indent=0.8)
    fija("Aviso", 10, bold=True, color=CRITICO, after=10)
    for s in ("Title", "Heading 1", "Heading 2"):  # sin bordes ni espaciado de tema
        pPr = st[s].element.get_or_add_pPr()
        for b in pPr.findall(qn("w:pBdr")):
            pPr.remove(b)


def escribir(cfg, crudo):
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = s.left_margin = s.right_margin = Cm(2)
    estilos(doc)
    perfiles = cfg.get("perfiles") or {}

    doc.add_paragraph(cfg["titulo"], style="Title")
    doc.add_paragraph(cfg["subtitulo"], style="Subtitle")
    if crudo:
        doc.add_paragraph(
            "RESUMEN PRELIMINAR. Sale de la transcripción automática, antes de la limpieza: las "
            "citas son literales de esa versión, pueden traer errores del reconocimiento de voz y "
            "la atribución de hablantes no está revisada. Sirve para tener una idea general del "
            "grupo; no se cita fuera del equipo sin cotejar cada cita contra el audio.",
            style="Aviso")

    for n, p in enumerate(cfg["puntos"], 1):
        h = doc.add_paragraph(f"{n}. {p['titulo']}", style="Heading 1")
        h.paragraph_format.keep_with_next = True
        c = doc.add_paragraph(p["cuerpo"])
        c.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for cita in citas_de(p):
            q = doc.add_paragraph(f"“{cita['texto']}”", style="Quote")
            q.paragraph_format.keep_with_next = True  # la cita no se separa de su atribución
            quien = perfiles.get(cita["hablante"]) or \
                f"Participante ({cita['hablante']} en la transcripción)"
            doc.add_paragraph(f"{quien}, {cita['ts']}", style="Atribución")

    doc.add_paragraph("Nota sobre la base", style="Heading 2")
    nb = doc.add_paragraph(cfg["nota_base"])
    nb.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for r in nb.runs:
        r.font.size = Pt(10)
    out = Path(cfg["salida"])
    out.parent.mkdir(parents=True, exist_ok=True)
    destino = str(out)
    if sys.platform == "win32" and len(str(out.resolve())) >= 250:
        destino = "\\\\?\\" + str(out.resolve())  # rutas de más de 260 caracteres en Windows
    doc.save(destino)
    return out


def main():
    ap = argparse.ArgumentParser(description="Resumen de 10 puntos de un grupo focal.")
    ap.add_argument("puntos")
    ap.add_argument("--solo-verificar", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    base = Path(a.puntos).resolve().parent
    cfg = json.loads(Path(a.puntos).read_text(encoding="utf-8-sig"))
    for k in ("fuente", "salida"):
        if not Path(cfg[k]).is_absolute():
            cfg[k] = str(base / cfg[k])
    tt, crudo = cargar_turnos(cfg["fuente"])
    if cfg.get("estado") == "revisado" and crudo:
        print("Aviso: la fuente es merged.json (cruda); el resumen sale como PRELIMINAR.")
    errores, avisos, total = verificar(cfg, tt, crudo)
    crudo = crudo or cfg.get("estado") == "preliminar"
    for x in avisos:
        print("AVISO:", x)
    for x in errores:
        print("ERROR:", x)
    if errores:
        sys.exit(f"{len(errores)} errores: no se escribió el documento.")
    print(f"Citas verificadas: {total} en {len(cfg['puntos'])} puntos, contra "
          f"{Path(cfg['fuente']).name} ({'cruda, preliminar' if crudo else 'limpia'}).")
    if not a.solo_verificar:
        print("OK ->", escribir(cfg, crudo))


if __name__ == "__main__":
    main()
