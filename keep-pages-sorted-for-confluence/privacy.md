# Keep Pages Sorted Alphabetically for Confluence: privacy policy

Keep Pages Sorted Alphabetically for Confluence ("the app") is made by Wrenkit.

## What the app reads

Only what it needs to keep the pages under each page and folder in order, from your Confluence site:
- the pages and folders above a page, to find the page or folder whose children it orders;
- the items directly under a page or folder, with their ids, types, titles and positions in the page tree;
- the date each page was created, read only in a space whose admin chose newest first or oldest first;
- the space's home page, where a sort of the whole space starts;
- whether the person opening or saving the app's setting is a space admin, asked of Confluence as that person;
- whether the person who caused a page change may edit a page, asked of Confluence before the app moves that page;
- the app's own account, so that the events its own moves cause are recognised and ignored.

It reads page titles, because it sorts by them, but it never asks for page content, comments, attachments, labels or
properties.

## What the app keeps

In Atlassian's Forge storage for your site, and nowhere else, it keeps one record per space: whether a space admin
turned the app on, which order they chose, and the id Confluence gives that space, so that a new space made later with
the same key as a deleted one starts with the app off. It also keeps the id of its own account, the one
Atlassian creates for the app on your site, which it reads from Confluence once, so that it can tell the changes its own
moves cause from the changes people make. It keeps no page titles,
page ids, names, email addresses, page content or account id of any person.

While a change waits in the app's queue, which Atlassian's Forge platform runs, the queued job holds the space key, the
space id, the page id and the account id of the person who caused the change, so that each move can be checked against that person.

## What leaves Atlassian

Nothing: the app runs on Atlassian's Forge platform, and its manifest declares no permission to reach anything outside
your Confluence site.

Its logs, which Atlassian keeps for us, hold one line per job, with the kind of job and counts of what happened (for
example "moved: 1"), including how many times Confluence asked it to slow down, how many moves it tried again because
another move held Confluence's page-move lock, and how many answers warned that the app's hourly allowance was running
low, and which of Confluence's rate-limit pools (the one every site shares, or one for your site alone) those answers named and which one ran out, or the kind of error when a job fails; one line for each change it drops before queueing any work, saying whether
the app's own move caused it or sorting is off in its space; one line when Atlassian refuses to queue a change, saying
which try it was; one line when Confluence asks a job to wait longer than a few seconds, saying which try it was and after how many seconds Atlassian sends it again; one line when a job leaves pages as they are because Confluence gave no date for one of them,
saying how many places are queued to be sorted again and after how many seconds, or that Atlassian refused that queueing; while the app is paused, one line per job saying it skipped; and one line each time a space admin
saves the setting, saying only whether it is on and which order.
They hold no page ids, titles, space keys, account ids or content.
Atlassian shows us these logs for the past 30 days only, and that limit is Atlassian's, not ours.

## Who sees it

Wrenkit sees those log lines and the app's usage figures (how much computing the app used) in Atlassian's developer
console. We hold nothing of yours
outside Atlassian, so we have nothing of yours to sell or share.

## Data processing

Atlassian processes the app's data under the Forge Terms and Atlassian's data processing addendum, and we have no other
processor.

## When you uninstall

The app has no uninstall step, so uninstalling it moves no page.
Atlassian's Forge hosted storage keeps the app's data (each space's switch and order, and the app's own account id) for 28 days after the uninstall,
where the app can no longer read it, and then deletes it.
Within the first 21 days, Atlassian can re-link it to a reinstalled app, but only if you ask.

## Contact

support@brendenbushman.com.
