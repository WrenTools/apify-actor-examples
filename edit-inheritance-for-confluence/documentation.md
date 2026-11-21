# Edit Inheritance for Confluence: documentation

Confluence Cloud passes **view** restrictions down to child pages, but not **edit** restrictions (Atlassian's issue
CONFCLOUD-5095). This app passes edit restrictions down, in the spaces where a space admin turns it on.

## Questions people ask

**Do child pages inherit edit restrictions of the parent?** Not in Confluence Cloud on its own. A view restriction on a
parent page covers every page below it; an edit restriction covers only the page it is set on, so child pages need
their own. Atlassian's feature request for this is CONFCLOUD-5095. In a space where this app is turned on, they do: a
child page that is created, moved or copied under a page with edit restrictions gets the same editors.

**How do I give edit permission to certain people on all child pages at once?** Set the editors on the parent page
and turn the app on in the space. Turning it on goes through the space once, from each of its top-level pages down (the homepage and every page beside
it): every child page
below a page with editors, that has no restrictions set by hand, gets that page's editors. With the app on, set or change the editors on a parent page and every such child page below it gets the
same list, with no click on each page.

**My parent page is restricted, so why can anyone in the space edit the new page under it?** Because Confluence copies
only the view restriction down; the new page's edit list starts empty. With the app on, a page created or moved there
gets the parent's editors once Confluence sends the app the page's event. The app works from that event, so until it
arrives the page is as Confluence left it. For a new page it then waits 5 seconds before it reads the page, so editors
someone sets in those first seconds are that page's own, and stay.

**Will it change pages where someone set the editors by hand?** No, with one narrow exception. A list a person set, or
changed after the app wrote it, is that page's own from then on, and pages below it inherit that list instead. Just before it writes a page's list, the app reads the page again and writes nothing if anyone
changed it. Confluence
gives no way to make a write depend on what the list holds, so a list set by hand in the fraction of a second between
that read and the write can still be replaced. In practice that is a new page restricted about 6 to 8 seconds after it is created, the
moment the app writes it, because the app waits 5 seconds before it first reads a new page. On our test site, with that
wait, none of 20 pages restricted 1 to 3 seconds after they were created was replaced (before the wait, 2 of 20 were), and
4 of 20 restricted 6 to 8 seconds after creation were.
If it happens, set the list again: it is then that page's own, and the app does not
write it again.

**Can it remove someone's access?** It never takes a restriction away. When editors are removed from a parent, the
pages below follow the new list; when a parent loses all its editors, or a page moves somewhere unrestricted, the
pages keep the editors they have.

**Does it work on the Confluence Free plan?** There is nothing for it to do there. On Confluence Free, everyone who can
log in can view and edit all content, and permissions cannot be changed (Atlassian's page on Confluence Cloud plans).
It is for Standard, Premium and Enterprise sites.

## Turn it on

1. Open the space's settings and the **Edit inheritance** tab.
2. Switch it on. Only a space admin can; the app checks this with Confluence as you. In the minute after the app is installed or
   updated, Atlassian may not accept the work yet: the switch then goes back to off and the tab asks you to try again in a
   minute.
3. The app needs permission to edit pages in the space. On our test site Confluence gave its account (an app named
   **edit-inheritance**) the Admin role in each space we made. If your space's permissions leave it out, it changes nothing
   there and the tab says so: in Space settings, Users, give **edit-inheritance** the Collaborator role or higher.
4. The pages already in the space get their parent pages' editors in the background; a large space takes a few
   minutes (a space of 482 pages took under 5 on our test site).
   A space of thousands of pages can take about an hour: Atlassian limits how much an app may ask of Confluence each
   hour, and when that runs out the app waits for the next hour and carries on (on our test site, giving 5,300 pages
   their editors took about an hour, most of it that wait).

## What it does

- **A new page, a moved page, a copied page.** If it has no edit restriction of its own, it gets the editors of the
  nearest page above it that has one. Folders, whiteboards, databases and Smart Links are passed through. Everything
  below a moved page is done too, in batches of 200 pages, so a large tree takes longer than the page itself. In a copied
  tree, Confluence tells the app about every copied page, and each one is done on its own, so a large copied tree takes
  longer too.
  On our developer site, a moved tree of 1,001 pages had its editors on every page about 13 minutes after the move, about
  78 pages a minute, and a copied tree of 113 pages about one minute after the copy.
  A new or moved live doc counts as a page.
- **Turning it on.** When a space admin turns the app on in a space, it goes through the pages already there once,
  from each of the space's top-level pages, folders, whiteboards, databases and Smart Links down (the homepage and
  everything beside it), and gives each the editors of the nearest page above it that has some, by the same rules as
  a new page. It does this as the admin who turned it on: a page that admin could not edit is left as it is.
- **The app's own account is added to each list it writes**, because Confluence needs it there to change the list
  later.
- **When a page's editors change**, the pages below whose list the app wrote, and that nobody has changed since, get the
  new list. So do pages below that have no restrictions at all, such as child pages that were there before the space
  was turned on. No button to press.

## What it never does

- It never changes a list a person set, or changed after the app wrote it, except one set in the fraction of
  a second while the app is writing that page's list (above).
- Nothing loses a restriction: not when a page above loses its editors, and not when a page moves somewhere
  unrestricted.
- It leaves alone a page with a view restriction of its own.
- It never copies a list longer than Confluence's answer holds.
- **It never writes for someone who could not have.** Before each change, it asks Confluence whether the person who
  caused the event may edit that page. If not, or if there is no such person, nothing is written.
- Without an active licence it does nothing.

## What you will see

Changes appear in each page's restrictions dialog, made by the app. A large tree is done in batches of 200 pages, so it
may take a few minutes.

## Limits

- Group membership is not read: a page with its own view restriction is skipped rather than risk a refused write.
- If Confluence refuses a change (for example the app's account may not edit that page), that page is skipped and the
  rest go on. In a space whose permissions leave the
  app out, every change is refused this way, once each and never retried, and other spaces are served as before.

## Turn it off

Switch the tab off. Lists already written stay as they are: turning it off removes nobody's restriction.
