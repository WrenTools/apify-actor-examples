# PDF Access Fixer

Make a PDF accessible to screen-reader users, offline, **including scanned PDFs**. This is PDF remediation: it fixes a
file that already exists. It reads scanned pages with OCR into a real text layer, then tags the original file (headings, lists, tables, reading order, alt text, form-field labels)
from a plan that a person reviews. The pages look the same afterwards.

It is **not fully automatic**, and it does not claim to be. Deciding what is a heading, what a table's headers are,
what an image means and whether OCR read a number right needs a person (or a model you trust) reading the page. The
tool does everything else and checks what it can measure.

## What it does

1. **`start`**: finds the pages that are images only (fewer than 20 characters of text and at least one image), renders
   each at 300 dpi and reads it with [Tesseract](https://github.com/tesseract-ocr/tesseract). It turns sideways scans
   upright. It then writes every word as invisible text over the scan, at the word's position, in a font embedded in the
   file. It analyses every page into text segments and images, and writes a **draft plan** (`plan.txt`).
2. **You review `plan.txt`** beside page pictures (`view`): fix the structure and reading order, write alt text, and on
   scanned pages correct what OCR misread (`TEXT` lines). Words Tesseract was unsure of are marked in the draft.
3. **`finish`**: writes the tags into a copy of the original. It refuses a plan that leaves out any text or image.
   It then checks the result: the pages render the same, no character is lost, everything is tagged or marked as
   decoration, and the structure a screen reader gets is written out in reading order. With veraPDF, it also checks
   PDF/UA-1.

Everything runs on your computer. No account, no upload: the tests run `start` and `finish` with every network call
from Python refused, and they succeed. Tesseract and veraPDF are local programs it starts.

## Install

Python 3.10 or later, and Tesseract for scanned pages (Windows: the [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki);
macOS: `brew install tesseract`; Debian/Ubuntu: `apt install tesseract-ocr`). For other languages, install their
Tesseract data and pass `--lang`, e.g. `--lang eng+spa`. So far it has been tested only on Windows 11 with Python 3.14
and Tesseract 5.4.

```
pip install -r requirements.txt
pip install .
```

[veraPDF](https://verapdf.org/software/) (free, needs Java) is optional; with it, `finish` checks PDF/UA-1.

## Use

```
pdf-access-fixer start minutes.pdf                 # writes minutes-access/ with plan.txt
pdf-access-fixer view minutes-access page 1        # picture of page 1 with segment numbers
pdf-access-fixer view minutes-access region 1:20,700,90,770   # zoom into a box (PDF points)
# ... edit minutes-access/plan.txt ...
pdf-access-fixer finish minutes-access --verapdf /path/to/verapdf
```

`finish` writes `minutes-access/minutes-accessible.pdf`, `check.json` and `check.fulltree.txt`: what a screen reader
gets, in order, with roles, alt text and table headers. Read it beside the pages before you publish the file. It exits
with status 1 and prints `PROBLEM:` lines if a check fails.

## The plan

One line per element, in reading order. Segment ids (`p1s4`: page 1, segment 4) come from the analysis and are drawn
on the `view` pictures.

```
title: Example Township board agenda, October 1, 2026
lang: en-US
H1 p1s4                          # a heading (H1-H6; never skip a level going down)
P p1s7 p1s8                      # a paragraph of two segments
ART p1s1                         # running header, page number, decoration
L
 LI p1s10
 LI p1s11
/L
TABLE
TR TH:p6s3 TH:p6s4 TH:p6s5
TR THR:p6s9 TD:p6s10 TD:-
/TABLE
FIG p2i0 | Chart of spending by month: highest in July, $41,200
DECO p1i0                        # an image that carries no information (on a scan: the page image itself)
FIG region:1:20,700,90,770 | Seal of Example Township             # part of a scanned page shown as a figure
TEXT p1s12 | Approval of April 16, 2026 Meeting Minutes              # what OCR should have read
FIELD Applicant Name | Applicant's full name
```

Also: `[a:b]` to split a segment (`P p1s7[0:54]`), `CELLALT`, `SPLITFIELD`, `LINK`, `TOUNICODE`, and lines inside a list
item. The full format is at the top of `pdf_access_fixer/apply.py`.

## What is tested, and what was measured

Tests (`python tests/run.py`, on scans the tests draw themselves):
- an image-only page is OCR'd and a page with text is not;
- the OCR text is found in the output, and the page renders the same (0 pixels changed at 100 dpi);
- a one-character word (a lone "%" or "A") is read back as text;
- a sideways scan is detected, read upright, and still renders the same; its text is analysed as whole lines;
- the tags follow the plan's order, and so does the OCR text itself (for viewers that read text in drawing order rather
  than by its tags), also where the plan splits one OCR line between two elements; a `TEXT` correction changes what is
  read and not how the page looks; a `FIG region` becomes a Figure with its alt text;
- a plan that leaves a segment out is refused;
- the output passes veraPDF PDF/UA-1 (`python tests/run.py --verapdf <launcher>`);
- `start` and `finish` succeed with every network call from Python refused, and make none.

Measured on four real scanned PDFs that US counties posted (a 34-page tax report scanned sideways, two forms, 9 pages
of minutes; 49 pages, no text layer at all), November 2026. The PDFs are not in this repository.
- **Before:** all four failed veraPDF PDF/UA-1 as posted. An earlier version of this tool, without OCR, could only put
  each page's words into alt text, and an independent review failed all four (no headings, lists or tables can exist
  on an image).
- **After:** all four pass veraPDF PDF/UA-1. Pages look the same: 0 pixels changed on three files, and at most 0.27% of
  a page's pixels (glyph edges) on the fourth.
- **Independent review** (reviewers who never saw the plans, comparing what a screen reader gets with the
  page images, against WCAG 2.1 AA): three passed on the first pass. The tax report failed it on misread digits and
  empty "0" cells. After one round of plan corrections, a fresh review passed it. **4 of 4 passed.**
- The plans were written by an AI model and checked by reviewers of the same model family. That review used no screen
  reader. The tax report needed 1,309 corrected OCR segments (`TEXT` lines). OCR alone is not enough: checking every
  number is the work.

**With a screen reader** (NVDA 2026.2 on Windows 11, November 2026; its speech recorded as it browsed each file by
headings, lists, graphics, tables and line by line). The files were the four county PDFs and a born-digital city form,
each before and after.
- **Before:** in the scans, NVDA found no text at all.
- **After, in the pdf.js viewer** (6.5.438, the viewer Firefox builds in; run here in Chrome): on every page NVDA read,
  it announced every tagged heading at its tagged level (53 headings in all), every tagged list with its item count,
  every table with its rows and columns, and every figure's alt text. The minutes, for example, gave 33 headings,
  8 lists, 4 tables and 10 alt texts, each matching the tags. All 9 pages of the minutes were read; only the first 2 of
  the tax report's 34 were.
- **In that viewer, headings and table cells are announced without their text,** and cells without their column
  headers; the text is read beside them. A tagged PDF that Chrome itself made behaves the same way, so this is the
  viewer.
- **On a scan, pdf.js now reads a line at a time.** Until this version it read one word per line: 361 of the minutes'
  372 lines on pages 1-2 held one word. Now 19 of 91 do, and those are mostly lines of one word (bullets, "AGENDA").
  Reading order on scans was also wrong until this version. The OCR text is now drawn in the plan's order on all 49
  scanned pages. Before this version, 11 pages of the tax report drew some table text out of order: there, the plan
  splits one OCR line between two cells.
- **Chrome's built-in PDF viewer ignores tags,** ours and a Chrome-made control alike. It guesses headings from type
  size and announces no lists or tables. Its engine, pdfium, mostly reads the text in drawing order. Measured with
  pdfium itself (build 159, not Chrome), it read the plan's order on 40 of the 49 scanned pages. On 7 pages it regroups
  words that sit almost level on the page: 4 pages of the minutes, 1 page of a form and 2 of the tax report. There,
  60 of the 14,920 words are read elsewhere on the page. On 3 pages of the tax report, it leaves out the space between
  two table cells in 8 places.
- Not tested: JAWS, VoiceOver, Adobe Acrobat Reader, Firefox itself.

## What it does not do

- It does not decide the structure for you. The draft plan is a heuristic guess. On scans, OCR misreads digits and small
  print, and every word needs checking against the page.
- It does not make a scanned form fillable. Its labels are read as text; there are no fields to fill.
- It does not fix colour contrast, which is the document's design.
- It has been tested with one screen reader (NVDA) in two viewers, not with JAWS, VoiceOver or Adobe Acrobat Reader.
  Its tags help only where the viewer reads tags: Chrome's built-in viewer does not, and pdf.js announces structure
  but not the text inside it.
- On a sideways scan made of several image layers, a few anti-aliased edge pixels can render differently (measured:
  at most 0.27% of a page's pixels, all at glyph edges). On every other page measured, 0 pixels changed.

## Section 508

The Revised 508 Standards, which US federal agencies subject to Section 508 must follow, require their electronic
content to conform to WCAG 2.0 Level A and AA (36 CFR part 1194, Appendix A, E205.4), and WCAG 2.0 is the only standard
they set for PDF files. The US Access Board decided against PDF/UA-1 as an alternative, because it does not cover colour
contrast, scripting or video, and noted that PDF/UA-1 "can still be useful to agencies conducting assessments of PDF
files to ensure WCAG 2.0 conformance" ([the standards and the rule](https://www.access-board.gov/ict/), read 15 November
2026).

This tool checks PDF/UA-1 with veraPDF, and the four county files above were also reviewed against WCAG 2.1 AA, by AI
reviewers. It does not check WCAG conformance itself and does not fix contrast, so **it cannot tell you that a file
meets Section 508**: a person has to check that.

## ADA Title II

The Justice Department's rule under Title II of the ADA (28 CFR 35.200) makes WCAG 2.1 Level AA the standard for the
web content of US state and local governments, which includes the documents they post, such as PDFs. It applies from
26 April 2027 to governments of 50,000 people or more, and from 26 April 2028 to smaller ones and to special districts,
with limited exceptions, among them some PDFs posted before those dates
([the Department's fact sheet](https://www.ada.gov/resources/2024-03-08-web-rule/) and
[its April 2026 rule moving the dates](https://www.ada.gov/assets/pdfs/2026-ifr.pdf), read 22 November 2026).

This tool does not check WCAG 2.1 AA itself (the review above was by AI reviewers), so **it cannot tell you that a
file meets the Title II rule**: a person has to check that.

## Licence

MIT. Tesseract (Apache-2.0) and veraPDF (GPLv3/MPLv2) are separate programs you install; they are not part of this
package. The Python libraries it uses are listed in `requirements.txt`.

Made by [WrenTools](https://github.com/WrenTools), which also makes paid OCR and PDF tools on Apify
([Image & Scanned PDF OCR](https://apify.com/wrentools/scanned-pdf-image-ocr),
[PDF to Text & Markdown](https://apify.com/wrentools/pdf-text-markdown-extractor)) and the Chrome extensions
[Offline OCR](https://chromewebstore.google.com/detail/offline-ocr-copy-text-fro/mfaolaapfbdmfilfgjgcpkdgfimljdpj) and
[Offline PDF to Text](https://chromewebstore.google.com/detail/offline-pdf-to-text-markd/pegdoilhklakigmdkjhabmgfbejoklbi).
