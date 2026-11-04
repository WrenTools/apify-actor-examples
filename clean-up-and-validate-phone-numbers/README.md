# Clean up and validate the phone numbers in a spreadsheet (Python)

This example cleans up a column of phone numbers that people typed in themselves, each written its own way. It sends
the Phone column of a CSV file to the
[Phone Number Validator](https://apify.com/wrentools/phone-number-validator-offline) Actor on Apify in one run, then
writes a copy of the file with each valid number in one standard form, its country and its kind of line, the rows that
repeat an earlier number marked, and the reason beside each number that can't be right. It is about 80 lines of
Python, with no packages to install.

**Disclosure:** we built and sell that Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

**Watch it first:** our video
[Clean Up and Validate Phone Numbers in a Spreadsheet: E.164, Possible vs Valid](https://youtu.be/mZWIW0tQaCk)
(narrated by a synthetic voice) works through this same sheet, and the
[written version](https://wrentools.hashnode.dev/validate-phone-numbers-in-python) shows the checks in Python.

## What the check does to a number

- **One standard form, E.164.** To a program, `0161 496 0123` and `+44 (0)161 496 0123` are two different strings,
  so it can't see that they are one number. E.164 writes every number one way: a plus, the country code, then the
  rest of the number with no spaces, dashes or brackets. Both of those become `+441614960123`: the 0 is dialled only
  from inside the country, so it comes off when +44 goes on the front. Store numbers in this form, and format them for
  people only when you show them.
- **A default country.** A number written without a plus doesn't say which country it is from, so the check needs a
  default. The example's sheet comes from a studio in Manchester, so it runs with `GB`.
- **Possible or valid.** A number is *possible* when it has the right number of digits for its country. It is
  *valid* when its digits also fall in a range that the country's numbering plan uses. The Actor reads the plans from
  Google's libphonenumber.
- **What no check of the digits can know:** whether a number is switched on, or whose it is. The Actor asks nobody:
  it only compares the digits with the plan, and no number leaves the run.

## Run it

You need Python 3 (we ran it with Python 3.14 on Windows 11), an
[Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API & Integrations). The
token goes in an environment variable, `APIFY_TOKEN`, never in the script.

```bash
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python clean_phones.py signups.csv GB    # Windows: py clean_phones.py signups.csv GB
```

The file needs a column named `Phone`; the second argument is the default country, as a two-letter code (`GB`, `US`,
`DE` ...). The script sends the column in one run of the Actor, waits for it, and writes `signups-clean.csv` beside
the file. It does not change the file you give it.

## Output

For [`signups.csv`](signups.csv), the made-up sign-up sheet from the video (nine rows, below), the script prints:

```
row 4: '+44 (0)161 496 0123' is the same number as row 1
row 5: '07700 900461' not-in-numbering-plan
row 6: '(415) 555-0132' not-in-numbering-plan
row 8: 'n/a' not-a-number
row 9: '02079460958' is the same number as row 2
9 rows: 6 valid (4 different numbers), 3 to check. Wrote signups-clean.csv
```

and `signups-clean.csv` is every row as it was, with five columns added:

```csv
Name,Phone,e164,country,line_type,problem,same_as_row
Amara Okafor,0161 496 0123,+441614960123,GB,FIXED_LINE,,
Dev Patel,020 7946 0958,+442079460958,GB,FIXED_LINE,,
Grace Liu,+61 491 570 156,+61491570156,AU,MOBILE,,
A. Okafor,+44 (0)161 496 0123,+441614960123,GB,FIXED_LINE,,1
Sam Hughes,07700 900461,,,,not-in-numbering-plan,
Maya Brooks,(415) 555-0132,,,,not-in-numbering-plan,
Owen Price,0113 496 0457,+441134960457,GB,FIXED_LINE,,
Ines Moreau,n/a,,,,not-a-number,
Dev Patel,02079460958,+442079460958,GB,FIXED_LINE,,2
```

What the three rows to check mean:

- **Sam Hughes** is *possible but not valid*: with the 0 left off it has 10 digits, like a British mobile, but
  07700 900 is a block the UK's regulator keeps for TV and film and doesn't give out. Only Sam can say the right
  number.
- **Maya Brooks** wrote an American number without +1, so it was read as British, where its 10 digits fit no range. A
  person can fix this one: in the video, `+1 (415) 555-0132` sent again came back valid, `+14155550132`, `US`, as
  `FIXED_LINE_OR_MOBILE` (in the US and Canada, mobiles and landlines share the same ranges, so the digits can't tell
  them apart).
- **Ines Moreau** typed `n/a`, which is not a number at all.

`same_as_row` points each repeat at the first row with the same E.164 number: Amara Okafor signed up twice, writing
her number two ways, and Dev Patel is in the sheet twice. Nothing is removed; you decide which row to keep.

### The sheet's numbers ring no one

Every number in `signups.csv` comes from a range set aside for fiction:

| Row | Number | Range |
|---|---|---|
| 1, 4 | 0161 496 0123 | Manchester, 0161 496 0000 to 0999 |
| 2, 9 | 020 7946 0958 | London, 020 7946 0000 to 0999 |
| 7 | 0113 496 0457 | Leeds, 0113 496 0000 to 0999 |
| 5 | 07700 900461 | UK mobile, 07700 900000 to 900999 |
| 6 | (415) 555-0132 | North America, 555-0100 to 555-0199 |
| 3 | +61 491 570 156 | Australia, on the regulator's list of mobile numbers for fiction |

The UK ranges are Ofcom's
[telephone numbers for use in TV and radio drama](https://web.archive.org/web/20241223042545id_/https://www.ofcom.org.uk/phones-and-broadband/phone-numbers/numbers-for-drama)
("The numbers will not be allocated to communications providers in the foreseeable future"); the North American range
and the Australian number are in Wikipedia's
[Fictitious telephone number](https://en.wikipedia.org/wiki/Fictitious_telephone_number) (the 555 range is "specifically
reserved by the North American Numbering Plan Administrator"; the Australian list is the ACMA's).

## Cost

The Actor charges **$0.0004 for each number checked** ($0.40 per 1,000), with no start fee, so this sheet's nine rows
cost $0.0036. You need an Apify account and its API token, as above.

`MAX_CHARGE_USD` at the top of the script caps what one run can cost you: at $0.0004 a number, `1.00` covers 2,500
numbers. If a run reaches the cap, the Actor stops, and the script, which gets back fewer results than rows, writes
nothing and says how many were checked. For a bigger sheet, raise the cap.

## Limits

- One column, named `Phone`, and one default country for the whole file. A number written with a plus is read by its
  own country code, whatever the default.
- An empty cell comes back as `empty`, and a row is never dropped, so the cleaned file has the same rows in the same
  order.
- The check says whether a number fits its country's plan, not whether it works or who has it.
