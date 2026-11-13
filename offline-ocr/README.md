# Wren Offline OCR: Copy Text from Screen

A Chrome extension by WrenTools. Select part of a page, a picture or a paused video and copy its text. The OCR runs on
your computer; nothing is uploaded.

Copy text you can't select: words in a picture, a paused video, a slide, a chart, a screenshot of an error.

Click the Wren OCR button (or press Alt+Shift+O), drag a box over the text, and it appears in a small panel with a Copy
button. It reads PDFs open in Chrome, zoomed pages and text inside frames. On pages Chrome closes to extensions, such as
its settings pages, it says so, and you can paste, drop or choose a screenshot instead.

Or right-click a picture on a page and choose "Copy text from this image": its text appears in the same panel.

## Reads on your computer

The text recognition (Tesseract) is built into the extension. Your screen is never sent anywhere: the extension works
with your network switched off, and it contains no code that contacts a server.

## Reads the text in the order you would

- Keeps columns apart: a two-column article or a row of dashboard cards is read one column at a time, not across.
- When you paste, drop or choose a scan or photo of a page that is tilted (tested up to 11 degrees), it is straightened
  before it is read.
- Words it is less sure of are underlined, so you know where to look.
- Join the lines into sentences, or put it all on one line, before you copy. Code keeps its lines.

## Thirteen languages, all offline

Reads English, Spanish, French, German, Portuguese, Italian, Russian, Chinese (Simplified and Traditional), Japanese,
Arabic, Hebrew and Persian, and vertical Japanese and Chinese. It starts in your browser's language when that is one of
them, and in English otherwise. Pick another in the panel and the next read starts in it.

## Asks for very little

It can't see a page until you click its button, press its shortcut or choose "Copy text from this image", and then only
the page in front of you. It remembers only your settings (the language you picked and the two line options), on your
computer, and never what you read or where. No history, no account, no tracking. Its permissions are `activeTab`,
`scripting`, `offscreen`, `contextMenus` and `storage`; the [privacy policy](privacy.md) says what each one is for.

## Good to know

- Made for printed and on-screen text, not handwriting.
- Small text full of symbols (code, for example) can come out with a character wrong, so check it before you rely on
  it.
- The download is about 31 MB, because the recognition engine and its language models are inside it.
- Its sister extension, [Offline PDF to Text & Markdown (with OCR)](../offline-pdf-text/README.md), turns a PDF into
  plain text or Markdown on your own computer, scanned pages included.

## Where to get it

Install it from the [Chrome Web Store](https://chromewebstore.google.com/detail/mfaolaapfbdmfilfgjgcpkdgfimljdpj).

Questions and problems: [sah.assetholding@gmail.com](mailto:sah.assetholding@gmail.com).
