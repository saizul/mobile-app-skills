import json

import pytest

from conftest import fixture, load_script, run_script

SKILL = "android-permissions-audit"
SCRIPT = "manifest_audit.py"
mod = load_script(SKILL, SCRIPT)
BAD = fixture("android", "bad", "AndroidManifest.xml")
GOOD = fixture("android", "good", "AndroidManifest.xml")


def found(findings, min_sev="info"):
    rank = mod.SEVERITIES.index(min_sev)
    return {(f.check, f.target) for f in findings if mod.SEVERITIES.index(f.severity) >= rank}


def test_bad_manifest():
    findings, info = mod.audit(BAD)
    f = found(findings)
    assert info["target_sdk"] == 34 and info["package"] == "com.example.pocketbudget"
    assert "RECORD_AUDIO" not in info["permissions"]  # tools:node="remove"
    for p in ("READ_SMS", "ACCESS_BACKGROUND_LOCATION", "QUERY_ALL_PACKAGES"):
        assert ("permission.restricted", p) in f
    assert ("permission.legacy_storage", "READ_EXTERNAL_STORAGE") in f
    assert ("permission.fgs_type", "FOREGROUND_SERVICE") in f
    assert ("app.debuggable", "application") in f
    assert ("app.cleartext", "application") in f
    assert ("app.backup", "application") in f
    assert ("component.exported_missing", "activity .ShareActivity") in f
    assert ("component.exported", "provider .data.ExpenseProvider") in f
    assert ("component.exported", "service .sync.SyncService") in f
    assert ("component.exported", "activity .admin.DebugMenuActivity") in f
    assert ("component.exported", "receiver .BootReceiver") in f
    assert ("permission.custom_weak", "com.example.pocketbudget.permission.SYNC") in f
    # launcher + deep link activity is not reported as a risky export
    assert not any(t == "activity .MainActivity" for _, t in found(findings, "low"))
    # the FileProvider is not exported
    assert not any("FileProvider" in t for _, t in f)


def test_network_security_config_resolved():
    f = {(x.check, x.severity, x.target) for x in mod.audit(BAD)[0]}
    assert ("nsc.cleartext", "high", "base-config") in f
    assert ("nsc.user_ca", "medium", "base-config") in f
    assert ("nsc.cleartext", "info", "domain-config 10.0.2.2") in f


def test_good_manifest_only_info():
    findings, info = mod.audit(GOOD, target_sdk=35)
    assert found(findings, "low") == set()
    assert info["package"] is None


def test_usage_hints_with_source():
    src = mod.find_source_text(fixture("android", "project"))
    f = found(mod.audit(BAD, source_text=src)[0])
    assert ("permission.unused", "READ_CONTACTS") in f
    assert ("permission.unused", "CAMERA") not in f  # mobile_scanner in pubspec.yaml


def test_gradle_target_sdk():
    assert mod.target_sdk_from_gradle(fixture("android", "project", "android", "app", "build.gradle")) == 35


@pytest.mark.parametrize(
    "target,severity",
    [(30, "low"), (31, "high"), (None, "high")],
)
def test_missing_exported_severity_depends_on_target(tmp_path, target, severity):
    m = tmp_path / "AndroidManifest.xml"
    m.write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
        '<activity android:name=".A"><intent-filter><action android:name="x.y.VIEW"/></intent-filter></activity>'
        "</application></manifest>"
    )
    f = [x for x in mod.audit(m, target_sdk=target)[0] if x.check == "component.exported_missing"]
    assert f and f[0].severity == severity


def test_errors(tmp_path):
    with pytest.raises(ValueError):
        mod.audit(fixture("android", "binary", "AndroidManifest.xml"))
    other = tmp_path / "x.xml"
    other.write_text("<resources/>")
    with pytest.raises(ValueError):
        mod.audit(other)


def test_cli(tmp_path):
    assert run_script(SKILL, SCRIPT, str(BAD)).returncode == 1
    assert run_script(SKILL, SCRIPT, str(GOOD)).returncode == 0
    assert run_script(SKILL, SCRIPT, str(BAD), "--fail-on", "none").returncode == 0
    r = run_script(
        SKILL,
        SCRIPT,
        str(BAD),
        "--json",
        "--min-severity",
        "high",
        "--source",
        str(fixture("android", "project")),
        "--res",
        str(fixture("android", "bad", "res")),
    )
    data = json.loads(r.stdout)
    assert r.returncode == 1 and data["target_sdk"] == 34
    assert {f["severity"] for f in data["findings"]} == {"high"}
    r = run_script(
        SKILL, SCRIPT, str(GOOD), "--gradle", str(fixture("android", "project", "android", "app", "build.gradle"))
    )
    assert "targetSdk=35" in r.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.xml")).returncode == 2
    assert run_script(SKILL, SCRIPT, str(fixture("android", "binary", "AndroidManifest.xml"))).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
