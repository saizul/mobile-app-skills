import json
import zipfile

import pytest

from conftest import fixture, load_script, run_script

SKILL = "app-size-reduction"
SCRIPT = "size_report.py"
mod = load_script(SKILL, SCRIPT)
SIZE = fixture("size")


def make_zip(path, files, stored=()):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data, compress_type=zipfile.ZIP_STORED if name in stored else zipfile.ZIP_DEFLATED)
    return path


def checks(findings):
    return {f.check for f in findings}


def test_universal_flutter_apk(tmp_path):
    png = b"\x89PNG" + bytes(range(256)) * 600
    apk = make_zip(
        tmp_path / "app-release.apk",
        {
            "classes.dex": b"dex\n" + b"x" * 5000,
            "lib/arm64-v8a/libflutter.so": b"\x7fELF" + b"a" * 20000,
            "lib/arm64-v8a/libapp.so": b"\x7fELF" + b"b" * 9000 + b".debug_info",
            "lib/armeabi-v7a/libflutter.so": b"\x7fELF" + b"c" * 18000,
            "lib/x86_64/libflutter.so": b"\x7fELF" + b"d" * 18000,
            "assets/flutter_assets/assets/images/hero.png": png,
            "assets/flutter_assets/assets/images/hero-copy.png": png,
            "assets/flutter_assets/fonts/MaterialIcons-Regular.otf": b"o" * 2000,
            "resources.arsc": b"r" * 3000,
            "META-INF/CERT.RSA": b"sig",
        },
        stored={"resources.arsc"},
    )
    summary, findings = mod.analyze(apk, large_kb=100, image_kb=100)
    assert summary["kind"] == "apk"
    assert summary["abis"] == ["arm64-v8a", "armeabi-v7a", "x86_64"]
    assert "Flutter engine (libflutter.so)" in summary["categories"]
    assert "Dart code (libapp.so)" in summary["categories"]
    f = checks(findings)
    assert {"abi.universal", "abi.emulator", "native.unstripped", "image.heavy", "files.duplicate", "asset.large"} <= f
    assert summary["total_compressed"] < summary["total_uncompressed"]


def test_aab_rn_bundle_not_hermes(tmp_path):
    aab = make_zip(
        tmp_path / "app-release.aab",
        {
            "BundleConfig.pb": b"cfg",
            "base/dex/classes.dex": b"dex",
            "base/lib/arm64-v8a/libhermes.so": b"\x7fELF",
            "base/assets/index.android.bundle": b"var __BUNDLE_START_TIME__=this.nativePerformanceNow?1:2;",
            "base/manifest/AndroidManifest.xml": b"m",
            "BUNDLE-METADATA/com.android.tools.build.debugsymbols/arm64-v8a/libhermes.so.sym": b"s" * 5000,
        },
    )
    summary, findings = mod.analyze(aab)
    assert summary["kind"] == "aab"
    assert "bundle metadata (not shipped)" in summary["categories"]
    assert summary["categories"]["JS bundle"]["files"] == 1
    assert {"js.not_hermes", "r8.no_mapping"} <= checks(findings)
    assert "abi.universal" not in checks(findings)


def test_hermes_bundle_and_debug_flutter(tmp_path):
    apk = make_zip(
        tmp_path / "a.zip",
        {
            "classes.dex": b"d",
            "assets/index.android.bundle": mod.HERMES_MAGIC + b"\x00" * 100,
            "assets/flutter_assets/kernel_blob.bin": b"k",
        },
    )
    summary, findings = mod.analyze(apk)
    assert summary["kind"] == "apk"
    assert "js.not_hermes" not in checks(findings)
    assert "flutter.debug_build" in checks(findings)


def test_ipa_categories(tmp_path):
    ipa = make_zip(
        tmp_path / "Runner.ipa",
        {
            "Payload/Runner.app/Runner": b"m" * 100,
            "Payload/Runner.app/Frameworks/Flutter.framework/Flutter": b"f" * 300,
            "Payload/Runner.app/Frameworks/App.framework/App": b"a" * 200,
            "Payload/Runner.app/Frameworks/App.framework/flutter_assets/fonts/x.ttf": b"t" * 50,
            "Payload/Runner.app/Assets.car": b"c" * 80,
            "Payload/Runner.app/en.lproj/InfoPlist.strings": b"s",
        },
    )
    summary, _ = mod.analyze(ipa)
    cats = summary["categories"]
    assert summary["kind"] == "ipa"
    for c in ("main executable", "Flutter engine (Flutter.framework)", "Dart code (App.framework)", "asset catalog"):
        assert c in cats, c


def test_bundletool_csv():
    summary, findings = mod.analyze(SIZE / "bundletool-size.csv")
    assert summary["kind"] == "bundletool get-size"
    assert summary["rows"][0]["dimensions"]["ABI"] == "arm64-v8a"
    assert summary["total_compressed"] == 25165824 and findings == []


@pytest.mark.parametrize("value,expected", [("1024", 1024), ("1.5 MB", 1572864), ("12 KB", 12288), ("", 0), ("x", 0)])
def test_bytes(value, expected):
    assert mod._bytes(value) == expected


def test_flutter_analyze_size_json():
    summary, _ = mod.analyze(SIZE / "apk-code-size-analysis_01.json")
    assert list(summary["categories"])[0] == "lib"
    assert summary["largest"][0]["path"] == "lib/arm64-v8a/libflutter.so"


def test_unzip_listing():
    summary, findings = mod.analyze(SIZE / "unzip-listing.txt")
    assert summary["files"] == 6 and summary["total_compressed"] is None
    assert "abi.universal" in checks(findings)


def test_errors(tmp_path):
    with pytest.raises(ValueError):
        mod.analyze(SIZE / "garbage.txt")


def test_cli(tmp_path):
    csv = str(SIZE / "bundletool-size.csv")
    assert run_script(SKILL, SCRIPT, csv).returncode == 0
    r = run_script(SKILL, SCRIPT, csv, "--budget-mb", "20")
    assert r.returncode == 1 and "budget.exceeded" in r.stdout
    r = run_script(SKILL, SCRIPT, str(SIZE / "unzip-listing.txt"), "--json", "--fail-on", "medium")
    data = json.loads(r.stdout)
    assert r.returncode == 1 and data["kind"] == "apk"
    assert run_script(SKILL, SCRIPT, str(SIZE / "apk-code-size-analysis_01.json")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(SIZE / "garbage.txt")).returncode == 2
    bad = tmp_path / "broken.apk"
    bad.write_bytes(b"PK not really")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
