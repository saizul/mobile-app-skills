import json

import pytest

from conftest import fixture, load_script, run_script

SKILL = "store-listing-writer"
SCRIPT = "check_listing.py"
mod = load_script(SKILL, SCRIPT)


def checks(findings):
    return {(f.store, f.field, f.check) for f in findings}


def test_bad_listing():
    findings, _ = mod.check(mod.load(str(fixture("store-listing", "bad.json"))))
    found = checks(findings)
    assert ("play", "title", "length.over") in found
    assert ("play", "short_description", "length.over") in found
    assert ("play", "title", "policy.promotional") in found
    assert ("play", "title", "style.all_caps") in found
    assert ("play", "short_description", "platform.other") in found
    assert ("play", "full_description", "policy.keyword_stuffing") in found
    assert ("play", "release_notes", "notes.generic") in found
    assert ("appstore", "name", "policy.price") in found
    assert ("appstore", "subtitle", "platform.other") in found
    assert ("appstore", "description", "field.missing") in found
    for c in ("keywords.spaces", "keywords.duplicate", "keywords.in_title", "keywords.filler", "keywords.separator"):
        assert ("appstore", "keywords", c) in found, c
    assert ("appstore", "keywords", "keywords.plural") in found


def test_good_listing_is_clean():
    findings, usage = mod.check(mod.load(str(fixture("store-listing", "good.json"))))
    assert [f.as_dict() for f in findings] == []
    title = next(u for u in usage if u["field"] == "title")
    assert title["length"] == 30 and title["limit"] == 30


def test_keywords_count_bytes_not_characters():
    jp = "家計簿,節約"  # 6 characters, 16 bytes
    assert mod.measure("appstore", "keywords", jp) == len(jp.encode())
    assert mod.measure("appstore", "subtitle", jp) == len(jp)
    long_jp = ",".join(["家計簿"] * 12)  # 47 chars, 119 bytes
    findings = mod.check_locale("appstore", "ja", {"name": "x", "description": "y", "keywords": long_jp})
    assert any(f.check == "length.over" and f.field == "keywords" for f in findings)


def test_fastlane_layout():
    listing = mod.load(str(fixture("store-listing", "fastlane-project")))
    assert set(listing["play"]) == {"en-US", "de-DE"}
    assert listing["play"]["en-US"]["release_notes"].startswith("Shared budgets")  # highest versionCode wins
    assert set(listing["appstore"]) == {"en-US", "ja"}  # review_information is not a locale
    findings, _ = mod.check(listing)
    over = {(f.store, f.locale, f.field) for f in findings if f.check == "length.over"}
    assert over == {("play", "de-DE", "title"), ("appstore", "ja", "keywords")}
    # pointing at the metadata folder directly works too
    assert mod.load(str(fixture("store-listing", "fastlane-project", "fastlane", "metadata"))) == listing


def test_flat_json_without_locale():
    listing = mod.normalize({"play": {"title": "Pocket Budget"}})
    assert listing == {"play": {"default": {"title": "Pocket Budget"}}}
    with pytest.raises(ValueError):
        mod.normalize({"android": {}})


@pytest.mark.parametrize(
    "title,promo",
    [("Pocket Budget", False), ("Best Budget Planner", True), ("Budget #1 Planner", True), ("Bestow Notes", False)],
)
def test_promotional_words_whole_word(title, promo):
    found = mod.check_locale("play", "en", {"title": title, "short_description": "x", "full_description": "y"})
    assert any(f.check == "policy.promotional" for f in found) is promo


def test_emoji_and_whitespace():
    found = mod.check_locale(
        "play", "en", {"title": " Pocket Budget \U0001f4b0", "short_description": "x", "full_description": "y"}
    )
    assert {"policy.emoji", "whitespace.edges"} <= {f.check for f in found}


def test_cli(tmp_path):
    bad = str(fixture("store-listing", "bad.json"))
    good = str(fixture("store-listing", "good.json"))
    assert run_script(SKILL, SCRIPT, bad).returncode == 1
    assert run_script(SKILL, SCRIPT, good).returncode == 0
    assert run_script(SKILL, SCRIPT, bad, "--fail-on", "none").returncode == 0
    r = run_script(SKILL, SCRIPT, bad, "--json", "--store", "appstore", "--min-severity", "medium")
    data = json.loads(r.stdout)
    assert {f["store"] for f in data["findings"]} == {"appstore"}
    assert all(f["severity"] in ("medium", "high") for f in data["findings"])
    r = run_script(SKILL, SCRIPT, "-", stdin=(fixture("store-listing", "good.json")).read_text())
    assert r.returncode == 0 and "0 finding(s)" in r.stdout
    limits = run_script(SKILL, SCRIPT, "--limits")
    assert limits.returncode == 0 and "100 bytes" in limits.stdout and "170" in limits.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.json")).returncode == 2
    (tmp_path / "empty").mkdir()
    assert run_script(SKILL, SCRIPT, str(tmp_path / "empty")).returncode == 2
    assert run_script(SKILL, SCRIPT).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
