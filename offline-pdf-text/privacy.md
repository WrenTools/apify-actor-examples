# Offline PDF to Text & Markdown privacy policy

*Offline PDF to Text & Markdown (with OCR), a Chrome extension by WrenTools. Effective 31 October 2026.*

**In short: the extension reads PDFs on your own computer and sends nothing to us or anyone else. The one thing it
keeps is the language you last picked for scanned pages, on your computer.**

## What the extension handles

The only data it handles is the PDF you give it, and only after you act:

- When you click its button (or press its shortcut) on a tab showing a PDF, it opens its reader page and fetches that
  same PDF again from the address the tab loaded it from, the way your browser does when you open the link. Your
  browser sends that site its usual cookies with the request, so a PDF you can see while signed in can be read. This
  request goes only to the site the PDF came from. It is the one network request the extension makes.
- When you choose or drop a PDF file on its reader page, it reads that file from your computer. Nothing is fetched.

What happens to the PDF:

- It is read in your computer's memory: its text with pdf.js, and pages without text (scans) with the text
  recognition engine (Tesseract) built into the extension. It is discarded when you close the reader page.
- It is never sent to us or to anyone else. The extension contains no code that contacts a server of ours or anyone
  else's; reading a dropped PDF works with your network switched off.
- The PDF is never stored, and neither is its name, its text or the address it came from. No history is kept. The
  extension has no account, no analytics and no tracking.
- The text is copied to your clipboard only when you press Copy, and saved as a file only when you press Save.
- A PDF that needs a password is not opened, and a PDF whose owner does not allow copying its text is not read.

## What the extension keeps

Only the language you last picked for scanned pages, so the next PDF you open starts in it. It is kept in Chrome's
storage for the extension on this computer, is not copied to your other browsers, and is removed when you remove the
extension. If you never pick a language, nothing is kept. Nothing else is ever stored.

## Permissions

- `activeTab`: lets the extension see the address of the current tab, only after you click its button or press its
  shortcut, so that it can open the PDF shown there.
- `storage`: lets the extension remember the language you last picked for scanned pages, on this computer.

It has no access to any website until you use it, none to your browsing history, and no other permission.

## Sharing and selling

We do not collect your data, so there is nothing to sell, share or transfer. The use of information received by this
extension adheres to the [Chrome Web Store User Data Policy](https://developer.chrome.com/docs/webstore/program-policies/limited-use),
including the Limited Use requirements.

## Changes

If a future version handles data differently, this page will say so before that version is published, with a new
effective date.

---

Questions: WrenTools, [sah.assetholding@gmail.com](mailto:sah.assetholding@gmail.com).
