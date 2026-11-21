"""Round 15, route (a) preparation (before analysis): the same drawing, regrouped so text can be tagged.
1. Every form XObject a page draws that contains text (at any depth) is inlined into the page stream:
   'q <Matrix> cm <BBox> re W n <form operators, resources renamed> Q'. Forms with no text stay forms.
2. In the forms that stay, old marked-content operators other than optional-content (/OC) ones are removed, and their
   /StructParent(s) keys dropped (the structure is rebuilt by apply.py).
Use: venv/Scripts/python -I -X utf8 prep.py in.pdf out.pdf
"""
import sys
from collections import Counter
import pikepdf
from pikepdf import Array, Dictionary, Name, Operator

CATS = ["/Font", "/XObject", "/ExtGState", "/ColorSpace", "/Pattern", "/Shading", "/Properties"]
DEVICE_CS = {"/DeviceGray", "/DeviceRGB", "/DeviceCMYK", "/Pattern"}
TEXT_OPS = {"Tj", "TJ", "'", '"'}
stats = Counter()

def has_text(xo, depth=0):
    if depth > 10:
        return False
    try:
        ops = pikepdf.parse_content_stream(xo)
    except Exception:
        return False
    res = xo.get("/Resources") or Dictionary()
    for ins in ops:
        n = str(ins.operator)
        if n in TEXT_OPS:
            return True
        if n == "Do":
            sub = (res.get("/XObject") or {}).get(str(ins.operands[0]))
            if sub is not None and sub.get("/Subtype") == Name.Form and has_text(sub, depth + 1):
                return True
    return False

def rename_ops(ops, ren):
    out = []
    for ins in ops:
        if isinstance(ins, pikepdf.ContentStreamInlineImage):
            out.append(ins); continue
        n = str(ins.operator); a = list(ins.operands)
        def r(cat, i):
            if i < len(a) and isinstance(a[i], Name) and str(a[i]) in ren.get(cat, {}):
                a[i] = Name(ren[cat][str(a[i])])
        if n == "Tf": r("/Font", 0)
        elif n == "Do": r("/XObject", 0)
        elif n == "gs": r("/ExtGState", 0)
        elif n in ("cs", "CS"):
            if str(a[0]) not in DEVICE_CS: r("/ColorSpace", 0)
        elif n in ("scn", "SCN"):
            if a and isinstance(a[-1], Name): r("/Pattern", len(a) - 1)
        elif n == "sh": r("/Shading", 0)
        elif n in ("BDC", "DP"): r("/Properties", 1)
        out.append(pikepdf.ContentStreamInstruction(a, ins.operator))
    return out

def inline(ops, res_of_stream, page_res, uid):
    """Return ops with text-bearing form Do's replaced by their contents (recursively)."""
    out = []
    xobjs = res_of_stream.get("/XObject") or Dictionary()
    for ins in ops:
        if not isinstance(ins, pikepdf.ContentStreamInlineImage) and str(ins.operator) == "Do":
            nm = str(ins.operands[0]); xo = xobjs.get(nm)
            if xo is not None and xo.get("/Subtype") == Name.Form and has_text(xo):
                uid[0] += 1; tag = f"I{uid[0]}_"
                fres = xo.get("/Resources") or res_of_stream
                ren = {}
                for cat in CATS:
                    d = fres.get(cat)
                    if d is None:
                        continue
                    if cat not in page_res:
                        page_res[cat] = Dictionary()
                    ren[cat] = {}
                    for k in d.keys():
                        new = "/" + tag + k[1:]
                        page_res[cat][new] = d[k]; ren[cat][k] = new
                sub = rename_ops(pikepdf.parse_content_stream(xo), ren)
                # nested text-bearing forms: resolve them against the renamed (page) resources
                sub = inline(sub, page_res, page_res, uid)
                out.append(pikepdf.ContentStreamInstruction([], Operator("q")))
                if "/Matrix" in xo:
                    out.append(pikepdf.ContentStreamInstruction(list(xo.Matrix), Operator("cm")))
                bb = [float(x) for x in xo.BBox]
                out.append(pikepdf.ContentStreamInstruction([bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]], Operator("re")))
                out.append(pikepdf.ContentStreamInstruction([], Operator("W")))
                out.append(pikepdf.ContentStreamInstruction([], Operator("n")))
                out.extend(sub)
                out.append(pikepdf.ContentStreamInstruction([], Operator("Q")))
                stats["inlined"] += 1
                if "/Group" in xo:
                    stats["inlined_with_group"] += 1
                continue
        out.append(ins)
    return out

def strip_marks(stream):
    ops = pikepdf.parse_content_stream(stream)
    out, stack, changed = [], [], False
    for ins in ops:
        n = "" if isinstance(ins, pikepdf.ContentStreamInlineImage) else str(ins.operator)
        if n in ("BDC", "BMC"):
            keep = n == "BDC" and ins.operands[0] == Name.OC
            stack.append(keep)
            if not keep:
                changed = True; continue
        elif n == "EMC":
            keep = stack.pop() if stack else False
            if not keep:
                changed = True; continue
        elif n in ("MP", "DP"):
            changed = True; continue
        out.append(ins)
    if changed:
        stream.write(pikepdf.unparse_content_stream(out)); stats["form_marks_stripped"] += 1

def forms_of(res, seen, depth=0):
    if res is None or depth > 10:
        return
    for k, xo in (res.get("/XObject") or {}).items():
        if xo.get("/Subtype") == Name.Form and xo.objgen not in seen:
            seen.add(xo.objgen); yield xo
            yield from forms_of(xo.get("/Resources"), seen, depth + 1)

def main(src, dst):
    pdf = pikepdf.open(src)
    uid = [0]
    for page in pdf.pages:
        res = page.obj.get("/Resources")
        if res is None:
            continue
        page.Resources = Dictionary({k: (Dictionary({kk: vv for kk, vv in v.items()}) if isinstance(v, Dictionary) else v)
                                     for k, v in page.Resources.items()})
        ops = pikepdf.parse_content_stream(page)
        new = inline(ops, page.Resources, page.Resources, uid)
        if len(new) != len(ops) or stats["inlined"]:
            page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(new))
    seen = set()
    for page in pdf.pages:
        for xo in list(forms_of(page.get("/Resources"), seen)):
            strip_marks(xo)
            for k in ("/StructParents", "/StructParent"):
                if k in xo:
                    del xo[k]
    pdf.save(dst)
    print(dict(stats))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
