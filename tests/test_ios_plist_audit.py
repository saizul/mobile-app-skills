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
