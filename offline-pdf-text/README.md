# Offline PDF to Text & Markdown (with OCR)

A Chrome extension by WrenTools. Turn a PDF into plain text or Markdown on your own computer, scanned pages included.
No upload, no page limit, no account.

Click the button (or press Alt+Shift+P) on a tab showing a PDF, and its reader opens beside it with the text. Anywhere
else, it opens a page where you can choose or drop a PDF. Switch between plain text and Markdown (headings, lists and
joined paragraphs), then Copy or Save it as a file.

## Reads on your computer

Each page's text is taken with pdf.js. A page with no text, such as a scan, is read with the text recognition engine
(Tesseract) built into the extension, at 300 dpi. The PDF is never sent to us or anyone else: a dropped PDF is read with
your network switched off, and the extension contains no code that contacts a server.

## Asks for very little

Its one permission is `activeTab`: it can't see a tab until you click its button or press its shortcut. It keeps
nothing: no history, no account, no tracking. The [privacy policy](privacy.md) says exactly what it handles.

## Good to know

- Scanned pages are read in English only, for now.
- A PDF that needs a password is not opened, and one whose owner does not allow copying its text is not read.
- Markdown headings come from font sizes, so an unusual layout can need a touch-up.
- The download is about 10 MB, because the recognition engine and its English model are inside it.
- Its sister extension, [Offline OCR](../offline-ocr/README.md), copies text from any part of the screen.

## Where to get it

Install it from the Chrome Web Store (link added when it is live).

Questions and problems: [sah.assetholding@gmail.com](mailto:sah.assetholding@gmail.com).
