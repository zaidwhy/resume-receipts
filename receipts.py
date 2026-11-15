"""Re-check every number on a resume against the public record behind it.

Verdicts, strictest first:
  matches              the source says exactly this (quoted span present, or the JSON field holds the value)
  not found in source  the source was read and does not say it
  could not be checked the source could not be fetched this run
  not publicly checkable  the claim has no public source (a private company repository, a transcript);
                       listed so the page never implies more than it checks

A quoted span matches only verbatim, after markdown emphasis is stripped and whitespace collapsed.

Usage: python receipts.py claims.json report.json
"""

import datetime
import json
import logging
import re
import sys
import urllib.error
import urllib.request

log = logging.getLogger("receipts")

FETCH_TIMEOUT_S = 20
FETCH_ATTEMPTS = 2
MAX_SOURCE_BYTES = 3_000_000
MAX_CLAIMS = 80
SCHEMA_VERSION = 1


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "resume-receipts/1.0",
                                                   "Accept": "application/json, text/plain, */*"})
    body = b""
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
                body = response.read(MAX_SOURCE_BYTES + 1)
            break
        except (TimeoutError, urllib.error.URLError):
            if attempt == FETCH_ATTEMPTS:
                raise
    if len(body) > MAX_SOURCE_BYTES:
        raise ValueError(f"source larger than {MAX_SOURCE_BYTES} bytes")
    return body.decode("utf-8", errors="replace")


def json_path(source: str, path: str):
    value = json.loads(source)
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def line_of(source: str, quote: str) -> int | None:
    joined, starts = "", []
    for number, raw in enumerate(source.splitlines(), 1):
        text = normalize(raw)
        if text:
            starts.append((len(joined), number))
            joined += text + " "
    position = joined.find(normalize(quote))
    if position < 0:
        return None
    return max((s for s in starts if s[0] <= position), default=(0, None))[1]


def check(claim: dict, cache: dict) -> dict:
    kind = claim.get("check", "quote")
    if kind == "private":
        return {"verdict": "not publicly checkable", "evidence": claim["reason"]}
    url = claim["source"]
    try:
        if url not in cache:
            cache[url] = fetch(url)
    except Exception as exc:
        log.warning("fetch failed for %s: %s", url, exc)
        return {"verdict": "could not be checked", "evidence": str(exc)[:200]}
    source = cache[url]
    if kind == "resolves":
        return {"verdict": "matches", "evidence": "source answered with a page"}
    if kind == "quote":
        line = line_of(source, claim["quote"])
        if line is None:
            return {"verdict": "not found in source", "evidence": ""}
        return {"verdict": "matches", "evidence": f"line {line}"}
    try:
        value = json_path(source, claim["field"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        return {"verdict": "not found in source", "evidence": f"field {claim['field']} unreadable: {exc}"[:200]}
    if kind == "equals":
        ok = value == claim["expected"]
    elif kind == "at_least":
        ok = isinstance(value, (int, float)) and value >= claim["minimum"]
    else:
        raise ValueError(f"unknown check '{kind}' in claim: {claim['claim']}")
    return {"verdict": "matches" if ok else "not found in source", "evidence": f"{claim['field']} = {json.dumps(value)}"}


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if len(sys.argv) != 3:
        print("usage: python receipts.py claims.json report.json", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as fh:
        claims = json.load(fh)
    if len(claims) > MAX_CLAIMS:
        print(f"claims file has {len(claims)} claims; the limit is {MAX_CLAIMS}", file=sys.stderr)
        return 2
    cache: dict[str, str] = {}
    results = [{**c, **check(c, cache)} for c in claims]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    report = {"schema_version": SCHEMA_VERSION,
              "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "counts": counts, "results": results}
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(counts))
    # A public claim that the source contradicts fails the run, so the daily job turns red.
    return 1 if counts.get("not found in source") else 0


if __name__ == "__main__":
    sys.exit(main())
