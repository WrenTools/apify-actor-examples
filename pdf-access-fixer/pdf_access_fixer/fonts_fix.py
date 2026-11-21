"""Round 15, route (a): font repairs that PDF/UA-1 needs and that leave the page looking the same.
- A simple TrueType font with no font program (Word's unembedded Arial, Times New Roman, Arial Narrow...) gets the
  matching system font embedded (Windows' own files; Arial Narrow -> Liberation Sans Narrow, metric-compatible, SIL OFL),
  subset to WinAnsi, with the program's advance widths set to the PDF's own /Widths so text positions do not move.
- ZapfDingbats (unembedded, used by form-field check marks) becomes an embedded symbolic TrueType font built from
  Segoe UI Symbol's glyphs for the same Unicode characters, with a ToUnicode map (Adobe's ZapfDingbats-to-Unicode table).
- Extra ToUnicode entries the plan supplies (TOUNICODE lines) for glyphs with no Unicode meaning in the file.
Every reachable font is visited: page resources, form XObjects, annotation appearance streams, AcroForm /DR.
"""
import io, re
from collections import Counter
import pikepdf
from pikepdf import Name, Dictionary, Array, String
from fontTools.ttLib import TTFont
from fontTools import subset as ftsubset
from fontTools.ttLib.tables._c_m_a_p import cmap_format_4

WF = r"C:\Windows\Fonts\\"
MAP = {
    "arial": "arial.ttf", "arialbold": "arialbd.ttf", "arialitalic": "ariali.ttf", "arialbolditalic": "arialbi.ttf",
    "arialnarrow": "LiberationSansNarrow-Regular.ttf", "arialnarrowbold": "LiberationSansNarrow-Bold.ttf",
    "arialnarrowitalic": "LiberationSansNarrow-Italic.ttf", "arialnarrowbolditalic": "LiberationSansNarrow-BoldItalic.ttf",
    "timesnewroman": "times.ttf", "timesnewromanbold": "timesbd.ttf", "timesnewromanitalic": "timesi.ttf",
    "timesnewromanbolditalic": "timesbi.ttf", "couriernew": "cour.ttf", "couriernewbold": "courbd.ttf",
    "couriernewitalic": "couri.ttf", "couriernewbolditalic": "courbi.ttf", "georgia": "georgia.ttf",
    "georgiabold": "georgiab.ttf", "georgiaitalic": "georgiai.ttf", "georgiabolditalic": "georgiaz.ttf",
    "calibri": "calibri.ttf", "calibribold": "calibrib.ttf", "calibriitalic": "calibrii.ttf", "calibribolditalic": "calibriz.ttf",
    "helvetica": "LiberationSans-Regular.ttf", "helveticabold": "LiberationSans-Bold.ttf",
}

def norm(basefont):
    b = re.sub(r"^[A-Z]{6}\+", "", basefont.lstrip("/"))
    b = b.lower().replace("-", "").replace(",", "").replace(" ", "")
    b = re.sub(r"mt$", "", b)
    b = re.sub(r"ps(?=(bold|italic|$))", "", b)
    b = b.replace("oblique", "italic")
    return b

# Adobe ZapfDingbats code -> Unicode (codes 0x21-0x7E; the exceptions to U+2700+(c-0x20))
ZAPF_EXC = {0x25: 0x260E, 0x2A: 0x261B, 0x2B: 0x261E, 0x48: 0x2605, 0x6C: 0x25CF, 0x6E: 0x25A0, 0x73: 0x25B2,
            0x74: 0x25BC, 0x75: 0x25C6, 0x77: 0x25D7}
def zapf_uni(c):
    return ZAPF_EXC.get(c, 0x2700 + (c - 0x20))

def walk_res(res, seen, out, depth=0):
    if res is None or depth > 8 or not isinstance(res, Dictionary):
        return
    for nm, f in (res.get("/Font") or {}).items():
        key = f.objgen if f.is_indirect else id(f)
        if key not in seen:
            seen.add(key); out.append(f)
        if f.get("/Subtype") == Name.Type3:
            walk_res(f.get("/Resources"), seen, out, depth + 1)
    for nm, xo in (res.get("/XObject") or {}).items():
        if xo.get("/Subtype") == Name.Form:
            walk_res(xo.get("/Resources"), seen, out, depth + 1)

def all_fonts(pdf):
    seen, out = set(), []
    for p in pdf.pages:
        walk_res(p.get("/Resources"), seen, out)
        for a in p.get("/Annots") or []:
            ap = a.get("/AP")
            if ap is None:
                continue
            for k in ("/N", "/D", "/R"):
                v = ap.get(k)
                if v is None:
                    continue
                streams = [v] if isinstance(v, pikepdf.Stream) else [v[s] for s in v.keys()] if isinstance(v, Dictionary) else []
                for s in streams:
                    if isinstance(s, pikepdf.Stream):
                        walk_res(s.get("/Resources"), seen, out)
    af = pdf.Root.get("/AcroForm")
    if af is not None:
        walk_res(af.get("/DR"), seen, out)
    return out

def used_codes(pdf):
    """Font dict objgen -> set of codes shown, from every content stream that names it (approximate: Tf + strings)."""
    return None

def ttf_program(path, widths_by_code, first, enc="cp1252"):
    f = TTFont(path)
    upem = f["head"].unitsPerEm
    cmap = f.getBestCmap()
    unis = set()
    for code in range(256):
        try:
            ch = bytes([code]).decode(enc)
        except UnicodeDecodeError:
            continue
        if ord(ch) in cmap:
            unis.add(ord(ch))
    opts = ftsubset.Options(); opts.notdef_outline = True; opts.name_IDs = ["*"]; opts.layout_features = []
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "kern", "DSIG"]
    sub = ftsubset.Subsetter(opts); sub.populate(unicodes=unis); sub.subset(f)
    cmap = f.getBestCmap(); hmtx = f["hmtx"]
    changed = 0
    for code, w in sorted(widths_by_code.items(), key=lambda kv: -kv[1]):
        if w <= 0:
            continue  # an unused code (Word writes 0): never let it change a shared glyph
        try:
            ch = bytes([code]).decode(enc)
        except UnicodeDecodeError:
            continue
        g = cmap.get(ord(ch))
        if g is None:
            continue
        adv, lsb = hmtx[g]
        want = round(w * upem / 1000)
        if abs(adv * 1000 / upem - w) > 0.5:
            hmtx[g] = (want, lsb); changed += 1
    buf = io.BytesIO(); f.save(buf)
    return buf.getvalue(), changed, f

def embed_truetype(pdf, fd, path):
    first = int(fd.get("/FirstChar", 0)); ws = [float(x) for x in fd.get("/Widths", [])]
    wbc = {first + i: w for i, w in enumerate(ws)}
    data, changed, f = ttf_program(path, wbc, first)
    st = pdf.make_stream(data); st.Length1 = len(data)
    desc = fd.get("/FontDescriptor")
    if desc is None:
        desc = pdf.make_indirect(Dictionary(Type=Name.FontDescriptor, FontName=fd.BaseFont, Flags=32,
                                            FontBBox=Array([-200, -250, 1200, 950]), ItalicAngle=0, Ascent=900,
                                            Descent=-210, CapHeight=700, StemV=80))
        fd.FontDescriptor = desc
    desc.FontFile2 = st
    if "/Widths" not in fd:  # standard-14 converted: widths from the program
        hm, cm, upem = f["hmtx"], f.getBestCmap(), f["head"].unitsPerEm
        fd.FirstChar = 32; fd.LastChar = 255
        arr = []
        for c in range(32, 256):
            try:
                g = cm.get(ord(bytes([c]).decode("cp1252")))
            except UnicodeDecodeError:
                g = None
            arr.append(round(hm[g][0] * 1000 / upem) if g else 0)
        fd.Widths = Array(arr)
    return changed

def build_zapf(pdf, fd):
    f = TTFont(WF + "seguisym.ttf")
    cm = f.getBestCmap()
    codes = [c for c in range(0x21, 0x7F) if zapf_uni(c) in cm]
    opts = ftsubset.Options(); opts.notdef_outline = True; opts.layout_features = []; opts.name_IDs = ["*"]
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "kern", "DSIG", "morx", "feat"]
    sub = ftsubset.Subsetter(opts); sub.populate(unicodes={zapf_uni(c) for c in codes}); sub.subset(f)
    cm = f.getBestCmap()
    t = cmap_format_4(4); t.platformID = 3; t.platEncID = 0; t.language = 0
    t.cmap = {0xF000 + c: cm[zapf_uni(c)] for c in codes if zapf_uni(c) in cm}
    f["cmap"].tables = [t]
    upem = f["head"].unitsPerEm; hm = f["hmtx"]
    buf = io.BytesIO(); f.save(buf); data = buf.getvalue()
    st = pdf.make_stream(data); st.Length1 = len(data)
    head = f["head"]; os2 = f["OS/2"]
    sc = lambda v: round(v * 1000 / upem)
    desc = pdf.make_indirect(Dictionary(Type=Name.FontDescriptor, FontName=Name("/SAHDingbats"), Flags=4,
                                        FontBBox=Array([sc(head.xMin), sc(head.yMin), sc(head.xMax), sc(head.yMax)]),
                                        ItalicAngle=0, Ascent=sc(os2.sTypoAscender), Descent=sc(os2.sTypoDescender),
                                        CapHeight=sc(getattr(os2, "sCapHeight", 700) or 700), StemV=80, FontFile2=st))
    for k in list(fd.keys()):
        if k not in ("/Type",):
            del fd[k]
    fd.Type = Name.Font; fd.Subtype = Name.TrueType; fd.BaseFont = Name("/SAHDingbats"); fd.FontDescriptor = desc
    fd.FirstChar = 0x21; fd.LastChar = 0x7E
    fd.Widths = Array([sc(hm[cm[zapf_uni(c)]][0]) if zapf_uni(c) in cm else 0 for c in range(0x21, 0x7F)])
    lines = [f"<{c:02X}> <{zapf_uni(c):04X}>" for c in codes]
    fd.ToUnicode = pdf.make_stream(tounicode_cmap(lines))

def tounicode_cmap(bfchar_lines):
    out = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
           "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def", "/CMapName /SAH-UCS def",
           "/CMapType 2 def", "1 begincodespacerange", "<00> <FF>", "endcodespacerange"]
    for i in range(0, len(bfchar_lines), 100):
        chunk = bfchar_lines[i:i + 100]
        out.append(f"{len(chunk)} beginbfchar"); out.extend(chunk); out.append("endbfchar")
    out += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(out).encode("ascii")

def parse_tounicode(data):
    """code -> text from an existing ToUnicode CMap (bfchar and bfrange, both forms)."""
    m = {}
    t = data.decode("latin-1")
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", t, re.S):
        for c, u in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            m[int(c, 16)] = bytes.fromhex(u).decode("utf-16-be", "replace") if u else ""
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", t, re.S):
        for c0, c1, rest in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)", blk):
            c0, c1 = int(c0, 16), int(c1, 16)
            if rest.startswith("["):
                for i, u in enumerate(re.findall(r"<([0-9A-Fa-f]*)>", rest)):
                    m[c0 + i] = bytes.fromhex(u).decode("utf-16-be", "replace")
            else:
                ub = bytes.fromhex(rest[1:-1])
                base = int.from_bytes(ub, "big")
                for i in range(c1 - c0 + 1):
                    m[c0 + i] = (base + i).to_bytes(len(ub), "big").decode("utf-16-be", "replace")
    return m

def plan_text(v):
    """A TOUNICODE value: literal text, or U+XXXX[ U+XXXX...] (so a space can be written as U+0020)."""
    v = v.strip()
    if re.fullmatch(r"(U\+[0-9A-Fa-f]{4,6}\s*)+", v):
        return "".join(chr(int(x, 16)) for x in re.findall(r"U\+([0-9A-Fa-f]{4,6})", v))
    return v

def add_tounicode(pdf, fd, mapping):
    """mapping: code -> text, merged over the font's existing ToUnicode (if any)."""
    two = fd.get("/Subtype") == Name.Type0
    cur = parse_tounicode(fd.ToUnicode.read_bytes()) if "/ToUnicode" in fd else {}
    for code, text in mapping.items():
        cur[code] = plan_text(text)
    lines = []
    for code, text in sorted(cur.items()):
        hexu = "".join(f"{b:02X}" for b in text.encode("utf-16-be"))
        lines.append(f"<{code:04X}> <{hexu}>" if two else f"<{code:02X}> <{hexu}>")
    data = tounicode_cmap(lines)
    if two:
        data = data.replace(b"<00> <FF>", b"<0000> <FFFF>")
    fd.ToUnicode = pdf.make_stream(data)

def fix(pdf, tounicode_plan=None):
    n = Counter()
    for fd in all_fonts(pdf):
        st = fd.get("/Subtype"); bf = str(fd.get("/BaseFont", ""))
        desc = fd.get("/FontDescriptor")
        descs = [desc] if desc is not None else []
        for d in fd.get("/DescendantFonts", []) or []:
            if d.get("/FontDescriptor") is not None:
                descs.append(d.FontDescriptor)
        for d in descs:
            for k in ("/CIDSet", "/CharSet"):
                if k in d:
                    del d[k]; n["removed" + k[1:]] += 1
        embedded = any(k in d for d in descs for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        if tounicode_plan:
            for key, mp in tounicode_plan.items():
                if key == bf.lstrip("/") or norm(key) == norm(bf):
                    add_tounicode(pdf, fd, mp); n["tounicode_from_plan"] += 1
        if embedded and st != Name.Type3:
            try:
                ch = fix_embedded_widths(pdf, fd)
            except Exception as e:  # a font program fontTools cannot read: leave it as it is (veraPDF judges)
                ch = 0; n['width_fix_error'] += 1
            if ch:
                n["embedded_width_fixed"] += ch
        if embedded or st == Name.Type3:
            continue
        nb = norm(bf)
        if nb in ("zapfdingbats", "zadb"):
            build_zapf(pdf, fd); n["zapf_built"] += 1; continue
        if nb in MAP and st in (Name.TrueType, Name.Type1):
            if st == Name.Type1:
                enc = fd.get("/Encoding")
                if enc is None:
                    fd.Subtype = Name.TrueType
                    fd.Encoding = Dictionary(Type=Name.Encoding, BaseEncoding=Name.WinAnsiEncoding, Differences=std_differences(pdf))
                elif enc == Name.WinAnsiEncoding:
                    fd.Subtype = Name.TrueType
                elif isinstance(enc, Dictionary) and enc.get("/BaseEncoding") in (None, Name.WinAnsiEncoding):
                    merged = {}
                    if enc.get("/BaseEncoding") is None:
                        da = list(std_differences(pdf))
                        for k in range(0, len(da), 2):
                            merged[int(da[k])] = da[k + 1]
                    code = 0
                    for x in enc.get("/Differences", []):
                        if isinstance(x, Name):
                            merged[code] = x; code += 1
                        else:
                            code = int(x)
                    arr = Array()
                    for c in sorted(merged):
                        arr.append(c); arr.append(merged[c])
                    fd.Subtype = Name.TrueType
                    fd.Encoding = Dictionary(Type=Name.Encoding, BaseEncoding=Name.WinAnsiEncoding, Differences=arr)
                else:
                    n["type1_nonwinansi_skipped"] += 1; continue
            ch = embed_truetype(pdf, fd, WF + MAP[nb]); n["embedded"] += 1; n["width_adjusted"] += ch
        else:
            n["unembedded_left:" + nb] += 1
    return dict(n)


# ---------------------------------------------------------------- widths of fonts that are already embedded
from fontTools.cffLib import CFFFontSet
from fontTools.misc.psCharStrings import T2WidthExtractor
from fontTools.agl import toUnicode as agl_uni
from pdfminer.latin_enc import ENCODING as LATIN

STD = {}; WIN = {}; MAC = {}
for name, std, mac, win, pdfenc in LATIN:
    if std is not None: STD[std] = name
    if win is not None: WIN[win] = name
    if mac is not None: MAC[mac] = name

def code_names(fd):
    """code -> glyph name for a simple font (base encoding + Differences)."""
    enc = fd.get("/Encoding")
    base = WIN
    diffs = None
    if isinstance(enc, Dictionary):
        be = enc.get("/BaseEncoding")
        base = MAC if be == Name.MacRomanEncoding else (STD if be is None and fd.get("/Subtype") == Name.Type1 else WIN)
        diffs = enc.get("/Differences")
    elif enc == Name.MacRomanEncoding:
        base = MAC
    elif enc is None and fd.get("/Subtype") == Name.Type1:
        base = STD
    names = dict(base)
    if diffs is not None:
        code = 0
        for x in diffs:
            if isinstance(x, Name):
                names[code] = str(x)[1:]; code += 1
            else:
                code = int(x)
    return names

def tt_glyph_for(f, fd, code, names):
    flags = int(fd.FontDescriptor.get("/Flags", 32))
    cmaps = {(t.platformID, t.platEncID): t.cmap for t in f["cmap"].tables}
    if flags & 4 and (3, 0) in cmaps:
        return cmaps[(3, 0)].get(0xF000 + code) or cmaps[(3, 0)].get(code)
    nm = names.get(code)
    if nm and (3, 1) in cmaps:
        u = agl_uni(nm)
        if u and len(u) == 1 and ord(u) in cmaps[(3, 1)]:
            return cmaps[(3, 1)][ord(u)]
    if (1, 0) in cmaps and code in cmaps[(1, 0)]:
        return cmaps[(1, 0)][code]
    if nm and nm in f.getGlyphOrder():
        return nm
    return None

def fix_embedded_widths(pdf, fd):
    """Make the embedded program's advance widths equal the PDF widths (the widths viewers lay text out with), so
    PDF/UA 7.21.5 holds and nothing on the page moves. Returns the number of glyphs changed."""
    st = fd.get("/Subtype")
    if st == Name.Type0:
        d = fd.DescendantFonts[0]
        desc = d.get("/FontDescriptor")
        if desc is None or "/FontFile2" not in desc or "/W" not in d:
            return 0
        f = TTFont(io.BytesIO(desc.FontFile2.read_bytes()))
        upem = f["head"].unitsPerEm; hm = f["hmtx"]; order = f.getGlyphOrder()
        c2g = d.get("/CIDToGIDMap")
        gmap = None
        if isinstance(c2g, pikepdf.Stream):
            b = c2g.read_bytes(); gmap = lambda c: (b[2 * c] << 8 | b[2 * c + 1]) if 2 * c + 1 < len(b) else None
        else:
            gmap = lambda c: c
        W = list(d.W); i = 0; changed = 0
        while i < len(W):
            c0 = int(W[i])
            if isinstance(W[i + 1], Array):
                ws = [float(x) for x in W[i + 1]]; cids = range(c0, c0 + len(ws)); i += 2
            else:
                c1 = int(W[i + 1]); w = float(W[i + 2]); cids = range(c0, c1 + 1); ws = [w] * len(cids); i += 3
            for c, w in zip(cids, ws):
                g = gmap(c)
                if g is None or g >= len(order):
                    continue
                gn = order[g]; adv, lsb = hm[gn]
                if abs(adv * 1000 / upem - w) > 0.9:
                    hm[gn] = (round(w * upem / 1000), lsb); changed += 1
        if changed:
            buf = io.BytesIO(); f.save(buf); data = buf.getvalue()
            desc.FontFile2 = pdf.make_stream(data); desc.FontFile2.Length1 = len(data)
        return changed
    desc = fd.get("/FontDescriptor")
    if desc is None or "/Widths" not in fd:
        return 0
    first = int(fd.get("/FirstChar", 0)); ws = [float(x) for x in fd.Widths]
    names = code_names(fd)
    changed = 0
    if "/FontFile2" in desc:
        f = TTFont(io.BytesIO(desc.FontFile2.read_bytes()))
        upem = f["head"].unitsPerEm; hm = f["hmtx"]
        done = {}
        for i, w in enumerate(ws):
            if w <= 0:
                continue
            g = tt_glyph_for(f, fd, first + i, names)
            if g is None or g in done:
                continue
            done[g] = w
            adv, lsb = hm[g]
            if abs(adv * 1000 / upem - w) > 0.9:
                hm[g] = (round(w * upem / 1000), lsb); changed += 1
        if changed:
            buf = io.BytesIO(); f.save(buf); data = buf.getvalue()
            desc.FontFile2 = pdf.make_stream(data); desc.FontFile2.Length1 = len(data)
        return changed
    if "/FontFile3" in desc and desc.FontFile3.get("/Subtype") == Name.Type1C:
        # veraPDF reads nominalWidthX/defaultWidthX as integers: make them integers and re-encode every explicit width
        # exactly (PDF width where a code maps to the glyph, else the glyph's own width), so both readings agree.
        cff = CFFFontSet(); cff.decompile(io.BytesIO(desc.FontFile3.read_bytes()), None)
        top = cff[cff.fontNames[0]]; css = top.CharStrings; priv = top.Private
        nominal = getattr(priv, "nominalWidthX", 0); default = getattr(priv, "defaultWidthX", 0)
        scale = float(top.FontMatrix[0]) * 1000 if hasattr(top, "FontMatrix") else 1.0
        builtin = getattr(top, "Encoding", None)
        target = {}
        for i, w in enumerate(ws):
            if w <= 0:
                continue
            code = first + i
            gn = names.get(code)
            if (gn is None or gn not in css) and isinstance(builtin, list) and code < len(builtin):
                gn = builtin[code]
            if gn is not None and gn in css:
                target.setdefault(gn, w / scale)
        new_nom = round(nominal); new_def = round(default)
        for gn in css.keys():
            cs = css[gn]; cs.decompile()
            ext = T2WidthExtractor(getattr(cs.private, "Subrs", []), getattr(top, "GlobalSubrs", []), nominal, default)
            ext.execute(cs)
            want = target.get(gn, ext.width)
            prog = cs.program
            if ext.gotWidth:
                prog[0] = want - new_nom
            elif abs(want - new_def) > 1e-6:
                prog.insert(0, want - new_nom)
            if abs(want - ext.width) > 1e-3:
                changed += 1
        priv.nominalWidthX = new_nom; priv.defaultWidthX = new_def
        buf = io.BytesIO(); cff.compile(buf, __import__("types").SimpleNamespace(recalcBBoxes=False)); data = buf.getvalue()
        desc.FontFile3 = pdf.make_stream(data, Subtype=Name.Type1C)
        return changed + 1
    return 0

def std_differences(pdf):
    """Differences array giving StandardEncoding's names where they differ from WinAnsi's (codes 32-255)."""
    arr = []
    for c in range(32, 256):
        s, w = STD.get(c), WIN.get(c)
        if s and s != w:
            arr.extend([c, Name("/" + s)])
    return Array(arr)
