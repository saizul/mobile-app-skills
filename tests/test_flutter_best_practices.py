import json

from conftest import fixture, load_script, run_script

SKILL = "flutter-best-practices"
SCRIPT = "flutter_audit.py"
mod = load_script(SKILL, SCRIPT)
BAD = fixture("flutter", "bad-app")
GOOD = fixture("flutter", "good-app")


def checks(findings):
    return {(f.check, f.where) for f in findings}


def test_bad_app():
    f = checks(mod.audit(BAD))
    names = {c for c, _ in f}
    assert ("deps.any", "pubspec.yaml flutter_bloc") in f
    assert ("deps.git_no_ref", "pubspec.yaml charts_lib") in f
    assert {"deps.overrides", "state.mixed", "sdk.old", "lints.package_missing", "lints.no_include"} <= names
    assert ("lints.safety_disabled", "analysis_options.yaml") in f
    assert ("build.future_in_build", "lib/screens/home.dart:12") in f
    assert ("perf.mediaquery_of", "lib/screens/home.dart:9") in f
    assert ("code.print", "lib/screens/home.dart:10") in f
    assert ("perf.listview_children", "lib/screens/home.dart:14") in f
    assert ("perf.shrinkwrap", "lib/screens/home.dart:15") in f
    assert ("security.token_in_prefs", "lib/screens/home.dart:25") in f
    assert ("net.plain_http", "lib/screens/home.dart:30") in f
    # commented-out code and generated files are skipped
    assert not any(w.endswith(":26") for _, w in f)
    assert not any(".g.dart" in w for _, w in f)


def test_good_app_is_clean():
    assert mod.audit(GOOD) == []


def test_missing_analysis_options(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: x\ndev_dependencies:\n  flutter_lints: ^5.0.0\n")
    assert {c for c, _ in checks(mod.audit(tmp_path))} == {"lints.no_options"}


def test_pubspec_parser():
    data = mod.parse_pubspec((BAD / "pubspec.yaml").read_text())
    deps = data["sections"]["dependencies"]
    assert deps["provider"] == "^6.1.0"
    assert "git:" in deps["charts_lib"] and "url:" in deps["charts_lib"]
    assert data["version"] == "1.0.0+1"


def test_stream_builder_inline(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: x\ndev_dependencies:\n  lints: ^5.0.0\n")
    (tmp_path / "analysis_options.yaml").write_text(
        "include: package:lints/recommended.yaml\nanalyzer:\n  language:\n"
        "    strict-casts: true\n    strict-inference: true\n    strict-raw-types: true\n"
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "a.dart").write_text(
        "StreamBuilder(stream: repo.watch(), builder: b);\nStreamBuilder(stream: _s);\n"
    )
    assert checks(mod.audit(tmp_path)) == {("build.stream_in_build", "lib/a.dart:1")}


def test_cli(tmp_path):
    assert run_script(SKILL, SCRIPT, str(BAD)).returncode == 1
    assert run_script(SKILL, SCRIPT, str(GOOD)).returncode == 0
    assert run_script(SKILL, SCRIPT, str(BAD), "--fail-on", "none").returncode == 0
    data = json.loads(run_script(SKILL, SCRIPT, str(BAD), "--json", "--min-severity", "medium").stdout)
    assert data["findings"] and all(f["severity"] == "medium" for f in data["findings"])
    assert run_script(SKILL, SCRIPT, str(tmp_path)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
