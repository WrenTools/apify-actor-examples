"""Round 15, route (a) step 1: read a PDF's pages with pdfminer, recording for every character, image and path which
page-level content-stream operator drew it (op index as pikepdf.parse_content_stream numbers them; a form XObject's
contents count as its 'Do'). Lines are pdfminer text lines (LAParams char_margin 1.0 so table cells split).
Output JSON: pages[{w,h,box,segments[{id,text,bbox,size,bold,font,spans[[op,elem,c0,c1]]}],images[...],paths[...],
forms[...], annots[...], nops, align_ok}], fonts.
Use: venv/Scripts/python -I -X utf8 analyze.py in.pdf out.json
"""
import json, re, sys
from collections import Counter
import pikepdf
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTChar, LTTextLineHorizontal, LTTextLineVertical, LTFigure, LTImage, LTCurve, LTTextContainer
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdffont import PDFCIDFont
from pdfminer.cmapdb import IdentityCMap
from pdfminer.psparser import PSKeyword, PSEOF, keyword_name
from pdfminer.pdfinterp import PDFContentParser
from pdfminer.pdftypes import stream_value
from pdfminer import settings

PATH_PAINT = {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}

class Dev(PDFPageAggregator):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.cur_op = -1; self.cur_elem = 0; self.cur_cid = 0; self.cur_name = ""
        self.paths = []; self.images = []
    def render_string(self, textstate, seq, ncs, gs):
        if self.cur_name not in ("Tj", "TJ", "'", '"'):  # inside a form: keep the Do's index, no element split
            return super().render_string(textstate, seq, ncs, gs)
        for i, el in enumerate(seq):
            self.cur_elem = i; self.cur_cid = 0
            super().render_string(textstate, [el], ncs, gs)
    def render_char(self, matrix, font, fontsize, scaling, rise, cid, ncs, gs):
        adv = super().render_char(matrix, font, fontsize, scaling, rise, cid, ncs, gs)
        it = self.cur_item._objs[-1]
        it.op = self.cur_op; it.elem = self.cur_elem; it.cidx = self.cur_cid; it.cidv = cid
        it.bpc = 1 if not isinstance(font, PDFCIDFont) else (2 if isinstance(font.cmap, IdentityCMap) else 0)
        self.cur_cid += 1
        return adv
    def render_image(self, name, stream):
        super().render_image(name, stream)
        it = self.cur_item._objs[-1]; it.op = self.cur_op
    def paint_path(self, gs, stroke, fill, evenodd, path):
        n0 = len(self.cur_item._objs)
        super().paint_path(gs, stroke, fill, evenodd, path)
        for it in self.cur_item._objs[n0:]:
            it.op = self.cur_op

class Interp(PDFPageInterpreter):
    nested = False
    def subinterp(self):
        s = Interp(self.rsrcmgr, self.device); s.nested = True
        s.parent_stream_ids = self.parent_stream_ids | self.stream_ids
        return s
    def dup(self):
        return self.subinterp()
    def execute(self, streams):
        valid = [stream_value(o) for o in streams]
        try:
            parser = PDFContentParser(valid)
        except PSEOF:
            return
        while True:
            try:
                (_, obj) = parser.nextobject()
            except PSEOF:
                break
            if isinstance(obj, PSKeyword):
                name = keyword_name(obj)
                if not self.nested:
                    self.opi += 1; self.names.append(name)
                    self.device.cur_op = self.opi; self.device.cur_name = name
                method = "do_" + name.replace("*", "_a").replace('"', "_w").replace("'", "_q")
                if hasattr(self, method):
                    func = getattr(self, method)
                    nargs = func.__code__.co_argcount - 1
                    if nargs:
                        args = self.pop(nargs)
                        if len(args) == nargs:
                            try:
                                func(*args)
                            except Exception:
                                pass
                    else:
                        func()
            else:
                self.push(obj)

def bb(o):
    return [round(o.x0, 2), round(o.y0, 2), round(o.x1, 2), round(o.y1, 2)]

def walk(o, out):
    if isinstance(o, (LTTextLineHorizontal, LTTextLineVertical)):
        out["lines"].append(o); return
    if isinstance(o, LTImage):
        out["images"].append(o); return
    if isinstance(o, LTChar):
        out["loose"].append(o); return
    if isinstance(o, LTCurve):
        out["paths"].append(o); return
    if isinstance(o, LTFigure):
        out["figures"].append(o)
    for c in getattr(o, "_objs", []) or []:
        walk(c, out)

def layout(rm, lap, mpage):
    dev = Dev(rm, laparams=lap)
    it = Interp(rm, dev); it.opi = -1; it.names = []
    it.process_page(mpage)
    out = {"lines": [], "images": [], "loose": [], "paths": [], "figures": []}
    walk(dev.get_result(), out)
    return out, it.names

def in_lines(out):
    """Characters laid out in lines of two or more characters: how well a layout reads as text lines."""
    return sum(n for n in (sum(1 for c in ln._objs if isinstance(c, LTChar)) for ln in out["lines"]) if n >= 2)

def main(src, dst):
    pdf = pikepdf.open(src)
    fp = open(src, "rb")
    doc = PDFDocument(PDFParser(fp))
    rm = PDFResourceManager(caching=True)
    lap = LAParams(char_margin=1.0, line_margin=0.4, boxes_flow=0.5, detect_vertical=False, all_texts=True)
    pages = []
    for pno, (mpage, ppage) in enumerate(zip(PDFPage.create_pages(doc), pdf.pages)):
        out, names = layout(rm, lap, mpage)
        # pdfminer lays a page out as it is displayed (its /Rotate applied). A page whose text stands upright only in
        # its own page space (a sideways scan the OCR stage gave an upright page space, displayed turned back as it
        # was) then reads as vertical, one character per line; lay such a page out in page space instead.
        user_space = False
        rot = (mpage.rotate or 0) % 360
        if rot:
            mpage.rotate = 0
            out0, names0 = layout(rm, lap, mpage)
            if in_lines(out0) > in_lines(out):
                out, names, user_space = out0, names0, True
            else:
                mpage.rotate = rot
        ops = pikepdf.parse_content_stream(ppage)
        pnames = ["EI" if str(op.operator) == "INLINE IMAGE" else str(op.operator) for op in ops]
        align_ok = pnames == names
        segs = []
        for li, ln in enumerate(out["lines"]):
            chars = [c for c in ln._objs if isinstance(c, LTChar)]
            if not chars:
                continue
            text = ln.get_text().rstrip("\n")
            spans = []
            for c in chars:
                k = (c.op, c.elem)
                if spans and spans[-1][0] == c.op and spans[-1][1] == c.elem and spans[-1][3] == c.cidx:
                    spans[-1][3] = c.cidx + 1
                else:
                    spans.append([c.op, c.elem, c.cidx, c.cidx + 1])
            sizes = Counter(round(c.size, 1) for c in chars if c.get_text().strip())
            fonts = Counter(c.fontname for c in chars if c.get_text().strip())
            fn = fonts.most_common(1)[0][0] if fonts else ""
            segs.append({"id": f"p{pno+1}s{len(segs)+1}", "text": text, "bbox": bb(ln),
                         "chars": "".join(c.get_text() for c in chars),
                         "size": sizes.most_common(1)[0][0] if sizes else 0, "font": fn,
                         "bold": bool(re.search(r"bold|black|heavy|semibold|demi", fn, re.I)),
                         "spans": spans, "bpc": sorted({c.bpc for c in chars})})
        for c in out["loose"]:
            segs.append({"id": f"p{pno+1}s{len(segs)+1}", "text": c.get_text(), "chars": c.get_text(), "bbox": bb(c), "size": round(c.size, 1),
                         "font": c.fontname, "bold": False, "spans": [[c.op, c.elem, c.cidx, c.cidx + 1]], "bpc": [c.bpc], "loose": True})
        imgs = [{"op": getattr(i, "op", -1), "bbox": bb(i), "name": i.name, "px": list(i.srcsize)} for i in out["images"]]
        paths = {}
        for p_ in out["paths"]:
            o = getattr(p_, "op", -1)
            if o in paths:
                b = paths[o]; paths[o] = [min(b[0], p_.x0), min(b[1], p_.y0), max(b[2], p_.x1), max(b[3], p_.y1)]
            else:
                paths[o] = list(bb(p_))
        annots = []
        for a in ppage.get("/Annots", []) or []:
            try:
                st = str(a.get("/Subtype")); r = [float(x) for x in a.get("/Rect")]
                row = {"subtype": st, "rect": r}
                if st == "/Link":
                    act = a.get("/A")
                    row["uri"] = str(act.get("/URI")) if act is not None and act.get("/URI") is not None else None
                if st == "/Widget":
                    f = a if a.get("/T") is not None else a.get("/Parent")
                    row["T"] = str(f.get("/T")) if f is not None and f.get("/T") is not None else None
                    row["TU"] = str(f.get("/TU")) if f is not None and f.get("/TU") is not None else None
                    ft = f.get("/FT") if f is not None else None
                    row["FT"] = str(ft) if ft is not None else None
                annots.append(row)
            except Exception as e:
                annots.append({"error": repr(e)[:100]})
        mb = [float(x) for x in ppage.mediabox]
        pages.append({"page": pno + 1, "box": mb, "rotate": rot, "user_space": user_space, "nops": len(pnames), "align_ok": align_ok,
                      "segments": segs, "images": imgs,
                      "paths": [{"op": k, "bbox": [round(x, 1) for x in v]} for k, v in sorted(paths.items())],
                      "annots": annots})
    fonts = []
    json.dump({"src": src, "npages": len(pages), "pages": pages}, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    for p in pages:
        print(p["page"], "ops", p["nops"], "align", p["align_ok"], "segs", len(p["segments"]), "imgs", len(p["images"]),
              "paths", len(p["paths"]), "annots", Counter(a.get("subtype") for a in p["annots"]))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
