"""OCR stage: give image-only pages a real, invisible text layer, so the tagging stages can treat them like born-digital
pages (segments, headings, lists, tables), while each page looks exactly as it did.

A page needs OCR when pdfium finds fewer than MIN_CHARS non-space characters on it and it draws at least one image.
Such a page is rendered with pdfium (DPI, grey), its orientation read with Tesseract's OSD, and read with Tesseract
(TSV: every word with its box, line and confidence). Each word is then drawn in text render mode 3 (invisible) with a
glyphless font embedded in the file, stretched (Tz) to the word's measured width and placed on its box, turned with the
page when the scan is sideways. Words on one Tesseract line are joined by a space character sized to the gap, except
where the gap is wider than GAP_SPLIT line heights (table columns, a label and its value): there no space is drawn, so
the analysis reads the parts as separate segments.

The font size is SIZE_SCALE times the line height, and the text matrix's upward vector is shortened by the same factor,
so in page space every glyph keeps its position and height. Only the size in text space changes: pdf.js keeps two words
in one text item (one line for a screen reader) only while the gap between them is at most 0.6 font sizes, and scanned
words stand 0.53-0.71 line heights apart (median, four county scans), so at a size of one line height it read a scan
one word per line (helper pdf-access-fixer-screen-reader-test, NVDA 2026.2, 2026-11-16).

The glyphless font (one empty glyph, 500 units wide, every CID mapped to it) is built here with fontTools, so the file
carries no font program from anywhere else. Codes are 2-byte CIDs equal to the character's Unicode value (Basic
Multilingual Plane only; Tesseract's output outside it is replaced by U+FFFD), and a ToUnicode CMap gives each code
its character.
"""
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pypdfium2.raw as R
from pikepdf import Array, Dictionary, Name

MIN_CHARS = 20          # fewer non-space characters than this on a page with an image: the page needs OCR
DPI = 300
GAP_SPLIT = 1.2         # a gap wider than this many line heights ends a segment (no space drawn across it)
# pdf.js 6.5.438 keeps a gap in one text item up to SPACE_IN_FLOW_MAX_FACTOR (0.6) font sizes. SOURCED: pdf.worker.mjs
# of https://github.com/mozilla/pdf.js/releases/download/v6.5.438/pdfjs-6.5.438-dist.zip, read 2026-11-16. DERIVED:
# 1.2 / 0.6 = 2, so every gap a segment joins (up to GAP_SPLIT line heights) stays inside one item.
SIZE_SCALE = GAP_SPLIT / 0.6
MIN_OSD_CONF = 2.0      # Tesseract's orientation confidence below this: keep the page as rendered
UNSURE_CONF = 80        # words read with less confidence than this are listed for a person to check
RETRY_CONF = 70         # a read whose mean word confidence is under this is retried in the other orientations
SURE_SCORE = 40         # ... as is one with fewer characters than this in words read at confidence 60 or more
FONT_NAME = "PAFGlyphless"
WINDOWS_TESSERACT = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")


class OcrUnavailable(RuntimeError):
    pass


def tesseract_path(given=None):
    if given:
        return str(given)
    found = shutil.which("tesseract")
    if found:
        return found
    if WINDOWS_TESSERACT.exists():
        return str(WINDOWS_TESSERACT)
    raise OcrUnavailable("Tesseract is not installed (https://github.com/tesseract-ocr/tesseract); "
                         "install it or pass --tesseract <path>")


def pages_needing_ocr(path):
    """1-based numbers of the pages with fewer than MIN_CHARS non-space characters and at least one image."""
    doc = pdfium.PdfDocument(str(path))
    out = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            text = tp.get_text_range()
            tp.close()
            chars = sum(1 for ch in text if not ch.isspace())
            has_image = any(obj.type == R.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects(max_depth=3))
            if chars < MIN_CHARS and has_image:
                out.append(i + 1)
            page.close()
    finally:
        doc.close()
    return out


def _run(args, timeout=600):
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr.decode("utf-8", "replace").strip() or "tesseract failed")[-400:])
    return proc.stdout.decode("utf-8", "replace")


def orientation(tess, png_path):
    """Degrees to turn the image clockwise so its text is upright (0, 90, 180, 270), from Tesseract's OSD; 0 when OSD
    is unsure or finds too little text."""
    try:
        out = _run([tess, str(png_path), "-", "--psm", "0", "--dpi", str(DPI)])
    except RuntimeError:
        return 0, 0.0
    rot, conf = 0, 0.0
    for line in out.splitlines():
        k, _, v = line.partition(":")
        if k.strip() == "Rotate":
            rot = int(v.strip())
        elif k.strip() == "Orientation confidence":
            conf = float(v.strip())
    return (rot if conf >= MIN_OSD_CONF else 0), conf


def read_words(tess, png_path, lang, psm):
    """Tesseract's words: dicts {text, conf, left, top, width, height, key=(block, par, line)} in reading order."""
    out = _run([tess, str(png_path), "-", "-l", lang, "--psm", str(psm), "--dpi", str(DPI), "tsv"])
    words = []
    for row in out.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        text = c[11].strip()
        if not text or float(c[10]) < 0:
            continue
        words.append({"text": text, "conf": float(c[10]), "left": int(c[6]), "top": int(c[7]), "width": int(c[8]),
                      "height": int(c[9]), "key": (int(c[2]), int(c[3]), int(c[4]))})
    return words


def _turn_matrix(T, box):
    """cm operands taking page space to the frame turned T degrees clockwise, with the box's lower-left at 0, 0."""
    x0, y0, x1, y1 = box
    cw, ch = x1 - x0, y1 - y0
    return {0: [1, 0, 0, 1, -x0, -y0], 90: [0, -1, 1, 0, -y0, cw + x0],
            180: [-1, 0, 0, -1, cw + x0, ch + y0], 270: [0, 1, -1, 0, ch + y0, -x0]}[T]


def upright_frame(pg, rot):
    """(visible box, T, (width, height) upright): T is how far page space must turn clockwise for the text to stand
    upright, counting the page's own /Rotate and the turn `rot` the rendered page needed."""
    box = [float(v) for v in (pg.obj.get("/CropBox") or pg.obj.MediaBox)]
    mb = [float(v) for v in pg.obj.MediaBox]
    box = [max(box[0], mb[0]), max(box[1], mb[1]), min(box[2], mb[2]), min(box[3], mb[3])]
    r0 = int(pg.obj.get("/Rotate", 0)) % 360
    T = (r0 + rot) % 360
    cw, ch = box[2] - box[0], box[3] - box[1]
    return box, T, ((cw, ch) if T in (0, 180) else (ch, cw))


def reframe(pdf, pg, box, T, upright, rot):
    """Give the page an upright page space without changing how it looks: its content is drawn turned T degrees into a
    new MediaBox of the upright size, and /Rotate turns the view back by `rot`, so a viewer shows the page as before.
    Annotation rectangles turn with it; the other page boxes are dropped (the new MediaBox is the old visible box)."""
    m = _turn_matrix(T, box)
    old = pg.obj.Contents.read_bytes()
    head = ("q " + " ".join(f"{v:g}" for v in m) + " cm" + chr(10)).encode()
    pg.obj.Contents = pikepdf.Stream(pdf, head + old + bytes([10]) + b"Q" + bytes([10]))
    pg.obj.MediaBox = Array([0, 0, upright[0], upright[1]])
    for k in ("/CropBox", "/BleedBox", "/TrimBox", "/ArtBox"):
        if k in pg.obj:
            del pg.obj[k]
    pg.obj.Rotate = (360 - rot) % 360
    for annot in pg.obj.get("/Annots", []) or []:
        if "/Rect" in annot:
            r = [float(v) for v in annot.Rect]
            pts = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x in (r[0], r[2]) for y in (r[1], r[3])]
            annot.Rect = Array([min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                                max(p[1] for p in pts)])


def mean_conf(words):
    """Character-weighted mean word confidence (0-100), or None when nothing was read."""
    n = sum(len(w["text"]) for w in words)
    return round(sum(w["conf"] * len(w["text"]) for w in words) / n, 1) if n else None


def _score(words):
    """Characters in words read with confidence 60 or more: how much sure text an orientation gave."""
    return sum(len(w["text"]) for w in words if w["conf"] >= 60)


def _unturn(x, y, rot, w0, h0):
    """A point of the image turned `rot` degrees clockwise, back in the rendered image (w0 x h0 before turning)."""
    if rot == 0:
        return x, y
    if rot == 90:      # turned clockwise: new (x, y) = (h0 - 1 - y0, x0)
        return y, h0 - x
    if rot == 180:
        return w0 - x, h0 - y
    if rot == 270:
        return w0 - y, x
    raise ValueError(rot)


def glyphless_font(pdf):
    """A Type0 font (Identity-H) over an embedded TrueType with one glyph (a 1-unit dot); every CID draws that glyph."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "g1"])
    fb.setupCharacterMap({0x20: "g1"})
    empty = TTGlyphPen(None).glyph()
    # g1 has an outline: pdfium leaves a text object whose only glyph has an empty outline out of the page's text, so a
    # one-character word ("%", "0", a bullet) was not read. Render mode 3 never paints it. The outline is a 1-unit dot
    # at the origin, not a box over the advance: a full-height box made each run's bounds overlap the lines above and
    # below, so a reader that breaks words between lines joined them ("STATEEQUALIZED", round 17's product re-run).
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((0, 1)); pen.lineTo((1, 1)); pen.lineTo((1, 0)); pen.closePath()
    fb.setupGlyf({".notdef": empty, "g1": pen.glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "g1": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": FONT_NAME, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    data = buf.getvalue()
    gidmap = b"\x00\x01" * 65536
    gidmap = b"\x00\x00" + gidmap[2:]            # CID 0 stays .notdef (never drawn)
    descriptor = Dictionary(Type=Name.FontDescriptor, FontName=Name("/" + FONT_NAME), Flags=4,
                            FontBBox=Array([0, -200, 500, 800]), ItalicAngle=0, Ascent=800, Descent=-200,
                            CapHeight=700, StemV=80, FontFile2=pikepdf.Stream(pdf, data))
    cid = Dictionary(Type=Name.Font, Subtype=Name.CIDFontType2, BaseFont=Name("/" + FONT_NAME),
                     CIDSystemInfo=Dictionary(Registry=pikepdf.String("Adobe"), Ordering=pikepdf.String("Identity"),
                                              Supplement=0),
                     FontDescriptor=pdf.make_indirect(descriptor), DW=500,
                     CIDToGIDMap=pikepdf.Stream(pdf, gidmap))
    font = Dictionary(Type=Name.Font, Subtype=Name.Type0, BaseFont=Name("/" + FONT_NAME), Encoding=Name("/Identity-H"),
                      DescendantFonts=Array([pdf.make_indirect(cid)]))
    return pdf.make_indirect(font)


def to_unicode_cmap(codes):
    lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
             "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange"]
    codes = sorted(codes)
    for i in range(0, len(codes), 100):
        chunk = codes[i:i + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        lines += [f"<{c:04X}> <{c:04X}>" for c in chunk]
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(lines).encode("ascii")


def _codes(text):
    return [ord(ch) if ord(ch) <= 0xFFFF and ord(ch) not in (0xFFFE, 0xFFFF) else 0xFFFD for ch in text]


def _hex(codes):
    return "<" + "".join(f"{c:04X}" for c in codes) + ">"


def text_ops(words, rot, size_px, to_page):
    """Content operators (as text) drawing `words` invisibly. `to_page(x, y)` maps a point of the rendered image (pixels)
    to page space; `rot` is the turn that made the words upright. Returns (ops, codes used, segments drawn, the words
    read with confidence under UNSURE_CONF with their boxes in page space)."""
    W0, H0 = size_px
    ops, used, nseg, unsure = [], set(), 0, []
    # group by Tesseract line, keep reading order
    lines, order = {}, []
    for w in words:
        if w["key"] not in lines:
            lines[w["key"]] = []
            order.append(w["key"])
        lines[w["key"]].append(w)
    for key in order:
        ws = sorted(lines[key], key=lambda w: w["left"])
        lh = max(1, sorted(w["height"] for w in ws)[len(ws) // 2])
        # the line's baseline and height: the median bottom and median height of its words (upright image pixels)
        bottom = sorted(w["top"] + w["height"] for w in ws)[len(ws) // 2]
        for i, w in enumerate(ws):
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            gap = (nxt["left"] - (w["left"] + w["width"])) if nxt else None
            join = nxt is not None and gap <= GAP_SPLIT * lh
            text = w["text"] + (" " if join else "")
            width = w["width"] + (gap if join else 0)
            if join and gap <= 0:
                width = w["width"] + max(1, lh // 4)
            x0, x1 = w["left"], w["left"] + width
            # three points in upright pixels: baseline start, baseline end, top of the start
            p0 = to_page(*_unturn(x0, bottom, rot, W0, H0))
            p1 = to_page(*_unturn(x1, bottom, rot, W0, H0))
            pu = to_page(*_unturn(x0, bottom - lh, rot, W0, H0))
            bx, by = p1[0] - p0[0], p1[1] - p0[1]
            ux, uy = pu[0] - p0[0], pu[1] - p0[1]
            blen = (bx * bx + by * by) ** 0.5
            ulen = (ux * ux + uy * uy) ** 0.5
            if blen <= 0 or ulen <= 0:
                continue
            size = ulen * SIZE_SCALE                    # font size in text space; the glyph is ulen tall on the page
            if w["conf"] < UNSURE_CONF:
                xs, ys = [p0[0], p1[0], pu[0]], [p0[1], p1[1], pu[1]]
                unsure.append({"text": w["text"], "conf": round(w["conf"]), "bbox": [round(min(xs), 1), round(min(ys), 1),
                               round(max(xs), 1), round(max(ys), 1)]})
            codes = _codes(text)
            used.update(codes)
            natural = 0.5 * size * len(codes)           # every glyph is 500/1000 em wide
            tz = 100.0 * blen / natural
            a, b, c, d = bx / blen, by / blen, ux / ulen / SIZE_SCALE, uy / ulen / SIZE_SCALE
            ops.append(f"{a:.5f} {b:.5f} {c:.5f} {d:.5f} {p0[0]:.3f} {p0[1]:.3f} Tm {tz:.3f} Tz")
            ops.append(f"/{FONT_NAME} {size:.3f} Tf {_hex(codes)} Tj")
            if not join:
                nseg += 1
    return ops, used, nseg, unsure


def ocr_pdf(src, dst, lang="eng", psm=3, tesseract=None, pages=None, log=print):
    """Write `dst`: `src` with an invisible text layer on each page that needs OCR. Returns a report dict."""
    tess = tesseract_path(tesseract)
    todo = pages_needing_ocr(src) if pages is None else list(pages)
    report = {"pages": [], "dpi": DPI, "lang": lang, "psm": psm, "tesseract": _version(tess)}
    pdf = pikepdf.open(str(src))
    doc = pdfium.PdfDocument(str(src))
    font = None
    used_all = set()
    tounicode = None
    with tempfile.TemporaryDirectory(prefix="paf-ocr-") as tmp:
        for pno in todo:
            page = doc[pno - 1]
            scale = DPI / 72
            img = page.render(scale=scale, grayscale=True).to_pil().convert("L")
            W0, H0 = img.size
            png = Path(tmp) / f"p{pno}.png"
            img.save(png)
            rot, conf = orientation(tess, png)
            tried = {}

            def read_turned(r):
                upng = Path(tmp) / f"p{pno}r{r}.png"
                (img.rotate(-r, expand=True) if r else img).save(upng)
                tried[r] = read_words(tess, upng, lang, psm)
                return tried[r]

            words = read_turned(rot)
            # OSD can miss a sideways page with little text (a cover) or with dense tables: when the read is poor, read
            # it in each other orientation and keep the one with the most confident text.
            if _score(words) < SURE_SCORE or (mean_conf(words) or 0) < RETRY_CONF:
                for r in (0, 90, 180, 270):
                    if r not in tried:
                        read_turned(r)
                best = max(tried, key=lambda r: _score(tried[r]))
                if best != rot:
                    rot, conf, words = best, -1.0, tried[best]

            pg = pdf.pages[pno - 1]
            box, T, upright = upright_frame(pg, rot)
            Hu = upright[1]

            def to_page(x, y, scale=scale, Hu=Hu, box=box, T=T):
                ux, uy = x / scale, Hu - y / scale            # upright frame, points, y up
                return (ux, uy) if T else (ux + box[0], uy + box[1])

            ops, used, nseg, unsure = text_ops(words, 0, (W0, H0), to_page)
            used_all |= used
            entry = {"page": pno, "rotate": rot, "reframed": bool(T), "osd_conf": conf, "orientations_read": sorted(tried), "words": len(words),
                     "segments": nseg, "mean_conf": mean_conf(words), "unsure_words": unsure}
            report["pages"].append(entry)
            log(f"page {pno}: turned {rot}, {len(words)} words, {nseg} segments, confidence {entry['mean_conf']}")
            page.close()
            if not ops:
                continue
            if font is None:
                font = glyphless_font(pdf)
                tounicode = pikepdf.Stream(pdf, b"")
                font.ToUnicode = pdf.make_indirect(tounicode)
            pg.contents_coalesce()
            if T:
                reframe(pdf, pg, box, T, upright, rot)
            res = pg.obj.get("/Resources")
            if res is None:
                pg.obj.Resources = res = Dictionary()
            if "/Font" not in res:
                res.Font = Dictionary()
            res.Font[Name("/" + FONT_NAME)] = font
            old = pg.obj.Contents.read_bytes()
            body = "\n".join(["BT", "3 Tr"] + ops + ["ET"]).encode("ascii")
            pg.obj.Contents = pikepdf.Stream(pdf, b"q\n" + old + b"\nQ\n" + body + b"\n")
    doc.close()
    if font is not None:
        font.ToUnicode.write(to_unicode_cmap(used_all))
    pdf.save(str(dst))
    pdf.close()
    return report


def _version(tess):
    try:
        return _run([tess, "--version"]).splitlines()[0].strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    import sys
    rep = ocr_pdf(sys.argv[1], sys.argv[2], log=lambda m: print(m, file=sys.stderr))
    if len(sys.argv) > 3:
        open(sys.argv[3], "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(rep, ensure_ascii=False))
