"""Round 15 checks 2-4, read back with pdfium (pypdfium2), a different library from the writer (pikepdf) and the
analyser (pdfminer):
  render: each page of original and output at 100 dpi; fraction of pixels whose largest channel differs by > 32.
  chars:  multiset of non-space characters each page shows (pdfium text page), original vs output.
  tagged: characters drawn inside MCID-marked content vs Artifact vs unmarked (output only); image objects likewise.
  tree:   the structure tree walked in order (pdfium's per-page struct tree), role, alt and the text of its MCIDs,
          written to <out>.tree.txt for the reviewer (reading order, headings, lists, tables, alt text).
Use: venv/Scripts/python -I -X utf8 check.py original.pdf output.pdf report.json
"""
import ctypes, json, sys
from collections import Counter
import pypdfium2 as pdfium
import pypdfium2.raw as R
from PIL import ImageChops

def ws(s):
    return "".join(ch for ch in s if not ch.isspace() and ch not in "￾￿\x00\x02")

def page_text(page):
    tp = page.get_textpage()
    t = tp.get_text_range()
    tp.close()
    return t

def obj_text(obj, tp):
    n = R.FPDFTextObj_GetText(obj, tp, None, 0)
    if n <= 2:
        return ""
    buf = (ctypes.c_ushort * (n // 2 + 1))()
    R.FPDFTextObj_GetText(obj, tp, buf, n)
    return bytes(buf)[: n - 2].decode("utf-16-le", "replace")

def marks(obj):
    out = []
    for k in range(R.FPDFPageObj_CountMarks(obj)):
        m = R.FPDFPageObj_GetMark(obj, k)
        n = ctypes.c_ulong(0)
        R.FPDFPageObjMark_GetName(m, None, 0, ctypes.byref(n))
        buf = (ctypes.c_ushort * (n.value // 2 + 1))()
        R.FPDFPageObjMark_GetName(m, buf, n.value, ctypes.byref(n))
        name = bytes(buf)[: max(0, n.value - 2)].decode("utf-16-le", "replace")
        v = ctypes.c_int(-1)
        has = R.FPDFPageObjMark_GetParamIntValue(m, b"MCID", ctypes.byref(v))
        out.append((name, v.value if has else None))
    return out

def walk_objs(container_count, get, tp, inherited, acc):
    for i in range(container_count):
        o = get(i)
        t = R.FPDFPageObj_GetType(o)
        mk = inherited + marks(o)
        if t == R.FPDF_PAGEOBJ_FORM:
            walk_objs(R.FPDFFormObj_CountObjects(o), lambda j, o=o: R.FPDFFormObj_GetObject(o, j), tp, mk, acc)
            continue
        mcid = next((v for n, v in reversed(mk) if v is not None), None)
        art = any(n == "Artifact" for n, v in mk)
        kind = "mcid" if mcid is not None and not art else ("artifact" if art else "unmarked")
        if t == R.FPDF_PAGEOBJ_TEXT:
            l, b_, r_, t_ = ctypes.c_float(), ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
            R.FPDFPageObj_GetBounds(o, ctypes.byref(l), ctypes.byref(b_), ctypes.byref(r_), ctypes.byref(t_))
            acc["text"].append((kind, mcid, obj_text(o, tp)))
            acc.setdefault("bounds", []).append((mcid, b_.value, t_.value))
        elif t == R.FPDF_PAGEOBJ_IMAGE:
            acc["image"].append((kind, mcid))
        elif t in (R.FPDF_PAGEOBJ_PATH, R.FPDF_PAGEOBJ_SHADING):
            acc["path"][kind] += 1

def wstr(fn, el):
    n = fn(el, None, 0)
    if n <= 2:
        return ""
    buf = (ctypes.c_ushort * (n // 2 + 1))()
    fn(el, buf, n)
    return bytes(buf)[: n - 2].decode("utf-16-le", "replace")

def tree_lines(page, mcid_text):
    st = R.FPDF_StructTree_GetForPage(page.raw)
    lines = []
    def rec(el, depth):
        role = wstr(R.FPDF_StructElement_GetType, el)
        alt = wstr(R.FPDF_StructElement_GetAltText, el)
        ids = []
        n = R.FPDF_StructElement_GetMarkedContentIdCount(el)
        for k in range(max(0, n)):
            ids.append(R.FPDF_StructElement_GetMarkedContentIdAtIndex(el, k))
        txt = "".join(mcid_text.get(i, "") for i in ids)
        lines.append("  " * depth + role + (f" [alt: {alt}]" if alt else "") + (f": {txt.strip()}" if txt.strip() else ""))
        for k in range(R.FPDF_StructElement_CountChildren(el)):
            ch = R.FPDF_StructElement_GetChildAtIndex(el, k)
            if ch:
                rec(ch, depth + 1)
    for k in range(R.FPDF_StructTree_CountChildren(st)):
        rec(R.FPDF_StructTree_GetChildAtIndex(st, k), 0)
    R.FPDF_StructTree_Close(st)
    return lines

def full_tree(outp, texts, bounds=None):
    """The whole structure tree in order (pikepdf walk), with each MCR's text as pdfium read it and each OBJR's
    annotation (subtype, TU or Contents). texts: {(page index, mcid): text}."""
    import pikepdf
    pdf = pikepdf.open(outp)
    pidx = {pg.objgen: i for i, pg in enumerate(pdf.pages)}
    lines = []
    def rec(e, depth, pg):
        role = str(e.get("/S", ""))[1:]
        alt = e.get("/Alt")
        attr = e.get("/A")
        scope = attr.get("/Scope") if isinstance(attr, pikepdf.Dictionary) else None
        pg = e.get("/Pg", pg)
        buf, kids = [], []
        k = e.get("/K")
        ks = list(k) if isinstance(k, pikepdf.Array) else ([k] if k is not None else [])
        head = "  " * depth + role + (f" [scope {str(scope)[1:]}]" if scope is not None else "") + (f" [alt: {alt}]" if alt is not None else "")
        lines.append(head); at = len(lines) - 1
        text = []
        for x in ks:
            if isinstance(x, int):
                key = (pidx.get(pg.objgen if pg is not None else None), x)
                text.append((texts.get(key, ""), (bounds or {}).get(key)))
            elif isinstance(x, pikepdf.Dictionary) and x.get("/Type") == pikepdf.Name.MCR:
                key = (pidx.get(x.Pg.objgen), int(x.MCID))
                text.append((texts.get(key, ""), (bounds or {}).get(key)))
            elif isinstance(x, pikepdf.Dictionary) and x.get("/Type") == pikepdf.Name.OBJR:
                o = x.Obj
                f = o if "/T" in o else o.get("/Parent")
                desc = str(o.get("/Subtype"))[1:]
                if f is not None and "/TU" in f:
                    desc += f" TU={f.TU}"
                elif "/Contents" in o:
                    desc += f" Contents={o.Contents}"
                text.append((f" <{desc}> ", None))
            elif isinstance(x, pikepdf.Dictionary):
                if text:
                    lines[at] += ": " + joined(text); text = []
                    lines.append("  " * depth + role + " (cont.)"); at = len(lines) - 1
                rec(x, depth + 1, pg)
        t = joined(text)
        if t:
            lines[at] += ": " + t
    def joined(parts):
        out, prev = "", None
        for t, bd in parts:
            if not t:
                continue
            if out and bd is not None and prev is not None and (bd[1] < prev[0] or bd[0] > prev[1]) and not out[-1].isspace() and not t[0].isspace():
                out += " "   # the next run starts on another line: a reader breaks the word there
            out += t
            if bd is not None:
                prev = bd
        return out.strip()
    root = pdf.Root.StructTreeRoot
    k = root.K
    for x in (list(k) if isinstance(k, pikepdf.Array) else [k]):
        rec(x, 0, None)
    return lines

def main(orig, outp, rep):
    a, b = pdfium.PdfDocument(orig), pdfium.PdfDocument(outp)
    res = {"pages": [], "orig": orig, "out": outp}
    tree = []
    alltexts = {}; allbounds = {}
    for i in range(len(a)):
        pa, pb = a[i], b[i] if i < len(b) else None
        row = {"page": i + 1}
        ia = pa.render(scale=100 / 72).to_pil().convert("RGB")
        if pb is None:
            row["missing"] = True; res["pages"].append(row); continue
        ib = pb.render(scale=100 / 72).to_pil().convert("RGB")
        if ia.size != ib.size:
            row["render_diff"] = None; row["size"] = [ia.size, ib.size]
        else:
            d = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 32 else 0)
            row["render_diff"] = round(sum(1 for v in d.get_flattened_data() if v) / (ia.size[0] * ia.size[1]), 6)
        ca, cb = Counter(ws(page_text(pa))), Counter(ws(page_text(pb)))
        row["chars_orig"] = sum(ca.values()); row["chars_out"] = sum(cb.values())
        row["chars_lost"] = sum((ca - cb).values()); row["chars_added"] = sum((cb - ca).values())
        tp = pb.get_textpage()
        acc = {"text": [], "image": [], "path": Counter()}
        walk_objs(R.FPDFPage_CountObjects(pb.raw), lambda j, p=pb: R.FPDFPage_GetObject(p.raw, j), tp, [], acc)
        tk = Counter()
        mcid_text = {}
        for kind, mcid, t in acc["text"]:
            tk[kind] += len(ws(t))
            if kind == "mcid":
                mcid_text[mcid] = mcid_text.get(mcid, "") + t
                alltexts[(i, mcid)] = alltexts.get((i, mcid), "") + t
        for mcid, lo, hi in acc.get("bounds", []):
            if mcid is not None and (i, mcid) not in allbounds:
                allbounds[(i, mcid)] = (lo, hi)
        row["tagged_chars"] = dict(tk)
        row["images"] = dict(Counter(k for k, m in acc["image"]))
        row["paths"] = dict(acc["path"])
        tree.append(f"=== page {i+1}")
        tree.extend(tree_lines(pb, mcid_text))
        tp.close()
        res["pages"].append(row)
    tot = lambda k: sum((p.get(k) or 0) for p in res["pages"])
    res["summary"] = {"pages": len(a), "out_pages": len(b), "max_render_diff": max((p.get("render_diff") or 0) for p in res["pages"]),
                      "chars_orig": tot("chars_orig"), "chars_lost": tot("chars_lost"), "chars_added": tot("chars_added"),
                      "unmarked_chars": sum(p.get("tagged_chars", {}).get("unmarked", 0) for p in res["pages"]),
                      "artifact_chars": sum(p.get("tagged_chars", {}).get("artifact", 0) for p in res["pages"]),
                      "tagged_chars": sum(p.get("tagged_chars", {}).get("mcid", 0) for p in res["pages"]),
                      "images_unmarked": sum(p.get("images", {}).get("unmarked", 0) for p in res["pages"])}
    json.dump(res, open(rep, "w", encoding="utf-8"), indent=1)
    open(rep.replace(".json", "") + ".tree.txt", "w", encoding="utf-8").write("\n".join(tree) + "\n")
    try:
        ft = full_tree(outp, alltexts, allbounds)
    except Exception as e:
        ft = [f"(no structure tree readable: {e!r})"]
    open(rep.replace(".json", "") + ".fulltree.txt", "w", encoding="utf-8").write("\n".join(ft) + "\n")
    print(json.dumps(res["summary"]))

if __name__ == "__main__":
    main(*sys.argv[1:4])
