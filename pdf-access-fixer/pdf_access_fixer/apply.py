"""Round 15, route (a): tag a PDF in place from a reviewed plan. The page content is kept operator for operator; only
marked-content operators are added around painting operators (and old non-/OC marks removed); the text operators of one
segment drawn one after another share one sequence. A text operator whose
characters belong to two plan elements is split at the character boundary (the text position carries on, so the page
looks the same). Every segment and image of the analysis must be placed by the plan, or the run refuses.

Plan format (plan.txt; '#' starts a comment):
  title: <document title>          lang: <BCP 47 tag>
  H1..H6 / P / ART <seg ids>       (ART = artifact: running headers, footers, page numbers, decoration)
  L / LI <seg ids> / /L            (lists; LI segs become LBody; nested L inside an LI allowed after the LI line)
  TABLE / TR / TH:<ids,> (or THR: row header) TD:<ids,> / /TABLE   (cells: comma-joined seg ids, '-' for an empty cell)
  FIG <img id> [<more img ids>] [paths:<page>:<x0>,<y0>,<x1>,<y1>] | <alt text>
  DECO <img ids>                   (decorative images, as artifacts)
  FIELD <field full name> | <label>  (the field's TU)
Use: venv/Scripts/python -I -X utf8 apply.py in.pdf analysis.json plan.txt out.pdf
"""
import json, re, sys
from collections import defaultdict, Counter
import os
import pikepdf
from pikepdf import Array, Dictionary, Name, Operator, String, Pdf
try:
    from . import fonts_fix
except ImportError:  # run as a script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fonts_fix

TEXT_SHOW = {"Tj", "TJ", "'", '"'}
PATH_BUILD = {"m", "l", "c", "v", "y", "h", "re"}
PATH_PAINT = {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}
MARKS = {"BDC", "BMC", "EMC", "MP", "DP"}
# Text operators that may sit inside one marked-content sequence between two text-show operators of the same owner:
# positioning and text state only. pdf.js starts a new text item (a screen reader's line) at every marked-content
# operator, so a sequence per word made NVDA read a scan one word per line (2026-11-16).
RUN_JOIN = {"Tm", "Td", "TD", "T*", "Tz", "Tf", "Tc", "Tw", "TL", "Ts", "Tr"}

class PlanError(Exception):
    pass

def parse_plan(text):
    plan = {"title": None, "lang": "en-US", "root": [], "deco": set(), "fields": {}, "tounicode": {}, "links": {}, "splitfields": [],
            "text": {}}
    stack = [plan["root"]]          # current container's children list
    cstack = []                     # open containers (dicts)
    for raw in text.splitlines():
        if raw.lstrip().startswith(("FIG", "FIELD", "TEXT")):
            line = raw.split("  # ", 1)[0].rstrip()   # alt text and labels may hold '#'; their comment needs two spaces
        else:
            line = raw.split("#", 1)[0].rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith("title:"):
            plan["title"] = s[6:].strip(); continue
        if s.startswith("lang:"):
            plan["lang"] = s[5:].strip(); continue
        w = s.split()
        tag = w[0]
        if tag in ("H1", "H2", "H3", "H4", "H5", "H6", "P", "ART", "Caption", "BlockQuote", "Note"):
            stack[-1].append({"role": tag, "segs": w[1:]})
        elif tag == "L":
            el = {"role": "L", "kids": []}; stack[-1].append(el); cstack.append(el); stack.append(el["kids"])
        elif tag == "LI":
            if not cstack or cstack[-1]["role"] != "L":
                raise PlanError(f"LI outside L: {s}")
            el = {"role": "LI", "segs": w[1:], "kids": []}; stack[-1].append(el)
        elif tag == "/L":
            cstack.pop(); stack.pop()
            # a nested L directly after an LI goes into that LI
        elif tag == "TABLE":
            el = {"role": "Table", "rows": []}; stack[-1].append(el); cstack.append(el)
        elif tag == "TR":
            row = []
            for c in w[1:]:
                kind, ids = c.split(":", 1)
                items = [] if ids == "-" else ids.split(",")
                cell = {"kind": kind, "segs": [], "fields": [], "paths": []}
                for it in items:
                    if it.startswith("field="):
                        cell["fields"].append(__import__("urllib.parse").parse.unquote(it[6:]))   # %20 for a space in a field name
                    elif it.startswith("paths="):
                        pg, box = it[6:].split(":"); cell["paths"].append((int(pg), [float(x) for x in box.split(";")]))
                    else:
                        cell["segs"].append(it)
                row.append(cell)
            cstack[-1]["rows"].append(row)
        elif tag == "CELLALT":
            rc, alt = s[7:].split("|", 1); r_, c_ = rc.strip().split(",")
            cstack[-1].setdefault("cellalt", {})[(int(r_), int(c_))] = alt.strip()
        elif tag == "SPLITFIELD":
            plan["splitfields"].append(s[10:].strip())
        elif tag == "/TABLE":
            cstack.pop()
        elif tag == "FIG":
            head, alt = s[3:].split("|", 1)
            imgs, paths, regions = [], [], []
            for t in head.split():
                if t.startswith("paths:"):
                    _, pg, box = t.split(":"); paths.append((int(pg), [float(x) for x in box.split(",")]))
                elif t.startswith("region:"):
                    _, pg, box = t.split(":"); regions.append((int(pg), [float(x) for x in box.split(",")]))
                elif t.startswith("seg:"):
                    imgs.append(t)
                else:
                    imgs.append(t)
            stack[-1].append({"role": "Figure", "imgs": [i for i in imgs if not i.startswith("seg:")],
                              "segs": [i[4:] for i in imgs if i.startswith("seg:")], "paths": paths, "regions": regions,
                              "alt": alt.strip()})
        elif tag == "TOUNICODE":
            mp = plan["tounicode"].setdefault(w[1], {})
            for kv in s.split(None, 2)[2].split("|"):
                k, v = kv.strip().split("=", 1)
                mp[int(k, 0)] = v
        elif tag == "LINK":
            k, d = s[4:].split("|", 1); plan["links"][k.strip()] = d.strip()
        elif tag == "TEXT":
            sid, txt = s[4:].split("|", 1)
            if sid.strip() in plan["text"]:
                raise PlanError(f"two TEXT lines for {sid.strip()}")
            plan["text"][sid.strip()] = txt.strip()
        elif tag == "DECO":
            plan["deco"].update(w[1:])
        elif tag == "FIELD":
            name, label = s[5:].split("|", 1); plan["fields"][name.strip()] = label.strip()
            stack[-1].append({"role": "Field", "name": name.strip(), "label": label.strip()})
        else:
            raise PlanError(f"unknown plan line: {s}")
    # attach nested lists: an L that directly follows an LI inside the same parent L becomes that LI's child
    def nest(children):
        out = []
        for el in children:
            if el["role"] == "L":
                nest_kids = nest(el["kids"]); el["kids"] = []
                for k in nest_kids:
                    if k["role"] != "LI" and el["kids"] and el["kids"][-1]["role"] == "LI":
                        el["kids"][-1]["kids"].append(k)   # a nested list, figure, paragraph or field inside the item
                    else:
                        el["kids"].append(k)
            out.append(el)
        return out
    plan["root"] = nest(plan["root"])
    if not plan["title"]:
        raise PlanError("plan has no title")
    return plan

def leaves(el):
    """(role-context, segs) pairs in reading order, for checking coverage."""
    if "segs" in el:
        yield from el["segs"]
    for k in el.get("kids", []):
        yield from leaves(k)
    for row in el.get("rows", []):
        for c in row:
            yield from c["segs"]

SUB = re.compile(r"^(p\d+s\d+)\[(\d*):(\d*)\]$")

def expand(an, plan):
    """Sub-segments: a plan may name part of a segment as <id>[a:b], a range over the segment's 'chars' (its drawn
    characters in order, no inferred spaces). The ranges named for one segment must cover it exactly, without overlap.
    The analysis is rewritten in memory so each split segment is replaced by its parts, in order."""
    toks = []
    def walk(el):
        toks.extend(el.get("segs", []))
        for k in el.get("kids", []):
            walk(k)
        for row in el.get("rows", []):
            for c in row:
                toks.extend(c["segs"])
    for el in plan["root"]:
        walk(el)
    want = defaultdict(list)
    for t in toks:
        m = SUB.match(t)
        if m:
            want[m.group(1)].append((t, m.group(2), m.group(3)))
    if not want:
        return
    for pg in an["pages"]:
        new = []
        for sg in pg["segments"]:
            if sg["id"] not in want:
                new.append(sg); continue
            ch = sg.get("chars")
            if ch is None:
                raise PlanError(f"analysis has no chars for {sg['id']}: re-run analyze.py")
            n = len(ch)
            if n != sum(c1 - c0 for _, _, c0, c1 in sg["spans"]):
                raise PlanError(f"{sg['id']}: chars and spans disagree ({n}); cannot split it")
            parts = sorted(((int(a) if a else 0, int(b) if b else n, t) for t, a, b in want[sg["id"]]))
            pos = 0
            for a, b, t in parts:
                if a != pos or b <= a or b > n:
                    raise PlanError(f"{sg['id']}: parts {[(x, y) for x, y, _ in parts]} do not cover 0..{n} exactly")
                pos = b
            if pos != n:
                raise PlanError(f"{sg['id']}: parts end at {pos}, the segment has {n} characters")
            flat = []  # one entry per character: (op, elem, cid)
            for op, elem, c0, c1 in sg["spans"]:
                for c in range(c0, c1):
                    flat.append((op, elem, c))
            x0, y0, x1, y1 = sg["bbox"]
            for a, b, t in parts:
                spans = []
                for op, elem, c in flat[a:b]:
                    if spans and spans[-1][0] == op and spans[-1][1] == elem and spans[-1][3] == c:
                        spans[-1][3] = c + 1
                    else:
                        spans.append([op, elem, c, c + 1])
                d = dict(sg); d.update(id=t, text=ch[a:b], chars=ch[a:b], spans=spans,
                                       bbox=[x0 + (x1 - x0) * a / n, y0, x0 + (x1 - x0) * b / n, y1])
                new.append(d)
        pg["segments"] = new

def main(src, an_path, plan_path, dst):
    an = json.load(open(an_path, encoding="utf-8"))
    plan = parse_plan(open(plan_path, encoding="utf-8").read())
    pdf = Pdf.open(src)
    correct_ocr_text(pdf, an, plan["text"])
    expand(an, plan)
    seginfo = {s["id"]: (p["page"], s) for p in an["pages"] for s in p["segments"]}
    imginfo = {}
    for p in an["pages"]:
        for n, im in enumerate(p["images"]):
            imginfo[f"p{p['page']}i{n}"] = (p["page"], im)
    # ---- coverage: every segment and image placed exactly once
    used = Counter()
    for el in plan["root"]:
        for sid in leaves(el):
            used[sid] += 1
    figimgs = Counter()
    def figs(el):
        if el["role"] == "Figure":
            yield el
        for k in el.get("kids", []):
            yield from figs(k)
    allfigs = [f for el in plan["root"] for f in figs(el)]
    for f in allfigs:
        for i in f["imgs"]:
            figimgs[i] += 1
    problems = []
    for sid in seginfo:
        if used[sid] != 1:
            problems.append(f"segment {sid} placed {used[sid]} times: {seginfo[sid][1]['text'][:50]!r}")
    for sid in used:
        if sid not in seginfo:
            problems.append(f"unknown segment {sid}")
    for iid in imginfo:
        n = figimgs[iid] + (iid in plan["deco"])
        if n != 1:
            problems.append(f"image {iid} placed {n} times")
    if problems:
        raise PlanError("plan does not place everything exactly once:\n  " + "\n  ".join(problems[:40]))

    # ---- struct elements (created lazily), MCIDs per page
    root = pdf.Root
    for k in ("/StructTreeRoot", "/MarkInfo"):
        if k in root:
            del root[k]
    st_root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
    doc_el = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.Document, P=st_root, K=Array()))
    st_root.K = Array([doc_el])
    pages = list(pdf.pages)
    # target per segment: struct element; created while walking plan
    seg_target = {}
    img_target = {}
    img_key = {}
    field_slot = {}
    explicit_key = {}
    path_targets = defaultdict(list)   # page -> [(bbox, elem)]
    region_targets = defaultdict(list)  # page -> [(bbox, elem, key)]: part of a scanned page shown again as a Figure
    def mk(role, parent, extra=None):
        d = Dictionary(Type=Name.StructElem, S=Name("/" + role), P=parent, K=Array())
        if extra:
            for k, v in extra.items():
                d[k] = v
        d = pdf.make_indirect(d)
        parent.K.append(d)
        return d
    def build(el, parent):
        r = el["role"]
        if r == "ART":
            for sid in el["segs"]:
                seg_target[sid] = None
            return
        if r == "L":
            e = mk("L", parent)
            for k in el["kids"]:
                build(k, e)
            return
        if r == "LI":
            li = mk("LI", parent)
            body = mk("LBody", li)
            for sid in el["segs"]:
                seg_target[sid] = body
            for k in el.get("kids", []):
                build(k, body)
            return
        if r == "Table":
            t = mk("Table", parent)
            explicit_key[t.objgen] = el["key"]
            for ri, row in enumerate(el["rows"]):
                tr = mk("TR", t)
                for ci_, c_ in enumerate(row):
                    c_["alt"] = el.get("cellalt", {}).get((ri + 1, ci_ + 1))
                explicit_key[tr.objgen] = el["rowkeys"][ri]
                for c in row:
                    if c["kind"] in ("TH", "THR"):
                        cell = mk("TH", tr, {"/A": Dictionary(O=Name.Table, Scope=Name.Column if c["kind"] == "TH" else Name.Row)})
                    else:
                        cell = mk("TD", tr)
                    explicit_key[cell.objgen] = c["key"]
                    if c.get("alt"):
                        cell.Alt = String(c["alt"])
                    for fn in c.get("fields", []):
                        field_slot[fn] = cell
                    for pg, box in c.get("paths", []):
                        path_targets[pg].append((box, cell, c["key"]))
                    for sid in c["segs"]:
                        seg_target[sid] = cell
            return
        if r == "Field":
            field_slot[el["name"]] = parent
            return
        if r == "Figure":
            e = mk("Figure", parent, {"/Alt": String(el["alt"])})
            explicit_key[e.objgen] = el["key"]
            for i in el["imgs"]:
                img_target[i] = e; img_key[i] = el["key"]
            for sid in el["segs"]:
                seg_target[sid] = e
            for pg, box in el["paths"]:
                path_targets[pg].append((box, e, el["key"]))
            for pg, box in el.get("regions", []):
                region_targets[pg].append((box, e, el["key"]))
            return
        e = mk(r, parent)
        for sid in el["segs"]:
            seg_target[sid] = e
    order_of_seg = {}; field_key = {}
    cnt = [0]
    def keyed(el):
        if el["role"] == "Field":
            field_key[el["name"]] = cnt[0]; cnt[0] += 1; return
        if el["role"] == "Figure":
            el["key"] = cnt[0]; cnt[0] += 1
        for sid in el.get("segs", []):
            order_of_seg[sid] = cnt[0]; cnt[0] += 1
        for k in el.get("kids", []):
            keyed(k)
        if el["role"] == "Table":
            el["key"] = cnt[0]; cnt[0] += 1
            el["rowkeys"] = []
        for row in el.get("rows", []):
            el["rowkeys"].append(cnt[0]); cnt[0] += 1
            for c in row:
                c["key"] = cnt[0]; cnt[0] += 1
                for sid in c["segs"]:
                    order_of_seg[sid] = cnt[0]; cnt[0] += 1
                for fn in c.get("fields", []):
                    field_key[fn] = cnt[0]; cnt[0] += 1
    for el in plan["root"]:
        keyed(el)
    for el in plan["root"]:
        build(el, doc_el)
    # ---- links: a Link element inside the element that owns the link's text, holding that text
    link_elem = {}
    for pno, page in enumerate(pages):
        segs = an["pages"][pno]["segments"]
        for ai, a in enumerate(page.get("/Annots") or []):
            if a.get("/Subtype") != Name.Link:
                continue
            r = [float(x) for x in a.Rect]; r = [min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])]
            ov = [x for x in segs if mostly_inside(x["bbox"], r)]
            host = None
            if not ov:  # the link covers part of a longer line: the Link goes inside that line's element, after it
                hits = [x for x in segs if mostly_inside(r, x["bbox"]) and x["id"] in seg_target]
                host = hits[0] if hits else None
            owner = seg_target.get(ov[0]["id"]) if ov else (seg_target.get(host["id"]) if host else None)
            parent = owner if owner is not None else doc_el
            le = mk("Link", parent)
            for x in ov:
                if seg_target.get(x["id"]) is owner:
                    seg_target[x["id"]] = le
            if host is not None:
                explicit_key[le.objgen] = order_of_seg[host["id"]] + 0.5
            elif not ov:
                above = [order_of_seg[x["id"]] for x in segs if x["bbox"][1] >= r[3] - 1 and x["id"] in order_of_seg]
                allk = [order_of_seg[x["id"]] for x in segs if x["id"] in order_of_seg]
                explicit_key[le.objgen] = (max(above) if above else (min(allk) if allk else 0)) + 0.5
            link_elem[(pno, ai)] = le

    # ---- per page content rewrite
    parent_nums = Array()
    next_key = 0
    elem_page_mcids = defaultdict(list)  # elem objgen -> [(page index, mcid, order key)]
    stats = Counter()
    for pno, page in enumerate(pages):
        pa = an["pages"][pno]
        ops = pikepdf.parse_content_stream(page)
        if len(ops) != pa["nops"] or not pa["align_ok"]:
            raise PlanError(f"page {pno+1}: analysis does not align with the content stream")
        # op -> list of (elem, c0, c1, target, seg order)
        parts = defaultdict(list)
        for s in pa["segments"]:
            tgt = seg_target[s["id"]]
            for op, elem, c0, c1 in s["spans"]:
                parts[op].append((elem, c0, c1, tgt, order_of_seg[s["id"]], s.get("bpc", [1])))
        imgs_by_op = {}
        for n, im in enumerate(pa["images"]):
            iid = f"p{pno+1}i{n}"
            imgs_by_op.setdefault(im["op"], []).append((img_target.get(iid), img_key.get(iid, 0)))
        path_bbox = {p["op"]: p["bbox"] for p in pa["paths"]}
        mcid_owner = []   # index = mcid -> elem
        out = []
        def new_mcid(elem, okey):
            m = len(mcid_owner); mcid_owner.append(elem)
            elem_page_mcids[elem.objgen].append((pno, m, okey))
            return m
        run = {}   # the text sequence wrapped last: its owner, the index in `out` of its EMC, its segment's plan order
        def wrap(seq, elem, okey=0, text=False):
            key = elem.objgen if elem is not None else None
            if (text and run and run["key"] == key and okey == run["okey"]
                    and all(_op_name(x) in RUN_JOIN for x in out[run["emc"] + 1:])):
                # the same segment (one line: okey is its place in the plan) again, with only text positioning
                # between: one sequence, one MCID. Two segments never share one, so each line stays its own unit for
                # ocr_text_in_reading_order, and a reader that joins a sequence's text joins no two lines.
                del out[run["emc"]]
                out.extend(seq); run["emc"] = len(out); out.append(([], Operator("EMC")))
                stats["text_joined"] += 1
                return
            run.clear()
            if elem is None:
                out.append(([Name.Artifact], Operator("BMC"))); out.extend(seq); out.append(([], Operator("EMC")))
                stats["artifact"] += 1
            else:
                m = new_mcid(elem, okey)
                out.append(([elem.S, Dictionary(MCID=m)], Operator("BDC"))); out.extend(seq); out.append(([], Operator("EMC")))
                stats["mcid"] += 1
            if text:
                run.update(key=key, emc=len(out) - 1, okey=okey)
        mark_stack = []
        pathbuf = []
        def in_box(b, box):
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]
        for i, ins in enumerate(ops):
            name = str(ins.operator)
            if name in MARKS:
                if name in ("BDC", "BMC"):
                    keep = name == "BDC" and len(ins.operands) >= 1 and ins.operands[0] == Name.OC
                    mark_stack.append(keep)
                    if keep:
                        out.append(ins)
                elif name == "EMC":
                    keep = mark_stack.pop() if mark_stack else False
                    if keep:
                        out.append(ins)
                continue
            if name in PATH_BUILD or (name in ("W", "W*") and pathbuf):
                pathbuf.append(ins); continue
            if name in PATH_PAINT or name == "n":
                seq = pathbuf + [ins]; pathbuf = []
                if name == "n":
                    out.extend(seq); continue
                b = path_bbox.get(i)
                tgt, tkey = None, 0
                if b:
                    for box, e, k_ in path_targets.get(pno + 1, []):
                        if in_box(b, box):
                            tgt, tkey = e, k_; break
                wrap(seq, tgt, tkey); continue
            if pathbuf:  # a stray path op sequence not ended by paint: emit as is
                out.extend(pathbuf); pathbuf = []
            if name in TEXT_SHOW:
                pl = parts.get(i)
                if not pl:
                    wrap([ins], None, text=True); stats["text_unowned"] += 1; continue
                tgts = {id(p[3]) if p[3] is not None else None for p in pl}
                if len(tgts) == 1:
                    wrap([ins], pl[0][3], min(p[4] for p in pl), text=True); continue
                # split needed
                if any(0 in p[5] for p in pl):
                    owner = Counter(id(p[3]) for p in pl).most_common(1)[0][0]
                    p0 = next(p for p in pl if id(p[3]) == owner)
                    wrap([ins], p0[3], p0[4], text=True); stats["split_refused_unknown_cmap"] += 1; continue
                pre, seqs = split_text(ins, name, pl)
                out.extend(pre)
                for t_, ok_, seq_ in seqs:
                    wrap(seq_, t_, ok_, text=True)
                stats["split"] += 1
                continue
            if name in ("Do", "EI"):
                tl = imgs_by_op.get(i)
                pl = parts.get(i)
                if tl is not None and not pl:
                    tk = next((t for t in tl if t[0] is not None), (None, 0))
                    wrap([ins], tk[0], tk[1]); continue
                if pl:
                    owner = Counter(id(p[3]) for p in pl).most_common(1)[0][0]
                    p0 = next(p for p in pl if id(p[3]) == owner)
                    if len({id(p[3]) for p in pl}) > 1:
                        stats["form_multi_owner"] += 1
                    wrap([ins], p0[3], p0[4]); continue
                b = path_bbox.get(i)
                tgt, tkey = None, 0
                if b:
                    for box, e, k_ in path_targets.get(pno + 1, []):
                        if in_box(b, box):
                            tgt, tkey = e, k_; break
                wrap([ins], tgt, tkey); continue
            if name == "sh":
                wrap([ins], None); continue
            out.append(ins)
        if pathbuf:
            out.extend(pathbuf)
        if region_targets.get(pno + 1):
            form = region_form(pdf, page, ops)
            res = page.Resources
            if "/XObject" not in res:
                res.XObject = Dictionary()
            res.XObject[Name.PAFRegion] = form
            for box, e, k_ in region_targets[pno + 1]:
                x0, y0, x1, y1 = to_page_space(box, page, pa)
                wrap([([], Operator("q")), ([x0, y0, x1 - x0, y1 - y0], Operator("re")), ([], Operator("W")),
                      ([], Operator("n")), ([Name.PAFRegion], Operator("Do")), ([], Operator("Q"))], e, k_)
                stats["region"] += 1
        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(out))
        page.StructParents = next_key
        parent_nums.append(next_key); parent_nums.append(pdf.make_indirect(Array(mcid_owner)))
        next_key += 1
    # ---- strip old struct refs in forms / annots, then fill element K with MCRs in reading order
    for p in pages:
        for nm, xo in (p.Resources.get("/XObject") or {}).items():
            for k in ("/StructParents", "/StructParent"):
                if k in xo:
                    del xo[k]
    # ---- annotations: links and widgets get struct elements and /StructParent
    for nm in plan["splitfields"]:
        split_field(pdf, nm)
    seg_by_page = {p["page"]: p["segments"] for p in an["pages"]}
    widx = {}
    tu_set = set()
    for pno, page in enumerate(pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        page.Tabs = Name.S
        for ai, a in enumerate(annots):
            st = a.get("/Subtype")
            for k in ("/StructParent",):
                if k in a:
                    del a[k]
            if st == Name.Popup:
                continue
            if st == Name.Link:
                r = [float(x) for x in a.Rect]
                txt = " ".join(s["text"] for s in seg_by_page[pno + 1] if mostly_inside(s["bbox"], [min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])]))
                uri = a.get("/A", {}).get("/URI") if a.get("/A") is not None else None
                desc = plan["links"].get(f"{pno+1}:{ai}")
                if desc is None:
                    u = str(uri) if uri is not None else ""
                    desc = txt.strip() or (("Email " + u[7:]) if u.lower().startswith("mailto:") else u) or "link"
                a.Contents = String(desc[:300])
                le = link_elem[(pno, ai)]
                le.K.append(Dictionary(Type=Name.OBJR, Obj=a, Pg=page.obj))
                a.StructParent = next_key; parent_nums.append(next_key); parent_nums.append(le); next_key += 1
                stats["link"] += 1
            elif st == Name.Widget:
                f = a if "/T" in a else a.get("/Parent")
                full = field_name(f) if f is not None else None
                widx[full] = widx.get(full, 0) + 1
                own = f"{full}@{widx[full]}"
                label = plan["fields"].get(full) if full else None
                if label is None and own in plan["fields"]:
                    label = plan["fields"][own]
                if label is None:
                    raise PlanError(f"no FIELD label for widget {full!r} on page {pno+1}")
                if f.objgen not in tu_set:   # one TU per field; per-box labels go on each Form element's /Alt
                    f.TU = String(plan['fields'].get(full) or label); tu_set.add(f.objgen)
                slot = own if own in field_slot else full
                fe = mk("Form", field_slot[slot])
                fe.Pg = page.obj
                fe.K.append(Dictionary(Type=Name.OBJR, Obj=a, Pg=page.obj))
                if own in plan["fields"]:
                    fe.Alt = String(plan["fields"][own])
                explicit_key[fe.objgen] = field_key[slot] + ai * 1e-4
                a.StructParent = next_key; parent_nums.append(next_key); parent_nums.append(fe); next_key += 1
                stats["widget"] += 1
            else:
                # other annotations: hide nothing, tag as Annot
                ae = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.Annot, P=doc_el, Pg=page.obj,
                                                  K=Array([Dictionary(Type=Name.OBJR, Obj=a, Pg=page.obj)])))
                doc_el.K.append(ae)
                if "/Contents" not in a:
                    a.Contents = String(str(st)[1:])
                a.StructParent = next_key; parent_nums.append(next_key); parent_nums.append(ae); next_key += 1
                stats["annot_other"] += 1
    keymemo = {}
    def key_of(e):
        if e.objgen in keymemo:
            return keymemo[e.objgen]
        ks = [t[2] for t in elem_page_mcids.get(e.objgen, [])]
        if e.objgen in explicit_key:
            ks.append(explicit_key[e.objgen])
        for k in e.K:
            if isinstance(k, Dictionary) and k.get("/Type") == Name.StructElem:
                kk = key_of(k)
                if kk is not None:
                    ks.append(kk)
        keymemo[e.objgen] = min(ks) if ks else None
        return keymemo[e.objgen]
    def fill(e):
        mc = sorted(elem_page_mcids.get(e.objgen, []), key=lambda t: (t[2], t[0], t[1]))
        items = [(t[2], 0, Dictionary(Type=Name.MCR, Pg=pages[t[0]].obj, MCID=t[1])) for t in mc]
        for k in list(e.K):
            if isinstance(k, Dictionary) and k.get("/Type") == Name.StructElem:
                fill(k)
                kk = key_of(k)
                items.append((kk if kk is not None else 1e18, 1, k))
            else:
                items.append((1e18, 2, k))
        items.sort(key=lambda t: (t[0], t[1]))
        e.K = Array([t[2] for t in items])
        if mc:
            e.Pg = pages[mc[0][0]].obj
    fill(doc_el)
    stats["ocr_units_reordered"] = ocr_text_in_reading_order(pdf, doc_el, pages)
    st_root.ParentTree = pdf.make_indirect(Dictionary(Nums=parent_nums))
    st_root.ParentTreeNextKey = next_key
    root.StructTreeRoot = st_root
    root.MarkInfo = Dictionary(Marked=True)
    root.Lang = String(plan["lang"])
    vp = root.get("/ViewerPreferences") or Dictionary()
    vp.DisplayDocTitle = True; root.ViewerPreferences = vp
    if "/OCProperties" in root:
        ocp = root.OCProperties
        if "/D" in ocp and "/Name" not in ocp.D:
            ocp.D.Name = String("Default")
        for c in ocp.get("/Configs", []) or []:
            if "/Name" not in c:
                c.Name = String("Config")
    per_res = {k: v for k, v in plan["tounicode"].items() if re.fullmatch(r"p\d+:/\S+", k)}
    for k, mp in per_res.items():
        pg, rn = k.split(":", 1)
        fdict = pages[int(pg[1:]) - 1].Resources.Font[rn]
        fonts_fix.add_tounicode(pdf, fdict, mp)
    fonts_fixed = fonts_fix.fix(pdf, {k: v for k, v in plan["tounicode"].items() if k not in per_res})
    fonts_fixed["tounicode_by_resource"] = len(per_res)
    root.Metadata = pdf.make_stream(xmp(plan, pdf), Type=Name.Metadata, Subtype=Name.XML)
    pdf.docinfo["/Title"] = String(plan["title"])
    pdf.save(dst, encryption=False)
    print(json.dumps({"out": dst, **stats, "fonts": fonts_fixed}))

def xmp(plan, pdf):
    from xml.sax.saxutils import escape
    prod = escape(str(pdf.docinfo.get("/Producer", "")))
    t = escape(plan["title"]); lang = escape(plan["lang"])
    x = f'''<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
 xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">
<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{t}</rdf:li></rdf:Alt></dc:title>
<dc:language><rdf:Bag><rdf:li>{lang}</rdf:li></rdf:Bag></dc:language>
<pdf:Producer>{prod}</pdf:Producer>
<pdfuaid:part>1</pdfuaid:part>
</rdf:Description></rdf:RDF></x:xmpmeta>
<?xpacket end="w"?>'''
    pdf.docinfo["/Producer"] = String(str(pdf.docinfo.get("/Producer", "")))
    return x.encode("utf-8")

INHERIT = ("/FT", "/Ff", "/DA", "/Q", "/MaxLen", "/Opt", "/DV")

def split_field(pdf, name):
    """Make each widget of a shared-name field its own field '<name>_<k>' (k = 1.. in page order), so each box has its
    own label and value. The form's look is unchanged; checkboxes start unchecked unless that box showed checked."""
    af = pdf.Root.AcroForm
    target = None
    def find(fields, prefix=""):
        nonlocal target
        for f in fields:
            full = (prefix + "." if prefix else "") + str(f.get("/T", ""))
            if full == name:
                target = f; return
            if "/Kids" in f:
                find(f.Kids, full)
    find(af.Fields)
    if target is None or "/Kids" not in target:
        raise PlanError(f"SPLITFIELD: no field {name!r} with several widgets")
    order = []
    for pi, pg in enumerate(pdf.pages):
        for ai, a in enumerate(pg.get("/Annots") or []):
            if a.get("/Parent") is not None and a.Parent.objgen == target.objgen:
                order.append(a)
    parent = target.get("/Parent")
    holder = parent.Kids if parent is not None else af.Fields
    keep = [x for x in holder if x.objgen != target.objgen]
    for k, w in enumerate(order, 1):
        for key in INHERIT:
            v = target.get(key)
            if v is None and parent is not None:
                v = None
            if v is not None and key not in w:
                w[key] = v
        w.T = String(f"{str(target.T)}_{k}")
        on = w.get("/AS")
        if target.get("/FT") == Name.Btn:
            w.V = on if on is not None else Name.Off
        elif "/V" in target:
            w.V = target.V
        if "/TU" in target:
            w.TU = target.TU
        del w["/Parent"]
        if parent is not None:
            w.Parent = parent
        keep.append(w)
    if parent is not None:
        parent.Kids = Array(keep)
    else:
        af.Fields = Array(keep)

def field_name(f):
    parts = []
    while f is not None:
        if "/T" in f:
            parts.append(str(f.T))
        f = f.get("/Parent")
    return ".".join(reversed(parts))

def insert_form(doc_el, fe, annot, pno, pages):
    """Put the Form element just after the last top-level element whose first MCR is on this page and above the field."""
    doc_el.K.append(fe)  # reading position is refined by the reviewer; appended at the end by default
    fe.P = doc_el

def mostly_inside(b, r):
    ix = max(0, min(b[2], r[2]) - max(b[0], r[0])); iy = max(0, min(b[3], r[3]) - max(b[1], r[1]))
    area = max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / area >= 0.5

def overlap(b, r):
    return not (b[2] < r[0] or b[0] > r[2] or b[3] < r[1] or b[1] > r[3])

def region_form(pdf, page, ops):
    """A form XObject drawing what the page drew before tagging, without its text (BT..ET) and without marked-content
    operators. A FIG region: line draws it clipped to its box inside the Figure, so the Figure has the pixels of that
    part of a scanned page (a seal, a signature, a photo) without a second copy of any text."""
    keep, in_text = [], False
    for ins in ops:
        nm = str(ins.operator)
        if nm == "BT":
            in_text = True; continue
        if nm == "ET":
            in_text = False; continue
        if in_text or nm in MARKS:
            continue
        keep.append(ins)
    mb = [float(v) for v in page.MediaBox]
    return pdf.make_stream(pikepdf.unparse_content_stream(keep), Type=Name.XObject, Subtype=Name.Form,
                           BBox=Array(mb), Resources=page.Resources)

def to_page_space(box, page, pa):
    """A box in the analysis's coordinates (pdfminer's: page space moved to the MediaBox origin and, unless the page
    was analysed in page space, turned by /Rotate) back in page space."""
    x0, y0, x1, y1 = [float(v) for v in page.MediaBox]
    rot = 0 if pa.get("user_space") else int(page.obj.get("/Rotate", 0)) % 360
    a, b, c, d, e, f = {90: (0, -1, 1, 0, -y0, x1), 180: (-1, 0, 0, -1, x1, y1), 270: (0, 1, -1, 0, y1, -x0)}.get(
        rot, (1, 0, 0, 1, -x0, -y0))
    det = a * d - b * c
    def inv(u, v):
        u, v = u - e, v - f
        return ((d * u - c * v) / det, (-b * u + a * v) / det)
    pts = [inv(box[0], box[1]), inv(box[2], box[3])]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

def _op_name(x):
    """The operator name of an output op: a parsed instruction or an (operands, Operator) pair."""
    return str(x.operator) if hasattr(x, "operator") else str(x[1])


OCR_FONT = "PAFGlyphless"

# Operators a unit of the OCR text block may hold: each unit sets its own position (Tm) and draws invisibly.
OCR_UNIT_OPS = {"Tm", "Tz", "Tf", "Tj", "TJ", "BDC", "BMC", "EMC"}


def ocr_text_in_reading_order(pdf, doc_el, pages):
    """Re-emit each page's OCR text block (the invisible text `start` wrote, in Tesseract's order) in the structure's
    reading order, so a viewer that reads the page's text in content order rather than by its tags (Chromium's PDF
    viewer, pdf.js) reads it as the plan does. A unit is a Tm outside marked content and what follows it up to the next
    such Tm (so a marked sequence holding several words moves as one); units move whole, so every glyph keeps its
    position and the page looks the same. A marked sequence drawn on from another one with no Tm of its own (the second
    part of a word op the plan gave to two elements) first gets a Tm at the text position the glyphs before it reached,
    with the Tz and Tf in force (`_cut_drawn_on`), so it is a unit of its own: without that it moved with the other
    element's line (04-report pages 15 and 23, helper pdf-access-fixer-pdfium-order). A block holding anything else (a
    relative move, a state change, unbalanced marks, another font) is left as it is. Returns the number of units that
    moved."""
    index = {p.obj.objgen: i for i, p in enumerate(pages)}
    order = {}

    def walk(e, pg=None):
        if isinstance(e, Array):
            for x in e:
                walk(x, pg)
        elif isinstance(e, Dictionary):
            if e.get("/Type") == Name.MCR:
                order.setdefault((index.get(e.Pg.objgen, pg), int(e.MCID)), len(order))
                return
            if "/Pg" in e:
                pg = index.get(e.Pg.objgen, pg)
            if "/K" in e:
                walk(e.K, pg)
        elif isinstance(e, int) and pg is not None:
            order.setdefault((pg, int(e)), len(order))

    walk(doc_el)
    moved = 0
    for pi, page in enumerate(pages):
        ops = pikepdf.parse_content_stream(page)
        names = [str(o.operator) for o in ops]
        em = _ocr_glyph_width(page)
        out, changed, i = [], False, 0
        while i < len(ops):
            if names[i] != "BT":
                out.append(ops[i]); i += 1
                continue
            try:
                e = names.index("ET", i)
            except ValueError:
                out.extend(ops[i:]); break
            block, bnames = ops[i:e + 1], names[i:e + 1]
            if em is not None and _ocr_units(block, bnames, pi, order) is not None:
                block = _cut_drawn_on(block, bnames, em)
                bnames = [str(o.operator) for o in block]
                changed = changed or len(block) != e + 1 - i
            units = _ocr_units(block, bnames, pi, order)
            if units is None:
                out.extend(block)
            else:
                head, body = units
                srt = sorted(body, key=lambda u: (u[0], u[1]))
                n = sum(1 for a, b in zip(body, srt) if a[1] != b[1])
                moved += n
                changed = changed or n > 0
                out.extend(head + [o for _, _, u in srt for o in u] + [block[-1]])
            i = e + 1
        if changed:
            page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(out))
    return moved


def _ocr_glyph_width(page):
    """The advance of every glyph of the OCR stage's font on this page, in text space units per unit of font size (its
    /DW over 1000), or None when the page has no such font or it is not the stage's own: a Type0 font with 2-byte codes
    (Identity-H) and one default width, no /W."""
    try:
        font = page.Resources.Font.get("/" + OCR_FONT)
        if font is None or str(font.get("/Encoding")) != "/Identity-H":
            return None
        cid = font.DescendantFonts[0]
        if "/W" in cid or "/DW" not in cid:
            return None
        return float(cid.DW) / 1000
    except (AttributeError, KeyError, IndexError, TypeError):
        return None


def _cut_drawn_on(block, names, em):
    """`block` with a Tm, Tz and Tf inserted before each marked sequence outside marked content that is drawn on from
    another one since the last Tm. The Tm is the last one moved along its baseline by the advance of the glyphs shown
    since (`em` per glyph and font size, less each TJ number, times Tz), so the sequence's glyphs stay where they were."""
    out = []
    level, tm, tz, tf, tx, closed = 0, None, 100.0, None, 0.0, False
    for o, n in zip(block, names):
        if n in ("BDC", "BMC") and level == 0 and closed and tm is not None and tf is not None:
            a, b, c, d, e, f = tm
            tm = [a, b, c, d, e + tx * a, f + tx * b]
            out += [pikepdf.ContentStreamInstruction([round(v, 5) for v in tm], Operator("Tm")),
                    pikepdf.ContentStreamInstruction([round(tz, 5)], Operator("Tz")),
                    pikepdf.ContentStreamInstruction([tf[0], tf[1]], Operator("Tf"))]
            tx, closed = 0.0, False
        if n == "Tm":
            tm, tx, closed = [float(x) for x in o.operands], 0.0, False
        elif n == "Tz":
            tz = float(o.operands[0])
        elif n == "Tf":
            tf = (o.operands[0], o.operands[1])
        elif n in ("Tj", "TJ") and tf is not None:
            size, h = float(tf[1]), tz / 100
            for it in ([o.operands[0]] if n == "Tj" else list(o.operands[0])):
                if isinstance(it, pikepdf.String):
                    tx += len(bytes(it)) // 2 * em * size * h
                else:
                    tx -= float(it) / 1000 * size * h
        elif n in ("BDC", "BMC"):
            level += 1
        elif n == "EMC":
            level -= 1
            closed = closed or level == 0
        out.append(o)
    return out


def _ocr_units(block, names, pi, order):
    """(head ops, [(reading-order key, position, unit ops)]) for an OCR text block BT ... ET, or None if it is not one."""
    inner = names[1:-1]
    if "Tm" not in inner or not any(n == "Tr" and str(o.operands[0]) == "3" for o, n in zip(block, names)):
        return None
    first = names.index("Tm")
    head, body, depth = block[:first], [], 0
    if any(n not in ("BT", "Tr") for n in names[:first]):
        return None
    starts, level = [], 0
    for k in range(first, len(names) - 1):
        if names[k] == "Tm" and level == 0:
            starts.append(k)
        elif names[k] in ("BDC", "BMC"):
            level += 1
        elif names[k] == "EMC":
            level -= 1
    for j, k in enumerate(starts):
        end = starts[j + 1] if j + 1 < len(starts) else len(names) - 1
        unit, keys = block[k:end], []
        for o, n in zip(unit, names[k:end]):
            if n not in OCR_UNIT_OPS:
                return None
            if n == "Tf" and str(o.operands[0]) != "/" + OCR_FONT:
                return None
            if n in ("BDC", "BMC"):
                depth += 1
                props = o.operands[1] if n == "BDC" and len(o.operands) > 1 else None
                if isinstance(props, Dictionary) and "/MCID" in props:
                    keys.append(order.get((pi, int(props.MCID)), float("inf")))
            elif n == "EMC":
                depth -= 1
        if depth != 0:
            return None
        body.append((min(keys) if keys else float("inf"), j, list(unit)))
    return list(head), body

def correct_ocr_text(pdf, an, fixes):
    """TEXT <seg> | <text>: replace what an OCR segment says (its text is invisible, so the page looks the same). The
    corrected text goes into the segment's first text op, stretched (Tz) over the width all its ops covered; the other
    ops draw an empty string, so the op count, and every op index of the analysis, stays the same. The segment's chars
    and spans are updated, so slices ([a:b]) and the coverage check read the corrected text."""
    if not fixes:
        return
    segs = {s["id"]: (p, s) for p in an["pages"] for s in p["segments"]}
    by_page = defaultdict(list)
    for sid, txt in fixes.items():
        if sid not in segs:
            raise PlanError(f"TEXT names unknown segment {sid}")
        p, s = segs[sid]
        if OCR_FONT not in s.get("font", ""):
            raise PlanError(f"TEXT {sid}: only text the OCR stage wrote can be corrected (font {s.get('font')!r})")
        if not txt:
            raise PlanError(f"TEXT {sid}: empty text (to drop a misread, mark the segment ART)")
        by_page[p["page"]].append((s, txt))
    for pno, items in by_page.items():
        page = pdf.pages[pno - 1]
        ops = list(pikepdf.parse_content_stream(page))
        for s, txt in items:
            idx = sorted({sp[0] for sp in s["spans"]})
            if any(str(ops[i].operator) != "Tj" for i in idx):
                raise PlanError(f"TEXT {s['id']}: not an OCR text segment")
            def state(i):   # the Tz and Tf in force for op i (the OCR stage sets both right before each word)
                tz = size = None
                for j in range(i - 1, -1, -1):
                    nm = str(ops[j].operator)
                    if nm == "Tz" and tz is None:
                        tz = (j, float(ops[j].operands[0]))
                    elif nm == "Tf" and size is None:
                        size = float(ops[j].operands[1])
                    if tz is not None and size is not None:
                        return tz, size
                raise PlanError(f"TEXT {s['id']}: no Tz/Tf before op {i}")
            total = 0.0
            for i in idx:
                (_, tz), size = state(i)
                total += 0.5 * size * (len(bytes(ops[i].operands[0])) // 2) * tz / 100
            (tzi, _), size = state(idx[0])
            codes = [ord(ch) if ord(ch) <= 0xFFFF else 0xFFFD for ch in txt]
            ops[tzi] = pikepdf.ContentStreamInstruction([round(100 * total / (0.5 * size * len(codes)), 3)], Operator("Tz"))
            ops[idx[0]] = pikepdf.ContentStreamInstruction(
                [pikepdf.String(b"".join(c.to_bytes(2, "big") for c in codes))], Operator("Tj"))
            for i in idx[1:]:
                ops[i] = pikepdf.ContentStreamInstruction([pikepdf.String(b"")], Operator("Tj"))
            add_to_unicode(page, codes)
            s["chars"] = txt; s["text"] = txt; s["spans"] = [[idx[0], 0, 0, len(codes)]]; s["bpc"] = [2]
        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(ops))

def add_to_unicode(page, codes):
    """Make sure the OCR font's ToUnicode maps every code a correction uses (each code means its own character)."""
    font = page.Resources.Font.get("/" + OCR_FONT)
    if font is None or "/ToUnicode" not in font:
        return
    cmap = font.ToUnicode.read_bytes().decode("ascii")
    have = set(int(h, 16) for h in re.findall(r"<([0-9A-F]{4})> <[0-9A-F]{4}>", cmap))
    new = sorted(set(codes) - have)
    if not new:
        return
    extra = []
    for i in range(0, len(new), 100):
        chunk = new[i:i + 100]
        extra.append(f"{len(chunk)} beginbfchar")
        extra += [f"<{c:04X}> <{c:04X}>" for c in chunk]
        extra.append("endbfchar")
    cmap = cmap.replace("endcmap", "\n".join(extra) + "\nendcmap", 1)
    font.ToUnicode.write(cmap.encode("ascii"))

def split_text(ins, name, pl):
    """Split one text-show op into consecutive TJ pieces, one per owner run. pl: (elem, c0, c1, target, okey, bpc).
    Returns (ops to emit first, [(target, order key, [ops])]). The text position carries on between pieces."""
    if name == "TJ":
        arr = list(ins.operands[0]); pre = []
    elif name == "Tj":
        arr = [ins.operands[0]]; pre = []
    elif name == "'":
        arr = [ins.operands[0]]; pre = [([], Operator("T*"))]
    else:  # '"'
        aw, ac, s = ins.operands
        arr = [s]; pre = [([aw], Operator("Tw")), ([ac], Operator("Tc")), ([], Operator("T*"))]
    bpc = max(max(p[5]) for p in pl)
    owner = {}
    for elem, c0, c1, tgt, ok, _ in pl:
        for c in range(c0, c1):
            owner[(elem, c)] = (tgt, ok)
    runs, lead = [], []
    for ei, el in enumerate(arr):
        if not isinstance(el, pikepdf.String):
            if runs:
                runs[-1][2].append(el)
            else:
                lead.append(el)
            continue
        b = bytes(el)
        n = len(b) // bpc
        for c in range(n):
            if (ei, c) in owner:
                o = owner[(ei, c)]
            elif runs:
                o = (runs[-1][0], runs[-1][1])
            else:
                o = (pl[0][3], pl[0][4])
            piece = b[c * bpc:(c + 1) * bpc]
            if runs and runs[-1][0] is o[0]:
                items = runs[-1][2]
                if items and isinstance(items[-1], bytes):
                    items[-1] += piece
                else:
                    items.append(piece)
            else:
                runs.append([o[0], o[1], lead + [piece]]); lead = []
        rest = b[n * bpc:]
        if rest and runs:
            runs[-1][2].append(rest)
    seqs = [(t, ok, [([Array([pikepdf.String(x) if isinstance(x, bytes) else x for x in items])], Operator("TJ"))])
            for t, ok, items in runs]
    return pre, seqs

def fix_fonts(pdf):
    """CIDSet / CharSet removal (an optional key that, when wrong, fails 7.21.4.2). Returns counts."""
    n = Counter()
    seen = set()
    for page in pdf.pages:
        for fdict in iter_fonts(page.Resources):
            if fdict.objgen in seen:
                continue
            seen.add(fdict.objgen)
            fds = []
            if "/FontDescriptor" in fdict:
                fds.append(fdict.FontDescriptor)
            for d in fdict.get("/DescendantFonts", []) or []:
                if "/FontDescriptor" in d:
                    fds.append(d.FontDescriptor)
            for fd in fds:
                for k in ("/CIDSet", "/CharSet"):
                    if k in fd:
                        del fd[k]; n["removed" + k[1:]] += 1
    return dict(n)

def iter_fonts(res, depth=0):
    if res is None or depth > 6:
        return
    for nm, f in (res.get("/Font") or {}).items():
        yield f
        if f.get("/Subtype") == Name.Type3 and "/Resources" in f:
            yield from iter_fonts(f.Resources, depth + 1)
    for nm, xo in (res.get("/XObject") or {}).items():
        if xo.get("/Subtype") == Name.Form and "/Resources" in xo:
            yield from iter_fonts(xo.Resources, depth + 1)

if __name__ == "__main__":
    main(*sys.argv[1:5])
