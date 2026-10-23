# Offline OCR: Copy Text from Screen

A Chrome extension by Wrenkit. Select any part of a page and copy its text. The OCR runs on your own computer;
nothing is uploaded.

Copy text you can't select: words in a picture, a paused video, a slide, a chart, a screenshot of an error.

Click the Offline OCR button (or press Alt+Shift+O), drag a box over the text, and it appears in a small panel with a
Copy button. On pages extensions can't open, such as the Chrome settings pages, you get a page where you can paste,
drop or choose an image instead.

## Reads on your computer

The text recognition (Tesseract) is built into the extension. Your screen is never sent anywhere: the extension works
with your network switched off, and it contains no code that contacts a server.

## Asks for very little

It can't see a page until you click its button or press its shortcut, and then only the page in front of you. It
keeps nothing: no history, no account, no tracking. Its permissions are `activeTab`, `scripting` and `offscreen`;
the [privacy policy](privacy.md) says what each one is for.

## Good to know

- English text only, for now.
- Made for printed and on-screen text, not handwriting.
- Small text full of symbols (code, for example) can come out with a character wrong, so check it before you rely on
  it.
- The download is about 15 MB, because the recognition engine and its English model are inside it.

## Where to get it

It has not been published on the Chrome Web Store yet. This page will link to it once it is.

Questions and problems: [sah.assetholding@gmail.com](mailto:sah.assetholding@gmail.com).
