"""pdf-access-fixer: one command, offline, files on disk.

    pdf-access-fixer start report.pdf            OCR the scanned pages, analyse, write a draft plan (report-access/plan.txt)
    pdf-access-fixer view report-access page 3   a picture of page 3 with each segment's number, to check the plan by
    pdf-access-fixer finish report-access        tag the original from the plan, then check the result

Between start and finish a person (or a model) reads plan.txt beside the page pictures and corrects it: headings,
lists, tables, reading order, alt text, form labels, and on scanned pages the OCR text. The draft is a heuristic
guess; it is not the finished structure, and finish does not judge whether the plan is right.
"""
import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

from . import __version__

STATE = "state.json"


def _quiet(fn, *a, **k):
    """Run a stage, keeping its own progress lines out of the way (they go to the stage log)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*a, **k)
    return result, buf.getvalue()


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cmd_start(args):
    from . import analyze, ocr, prep, propose
    src = Path(args.pdf).resolve()
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    work = Path(args.work) if args.work else src.with_name(src.stem + "-access")
    work.mkdir(parents=True, exist_ok=True)
    logs = []
    ocr_report = None
    pages = [] if args.no_ocr else ocr.pages_needing_ocr(src)
    if args.ocr_pages:
        pages = sorted({int(x) for x in args.ocr_pages.split(",")})
    if pages:
        print(f"OCR of {len(pages)} page(s) with Tesseract ({args.lang}): {', '.join(map(str, pages))}")
        ocr_report = ocr.ocr_pdf(src, work / "ocr.pdf", lang=args.lang, tesseract=args.tesseract, pages=pages,
                                 log=lambda m: print("  " + m))
        (work / "ocr.json").write_text(json.dumps(ocr_report, ensure_ascii=False, indent=1), encoding="utf-8")
        base = work / "ocr.pdf"
    else:
        shutil.copyfile(src, work / "ocr.pdf")
        base = work / "ocr.pdf"
        (work / "ocr.json").unlink(missing_ok=True)
    _, log = _quiet(prep.main, str(base), str(work / "prep.pdf"))
    logs.append(log)
    _, log = _quiet(analyze.main, str(work / "prep.pdf"), str(work / "analysis.json"))
    logs.append(log)
    an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    bad = [p["page"] for p in an["pages"] if not p["align_ok"]]
    if bad:
        print(f"cannot tag: the analysis does not line up with the content of page(s) {bad}", file=sys.stderr)
        return 1
    plan = work / "plan.txt"
    draft = work / "draft-plan.txt"
    _quiet(propose.main, str(work / "analysis.json"), str(draft), args.title or None,
           str(work / "ocr.json") if ocr_report else None)
    if plan.exists() and not args.new_plan:
        print(f"kept your plan {plan} (the fresh draft is {draft}; --new-plan replaces the plan)")
    else:
        shutil.copyfile(draft, plan)
    (work / "start.log").write_text("".join(logs), encoding="utf-8")
    state = {"version": __version__, "input": str(src), "input_sha256": _sha256(src), "ocr_pages": pages,
             "lang": args.lang}
    (work / STATE).write_text(json.dumps(state, indent=1), encoding="utf-8")
    nseg = sum(len(p["segments"]) for p in an["pages"])
    nimg = sum(len(p["images"]) for p in an["pages"])
    print(f"{len(an['pages'])} page(s), {nseg} text segment(s), {nimg} image(s); draft plan: {plan}")
    if ocr_report:
        unsure = sum(len(p.get("unsure_words", [])) for p in ocr_report["pages"])
        confs = [p["mean_conf"] for p in ocr_report["pages"] if p["mean_conf"] is not None]
        print(f"OCR: mean word confidence {min(confs) if confs else '-'}-{max(confs) if confs else '-'} per page; "
              f"{unsure} word(s) read with low confidence are marked [OCR unsure: ...] in the plan.")
    print("Next: correct the plan against the pages (pdf-access-fixer view <work> page <n>), then "
          f"pdf-access-fixer finish {work}")
    return 0


def _load(work):
    work = Path(work)
    if not (work / STATE).exists():
        raise SystemExit(f"{work} is not a work folder made by 'pdf-access-fixer start'")
    state = json.loads((work / STATE).read_text(encoding="utf-8"))
    an = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    return work, state, an


def cmd_view(args):
    from . import view
    work, state, an = _load(args.work)
    (work / "view").mkdir(exist_ok=True)
    name = f"{args.mode}-{args.what.replace(':', '_').replace(',', '_')}{'-plain' if args.plain else ''}.png"
    out = work / "view" / name
    view.render(work / "prep.pdf", an, args.mode, args.what, out, plain=args.plain)
    print(out)
    return 0


def cmd_finish(args):
    from . import apply, check, verapdf
    work, state, an = _load(args.work)
    src = Path(state["input"])
    if not src.exists() or _sha256(src) != state["input_sha256"]:
        print(f"the input {src} changed or moved since start; run start again", file=sys.stderr)
        return 2
    plan = Path(args.plan) if args.plan else work / "plan.txt"
    out = Path(args.out) if args.out else work / (src.stem + "-accessible.pdf")
    try:
        _, log = _quiet(apply.main, str(work / "prep.pdf"), str(work / "analysis.json"), str(plan), str(out))
    except apply.PlanError as e:
        print(f"the plan cannot be applied:\n{e}", file=sys.stderr)
        return 1
    (work / "finish.log").write_text(log, encoding="utf-8")
    _, log = _quiet(check.main, str(src), str(out), str(work / "check.json"))
    summary = json.loads((work / "check.json").read_text(encoding="utf-8"))["summary"]
    problems = []
    if summary["chars_lost"]:
        problems.append(f"{summary['chars_lost']} character(s) of the original are not in the output's text")
    if summary["unmarked_chars"] or summary["images_unmarked"]:
        problems.append(f"{summary['unmarked_chars']} character(s) and {summary['images_unmarked']} image(s) are "
                        "neither tagged nor marked as artifacts")
    print(f"wrote {out}")
    print(f"pages look the same: largest share of pixels changed on a page = {summary['max_render_diff']:.4%} "
          "(rendered at 100 dpi, a pixel counts when a channel moves by more than 32)")
    print(f"text: {summary['tagged_chars']} character(s) tagged, {summary['artifact_chars']} marked as artifacts, "
          f"{summary['chars_lost']} lost, {summary['chars_added']} added (OCR text and corrections)")
    print(f"what a screen reader gets, in order: {work / 'check.fulltree.txt'}")
    vera = None
    if args.verapdf or args.verapdf_home:
        try:
            vera = verapdf.check(out, launcher=args.verapdf, home=args.verapdf_home, java=args.java)
        except verapdf.VeraUnavailable as e:
            print(f"veraPDF: not run ({e})", file=sys.stderr)
            return 1
        (work / "verapdf.json").write_text(json.dumps(vera, indent=1), encoding="utf-8")
        if vera["compliant"]:
            print("veraPDF PDF/UA-1: passed")
        else:
            problems.append("veraPDF PDF/UA-1 failed: " + "; ".join(
                f"{f['rule']} x{f['checks']} {f['message']}" for f in vera["failed"]))
    else:
        print("veraPDF: not run (pass --verapdf <launcher> to check PDF/UA-1)")
    print("Not checked by this tool: whether the plan's structure, reading order, alt text and OCR corrections are "
          "right (a person checks the plan), colour contrast, and how a screen reader announces the file.")
    for p in problems:
        print("PROBLEM: " + p, file=sys.stderr)
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pdf-access-fixer", description=__doc__.split("\n\n")[0])
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="OCR scanned pages, analyse, write a draft plan")
    s.add_argument("pdf")
    s.add_argument("--work", help="work folder (default: <pdf name>-access beside the PDF)")
    s.add_argument("--lang", default="eng", help="Tesseract language(s), e.g. eng or eng+spa (default eng)")
    s.add_argument("--tesseract", help="path to the tesseract program, if it is not on PATH")
    s.add_argument("--title", help="document title for the draft plan")
    s.add_argument("--no-ocr", action="store_true", help="never OCR")
    s.add_argument("--ocr-pages", help="OCR exactly these pages (comma-separated), instead of the image-only ones")
    s.add_argument("--new-plan", action="store_true", help="replace an existing plan.txt with the fresh draft")
    s.set_defaults(fn=cmd_start)
    v = sub.add_parser("view", help="picture of a page (segment numbers drawn), an image or a box")
    v.add_argument("work")
    v.add_argument("mode", choices=["page", "img", "region"])
    v.add_argument("what", help="page number; image id like p3i0; or region <page>:<x0>,<y0>,<x1>,<y1>")
    v.add_argument("--plain", action="store_true", help="the page as displayed, nothing drawn")
    v.set_defaults(fn=cmd_view)
    f = sub.add_parser("finish", help="tag the original from the plan and check the result")
    f.add_argument("work")
    f.add_argument("--plan", help="plan file (default: <work>/plan.txt)")
    f.add_argument("--out", help="output PDF (default: <work>/<name>-accessible.pdf)")
    f.add_argument("--verapdf", help="veraPDF launcher (verapdf or verapdf.bat) to check PDF/UA-1")
    f.add_argument("--verapdf-home", help="veraPDF install folder, with --java, instead of the launcher")
    f.add_argument("--java", help="java program for --verapdf-home")
    f.set_defaults(fn=cmd_finish)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
