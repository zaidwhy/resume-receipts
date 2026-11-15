# resume-receipts

Every number on my resume, re-checked every morning against the public record behind it.

A resume is a list of claims nobody checks. This repository checks mine: each claim in
[`claims.json`](claims.json) points at its source (a GitHub API field, a line in a results file, a
registry entry, a DOI), and a daily job fetches the source and records whether it still says what the
resume says. The result is [`report.json`](report.json), shown at
[solstine.dev/receipts](https://www.solstine.dev/receipts).

## The rule

A claim is **matched** only when the source says it verbatim: the quoted span is present (after markdown
emphasis is stripped and whitespace collapsed), or the JSON field holds the stated value. Paraphrase does
not count. A source that cannot be fetched is **could not be checked**, never matched.

Some claims have no public source: work in private company repositories, university records, a test count
that only exists as a test run. Those are listed as **not publicly checkable** with the reason, so the page
never implies it checks more than it does.

If a public source ever contradicts the resume, the job fails and the report says which claim.

## Checks

| check | passes when |
|---|---|
| `quote` (default) | the quoted span appears in the fetched text |
| `equals` | a JSON field (dotted path, e.g. `info.name`) equals the expected value |
| `at_least` | a numeric JSON field is at least the stated minimum (star counts only go up the page as floors) |
| `resolves` | the URL answers with a page (DOIs, store listings) |
| `private` | never fetched; carries the reason it cannot be checked publicly |

## Run it

```
python receipts.py claims.json report.json
python -m pytest -q
```

Standard library only. The tests plant false claims (a wrong number, a flipped PR state, an inflated star
count) and assert that each is rejected; a checker that only ever agrees proves nothing.

This grew out of a job application to a company whose product refuses to mark a statement verified unless
the quoted text is in the record. Applying the same rule to my own resume seemed fair.
