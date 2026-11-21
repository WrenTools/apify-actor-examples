"""Round 15: draft a tagging plan from an analysis (heuristics only; a person reviews and corrects it before apply).
Use: venv/Scripts/python -I -X utf8 propose.py analysis.json plan.txt [title]
Each plan line carries the segment texts as a '#' comment so the reviewer reads the plan beside the page image.
"""
import json, re, sys
from collections import Counter

BULLET = re.compile(r"^\s*([•▪◦●○■□‣⁃\-–*]|\(?\d{1,2}[.)]|\(?[a-zA-Z][.)]|[ivxIVX]{1,4}\.)\s+")
PAGENUM = re.compile(r"^\s*(page\s*)?\d+(\s*(of|/)\s*\d+)?\s*$", re.I)

def norm(t):
    return re.sub(r"\d+", "#", t.strip().lower())

OCR_FONT = "PAFGlyphless"

def unsure_by_segment(an, ocr_report):
    """Segment id -> words OCR read with low confidence inside it (from the OCR stage's report)."""
    out = {}
    if not ocr_report:
        return out
    for pr in ocr_report.get("pages", []):
        pa = an["pages"][pr["page"] - 1]
        ox, oy = (pa["box"][0], pa["box"][1])
        for w in pr.get("unsure_words", []):
            cx = (w["bbox"][0] + w["bbox"][2]) / 2 - ox; cy = (w["bbox"][1] + w["bbox"][3]) / 2 - oy
            for s in pa["segments"]:
                b = s["bbox"]
                if b[0] - 1 <= cx <= b[2] + 1 and b[1] - 1 <= cy <= b[3] + 1:
                    out.setdefault(s["id"], []).append(f"{w['text']} ({w['conf']})")
                    break
    return out

def main(src, dst, title=None, ocr_path=None):
    an = json.load(open(src, encoding="utf-8"))
    ocr_report = json.load(open(ocr_path, encoding="utf-8")) if ocr_path else None
    unsure = unsure_by_segment(an, ocr_report)
    sizes = Counter()
    for p in an["pages"]:
        for s in p["segments"]:
            sizes[s["size"]] += len(s["text"])
    body = sizes.most_common(1)[0][0] if sizes else 10
    big = sorted({s for s in sizes if s >= body * 1.18}, reverse=True)
    level = {s: min(i + 1, 6) for i, s in enumerate(big)}
    # repeated top/bottom text across pages
    edge = Counter()
    for p in an["pages"]:
        h = p["box"][3] - p["box"][1]
        for s in p["segments"]:
            if s["bbox"][1] > p["box"][1] + 0.93 * h or s["bbox"][3] < p["box"][1] + 0.07 * h:
                edge[norm(s["text"])] += 1
    lines = [f"title: {title or 'TODO'}", "lang: en-US", f"# body size {body}; heading sizes {big}"]
    def c(segs):
        low = [w for s in segs for w in unsure.get(s["id"], [])]
        return "  # " + " / ".join(s["text"][:60] for s in segs) + (
            ("  [OCR unsure: " + ", ".join(low) + "]") if low else "")
    for p in an["pages"]:
        lines.append(f"# ---- page {p['page']}")
        h = p["box"][3] - p["box"][1]
        cur = None  # (role, [segs])
        out = []
        def flush():
            nonlocal cur
            if cur:
                out.append(cur)
            cur = None
        prev = None
        for s in p["segments"]:
            t = s["text"].strip()
            at_edge = s["bbox"][1] > p["box"][1] + 0.93 * h or s["bbox"][3] < p["box"][1] + 0.07 * h
            if not t or (at_edge and (PAGENUM.match(t) or (len(an["pages"]) > 1 and edge[norm(s["text"])] >= 2))):
                flush(); out.append(("ART", [s])); prev = None; continue
            if s["size"] in level:
                role = f"H{level[s['size']]}"
            elif BULLET.match(t):
                role = "LI"
            else:
                role = "P"
            cont = False
            if cur and prev is not None:
                gap = prev["bbox"][1] - s["bbox"][3]
                same = abs(prev["size"] - s["size"]) < 0.6 and prev["bold"] == s["bold"]
                near = -0.5 * s["size"] < gap < 0.9 * s["size"]
                if cur[0] == "P" and role == "P" and same and near:
                    cont = True
                if cur[0] == "LI" and role == "P" and near and s["bbox"][0] > cur[1][0]["bbox"][0] + 2:
                    cont = True
                if cur[0].startswith("H") and role == cur[0] and near:
                    cont = True
            if cont:
                cur[1].append(s)
            else:
                flush(); cur = (role, [s])
            prev = s
        flush()
        inlist = False
        for role, segs in out:
            ids = " ".join(x["id"] for x in segs)
            if role == "LI" and not inlist:
                lines.append("L"); inlist = True
            if role != "LI" and inlist:
                lines.append("/L"); inlist = False
            lines.append((" " if role == "LI" else "") + f"{role} {ids}{c(segs)}")
        if inlist:
            lines.append("/L")
        scanned = any(OCR_FONT in s.get("font", "") for s in p["segments"])
        for n, im in enumerate(p["images"]):
            if scanned:   # the scan itself: its words are the OCR text, so the image is drawn as an artifact
                lines.append(f"DECO p{p['page']}i{n}  # scanned page image {im['px']} at {im['bbox']}; show a photo, "
                             f"seal, chart or signature in it with FIG region:{p['page']}:<x0>,<y0>,<x1>,<y1> | <alt>")
            else:
                lines.append(f"FIG p{p['page']}i{n} | TODO alt  # image {im['px']} at {im['bbox']}")
        for a in p["annots"]:
            if a.get("subtype") == "/Widget" and a.get("T"):
                lines.append(f"FIELD {a['T']} | {a.get('TU') or a['T']}  # {a.get('FT')} at {[round(x) for x in a['rect']]}")
    open(dst, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(dst, len(lines), "lines; body", body, "headings", big)

if __name__ == "__main__":
    main(*sys.argv[1:])
