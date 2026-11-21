# Security: Keep Pages Sorted Alphabetically for Confluence

## Report a vulnerability

Write to **support@brendenbushman.com** with the subject "Security": what you found, the steps to see it, and your
site's address.
We treat a security report as critical, so we answer within 24 hours, as on our support page.
Please do not test against other customers' sites, and give us the time below to fix it before you publish.

## How fast we fix

We follow Atlassian's Security Bug Fix Policy for cloud apps, by the severity of the issue (its CVSS score):

| Severity | CVSS score | Fixed within |
|---|---|---|
| Critical | 9.0 or more | 10 days of being reported or triaged |
| High | 7.0 or more | 4 weeks |
| Medium | 4.0 or more | 12 weeks |
| Low | under 4.0 | 25 weeks |

A fix ships as a new version of the app.

## What the app keeps, and what it logs

- **Stored, in Atlassian's Forge storage only:** for each space, whether a space admin turned the app on and which order
  they chose, and the app's own account id, so that it can tell its own moves from people's; nothing else: no titles,
  names, email addresses, page content or any person's account id.
- **Nothing leaves Atlassian:** the app declares no permission to reach anything outside your Confluence site.
- **Logs:** one line per job, with the kind of job and counts of what it did (rate-limit retries, moves tried again
  after a move conflict, rate-limit warnings, and which rate-limit pool, shared by every site or per site, the answers named and which one ran out, among them), or the kind of error when a job fails; one line for each
  change it drops before queueing any work, saying whether the app's own move caused it or sorting is off in its space;
  one line when Atlassian refuses to queue a change; one line when Confluence asks a job to wait longer than a few seconds,
  saying which try it was and after how many seconds Atlassian sends it again; one line when pages left as they are for a missing date are queued
  to be sorted again, saying how many and after how many seconds, or that Atlassian refused it; while the app is paused, one line per job saying it skipped; and
  one line each time a space admin saves the setting, saying only whether it is on and which order; no page ids, titles,
  space keys, account ids or content.
- The logs are kept by Atlassian's Forge platform, which shows them for the past 30 days; that is Forge's retention, not
  a promise of ours.
- **No passwords, API tokens or keys of yours:** the app calls Confluence through Atlassian's Forge platform, as the app
  or as the person using its settings tab.
- **Never more than the person could do:** before each move, the app asks Confluence whether the person who caused the
  change may edit that page, and leaves the page where it is if not.
- **Pages only, and never to another parent:** the app moves a page only before or after a page beside it.
- **After you uninstall,** Atlassian's Forge storage keeps the app's stored data for 28 days, and the app can no longer
  read it.

## If something goes wrong

A security incident, as Atlassian defines it for apps, is any actual or suspected unauthorized access to, or use,
disclosure, change or destruction of, your data that we hold; a compromise of the app; or an issue that materially
degrades Atlassian's systems.
If one happens, we follow Atlassian's steps for an app security incident:

1. **Contain it** as fast as we can: ship a version of the app that moves nothing on any site until the cause is fixed,
   and work with Atlassian on any further step.
2. **Tell Atlassian** promptly, and no later than 24 hours, with what we know, and keep them updated.
3. **Find the cause** from the app's logs, its code and the history of every version we released: which sites were
   affected, and for how long.
4. **Tell affected customers** within 72 hours of finding the incident where we can, with what happened, what was
   affected and what we are doing.
5. **Fix it** within the times above, and then review what let it happen, so that it does not happen again.
