import json
import plistlib

import pytest

from conftest import fixture, load_script, run_script

SKILL = "ios-plist-audit"
SCRIPT = "plist_audit.py"
mod = load_script(SKILL, SCRIPT)
BAD = fixture("ios", "bad", "Info.plist")
GOOD = fixture("ios", "good", "Info.plist")


def keys(findings, check=None):
    return {(f.check, f.key) for f in findings if check is None or f.check == check}


def test_bad_plist_with_project():
    ent = mod.load_plist(fixture("ios", "bad-project", "ios", "App", "App.entitlements"))
    findings, caps = mod.audit(mod.load_plist(BAD), ent, fixture("ios", "bad-project"))
    missing = {k for _, k in keys(findings, "usage.missing")}
    assert {
        "NSBluetoothAlwaysUsageDescription",
        "NSHealthShareUsageDescription",
        "NSHealthUpdateUsageDescription",
        "NSLocationWhenInUseUsageDescription",
        "NSMicrophoneUsageDescription",
        "NSUserTrackingUsageDescription",
    } == missing
    assert "contacts" not in caps  # CNContactStore only appears in node_modules
    f = keys(findings)
    assert ("usage.empty", "NSPhotoLibraryUsageDescription") in f
    assert ("usage.vague", "NSCameraUsageDescription") in f
    assert ("usage.placeholder", "NSContactsUsageDescription") in f
    assert ("usage.deprecated", "NSLocationAlwaysUsageDescription") in f
    assert ("ats.arbitrary_loads", "NSAllowsArbitraryLoads") in f
    assert ("ats.insecure_domain", "legacy-api.example.com") in f
    assert ("ats.old_tls", "legacy-api.example.com") in f
    assert ("schemes.too_many", "LSApplicationQueriesSchemes") in f
    assert ("privacy.manifest_missing", "PrivacyInfo.xcprivacy") in f  # the one under Pods does not count
    assert ("export.encryption", "ITSAppUsesNonExemptEncryption") in f
    assert ("version.hardcoded", "CFBundleShortVersionString") in f
    assert ("version.hardcoded", "CFBundleVersion") not in f  # uses $(FLUTTER_BUILD_NUMBER)
    # no duplicate report for the location pair
    assert sum(1 for c, k in f if k == "NSLocationWhenInUseUsageDescription") == 1
    local = next(x for x in findings if x.key == "localhost")
    assert local.severity == "info"


def test_good_binary_plist_with_flutter_project():
    info = mod.load_plist(GOOD)  # binary plist
    findings, caps = mod.audit(info, None, fixture("ios", "good-project"))
    assert {"camera", "photos", "microphone", "faceid"} <= set(caps)
    assert "health" not in caps  # dev_dependencies are ignored
    assert findings == []


def test_plist_without_project_infers_from_background_modes():
    findings, caps = mod.audit({"UIBackgroundModes": ["location"], "ITSAppUsesNonExemptEncryption": False})
    assert caps == {"location-always": "UIBackgroundModes: location"}
    assert {k for _, k in keys(findings, "usage.missing")} == {
        "NSLocationWhenInUseUsageDescription",
        "NSLocationAlwaysAndWhenInUseUsageDescription",
    }


@pytest.mark.parametrize(
    "text,check",
    [
        ("", "usage.empty"),
        ("TODO", "usage.placeholder"),
        ("Lorem ipsum", "usage.placeholder"),
        ("This app needs access to your camera.", "usage.vague"),
        ("$(PRODUCT_NAME) needs the camera", "usage.vague"),
        ("Camera use", "usage.vague"),
        ("Scan paper receipts so the app can fill in the amount for you.", None),
    ],
)
def test_purpose_string_quality(text, check):
    found = {f.check for f in mod.audit_strings({"NSCameraUsageDescription": text})}
    assert found == ({check} if check else set())


def test_ats_scoped_keys():
    f = keys(
        mod.audit_ats(
            {
                "NSAppTransportSecurity": {
                    "NSAllowsArbitraryLoads": True,
                    "NSAllowsArbitraryLoadsInWebContent": True,
                    "NSAllowsLocalNetworking": True,
                }
            }
        )
    )
    assert ("ats.arbitrary_loads_scoped", "NSAllowsArbitraryLoadsInWebContent") in f
    assert ("ats.local_networking", "NSAllowsLocalNetworking") in f


def test_swift_api_detection(tmp_path):
    (tmp_path / "App").mkdir()
    (tmp_path / "App" / "Scanner.swift").write_text("let s = AVCaptureDevice.default(for: .video)\nATTrackingManager.x")
    caps = mod.code_capabilities(tmp_path)
    assert set(caps) == {"camera", "tracking"}


def test_errors(tmp_path):
    with pytest.raises(ValueError):
        mod.load_plist(fixture("ios", "broken.plist"))
    with pytest.raises(ValueError):
        mod.load_plist(fixture("ios", "array.plist"))


def test_cli(tmp_path):
    assert run_script(SKILL, SCRIPT, str(BAD)).returncode == 1
    assert run_script(SKILL, SCRIPT, str(GOOD), "--project", str(fixture("ios", "good-project"))).returncode == 0
    assert run_script(SKILL, SCRIPT, str(BAD), "--fail-on", "none").returncode == 0
    r = run_script(
        SKILL,
        SCRIPT,
        str(BAD),
        "--project",
        str(fixture("ios", "bad-project")),
        "--entitlements",
        str(fixture("ios", "bad-project", "ios", "App", "App.entitlements")),
        "--json",
        "--min-severity",
        "high",
    )
    data = json.loads(r.stdout)
    assert "health" in data["capabilities"] and all(f["severity"] == "high" for f in data["findings"])
    p = tmp_path / "Info.plist"
    p.write_bytes(plistlib.dumps({"ITSAppUsesNonExemptEncryption": False}))
    assert run_script(SKILL, SCRIPT, str(p), "--fail-on", "info").returncode == 0
    assert run_script(SKILL, SCRIPT, str(fixture("ios", "broken.plist"))).returncode == 2
    assert run_script(SKILL, SCRIPT, str(GOOD), "--project", str(tmp_path / "nope")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0


CAMERA = "Scan receipts with the camera to add expenses automatically."
PHOTOS = "Pick a photo of a receipt from your library to attach it to an expense."
LOC_INFO = {
    "CFBundleDevelopmentRegion": "en",
    "NSCameraUsageDescription": CAMERA,
    "NSPhotoLibraryUsageDescription": PHOTOS,
    "ITSAppUsesNonExemptEncryption": False,
}


def loc_project(tmp_path, files):
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    (tmp_path / "ios" / "App" / "PrivacyInfo.xcprivacy").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "ios" / "App" / "PrivacyInfo.xcprivacy").write_text("<plist/>", encoding="utf-8")
    return tmp_path


def test_parse_strings_handles_comments_escapes_and_utf16():
    text = (
        '/* Camera */\n"NSCameraUsageDescription" = "Scanne \\"Belege\\" // nicht kommentar";\n'
        '// line comment\nNSPhotoLibraryUsageDescription = "Fotos";\n'
    )
    parsed = mod.parse_strings(text.encode("utf-16"))
    assert parsed == {
        "NSCameraUsageDescription": 'Scanne "Belege" // nicht kommentar',
        "NSPhotoLibraryUsageDescription": "Fotos",
    }
    assert mod.parse_strings(text.encode("utf-8")) == parsed


def test_untranslated_and_placeholder_localizations(tmp_path):
    project = loc_project(
        tmp_path,
        {
            "ios/App/en.lproj/InfoPlist.strings": f'"NSCameraUsageDescription" = "{CAMERA}";',
            "ios/App/Base.lproj/InfoPlist.strings": "",
            "ios/App/de.lproj/InfoPlist.strings": '"NSCameraUsageDescription" = "Belege mit der Kamera scannen, um Ausgaben anzulegen.";',
            "ios/App/fr.lproj/InfoPlist.strings": (
                '"NSCameraUsageDescription" = "TODO";\n"NSPhotoLibraryUsageDescription" = "";'
            ),
            "ios/Pods/X/es.lproj/InfoPlist.strings": "",
        },
    )
    findings, _ = mod.audit(dict(LOC_INFO), None, project)
    got = {(f.check, f.key) for f in findings if f.check.startswith("usage.")}
    assert got == {
        ("usage.untranslated", "de: NSPhotoLibraryUsageDescription"),
        ("usage.localized_placeholder", "fr: NSCameraUsageDescription"),
        ("usage.localized_placeholder", "fr: NSPhotoLibraryUsageDescription"),
    }
    sev = {f.check: f.severity for f in findings}
    assert sev["usage.untranslated"] == "low" and sev["usage.localized_placeholder"] == "medium"


def test_xcstrings_catalog(tmp_path):
    catalog = {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "NSCameraUsageDescription": {
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": CAMERA}},
                    "bn": {"stringUnit": {"state": "translated", "value": "খরচ যোগ করতে ক্যামেরা দিয়ে রসিদ স্ক্যান করুন।"}},
                    "ja": {"stringUnit": {"state": "new", "value": ""}},
                }
            },
            "CFBundleDisplayName": {"localizations": {"ar": {"stringUnit": {"state": "translated", "value": "x"}}}},
        },
    }
    project = loc_project(tmp_path, {"ios/App/InfoPlist.xcstrings": json.dumps(catalog, ensure_ascii=False)})
    findings, _ = mod.audit(dict(LOC_INFO), None, project)
    got = {(f.check, f.key) for f in findings if f.check.startswith("usage.")}
    assert got == {
        ("usage.untranslated", "ar: NSCameraUsageDescription, NSPhotoLibraryUsageDescription"),
        ("usage.untranslated", "bn: NSPhotoLibraryUsageDescription"),
        ("usage.untranslated", "ja: NSPhotoLibraryUsageDescription"),
        ("usage.localized_placeholder", "ja: NSCameraUsageDescription"),
    }


def test_development_region_variants_are_skipped(tmp_path):
    project = loc_project(
        tmp_path, {"ios/App/English.lproj/InfoPlist.strings": "", "ios/App/en-GB.lproj/InfoPlist.strings": ""}
    )
    findings, _ = mod.audit(dict(LOC_INFO, CFBundleDevelopmentRegion="$(DEVELOPMENT_LANGUAGE)"), None, project)
    assert not [f for f in findings if f.check.startswith("usage.")]


def test_localization_cli_json(tmp_path):
    project = loc_project(tmp_path, {"ios/App/de.lproj/InfoPlist.strings": "/* empty */"})
    plist = tmp_path / "Info.plist"
    plist.write_bytes(plistlib.dumps(LOC_INFO))
    res = run_script(SKILL, SCRIPT, str(plist), "--project", str(project), "--json", "--fail-on", "low")
    assert res.returncode == 1
    checks = [f["check"] for f in json.loads(res.stdout)["findings"]]
    assert checks.count("usage.untranslated") == 1
