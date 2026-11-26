import json

import pytest

from conftest import fixture, load_script, run_script

SKILL = "react-native-best-practices"
SCRIPT = "rn_audit.py"
mod = load_script(SKILL, SCRIPT)
RN = fixture("react-native")


def checks(findings):
    return {(f.check, f.where) for f in findings}


def test_bad_app():
    findings, info = mod.audit(RN / "bad-app")
    f = checks(findings)
    names = {c for c, _ in f}
    assert info["react_native"] == "0.79.5"
    assert ("engine.hermes_off", "android/gradle.properties") in f
    assert ("engine.hermes_off", "ios/Podfile") in f
    assert "arch.legacy" in names
    assert ("deps.advice", "package.json moment") in f
    assert ("deps.advice", "package.json react-native-camera") in f
    assert ("security.token_in_asyncstorage", "src/screens/Budgets.tsx:7") in f
    assert ("perf.scrollview_map", "src/screens/Budgets.tsx:14") in f
    assert ("perf.flatlist_key", "src/screens/Budgets.tsx:18") in f
    assert ("perf.native_driver_off", "src/screens/Budgets.tsx:12") in f
    assert ("deps.lodash_full", "src/screens/Budgets.tsx:3") in f
    assert ("net.plain_http", "src/screens/Budgets.tsx:23") in f
    assert ("build.r8_off", "android/app/build.gradle") in f
    assert {"perf.console_log", "lint.none"} <= names
    assert not any("node_modules" in w for _, w in f)


def test_good_app_is_clean():
    findings, _ = mod.audit(RN / "good-app")
    assert findings == []


def test_dead_flag_on_new_arch_only_versions():
    findings, _ = mod.audit(RN / "dead-flag-app")
    assert [(f.check, f.severity) for f in findings] == [("arch.dead_flag", "low")]


def test_expo_config():
    f = {c for c, _ in checks(mod.audit(RN / "expo-app")[0])}
    assert {"engine.hermes_off", "arch.legacy"} <= f


@pytest.mark.parametrize(
    "spec,expected", [("0.79.5", (0, 79)), ("^0.83.1", (0, 83)), ("~0.76.0-rc.1", (0, 76)), (None, None)]
)
def test_version_tuple(spec, expected):
    assert mod.version_tuple(spec) == expected


def test_not_rn_project(tmp_path):
    with pytest.raises(ValueError):
        mod.audit(RN / "not-rn")
    with pytest.raises(ValueError):
        mod.audit(tmp_path)
    (tmp_path / "package.json").write_text("{broken")
    with pytest.raises(ValueError):
        mod.audit(tmp_path)


def test_cli():
    assert run_script(SKILL, SCRIPT, str(RN / "bad-app")).returncode == 1
    assert run_script(SKILL, SCRIPT, str(RN / "good-app")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(RN / "dead-flag-app")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(RN / "dead-flag-app"), "--fail-on", "low").returncode == 1
    data = json.loads(run_script(SKILL, SCRIPT, str(RN / "bad-app"), "--json").stdout)
    assert data["react_native"] == "0.79.5" and data["findings"]
    assert run_script(SKILL, SCRIPT, str(RN / "not-rn")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
