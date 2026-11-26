import json
import shutil

from conftest import fixture, load_script, run_script

SKILL = "release-checklist"
SCRIPT = "release_preflight.py"
mod = load_script(SKILL, SCRIPT)


def checks(findings):
    return {(f.check, f.where) for f in findings}


def test_flutter_project():
    findings, summary = mod.check(fixture("release", "flutter-app"), previous_android=41)
    assert summary["project"] == "flutter"
    assert summary["versions"]["android"] == {"name": "2.3.0", "build": 41, "from": "pubspec.yaml"}
    f = checks(findings)
    assert ("build.not_increased", "pubspec.yaml") in f
    assert ("signing.debug_key", "android/app/build.gradle.kts") in f
    assert ("android.target_sdk", "android/app/build.gradle.kts") in f
    assert ("secrets.not_ignored", "android/key.properties") in f
    assert ("secrets.keystore_in_repo", "android/upload.jks") in f
    # passwords are never printed
    assert all("<hidden>" not in x.message for x in findings)


def test_rn_project_clean_with_increasing_build(tmp_path):
    root = tmp_path / "app"
    shutil.copytree(fixture("release", "rn-app"), root)
    # created here because the fixture's own .gitignore keeps them out of this repository
    (root / "android" / "app" / "release.keystore").write_text("fake")
    (root / "android" / "keystore.properties").write_text("MYAPP_UPLOAD_STORE_PASSWORD=<hidden>\n")
    findings, summary = mod.check(root, previous_android=119, previous_ios=119)
    assert summary["project"] == "react-native"
    assert summary["versions"]["android"]["build"] == 120
    assert summary["versions"]["ios"]["name"] == "1.8.0"
    assert findings == []  # release.keystore and keystore.properties are git-ignored, debug.keystore skipped
    (root / ".gitignore").write_text("node_modules/\n")
    f = checks(mod.check(root)[0])
    assert ("secrets.keystore_in_repo", "android/app/release.keystore") in f
    assert ("secrets.not_ignored", "android/keystore.properties") in f
    assert not any("debug.keystore" in w for _, w in f)


def test_version_going_backwards():
    findings, _ = mod.check(fixture("release", "rn-app"), previous_version="1.9.0")
    assert {c for c, _ in checks(findings)} == {"version.decreased"}


def test_expo_project():
    findings, summary = mod.check(fixture("release", "expo-app"))
    assert summary["project"] == "expo"
    assert summary["versions"]["ios"]["build"] == 7
    assert ("version.format", "app.json") in checks(findings)


def test_gradle_signing_variants(tmp_path):
    root = tmp_path / "app"
    shutil.copytree(fixture("release", "rn-app"), root)
    gradle = root / "android" / "app" / "build.gradle"
    text = gradle.read_text()
    gradle.write_text(text.replace("signingConfig signingConfigs.release", "signingConfig signingConfigs.debug"))
    assert ("signing.debug_key", "android/app/build.gradle") in checks(mod.check(root)[0])
    gradle.write_text(
        text.replace("storePassword MYAPP_UPLOAD_STORE_PASSWORD", 'storePassword "hunter2-not-real"').replace(
            "minifyEnabled enableProguardInReleaseBuilds", "minifyEnabled false"
        )
    )
    findings = mod.check(root)[0]
    f = checks(findings)
    assert ("signing.hardcoded_password", "android/app/build.gradle") in f
    assert ("build.minify_off", "android/app/build.gradle") in f
    assert all("hunter2" not in x.message for x in findings)
    gradle.write_text(text.replace("signingConfig signingConfigs.release\n", ""))
    assert ("signing.missing", "android/app/build.gradle") in checks(mod.check(root)[0])


def test_xcode_config_mismatch_and_version_code_limit(tmp_path):
    root = tmp_path / "app"
    shutil.copytree(fixture("release", "rn-app"), root)
    pbx = root / "ios" / "Pocket.xcodeproj" / "project.pbxproj"
    pbx.write_text(
        pbx.read_text().replace("MARKETING_VERSION = 1.8.0; }; };\n\t\tA2", "MARKETING_VERSION = 1.7.0; }; };\n\t\tA2")
    )
    gradle = root / "android" / "app" / "build.gradle"
    gradle.write_text(gradle.read_text().replace("versionCode 120", "versionCode 2100000001"))
    f = {c for c, _ in checks(mod.check(root)[0])}
    assert {"version.xcode_configs", "build.too_large"} <= f


def test_gitignored():
    root = fixture("release", "rn-app")
    assert mod.gitignored(root, "android/app/release.keystore")
    assert mod.gitignored(root, "android/keystore.properties")
    assert not mod.gitignored(fixture("release", "flutter-app"), "android/key.properties")


def test_gradle_block_parsing():
    text = "android { buildTypes { debug { a } release { signingConfig x\n nested { y } } } }"
    assert "signingConfig x" in mod.release_block(text)
    assert mod.release_block("android {}") == ""


def test_cli(tmp_path):
    flutter = str(fixture("release", "flutter-app"))
    rn = str(fixture("release", "rn-app"))
    assert run_script(SKILL, SCRIPT, flutter).returncode == 1
    assert run_script(SKILL, SCRIPT, rn).returncode == 0
    assert run_script(SKILL, SCRIPT, flutter, "--fail-on", "none").returncode == 0
    r = run_script(SKILL, SCRIPT, flutter, "--json", "--min-target-sdk", "30")
    data = json.loads(r.stdout)
    assert data["project"] == "flutter"
    assert "android.target_sdk" not in {f["check"] for f in data["findings"]}
    r = run_script(SKILL, SCRIPT, rn, "--previous-android", "120")
    assert r.returncode == 1 and "build.not_increased" in r.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "nope")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
