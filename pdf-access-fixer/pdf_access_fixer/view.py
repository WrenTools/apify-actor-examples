"""Page pictures for the person (or model) reviewing a plan: a page with each segment's number drawn at its top-left (red),
images outlined (blue, with their ids) and form fields outlined (green); or a crop of one image or of any box.

    render(pdf_path, analysis, "page", "3", out_png)            page 3 with segment, image and field boxes
    render(pdf_path, analysis, "page", "3", out_png, plain=True) page 3 as it is displayed, nothing drawn
    render(pdf_path, analysis, "img", "p3i0", out_png)          image p3i0 as it appears on the page
    render(pdf_path, analysis, "region", "3:20,700,60,760", out_png)  any box, in the analysis's coordinates, at 3x

Boxes are in the analysis's coordinates: PDF points from the page's lower-left corner. A page the OCR stage read
sideways is analysed upright, and drawn upright here (unless plain).
"""
import pypdfium2 as pdfium
from PIL import ImageDraw


def _frame(page, pa, plain=False):
    """(render rotation, height of the analysis frame in points) for a page."""
    upright = pa.get("user_space") and not plain
    H = (pa["box"][3] - pa["box"][1]) if upright else page.get_height()
    rot = (360 - pa.get("rotate", 0)) % 360 if upright else 0
    return rot, H


def render(pdf_path, an, mode, arg, out_png, plain=False):
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        if mode == "page":
            n = int(arg)
            page = doc[n - 1]
            pa = an["pages"][n - 1]
            rot, H = _frame(page, pa, plain)
            w_pt = (pa["box"][2] - pa["box"][0]) if pa.get("user_space") and not plain else page.get_width()
            scale = min(2.0, 1250 / w_pt)
            im = page.render(scale=scale, rotation=rot).to_pil().convert("RGB")
            if not plain:
                d = ImageDraw.Draw(im)

                def rect(b):
                    return [b[0] * scale, (H - b[3]) * scale, b[2] * scale, (H - b[1]) * scale]
                for s in pa["segments"]:
                    r = rect(s["bbox"])
                    d.rectangle(r, outline=(255, 160, 160))
                    d.text((r[0] - 2, r[1] - 9), s["id"].split("s")[1], fill=(220, 0, 0))
                for k, img in enumerate(pa["images"]):
                    r = rect(img["bbox"])
                    d.rectangle(r, outline=(0, 0, 255), width=2)
                    d.text((r[0] + 2, r[1] + 2), f"p{n}i{k}", fill=(0, 0, 255))
                for a in pa["annots"]:
                    if a.get("subtype") == "/Widget":
                        d.rectangle(rect(a["rect"]), outline=(0, 160, 0))
        else:
            if mode == "img":
                n = int(arg[1:].split("i")[0])
                box = an["pages"][n - 1]["images"][int(arg.split("i")[1])]["bbox"]
            elif mode == "region":
                pg, b = arg.split(":")
                n = int(pg)
                box = [float(v) for v in b.split(",")]
            else:
                raise ValueError(f"unknown view mode {mode!r} (page, img or region)")
            page = doc[n - 1]
            pa = an["pages"][n - 1]
            rot, H = _frame(page, pa)
            scale = 3.0
            full = page.render(scale=scale, rotation=rot).to_pil().convert("RGB")
            x0, y0, x1, y1 = box
            im = full.crop([int(max(0, x0 * scale)), int(max(0, (H - y1) * scale)), int(min(full.width, x1 * scale)),
                            int(min(full.height, (H - y0) * scale))])
            if im.width > 1200:
                im = im.resize((1200, int(im.height * 1200 / im.width)))
        im.save(str(out_png))
        return im.size
    finally:
        doc.close()
