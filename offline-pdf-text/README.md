# Offline PDF to Text & Markdown (with OCR)

A Chrome extension by WrenTools. Turn a PDF into plain text or Markdown on your own computer, scanned pages included.
No upload, no page limit, no account.

Click the button (or press Alt+Shift+P) on a tab showing a PDF, and its reader opens beside it with the text. Anywhere
else, it opens a page where you can choose or drop a PDF. Switch between plain text and Markdown, then Copy or Save it
as a file.

## Reads on your computer

Each page's text is taken with pdf.js. A page with no text, such as a scan, is read with the text recognition engine
(Tesseract) built into the extension, at 300 dpi. The PDF is never sent to us or anyone else: a dropped PDF is read with
your network switched off, and the one request the extension makes is for the PDF your tab already shows, from the site
it came from.

## Markdown that keeps the structure

Headings are worked out from the type sizes, lists stay lists, and lines broken across the page are joined back into
paragraphs. Columns are read in order, tables are rebuilt as Markdown tables, and running heads and page numbers are
left out (it tells you how many).

## Scanned pages in 13 languages

Scanned pages are read in English, Spanish, French, German, Portuguese, Italian, Russian, Chinese (Simplified and
Traditional), Japanese, Arabic, Hebrew or Persian. It starts in the language you last picked, or else in your browser's
language when it is one of them; pick another and the PDF is read again. Text that is already in the PDF comes out in
any language.

Scanned pages are straightened before they are read (tested up to 15 degrees either way), a two-column scan is read one
column at a time, and running heads and page numbers are left out of scanned pages too.

## Asks for very little

It asks for two permissions. `activeTab`: it can't see a tab until you click its button or press its shortcut.
`storage`: it remembers the language you last picked for scanned pages, on your computer, and nothing else: no history,
no account, no tracking. The [privacy policy](privacy.md) says exactly what it handles.

## Good to know

- Vertical Chinese and Japanese text is not read.
- Tables are rebuilt from the text a PDF carries, not from scanned pages, and only when their columns are spaced apart.
  Images are not rebuilt.
- A word that has its own hyphen and is broken at the end of a line ("self-" then "selected") can come out joined.
- A PDF that needs a password is not opened, and one whose owner does not allow copying its text is not read.
- The download is about 26.5 MiB, because the PDF engine, the recognition engine and its 13 language models are inside
  it.
- Its sister extension, [Offline OCR](../offline-ocr/README.md), copies text from any part of the screen.

## Where to get it

Install it from the [Chrome Web Store](https://chromewebstore.google.com/detail/pegdoilhklakigmdkjhabmgfbejoklbi).

Questions and problems: [sah.assetholding@gmail.com](mailto:sah.assetholding@gmail.com).
