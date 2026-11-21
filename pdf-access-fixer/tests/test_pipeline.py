"""The README's claims, tested on scans these tests draw themselves (no third-party PDF is used).

OCR tests need Tesseract (on PATH, or at its default Windows path); they are skipped without it. The PDF/UA-1 test needs
veraPDF: run `python tests/run.py --verapdf <launcher>` (or `--verapdf-home <folder> --java <java>`); it is skipped
otherwise. tests/run.py prints how many tests were skipped.
"""
import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw, ImageFont

from pdf_access_fixer import analyze, apply, cli, ocr

VERAPDF = {}          # filled by tests/run.py: launcher, or home + java


def tesseract():
    try:
        return ocr.tesseract_path()
    except ocr.OcrUnavailable:
        return None


needs_tesseract = unittest.skipUnless(tesseract(), "Tesseract is not installed")

LINES = [("Annual Budget Report", 64), ("Parks and Recreation", 40), ("The council approved the budget on Monday.", 32),
         ("Total spending was 4,250 dollars.", 32)]


def draw_scan(path, sideways=False, seal=True, dpi=150):
    """A one-page image-only PDF, US letter: LINES drawn as text, optionally a filled 'seal' at the top right. With
    sideways=True the text is drawn on a landscape sheet and turned a quarter turn onto the portrait page, as a
    landscape table is often scanned."""
    size = (1650, 1275) if sideways else (1275, 1650)
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    y = 150
    for text, fs in LINES:
        d.text((150, y), text, fill=0, font=ImageFont.load_default(size=fs))
        y += int(fs * 2.2)
    if seal:
        d.ellipse([size[0] - 330, 120, size[0] - 150, 300], fill=60)
    if sideways:
        img = img.rotate(90, expand=True)
    img.save(path, "PDF", resolution=dpi)
    return path


def render(path, page=0, dpi=100):
    doc = pdfium.PdfDocument(str(path))
    try:
        return doc[page].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        doc.close()


def changed_share(a, b):
    """Share of pixels whose largest channel moved by more than 32 (check.py's measure)."""
    if a.size != b.size:
        return 1.0
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 32 else 0)
    hist = diff.histogram()
    return hist[255] / (a.size[0] * a.size[1])


def page_text(path, page=0):
    doc = pdfium.PdfDocument(str(path))
    try:
        tp = doc[page].get_textpage()
        return tp.get_text_range()
    finally:
        doc.close()


def char_origins(path, page=0):
    """Sorted (character, x, y) of every non-space character pdfium reads on a page, its origin to 0.01 pt."""
    import pypdfium2.raw as R
    import ctypes
    doc = pdfium.PdfDocument(str(path))
    try:
        tp = doc[page].get_textpage()
        out = []
        for i in range(tp.count_chars()):
            ch = chr(R.FPDFText_GetUnicode(tp.raw, i))
            if ch.isspace():
                continue
            x, y = ctypes.c_double(), ctypes.c_double()
            R.FPDFText_GetCharOrigin(tp.raw, i, ctypes.byref(x), ctypes.byref(y))
            out.append((ch, round(x.value, 2), round(y.value, 2)))
        return sorted(out)
    finally:
        doc.close()


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli.main([str(a) for a in argv])
    return rc, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="paf-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Detection(Base):
    def test_a_page_with_text_is_not_ocrd_and_an_image_only_page_is(self):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        page = pdf.pages[0]
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica)))
        page.Contents = pdf.make_stream(b"BT /F1 12 Tf 72 700 Td (A page that already has its text layer.) Tj ET")
        pdf.save(self.tmp / "digital.pdf")
        self.assertEqual(ocr.pages_needing_ocr(self.tmp / "digital.pdf"), [])
        draw_scan(self.tmp / "scan.pdf")
        self.assertEqual(ocr.pages_needing_ocr(self.tmp / "scan.pdf"), [1])


@needs_tesseract
class Ocr(Base):
    def test_an_upright_scan_gets_its_words_and_looks_the_same(self):
        src = draw_scan(self.tmp / "scan.pdf")
        rep = ocr.ocr_pdf(src, self.tmp / "ocr.pdf", log=lambda m: None)
        self.assertEqual(rep["pages"][0]["rotate"], 0)
        text = page_text(self.tmp / "ocr.pdf")
        for phrase in ("Annual Budget Report", "Parks and Recreation", "4,250"):
            self.assertIn(phrase, text)
        self.assertEqual(changed_share(render(src), render(self.tmp / "ocr.pdf")), 0.0)

    def test_a_one_character_word_is_read(self):
        # pdfium left a lone glyph with an empty outline out of the text (round 17: list bullets, "%" and "0" cells)
        img = Image.new("L", (1275, 1650), 255)
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=40)
        d.text((150, 300), "Total", fill=0, font=font)
        d.text((700, 300), "%", fill=0, font=font)
        d.text((150, 400), "A", fill=0, font=font)
        d.text((700, 400), "1,250", fill=0, font=font)
        img.save(self.tmp / "lone.pdf", "PDF", resolution=150)
        ocr.ocr_pdf(self.tmp / "lone.pdf", self.tmp / "ocr.pdf", log=lambda m: None)
        words = page_text(self.tmp / "ocr.pdf").split()
        self.assertIn("%", words)
        self.assertIn("A", words)

    def test_each_ocr_word_has_flat_bounds_on_its_baseline(self):
        # Round 17: with a full-height box as the OCR font's glyph, the checker's reading of 3 of the 4 reviewed scans
        # changed (words joined: "STATEEQUALIZED", "10)Check"), because each run's bounds now reached into the lines
        # around it. The glyph is a 1-unit dot, so a run's bounds stay flat on its baseline, as in the reviewed output.
        src = draw_scan(self.tmp / "scan.pdf", seal=False)
        ocr.ocr_pdf(src, self.tmp / "ocr.pdf", log=lambda m: None)
        page = pdfium.PdfDocument(str(self.tmp / "ocr.pdf"))[0]
        heights = []
        for obj in page.get_objects():
            if obj.type == pdfium.raw.FPDF_PAGEOBJ_TEXT:
                left, bottom, right, top = obj.get_bounds()
                heights.append(top - bottom)
        self.assertGreater(len(heights), 3)
        self.assertLess(max(heights), 0.5, heights)

    def test_a_sideways_scan_is_read_upright_and_still_looks_the_same(self):
        src = draw_scan(self.tmp / "side.pdf", sideways=True)
        rep = ocr.ocr_pdf(src, self.tmp / "ocr.pdf", log=lambda m: None)
        self.assertIn(rep["pages"][0]["rotate"], (90, 270))
        self.assertTrue(rep["pages"][0]["reframed"])
        self.assertEqual(changed_share(render(src), render(self.tmp / "ocr.pdf")), 0.0)
        with contextlib.redirect_stdout(io.StringIO()):
            analyze.main(str(self.tmp / "ocr.pdf"), str(self.tmp / "an.json"))
        an = json.loads((self.tmp / "an.json").read_text(encoding="utf-8"))
        texts = [s["text"] for s in an["pages"][0]["segments"]]
        self.assertTrue(an["pages"][0]["user_space"])
        self.assertIn("Annual Budget Report", texts)   # whole lines, not one character per segment


# pdf.js 6.5.438 (src/core/evaluator.js, getTextContent) keeps two runs in one text item only if the distance between
# them is at least SPACE_IN_FLOW_MIN_FACTOR and at most SPACE_IN_FLOW_MAX_FACTOR times the font size, and it starts a
# new item at every marked-content operator. SOURCED: pdf.worker.mjs of
# https://github.com/mozilla/pdf.js/releases/download/v6.5.438/pdfjs-6.5.438-dist.zip, read 2026-11-16.
PDFJS_SPACE_IN_FLOW = (0.102, 0.6)


def joined_word_gaps(path):
    """For every OCR word drawn with a trailing space, the gap to the next word's first glyph along the baseline, in
    units of the font size, read from the drawn Tm/Tz/Tf/Tj operators (the OCR stage's own block only)."""
    gaps = []
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            units, cur = [], None
            for o in pikepdf.parse_content_stream(page):
                n = str(o.operator)
                if n == "Tm":
                    cur = {"m": [float(x) for x in o.operands], "gap_after": []}
                    units.append(cur)
                elif cur is not None and n == "Tz":
                    cur["tz"] = float(o.operands[0])
                elif cur is not None and n == "Tf":
                    cur["size"] = float(o.operands[1])
                elif cur is not None and n == "Tj":
                    cur["codes"] = bytes(o.operands[0])
                elif n == "ET":
                    cur = None
            for a, b in zip(units, units[1:]):
                if not a.get("codes", b"").endswith(b"\x00\x20"):
                    continue
                n = len(a["codes"]) // 2
                adv = 0.5 * a["size"] * a["tz"] / 100        # every glyph is 500/1000 em wide
                ux, uy = a["m"][0], a["m"][1]
                along = (b["m"][4] - a["m"][4]) * ux + (b["m"][5] - a["m"][5]) * uy
                gaps.append((along - adv * (n - 1)) / a["size"])
    return gaps


def draw_spaced_scan(path):
    """A one-page scan of typed lines whose words are set apart as in the county scans the screen-reader test read
    (there the median gap was 0.53-0.71 of a word's height; pdf.js split a line at each gap over 0.6)."""
    img = Image.new("L", (1275, 1650), 255)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=36)
    y = 200
    for words in (["Board", "of", "Trustees", "Regular", "Meeting"], ["Minutes", "of", "the", "October", "Session"],
                  ["Motion", "to", "approve", "carried", "unanimously"]):
        x = 150
        for w in words:
            d.text((x, y), w, fill=0, font=font)
            x += d.textlength(w, font=font) + 22
        y += 90
    img.save(path, "PDF", resolution=150)
    return path


def text_runs_per_line(path):
    """{baseline y: number of marked-content sequences its text is drawn in}, for the OCR text of page 1."""
    lines = defaultdict(set)
    with pikepdf.open(path) as pdf:
        mcid, depth_mcid, y = None, [], None
        for o in pikepdf.parse_content_stream(pdf.pages[0]):
            n = str(o.operator)
            if n in ("BDC", "BMC"):
                props = o.operands[1] if n == "BDC" and len(o.operands) > 1 else None
                depth_mcid.append(int(props.MCID) if isinstance(props, pikepdf.Dictionary) and "/MCID" in props else None)
            elif n == "EMC" and depth_mcid:
                depth_mcid.pop()
            elif n == "Tm":
                y = round(float(o.operands[5]), 1)
            elif n == "Tj" and y is not None and bytes(o.operands[0]).strip(b"\x00 "):
                lines[y].add(depth_mcid[-1] if depth_mcid else None)
    return {k: len(v) for k, v in lines.items()}


@needs_tesseract
class ScreenReaderLines(Base):
    """NVDA in pdf.js read a fixed scan one word per line (359 of 369 lines, minutes pages 1-2; helper
    pdf-access-fixer-screen-reader-test, 2026-11-16): pdf.js made each OCR word its own text item. Two causes, each
    pinned here: every word had its own marked-content sequence, and the gaps between words were wider than pdf.js's
    limit for a space inside one item."""

    def test_joined_ocr_words_are_spaced_within_pdfjs_in_flow_space(self):
        src = draw_spaced_scan(self.tmp / "spaced.pdf")
        ocr.ocr_pdf(src, self.tmp / "ocr.pdf", log=lambda m: None)
        gaps = [g for g in joined_word_gaps(self.tmp / "ocr.pdf") if g > 0]
        self.assertGreater(len(gaps), 8, gaps)
        lo, hi = PDFJS_SPACE_IN_FLOW
        self.assertEqual([round(g, 3) for g in gaps if not lo <= g <= hi], [], f"gaps in font sizes: {gaps}")
        self.assertEqual(changed_share(render(src), render(self.tmp / "ocr.pdf")), 0.0)

    def test_the_ocr_text_is_as_tall_as_the_printed_words(self):
        # the larger font size is in text space only: on the page each line's text is as tall as its printed words
        src = draw_spaced_scan(self.tmp / "spaced.pdf")
        ocr.ocr_pdf(src, self.tmp / "ocr.pdf", log=lambda m: None)
        with contextlib.redirect_stdout(io.StringIO()):
            analyze.main(str(self.tmp / "ocr.pdf"), str(self.tmp / "an.json"))
        an = json.loads((self.tmp / "an.json").read_text(encoding="utf-8"))
        em = 36 * 72 / 150                    # the font's size on the page, in points (36 px at 150 dpi)
        heights = [round(s["bbox"][3] - s["bbox"][1], 2) for s in an["pages"][0]["segments"]]
        self.assertEqual(len(heights), 3, heights)
        self.assertTrue(all(0.5 * em <= h <= em for h in heights), (heights, em))

    def test_each_line_of_ocr_text_is_drawn_in_one_marked_sequence(self):
        src = draw_spaced_scan(self.tmp / "spaced.pdf")
        rc, out, err = run_cli("start", src)
        self.assertEqual(rc, 0, err)
        work = self.tmp / "spaced-access"
        an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
        segs = [s["id"] for s in an["pages"][0]["segments"]]
        self.assertEqual(len(segs), 3, [s["text"] for s in an["pages"][0]["segments"]])
        lines = ["title: Board minutes", "lang: en-US", f"H1 {segs[0]}", f"H2 {segs[1]}", f"P {segs[2]}", "DECO p1i0"]
        (work / "plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        out_pdf = work / "spaced-accessible.pdf"
        runs = text_runs_per_line(out_pdf)
        self.assertEqual(len(runs), 3, runs)
        self.assertEqual(sorted(runs.values()), [1, 1, 1], runs)
        self.assertEqual(changed_share(render(src), render(out_pdf)), 0.0)
        summary = json.loads((work / "check.json").read_text(encoding="utf-8"))["summary"]
        self.assertEqual((summary["chars_lost"], summary["unmarked_chars"]), (0, 0))


class MarkedRuns(Base):
    """One owner's text shares a marked sequence only across text positioning, never across text objects."""

    def test_a_marked_sequence_never_spans_two_text_objects(self):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        page = pdf.pages[0]
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
            Encoding=pikepdf.Name.WinAnsiEncoding)))
        # one line drawn in two text objects (187.164 = 72 + the Helvetica width of "Board of Trustees " at 14 pt)
        page.Contents = pdf.make_stream(b"BT /F1 14 Tf 72 700 Td (Board of Trustees ) Tj ET\n"
                                        b"BT /F1 14 Tf 187.164 700 Td (Regular Meeting) Tj ET\n")
        pdf.save(self.tmp / "digital.pdf")
        rc, out, err = run_cli("start", self.tmp / "digital.pdf")
        self.assertEqual(rc, 0, err)
        work = self.tmp / "digital-access"
        an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
        segs = [s["id"] for s in an["pages"][0]["segments"]]
        self.assertEqual([s_["text"] for s_ in an["pages"][0]["segments"]], ["Board of Trustees Regular Meeting"])
        (work / "plan.txt").write_text("title: Board minutes\nlang: en-US\nP " + " ".join(segs) + "\n", encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err + out)
        with pikepdf.open(work / "digital-accessible.pdf") as p:
            names = [str(o.operator) for o in pikepdf.parse_content_stream(p.pages[0])]
        depth, crossed = 0, []
        for n in names:
            if n in ("BDC", "BMC"):
                depth += 1
            elif n == "EMC":
                depth -= 1
            elif n in ("BT", "ET") and depth:
                crossed.append(n)
        self.assertEqual(crossed, [], names)
        self.assertEqual(names.count("BDC"), 2, names)


class Helpers(Base):
    def start(self, **kw):
        src = draw_scan(self.tmp / "report.pdf", **kw)
        rc, out, err = run_cli("start", src)
        self.assertEqual(rc, 0, err)
        work = self.tmp / "report-access"
        an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
        segs = {s["text"]: s["id"] for s in an["pages"][0]["segments"]}
        return src, work, an, segs

    def write_plan(self, work, segs, extra=""):
        sid = {t.split()[0]: i for t, i in segs.items()}
        lines = ["title: Annual Budget Report", "lang: en-US", f"H1 {sid['Annual']}", f"H2 {sid['Parks']}",
                 f"P {sid['The']} {sid['Total']}", "DECO p1i0", extra]
        (work / "plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return sid

    def vera_args(self):
        if VERAPDF.get("launcher"):
            return ["--verapdf", VERAPDF["launcher"]]
        if VERAPDF.get("home"):
            return ["--verapdf-home", VERAPDF["home"], "--java", VERAPDF["java"]]
        return []


@needs_tesseract
class Pipeline(Helpers):
    def test_finish_tags_the_ocr_text_in_plan_order_and_the_page_looks_the_same(self):
        src, work, an, segs = self.start(seal=False)
        self.assertEqual(len(segs), 4, segs)
        self.write_plan(work, segs)
        rc, out, err = run_cli("finish", work, *self.vera_args())
        self.assertEqual(rc, 0, err)
        out_pdf = work / "report-accessible.pdf"
        self.assertEqual(changed_share(render(src), render(out_pdf)), 0.0)
        summary = json.loads((work / "check.json").read_text(encoding="utf-8"))["summary"]
        self.assertEqual((summary["chars_lost"], summary["unmarked_chars"], summary["images_unmarked"]), (0, 0, 0))
        tree = (work / "check.fulltree.txt").read_text(encoding="utf-8")
        order = [tree.index(k) for k in ("H1", "Annual Budget Report", "H2", "Parks and Recreation", "P", "4,250")]
        self.assertEqual(order, sorted(order))
        with pikepdf.open(out_pdf) as p:
            self.assertEqual(str(p.Root.Lang), "en-US")
            self.assertTrue(p.Root.MarkInfo.Marked)
            self.assertEqual(str(p.docinfo["/Title"]), "Annual Budget Report")

    def test_the_ocr_text_is_drawn_in_the_plan_reading_order(self):
        # Viewers that read the page's text in content order rather than by its tags (Chromium's PDF viewer, pdf.js)
        # must get the plan's order too (helper pdf-access-fixer-screen-reader-test, NVDA measurement 2026-11-16).
        src, work, an, segs = self.start(seal=False)
        sid = {t.split()[0]: i for t, i in segs.items()}
        lines = ["title: Annual Budget Report", "lang: en-US", f"H1 {sid['Annual']}", f"P {sid['Total']}",
                 f"P {sid['The']}", f"H2 {sid['Parks']}", "DECO p1i0"]
        (work / "plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        out_pdf = work / "report-accessible.pdf"
        text = page_text(out_pdf)
        order = [text.index(k) for k in ("Annual Budget Report", "4,250", "The council", "Parks and Recreation")]
        self.assertEqual(order, sorted(order), text)
        self.assertEqual(changed_share(render(src), render(out_pdf)), 0.0)

    def test_one_element_read_out_of_drawing_order_keeps_the_plan_order(self):
        # one element's segments share a marked sequence only while the plan reads them in drawing order
        src, work, an, segs = self.start(seal=False)
        sid = {t.split()[0]: i for t, i in segs.items()}
        lines = ["title: Annual Budget Report", "lang: en-US", f"H1 {sid['Annual']}", f"H2 {sid['Parks']}",
                 f"P {sid['Total']} {sid['The']}", "DECO p1i0"]
        (work / "plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        text = page_text(work / "report-accessible.pdf")
        self.assertLess(text.index("4,250"), text.index("The council"), text)

    def test_a_segment_split_between_two_elements_is_drawn_in_the_plan_order(self):
        # 04-report pages 15 and 23 (helper pdf-access-fixer-pdfium-order, 2026-11-16): the plan gave one OCR line's
        # words to two table headers, and the second header's part (a trailing space, then its words) moved with the
        # first header's line, so pdfium (Chrome's viewer) read "STATE EQUALIZED" after "TAXABLE VALUE".
        src = self.tmp / "split.pdf"
        img = Image.new("L", (1275, 1650), 255)
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=36)
        for y, words in ((200, ["Alpha", "Beta"]), (290, ["Gamma", "Delta"])):
            x = 150
            for w in words:
                d.text((x, y), w, fill=0, font=font)
                x += d.textlength(w, font=font) + 22
        img.save(src, "PDF", resolution=150)
        rc, out, err = run_cli("start", src)
        self.assertEqual(rc, 0, err)
        work = self.tmp / "split-access"
        an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
        segs = {s["text"]: s["id"] for s in an["pages"][0]["segments"]}
        self.assertEqual(sorted(segs), ["Alpha Beta", "Gamma Delta"], segs)
        a, g = segs["Alpha Beta"], segs["Gamma Delta"]
        lines = ["title: Split lines", "lang: en-US", f"P {a}[0:5] {g}[0:5]", f"P {a}[5:] {g}[5:]", "DECO p1i0"]
        (work / "plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        out_pdf = work / "split-accessible.pdf"
        self.assertEqual(page_text(out_pdf).split(), ["Alpha", "Gamma", "Beta", "Delta"])
        self.assertEqual(char_origins(out_pdf), char_origins(work / "ocr.pdf"))
        self.assertEqual(changed_share(render(src), render(out_pdf)), 0.0)
        summary = json.loads((work / "check.json").read_text(encoding="utf-8"))["summary"]
        self.assertEqual((summary["chars_lost"], summary["unmarked_chars"]), (0, 0))

    def test_a_text_correction_changes_what_is_read_and_not_how_it_looks(self):
        src, work, an, segs = self.start(seal=False)
        sid = self.write_plan(work, segs, extra="")
        plan = (work / "plan.txt").read_text(encoding="utf-8")
        (work / "plan.txt").write_text(plan + f"TEXT {sid['Total']} | Total spending was 4,250 dollars (corrected).\n",
                                       encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        out_pdf = work / "report-accessible.pdf"
        self.assertIn("4,250 dollars (corrected).", page_text(out_pdf))
        self.assertEqual(changed_share(render(src), render(out_pdf)), 0.0)

    def test_a_region_of_the_scan_becomes_a_figure_with_its_alt_text(self):
        src, work, an, segs = self.start(seal=True)
        # the seal: ellipse at x 1320-1500, y 120-300 px of a 1650 px-high page at 150 dpi -> points from bottom-left
        k = 72 / 150
        box = [1275 * k - 330 * k - 4, (1650 - 300) * k - 4, 1275 * k - 150 * k + 4, (1650 - 120) * k + 4]
        self.write_plan(work, segs, extra="FIG region:1:%s | Grey round seal" % ",".join(f"{v:.1f}" for v in box))
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 0, err)
        out_pdf = work / "report-accessible.pdf"
        self.assertLess(changed_share(render(src), render(out_pdf)), 0.001)
        tree = (work / "check.fulltree.txt").read_text(encoding="utf-8")
        self.assertIn("Figure [alt: Grey round seal]", tree)

    def test_a_plan_that_leaves_a_segment_out_is_refused(self):
        src, work, an, segs = self.start(seal=False)
        sid = self.write_plan(work, segs)
        plan = (work / "plan.txt").read_text(encoding="utf-8").replace(f" {sid['Total']}", "")
        (work / "plan.txt").write_text(plan, encoding="utf-8")
        rc, out, err = run_cli("finish", work)
        self.assertEqual(rc, 1)
        self.assertIn(f"segment {sid['Total']} placed 0 times", err)

    def test_the_draft_plan_marks_the_scan_as_decoration_and_flags_unsure_words(self):
        src, work, an, segs = self.start(seal=True)
        draft = (work / "plan.txt").read_text(encoding="utf-8")
        self.assertRegex(draft, r"(?m)^DECO p1i0  # scanned page image")
        self.assertIn("FIG region:", draft)

    def test_the_output_passes_verapdf_pdf_ua_1(self):
        if not self.vera_args():
            self.skipTest("veraPDF not given (tests/run.py --verapdf ...)")
        src, work, an, segs = self.start(seal=True)
        self.write_plan(work, segs, extra="FIG region:1:500,610,600,710 | Grey round seal")
        rc, out, err = run_cli("finish", work, *self.vera_args())
        self.assertEqual(rc, 0, err)
        self.assertIn("veraPDF PDF/UA-1: passed", out)
        self.assertTrue(json.loads((work / "verapdf.json").read_text(encoding="utf-8"))["compliant"])


@needs_tesseract
class Offline(Helpers):
    def test_start_and_finish_open_no_network_connection(self):
        import socket
        tried = []

        def refuse(*a, **k):
            tried.append(a)
            raise OSError("network cut by the test")
        saved = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
        socket.socket.connect = socket.socket.connect_ex = refuse
        socket.create_connection = socket.getaddrinfo = refuse
        try:
            with self.assertRaises(OSError):          # positive control: the cut is in force
                socket.create_connection(("example.com", 80))
            self.assertEqual(len(tried), 1)
            tried.clear()
            src, work, an, segs = self.start(seal=False)
            self.write_plan(work, segs)
            rc, out, err = run_cli("finish", work)
        finally:
            socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo = saved
        self.assertEqual(rc, 0, err)
        self.assertEqual(tried, [])


class PlanRules(Base):
    def test_text_lines_are_only_for_ocr_text(self):
        an = {"pages": [{"page": 1, "segments": [{"id": "p1s1", "font": "Helvetica", "spans": [[3, 0, 0, 4]],
                                                  "chars": "Word", "text": "Word"}]}]}
        with self.assertRaisesRegex(apply.PlanError, "only text the OCR stage wrote"):
            apply.correct_ocr_text(None, an, {"p1s1": "Ward"})

    def test_a_region_box_maps_back_to_page_space(self):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        page = pdf.pages[0]
        self.assertEqual(apply.to_page_space([10, 20, 30, 40], page, {"user_space": False}), (10, 20, 30, 40))
        page.obj.Rotate = 90
        x0, y0, x1, y1 = apply.to_page_space([10, 20, 30, 40], page, {"user_space": False})
        # pdfminer shows a /Rotate 90 page turned: its (u, v) is page (612 - v, u)
        self.assertEqual((round(x0), round(y0), round(x1), round(y1)), (572, 10, 592, 30))


class OcrReadingOrder(Base):
    """Only the OCR stage's own invisible text is moved into reading order; nothing else on a page ever is."""

    def page(self, body):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        page = pdf.pages[0]
        page.Contents = pdf.make_stream(body.encode("ascii"))
        # the structure reads MCID 1 before MCID 0
        doc = pikepdf.Dictionary(S=pikepdf.Name.Document, K=pikepdf.Array([1, 0]), Pg=page.obj)
        return pdf, page, doc

    def unit(self, font, mcid, x, word):
        return f"1 0 0 1 {x} 700 Tm 100 Tz /{font} 12 Tf /P <</MCID {mcid}>> BDC ({word}) Tj EMC"

    def test_ocr_units_follow_the_structure(self):
        pdf, page, doc = self.page("BT 3 Tr " + self.unit(apply.OCR_FONT, 0, 300, "second") + " "
                                   + self.unit(apply.OCR_FONT, 1, 100, "first") + " ET")
        self.assertEqual(apply.ocr_text_in_reading_order(pdf, doc, pdf.pages), 2)
        drawn = [str(o.operands[0]) for o in pikepdf.parse_content_stream(page) if str(o.operator) == "Tj"]
        self.assertEqual(drawn, ["first", "second"])

    def test_a_marked_sequence_of_several_words_moves_as_one(self):
        # finish draws a line's words in one marked sequence (one pdf.js text item, one screen-reader line)
        two_words = (f"1 0 0 1 300 700 Tm 100 Tz /{apply.OCR_FONT} 12 Tf /P <</MCID 0>> BDC (second) Tj "
                     f"1 0 0 1 340 700 Tm 100 Tz /{apply.OCR_FONT} 12 Tf (half) Tj EMC")
        pdf, page, doc = self.page("BT 3 Tr " + two_words + " " + self.unit(apply.OCR_FONT, 1, 100, "first") + " ET")
        self.assertEqual(apply.ocr_text_in_reading_order(pdf, doc, pdf.pages), 2)
        drawn = [str(o.operands[0]) for o in pikepdf.parse_content_stream(page) if str(o.operator) == "Tj"]
        self.assertEqual(drawn, ["first", "second", "half"])

    def test_a_marked_sequence_drawn_on_from_another_moves_alone_from_where_its_glyphs_are(self):
        # a plan that splits one OCR word op between two elements leaves the second part drawn on from the first, with
        # no Tm of its own (04-report pages 15 and 23). It gets a Tm at the text position the drawn glyphs reached,
        # with the Tz and Tf in force, so it moves to its own place in the reading order and every glyph stays put.
        f = apply.OCR_FONT
        hexs = lambda t: "<" + "".join(f"{ord(c):04X}" for c in t) + ">"
        cases = {   # name: (Tz, the first part's TJ items, its advance in text space: 0.5 em a glyph minus TJ numbers)
            "a plain part": (100, f"{hexs('ALMA')}", 4 * 0.5 * 12),
            "a stretched part with a TJ shift": (50, f"{hexs('AL')} -250 {hexs('MA')}", (4 * 0.5 + 0.25) * 12 * 0.5)}
        for name, (tz, items, adv) in cases.items():
            with self.subTest(name):
                body = (f"BT 3 Tr 1 0 0 1 100 700 Tm {tz} Tz /{f} 12 Tf /TH <</MCID 0>> BDC [{items}] TJ EMC "
                        f"/TH <</MCID 2>> BDC [{hexs(' ')}] TJ 1 0 0 1 140 700 Tm 100 Tz /{f} 12 Tf {hexs('LMA')} Tj EMC "
                        f"1 0 0 1 100 690 Tm 100 Tz /{f} 12 Tf /TH <</MCID 1>> BDC {hexs('29010')} Tj EMC ET")
                pdf, page, _ = self.page(body)
                page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary({"/" + f: ocr.glyphless_font(pdf)}))
                doc = pikepdf.Dictionary(S=pikepdf.Name.Document, K=pikepdf.Array([0, 1, 2]), Pg=page.obj)
                self.assertGreater(apply.ocr_text_in_reading_order(pdf, doc, pdf.pages), 0)
                ops = list(pikepdf.parse_content_stream(page))
                drawn = []
                for o in ops:
                    if str(o.operator) in ("Tj", "TJ"):
                        items_ = [o.operands[0]] if str(o.operator) == "Tj" else [x for x in o.operands[0]
                                                                                  if isinstance(x, pikepdf.String)]
                        b = b"".join(bytes(x) for x in items_)
                        drawn.append("".join(chr(int.from_bytes(b[k:k + 2], "big")) for k in range(0, len(b), 2)))
                self.assertEqual(drawn, ["ALMA", "29010", " ", "LMA"])
                names = [str(o.operator) for o in ops]
                k = drawn.index(" ")
                show = [i for i, n in enumerate(names) if n in ("Tj", "TJ")][k]
                tm = max(i for i in range(show) if names[i] == "Tm")
                self.assertEqual([round(float(x), 3) for x in ops[tm].operands], [1, 0, 0, 1, round(100 + adv, 3), 700])
                self.assertEqual(names[tm:tm + 3], ["Tm", "Tz", "Tf"])
                self.assertEqual((float(ops[tm + 1].operands[0]), float(ops[tm + 2].operands[1])), (tz, 12))

    def test_no_part_is_cut_when_the_font_does_not_give_every_glyph_one_width(self):
        # the cut computes where the glyphs end from the stage's font (one /DW, no /W); any other widths: no cut
        f = apply.OCR_FONT
        hexs = lambda t: "<" + "".join(f"{ord(c):04X}" for c in t) + ">"
        body = (f"BT 3 Tr 1 0 0 1 100 700 Tm 100 Tz /{f} 12 Tf /TH <</MCID 0>> BDC [{hexs('ALMA')}] TJ EMC "
                f"/TH <</MCID 2>> BDC [{hexs(' ')}] TJ EMC "
                f"1 0 0 1 100 690 Tm 100 Tz /{f} 12 Tf /TH <</MCID 1>> BDC {hexs('29010')} Tj EMC ET")
        pdf, page, _ = self.page(body)
        font = ocr.glyphless_font(pdf)
        font.DescendantFonts[0].W = pikepdf.Array([65, pikepdf.Array([600])])
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary({"/" + f: font}))
        doc = pikepdf.Dictionary(S=pikepdf.Name.Document, K=pikepdf.Array([0, 1, 2]), Pg=page.obj)
        apply.ocr_text_in_reading_order(pdf, doc, pdf.pages)
        names = [str(o.operator) for o in pikepdf.parse_content_stream(page)]
        self.assertEqual(names.count("Tm"), 2, names)

    def test_text_in_another_font_or_with_a_relative_move_is_left_alone(self):
        cases = {"another font": "BT 3 Tr " + self.unit("F1", 0, 300, "b") + " " + self.unit("F1", 1, 100, "a") + " ET",
                 "visible text": "BT " + self.unit(apply.OCR_FONT, 0, 300, "b") + " "
                                 + self.unit(apply.OCR_FONT, 1, 100, "a") + " ET",
                 "a relative move": "BT 3 Tr " + self.unit(apply.OCR_FONT, 0, 300, "b") + " 5 0 Td "
                                    + self.unit(apply.OCR_FONT, 1, 100, "a") + " ET",
                 # a mark around several words moves them as one unit; one still open at the block's end is refused
                 "a mark left open at the end of the block": "BT 3 Tr " + self.unit(apply.OCR_FONT, 0, 300, "b") + " "
                                                             + self.unit(apply.OCR_FONT, 1, 100, "a")
                                                             + " /Span BMC ET EMC",
                 "a state change before the first unit": "BT 3 Tr 2 Tc " + self.unit(apply.OCR_FONT, 0, 300, "b") + " "
                                                         + self.unit(apply.OCR_FONT, 1, 100, "a") + " ET"}
        for name, body in cases.items():
            with self.subTest(name):
                pdf, page, doc = self.page(body)
                before = page.obj.Contents.read_bytes()
                self.assertEqual(apply.ocr_text_in_reading_order(pdf, doc, pdf.pages), 0)
                self.assertEqual(page.obj.Contents.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
