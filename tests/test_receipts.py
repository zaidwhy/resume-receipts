import json
import urllib.error

import pytest

import receipts

README = "Plain BM25 on the same 500 questions scores 95.2% (**476 of 500**).\nexact McNemar p = 0.28\n"
PR_JSON = json.dumps({"merged": True, "stargazers_count": 8829, "info": {"name": "tiebreak-rerank"}})


@pytest.fixture
def sources(monkeypatch):
    pages = {"https://x/readme": README, "https://x/pr": PR_JSON}

    def fake_fetch(url):
        if url not in pages:
            raise urllib.error.URLError("unreachable")
        return pages[url]

    monkeypatch.setattr(receipts, "fetch", fake_fetch)


def verdict(claim):
    return receipts.check(claim, {})["verdict"]


def test_quote_matches_through_markdown_emphasis(sources):
    claim = {"claim": "c", "source": "https://x/readme", "quote": "scores 95.2% (476 of 500)"}
    assert verdict(claim) == "matches"


def test_planted_wrong_number_is_rejected(sources):
    claim = {"claim": "c", "source": "https://x/readme", "quote": "scores 95.2% (486 of 500)"}
    assert verdict(claim) == "not found in source"


def test_flipped_pr_state_is_rejected(sources):
    claim = {"claim": "c", "check": "equals", "source": "https://x/pr", "field": "merged", "expected": False}
    assert verdict(claim) == "not found in source"


def test_at_least_rejects_an_inflated_star_count(sources):
    ok = {"claim": "c", "check": "at_least", "source": "https://x/pr", "field": "stargazers_count", "minimum": 8800}
    inflated = {**ok, "minimum": 9000}
    assert verdict(ok) == "matches"
    assert verdict(inflated) == "not found in source"


def test_nested_field(sources):
    claim = {"claim": "c", "check": "equals", "source": "https://x/pr", "field": "info.name", "expected": "tiebreak-rerank"}
    assert verdict(claim) == "matches"


def test_unreachable_source_is_never_reported_as_matched(sources):
    claim = {"claim": "c", "source": "https://x/missing", "quote": "anything"}
    assert verdict(claim) == "could not be checked"


def test_private_claim_is_labelled_not_checked(sources):
    claim = {"claim": "c", "check": "private", "reason": "company repository"}
    assert receipts.check(claim, {}) == {"verdict": "not publicly checkable", "evidence": "company repository"}


def test_contradicted_claim_fails_the_run(sources, tmp_path, monkeypatch):
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps([{"claim": "c", "source": "https://x/readme", "quote": "999 of 500"}]), encoding="utf-8")
    report = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["receipts.py", str(claims), str(report)])
    assert receipts.main() == 1
    assert json.loads(report.read_text(encoding="utf-8"))["counts"] == {"not found in source": 1}
