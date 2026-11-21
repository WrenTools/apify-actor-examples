# Edit Inheritance for Confluence: privacy policy

Edit Inheritance for Confluence ("the app") is made by Wrenkit. This page says what the app reads, what it keeps, and
where.

## What the app reads

Only what it needs to pass edit restrictions down a page tree, from your Confluence site:
- the parent pages above a page and the pages below it;
- each page's own view and edit restrictions: the people and groups on them;
- whether the person who caused a page event may edit a page, asked of Confluence;
- whether the person changing the app's space setting is a space admin;
- when a space admin turns the app on in a space: the space's homepage and its top-level pages, and, to find the
  folders, whiteboards, databases and Smart Links at the top of the space, the id and type of the one each page is in
  and of those above it; that is where it starts going through the pages already there;
- when a space admin opens the app's settings tab: the space's homepage, its restrictions, and whether the app itself
  may edit it, so the tab can say if the space's permissions leave the app out;
- the app's own account on your site.

It asks Confluence for no page content, comments or attachments: no call in the app reads them. Some answers carry
more than the app asks for: the lists of a page's children, of a space's top-level pages and of a space's pages give
each page's title, and the space's answer gives its name. The app takes only the ids from them, and from the lists of
the pages and other content above a page, a folder, a whiteboard, a database or a Smart Link (and whether each child,
parent or ancestor is a page or one of those), and ignores the rest: no title or space name is used, kept, logged or
queued.

## What the app keeps

In Atlassian's Forge storage for your site, and nowhere else:
- per space, whether a space admin turned the app on;
- per page whose edit list the app wrote: the list it wrote (Atlassian account ids and group ids) and the page it was
  inherited from, so it can tell later whether a person has changed it.
  The record is deleted when a person changes that list.

It keeps no names, email addresses or page content.

## What leaves Atlassian

Nothing. The app runs on Atlassian's Forge platform and makes no call outside your Confluence site: its manifest
declares no external fetch or egress permission. Its logs, which Atlassian keeps for us,
hold one line per job: the job's kind, counts of outcomes (for example "applied: 3"), how many times Confluence
asked it to slow down and it tried again, and how many of Confluence's answers warned that the app's hourly allowance was
running low, which of Confluence's rate-limit pools (the one every site shares, or one for your site alone) those answers named and which one ran out, and whether the job asked Confluence for the app's own account (1 or 0), or, when Confluence asks the app to wait longer than a few seconds, how long it asked (in seconds) and which try it was, or, when a job fails, the kind of error (for a storage error, its code, such as `STORAGE_LIMIT_EXCEEDED`) and
those same counts; and one line when a space admin turns the app on or off in a space, saying only that the setting is now on
or off. They hold no page ids, space keys, account ids, names or content. Atlassian shows us these logs for the past 30 days only; that limit is Atlassian's, not ours.

## Who sees it

Wrenkit sees only those log lines, in Atlassian's developer console. We do not sell, share or analyse your data.

## Data processing

Atlassian processes the app's data under the Forge Terms and Atlassian's data processing addendum. We have no other
processor.

## When you uninstall

The app stops. Atlassian's Forge hosted storage keeps the app's data (the edit lists it wrote and each space's setting)
for 28 days after the uninstall, where the app can no longer read it, and then deletes it. Within the first 21 days,
Atlassian can re-link it to a reinstalled app, but only if you ask.

## Contact

support@brendenbushman.com
