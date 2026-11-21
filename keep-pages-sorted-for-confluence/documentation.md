# Keep Pages Sorted Alphabetically for Confluence: documentation

In Confluence Cloud, a new page lands at the bottom of the pages under its parent, and sorting a page tree A to Z is a
one-time act.
Atlassian's feature request for a lasting order is CONFCLOUD-65454, "Reorder pages alphabetically (permanently)".
This app keeps the pages in order, in the spaces where a space admin turns it on.

## Questions people ask

**Can Confluence keep child pages in alphabetical order permanently?**
Not on its own: its sort is one-time, and new pages go to the bottom.
With this app on in a space, the pages under every page and folder stay in A to Z order, or in the order the space admin
chose, as pages are created, renamed, moved, copied and restored.
Live docs too: a new one is put in its place within seconds, and one renamed in the editor about ten minutes after the
person editing it has left it, when Confluence ends its editing session.

**Will Step 10 come before Step 2?**
No: in the title orders this app compares numbers as numbers, so Step 2 comes before Step 10, and it ignores capitals and accents.

**Can it sort newest first?**
Yes: a space admin can choose A to Z or Z to A by title, or newest first or oldest first by the date each page was
created.

**What if someone drags a page out of order?**
The app puts it back: on our test site, a page dragged above its neighbours in the sidebar was moved back with one move.
Confluence's own one-time *Sort Alphabetically* (Space settings > Content > Reorder) is put back too, in a space kept in
another order: on our test site, four pages it sorted A to Z were back in Z to A about 5 seconds later, with the fewest moves.
The app acts on the event Confluence sends for that click, and in one of seven clicks on our test site Confluence sent
none, so those pages stayed in A to Z order until the next change among them. That click came with a page beside it renamed in the same second, but four later clicks, two of them with such a
rename, each got their event and were put back with the fewest moves. To put a space back in order at any time, switch "Keep pages in order in this space" off and
on again.

**Does it sort folders?**
No: it moves pages only, so folders, whiteboards and databases keep their places and the pages around them are ordered.
The pages inside a folder are sorted.

## Turn it on

1. Open the space's settings and the **Page order** tab, under Integrations.
2. Choose the order, then switch on "Keep pages in order in this space"; only a space admin can, and the app checks this
   with Confluence as you.
3. The whole space is put in order in the background, from its home page down.
   On our test site a space of 300 pages took under two minutes: the last of 267 moves came 98 s after the switch was saved.

## What it does

- **The four orders:** A to Z or Z to A by title, with numbers compared as numbers, or newest first or oldest first by
  the date each page was created.
- Pages created at the same moment, or with the same title, are always put in the same order, so no page flips back and
  forth.
- **Changing the order** while the app is on puts the whole space in the new order once.
- **From then on**, a page that is created, renamed, moved, copied or restored goes to its place among the pages beside
  it, and a moved or copied page also has the pages below it put in order, also when it is moved into another space.
  Confluence's Trash restores one page at a time, without the pages that were below it, so a restored page goes to its
  place on its own.
- **The fewest moves:** pages already in order stay where they are, and each other page is moved once, so renaming one
  page among 100 moves that one page.
  When several pages under one page are edited within seconds of each other, the app handles that page's edits one at a
  time, while edits under other pages go on alongside. Pages sorted again after Sort Alphabetically on the Reorder page are handled the same way,
  with each set of pages under one page sorted by one job at a time, so a click there and an edit beside that page still
  take the fewest moves. On our test site, 8 edits within 10 seconds under a page with 1,000 pages below it took 8 moves,
  the fewest, and the pages were in order 5 seconds after the last edit.
- Where pages are already in order, the app only reads them, and moves nothing.

## What it never does

- It never changes a page's parent: it moves a page only before or after a page beside it.
- It never moves the pages at the top level of a space.
- It never moves a folder, whiteboard or database.
- **It never moves a page for someone who could not edit it:**
  before each move, it asks Confluence whether the person who caused the change may edit that page, and if not, that page
  stays where it is and the rest are ordered around it.
  A change with no person behind it moves nothing.
- It never guesses the current order: where Confluence does not give a page's position, nothing under that page is moved.
- Without an active licence it reads and moves nothing.

## Pages with edit restrictions

A page whose edit restrictions leave out Keep Pages Sorted keeps its place, because Confluence does not let the app move
it, and the pages around it are ordered.
To sort it, add the app to the page's editors, as the settings tab says.

## Limits

- The title orders use one fixed alphabet, English rules with numbers as numbers, and not your language's own.
  So letters some languages sort apart are ordered as their base letter, as German orders them: å, ä and ö among the
  a's and o's, where Swedish and Finnish put them after z; æ as ae and ø as o, where Danish and Norwegian put æ, ø and å
  after z; ł and ć as l and c, where Polish puts each after its base letter; and ñ as n, where Spanish puts it after n.
- Folders are not sorted, because the app moves pages only.
- Where Confluence gives no creation date for a page, the newest-first and oldest-first orders leave the pages beside it
  as they are for that moment, and sort them again about a minute later, once. If a date is still missing then, they stay as they are until the
  next page change there. On our test site this happened only when
  a page beside them was sent to the trash at the moment the app read them.
- The largest we have tested on our own site: a space of 2,041 pages, 1,590 of them out of order, was in order less than
  7 minutes after it was turned on, in each of three runs;
  and one page with 1,000 pages below it, at about 0.47 s per move (939 moves in 7 min 45 s).
  The pages below one page are put in order by one job at a time, so a page with a few thousand pages below it, out of
  order, may take tens of minutes to sort when the app is turned on.

## Turn it off

Switch the tab off; pages stay where they are, and pages created while it is off stay where Confluence puts them.
Switching it back on puts the whole space in order again.
If a space is deleted while the app is on in it, a new space made later with the same key starts with the app off, until
one of its own space admins turns it on.
