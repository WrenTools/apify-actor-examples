# Security: Edit Inheritance for Confluence

## Report a vulnerability

Write to **support@brendenbushman.com** with the subject "Security": what you found, the steps to see it, and your
site's address. We treat a security report as critical, so we answer within 24 hours, as on our support page. Please do
not test against other customers' sites, and give us the time below to fix it before you publish.

## How fast we fix

We follow Atlassian's Security Bug Fix Policy for cloud apps. By the severity of the issue (its CVSS score), a fix must
ship within:

| Severity | CVSS score | Fixed within |
|---|---|---|
| Critical | 9.0 or more | 10 days of being reported or triaged |
| High | 7.0 or more | 4 weeks |
| Medium | 4.0 or more | 12 weeks |
| Low | under 4.0 | 25 weeks |

A fix ships as a new version of the app.

## What the app keeps, and what it logs

- **Stored, in Atlassian's Forge storage only:** for each space, whether a space admin turned the app on; for each page
  the app gave an edit list, the account ids and group ids it wrote and the page it took them from. No names, email addresses or page content.
- **Nothing leaves Atlassian.** The app declares no permission to reach anything outside your Confluence site.
- **Logs:** one line per job, with the kind of job, counts of what it did, how many times Confluence asked it to slow
  down and it tried again, how many of Confluence's answers warned that the app's hourly allowance was running low, which rate-limit pool (shared by every site, or per site) they named and which one ran out, and
  whether the job asked Confluence for the app's own account (1 or 0), or the kind of error (for a storage error, its code) and those counts when a job fails;
  and one line each time a space admin turns the app on or off, saying only which way. No page ids, space keys,
  account ids, names or content. The logs are kept by
  Atlassian's Forge platform, which shows them for the past 30 days; that is Forge's retention, not a promise of ours.
- **No passwords, API tokens or keys of yours.** The app calls Confluence through Atlassian's Forge platform, as the app
  or as the person using its settings tab.
- **Never more than the person could do:** before each change, the app asks Confluence whether the person who caused it
  may edit that page, and changes nothing if not.
- **After you uninstall,** Atlassian's Forge storage keeps the app's stored data for 28 days; the app can no longer read
  it.

## If something goes wrong

A security incident, as Atlassian defines it for apps, is any actual or suspected unauthorized access to, or use,
disclosure, change or destruction of, your data that we hold; a compromise of the app; or an issue that materially
degrades Atlassian's systems. If one happens, we:

1. **Contain it** as fast as we can: ship a version of the app that changes nothing on any site until the cause is
   fixed, and work with Atlassian on any further step.
2. **Tell Atlassian** promptly, and no later than 24 hours, with what we know, and keep them updated.
3. **Find the cause:** from the app's logs, its code and the history of every version we released, which pages and
   sites were affected, and for how long.
4. **Tell affected customers**, within 72 hours of finding the incident where we can, with what happened, what was
   affected and what we are doing.
5. **Fix it**, within the times above, and then review what let it happen, so that it does not happen again.
