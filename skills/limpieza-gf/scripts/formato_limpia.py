#!/usr/bin/env python3
"""Transcripción limpia en el formato de las limpias del equipo, a partir de limpia/turns_ts.json.

Uso:  python formato_limpia.py CARPETA_DE_LA_SESION

Lee CARPETA/limpieza.json («nombre», «perfiles») y escribe dos archivos en CARPETA:
  <nombre>_Limpia.docx                     todos los participantes como «R»
  <nombre>_Limpia con participantes.docx   cada turno con su código (P1, P2…) y la tabla con «Código» y «Turnos»

Formato: Arial 11, carta, márgenes de 2.54 cm, texto justificado. Título «Transcripción <nombre>» en negrita
de 14 puntos, «Perfil de participantes» en negrita de 12 y tabla Sexo / Edad / Ocupación con encabezado gris.
Turnos «MODERADOR: [HH:MM:SS] texto» (etiqueta y texto en negrita, marca normal) y «R: [HH:MM:SS] texto»
(etiqueta en negrita). Quien habla y no participa («Voz al fondo») va como «VOZ AL FONDO», en el formato de
«R», para que no se cuente como participante. El resumen-gf lee estos archivos directamente.
"""
import collections, json, sys
from pathlib import Path

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, Inches
except ImportError:
    sys.exit("Falta python-docx: python -m pip install python-docx")

FUENTE = "Arial"
GRIS_ENCABEZADO, GRIS_BORDE = "E7E6E6", "999999"


def fuente_base(d):
    st = d.styles["Normal"]
    st.font.name, st.font.size = FUENTE, Pt(11)
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FUENTE)
    pf = st.paragraph_format
    pf.space_before, pf.space_after = Pt(0), Pt(0)
    pf.line_spacing = 1.0


def parrafo(d_o_celda, texto="", negrita=False, tam=None, despues=0, linea=None, cursiva=False):
    p = d_o_celda.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(despues)
    if linea:
        p.paragraph_format.line_spacing = linea
    if texto:
        r = p.add_run(texto)
        r.bold, r.italic = negrita, cursiva
        if tam:
            r.font.size = Pt(tam)
    return p


def bordes_tabla(tb):
    tblpr = tb._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "0"), ("w:color", "000000")):
            e.set(qn(k), v)
        b.append(e)
    tblpr.append(b)


def celda(c, texto, ancho, encabezado=False):
    tcpr = c._tc.get_or_add_tcPr()
    w = OxmlElement("w:tcW")
    w.set(qn("w:w"), str(ancho))
    w.set(qn("w:type"), "dxa")
    tcpr.append(w)
    bs = OxmlElement("w:tcBorders")
    for lado in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{lado}")
        for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "0"), ("w:color", GRIS_BORDE)):
            e.set(qn(k), v)
        bs.append(e)
    tcpr.append(bs)
    if encabezado:
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear")
        sh.set(qn("w:fill"), GRIS_ENCABEZADO)
        tcpr.append(sh)
    mar = OxmlElement("w:tcMar")
    for lado, v in (("top", 60), ("left", 100), ("bottom", 60), ("right", 100)):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tcpr.append(mar)
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(texto)
    r.bold = encabezado
    r.font.size = Pt(10)


def armar(D, C, TT, con_codigos):
    d = docx.Document()
    fuente_base(d)
    s = d.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    s.top_margin = s.bottom_margin = s.left_margin = s.right_margin = Cm(2.54)
    nombre = C["nombre"]
    parrafo(d, f"Transcripción {nombre}", negrita=True, tam=14, despues=10)
    parrafo(d, "Perfil de participantes", negrita=True, tam=12, despues=6)
    conteo = collections.Counter(t["label"] for t in TT)
    if con_codigos:
        enc, anchos = ("Código", "Sexo", "Edad", "Ocupación", "Turnos"), (900, 900, 900, 5760, 900)
        filas = [(c, sx, e, o, str(conteo[c])) for c, sx, e, o in C["perfiles"]]
    else:
        enc, anchos = ("Sexo", "Edad", "Ocupación"), (900, 900, 7560)
        filas = [(sx, e, o) for _, sx, e, o in C["perfiles"]]
    tb = d.add_table(rows=1 + len(filas), cols=len(enc))
    bordes_tabla(tb)
    tb.autofit = False
    tblpr = tb._tbl.tblPr
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(sum(anchos)))
    tw.set(qn("w:type"), "dxa")
    tblpr.append(tw)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblpr.append(lay)
    for g, w in zip(tb._tbl.tblGrid.findall(qn("w:gridCol")), anchos):
        g.set(qn("w:w"), str(w))
    for n, (fila, vals) in enumerate(zip(tb.rows, [enc] + filas)):
        for c, v, w in zip(fila.cells, vals, anchos):
            celda(c, v, w, encabezado=(n == 0))
    if con_codigos:
        parrafo(d, f"Códigos P1 a P{len(C['perfiles'])} en el orden de la tabla. " + C.get(
            "nota_participantes", "Quién habla lo identificó el equipo de oído. Los nombres de personas dichos en voz "
            "alta se reemplazaron por [PARTICIPANTE]; se mantienen los de funcionarios públicos."), cursiva=True)
    parrafo(d)
    for t in TT:
        p = parrafo(d, despues=8, linea=1.15)
        es_mod = t["label"] == "Moderador"
        lab = ("MODERADOR" if es_mod else "VOZ AL FONDO" if t["label"] == "Voz al fondo"
               else (t["label"] if con_codigos else "R"))
        p.add_run(f"{lab}: ").bold = True
        if es_mod:
            p.add_run(f"[{t['ts']}] ")
            p.add_run(t["text"]).bold = True
        else:
            p.add_run(f"[{t['ts']}] {t['text']}")
    salida = D / (f"{nombre}_Limpia con participantes.docx" if con_codigos else f"{nombre}_Limpia.docx")
    d.save(salida)
    return salida


def main(carpeta):
    D = Path(carpeta).resolve()
    C = json.loads((D / "limpieza.json").read_text(encoding="utf-8"))
    TT = json.loads((D / "limpia" / "turns_ts.json").read_text(encoding="utf-8"))
    if "perfiles" not in C or "nombre" not in C:
        sys.exit("limpieza.json necesita «nombre» (p. ej. «GF3») y «perfiles»: [[código, sexo, edad, ocupación], …].")
    for cc in (False, True):
        print("OK", armar(D, C, TT, cc).name, len(TT), "turnos")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
