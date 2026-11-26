#!/usr/bin/env python3
"""Summarise where the bytes go in an Android or iOS build and suggest what to cut.

Inputs (detected automatically):
  * an .apk, .aab or .ipa file (read as a zip; nothing is extracted or executed)
  * `bundletool get-size total --apks=app.apks [--dimensions=...]` CSV output
  * Flutter `--analyze-size` JSON (apk-code-size-analysis_*.json / ios-code-size-analysis_*.json)
  * a size listing: `unzip -l app.apk` or `du -ab` style "<bytes> <path>" lines

Findings: universal APKs with several ABIs, unstripped native libraries, JS bundles not
compiled to Hermes bytecode, Flutter debug builds, large images and assets, duplicate
files, fonts, missing R8 mapping in bundles, and an optional size budget.

Exit codes: 0 = ok, 1 = findings at or above --fail-on (or over --budget-mb), 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
HERMES_MAGIC = bytes.fromhex("c61fbc03c103191f")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
FONT_EXT = {".ttf", ".otf", ".ttc"}
ABI_RE = re.compile(r"(?:^|/)lib/([^/]+)/[^/]+\.so$")


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def category(path: str) -> str:
    p = re.sub(r"^(base|feature_[^/]+|[a-z_]+_module)/", "", path) if not path.startswith("Payload/") else path
    if path.startswith("BUNDLE-METADATA/"):
        return "bundle metadata (not shipped)"
    if path.startswith("Payload/"):
        if "/Frameworks/Flutter.framework/" in path:
            return "Flutter engine (Flutter.framework)"
        if "/Frameworks/App.framework/flutter_assets/" in path:
            return "Flutter assets"
        if "/Frameworks/App.framework/" in path:
            return "Dart code (App.framework)"
        if "/Frameworks/" in path:
            return "frameworks"
        if path.endswith(".jsbundle"):
            return "JS bundle"
        if path.endswith("Assets.car"):
            return "asset catalog"
        if "/PlugIns/" in path:
            return "app extensions"
        if path.endswith((".lproj", ".strings")) or ".lproj/" in path:
            return "localizations"
        if re.match(r"^Payload/[^/]+\.app/[^/.]+$", path):
            return "main executable"
        return "other resources"
    if ABI_RE.search(p):
        name = p.rsplit("/", 1)[-1]
        if name == "libflutter.so":
            return "Flutter engine (libflutter.so)"
        if name == "libapp.so":
            return "Dart code (libapp.so)"
        if name.startswith(("libhermes", "libjsc")):
            return "JS engine"
        return "native libraries (other)"
    if re.match(r"^(dex/)?classes\d*\.dex$", p):
        return "dex (Kotlin/Java)"
    if p.startswith("assets/flutter_assets/"):
        return "Flutter assets"
    if p.endswith((".bundle", ".jsbundle")) and p.startswith("assets/"):
        return "JS bundle"
    if p.startswith("assets/"):
        return "assets"
    if p.startswith("res/") or p in ("resources.arsc", "resources.pb"):
        return "resources"
    if p.startswith("META-INF/"):
        return "signature/metadata"
    return "other"


class Entry:
    __slots__ = ("compressed", "crc", "name", "size", "stored")

    def __init__(self, name, size, compressed=None, crc=None, stored=False):
        self.name, self.size, self.compressed, self.crc, self.stored = name, size, compressed, crc, stored


class Finding:
    __slots__ = ("check", "fix", "message", "severity", "target")

    def __init__(self, check, severity, target, message, fix):
        self.check, self.severity, self.target, self.message, self.fix = check, severity, target, message, fix

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("check", "severity", "target", "message", "fix")}


def read_archive(path: Path) -> tuple[list[Entry], dict]:
    entries, probes = [], {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            entries.append(Entry(info.filename, info.file_size, info.compress_size, info.CRC, info.compress_type == 0))
            name = info.filename
            if name.endswith(".so") and info.file_size < 300 * 1024 * 1024:
                with zf.open(info) as fh:
                    data = fh.read()
                probes[name] = {"debug_info": b".debug_info" in data}
            elif name.endswith((".bundle", ".jsbundle")) and ("assets/" in name or name.startswith("Payload/")):
                with zf.open(info) as fh:
                    probes[name] = {"hermes": fh.read(8) == HERMES_MAGIC}
    return entries, probes


def parse_listing(text: str) -> list[Entry]:
    entries = []
    for line in text.splitlines():
        m = re.match(
            r"^\s*(\d+)\s+(?:\d+\s+\S+\s+\d+%\s+)?(?:\d{2,4}-\d{2}-\d{2,4}\s+\d{2}:\d{2}\s+)?(?:[0-9a-f]{8}\s+)?(\S.*)$",
            line,
        )
        if not m or m.group(2).strip() in ("Name", "files") or m.group(2).endswith("/"):
            continue
        name = re.sub(r"^\./", "", m.group(2).strip())
        if re.match(r"^\d+ files?$", name):
            continue
        entries.append(Entry(name, int(m.group(1))))
    return entries


def parse_bundletool_csv(text: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    out = []
    for r in rows:
        dims = {k: v for k, v in r.items() if k not in ("MIN", "MAX") and v}
        out.append({"dimensions": dims, "min": _bytes(r.get("MIN")), "max": _bytes(r.get("MAX"))})
    return out


def _bytes(value: str | None) -> int:
    if value is None:
        return 0
    v = value.strip().replace(",", "")
    m = re.match(r"^([\d.]+)\s*([KMG]?i?B)?$", v, re.I)
    if not m:
        return 0
    mult = {"": 1, "B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    unit = (m.group(2) or "").upper().replace("I", "")
    return int(float(m.group(1)) * mult.get(unit, 1))


def flutter_tree_leaves(node: dict, prefix: str = "") -> list[tuple[str, int]]:
    name = node.get("n") or node.get("name") or "?"
    path = f"{prefix}/{name}" if prefix else name
    children = node.get("children") or []
    if not children:
        return [(path, int(node.get("value") or 0))]
    out = []
    for ch in children:
        out += flutter_tree_leaves(ch, path)
    return out


def analyze_entries(
    entries: list[Entry], probes: dict, kind: str, large_kb: int, image_kb: int
) -> tuple[dict, list[Finding]]:
    out: list[Finding] = []
    shipped = [e for e in entries if not e.name.startswith("BUNDLE-METADATA/")]
    cats: dict[str, dict] = {}
    for e in entries:
        c = cats.setdefault(category(e.name), {"files": 0, "size": 0, "compressed": 0})
        c["files"] += 1
        c["size"] += e.size
        c["compressed"] += e.compressed if e.compressed is not None else e.size
    total = sum(e.size for e in shipped)
    total_c = sum((e.compressed if e.compressed is not None else e.size) for e in shipped)

    abis = sorted({m.group(1) for e in shipped if (m := ABI_RE.search(e.name))})
    if kind == "apk" and len(abis) > 1:
        out.append(
            Finding(
                "abi.universal",
                "medium",
                ", ".join(abis),
                f"APK contains native code for {len(abis)} ABIs",
                "upload an AAB (Play serves one ABI per device) or build with --split-per-abi",
            )
        )
    if kind == "apk" and any(a in ("x86", "x86_64") for a in abis) and len(abis) > 1:
        out.append(
            Finding(
                "abi.emulator",
                "low",
                "x86/x86_64",
                "emulator ABIs shipped",
                "use abiFilters 'arm64-v8a', 'armeabi-v7a' for release if you do not target x86 devices",
            )
        )
    for name, probe in sorted(probes.items()):
        if probe.get("debug_info"):
            out.append(
                Finding(
                    "native.unstripped",
                    "medium",
                    name,
                    "native library contains debug info",
                    "strip symbols (NDK debugSymbolLevel in the bundle, strip in the build)",
                )
            )
        if "hermes" in probe and not probe["hermes"]:
            out.append(
                Finding(
                    "js.not_hermes",
                    "medium",
                    name,
                    "JS bundle is plain JavaScript, not Hermes bytecode",
                    "enable Hermes (default since RN 0.70) and build a release bundle",
                )
            )
    if any(e.name.endswith("flutter_assets/kernel_blob.bin") for e in entries):
        out.append(
            Finding(
                "flutter.debug_build",
                "high",
                "kernel_blob.bin",
                "this is a Flutter debug/JIT build",
                "measure `flutter build appbundle --release` / `flutter build ipa` output",
            )
        )
    if kind == "aab" and not any("proguard.map" in e.name or "obfuscation" in e.name for e in entries):
        dex = [e for e in entries if e.name.endswith(".dex")]
        if dex:
            out.append(
                Finding(
                    "r8.no_mapping",
                    "info",
                    "BUNDLE-METADATA",
                    "no R8 mapping file in the bundle",
                    "R8 minify/shrink may be off: set isMinifyEnabled and isShrinkResources for release",
                )
            )
    large = sorted(
        (
            e
            for e in shipped
            if e.size >= large_kb * 1024
            and category(e.name) in ("assets", "Flutter assets", "resources", "other resources", "asset catalog")
        ),
        key=lambda e: -e.size,
    )
    for e in large[:10]:
        out.append(
            Finding(
                "asset.large",
                "low",
                e.name,
                f"{human(e.size)} asset",
                "compress, download on demand, or move to Play Asset Delivery / On-Demand Resources",
            )
        )
    images = [e for e in shipped if Path(e.name).suffix.lower() in IMAGE_EXT and e.size >= image_kb * 1024]
    if images:
        size = sum(e.size for e in images)
        out.append(
            Finding(
                "image.heavy",
                "low",
                f"{len(images)} image(s)",
                f"{human(size)} in PNG/JPEG images over {image_kb} KB",
                "convert to WebP (Android) or use asset catalogs / HEIC; resize to the largest display size",
            )
        )
    fonts = [e for e in shipped if Path(e.name).suffix.lower() in FONT_EXT]
    if sum(e.size for e in fonts) > 1024 * 1024:
        out.append(
            Finding(
                "font.heavy",
                "low",
                f"{len(fonts)} font file(s)",
                f"{human(sum(e.size for e in fonts))} of fonts",
                "subset fonts, drop unused weights, use variable fonts or downloadable fonts",
            )
        )
    seen: dict[tuple, list[Entry]] = {}
    for e in shipped:
        if e.crc is not None and e.size >= 10 * 1024:
            seen.setdefault((e.crc, e.size), []).append(e)
    dups = [v for v in seen.values() if len(v) > 1]
    if dups:
        wasted = sum(v[0].size * (len(v) - 1) for v in dups)
        names = "; ".join(" = ".join(x.name for x in v[:3]) for v in dups[:3])
        out.append(
            Finding(
                "files.duplicate",
                "low",
                names,
                f"{len(dups)} duplicated file set(s), {human(wasted)} wasted",
                "keep one copy (assets declared twice, same image in several folders)",
            )
        )
    summary = {
        "kind": kind,
        "files": len(entries),
        "total_uncompressed": total,
        "total_compressed": total_c if any(e.compressed is not None for e in shipped) else None,
        "abis": abis,
        "categories": dict(sorted(cats.items(), key=lambda kv: -kv[1]["size"])),
        "largest": [
            {"path": e.name, "size": e.size, "category": category(e.name)}
            for e in sorted(shipped, key=lambda e: -e.size)[:15]
        ],
    }
    return summary, out


def analyze(path: Path, large_kb: int = 500, image_kb: int = 100) -> tuple[dict, list[Finding]]:
    suffix = path.suffix.lower()
    if suffix in (".apk", ".aab", ".ipa", ".zip") and zipfile.is_zipfile(path):
        entries, probes = read_archive(path)
        kind = suffix[1:] if suffix != ".zip" else "zip"
        if kind == "zip":
            names = {e.name for e in entries}
            kind = (
                "aab"
                if "BundleConfig.pb" in names
                else ("ipa" if any(n.startswith("Payload/") for n in names) else "apk")
            )
        return analyze_entries(entries, probes, kind, large_kb, image_kb)
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        leaves = sorted(
            (leaf for ch in data.get("children") or [] for leaf in flutter_tree_leaves(ch)), key=lambda kv: -kv[1]
        )
        top = {}
        for ch in data.get("children") or []:
            name = ch.get("n") or ch.get("name") or "?"
            top[name] = sum(v for _, v in flutter_tree_leaves(ch))
        summary = {
            "kind": f"flutter-analyze-size ({data.get('type', '?')})",
            "total_uncompressed": sum(v for _, v in leaves),
            "categories": {k: {"size": v} for k, v in sorted(top.items(), key=lambda kv: -kv[1])},
            "largest": [{"path": p, "size": v} for p, v in leaves[:15]],
        }
        return summary, []
    first = stripped.splitlines()[0] if stripped else ""
    if "MIN" in first and "MAX" in first and "," in first:
        rows = parse_bundletool_csv(stripped)
        summary = {
            "kind": "bundletool get-size",
            "rows": rows,
            "total_compressed": max((r["max"] for r in rows), default=0),
        }
        return summary, []
    entries = parse_listing(text)
    if not entries:
        raise ValueError(
            f"{path}: unrecognised input (expected .apk/.aab/.ipa, bundletool CSV, Flutter JSON or listing)"
        )
    kind = (
        "aab"
        if any(e.name.startswith("base/") for e in entries)
        else ("ipa" if any(e.name.startswith("Payload/") for e in entries) else "apk")
    )
    return analyze_entries(entries, {}, kind, large_kb, image_kb)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("input", type=Path, help=".apk/.aab/.ipa, bundletool CSV, Flutter size JSON, or listing text")
    p.add_argument("--budget-mb", type=float, help="fail when the (max download / compressed) size exceeds this")
    p.add_argument("--large-kb", type=int, default=500, help="report single assets at least this big (default 500)")
    p.add_argument("--image-kb", type=int, default=100, help="report images at least this big (default 100)")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="high")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        summary, findings = analyze(args.input, args.large_kb, args.image_kb)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    measured = summary.get("total_compressed") or summary.get("total_uncompressed") or 0
    if args.budget_mb is not None and measured > args.budget_mb * 1024 * 1024:
        findings.append(
            Finding(
                "budget.exceeded",
                "high",
                str(args.input),
                f"{human(measured)} exceeds the {args.budget_mb} MB budget",
                "cut the largest categories first",
            )
        )
    if args.json:
        print(json.dumps({**summary, "findings": [f.as_dict() for f in findings]}, indent=2))
    else:
        print(f"{args.input.name}: {summary['kind']}")
        if "rows" in summary:
            for r in summary["rows"]:
                dims = ", ".join(f"{k}={v}" for k, v in r["dimensions"].items()) or "all devices"
                print(f"  {dims:<40} download {human(r['min'])} - {human(r['max'])}")
        else:
            total = summary.get("total_uncompressed") or 0
            comp = summary.get("total_compressed")
            print(f"  total {human(total)} uncompressed" + (f", {human(comp)} compressed" if comp else ""))
            print("\n  By category:")
            for name, c in summary["categories"].items():
                pct = 100 * c["size"] / total if total else 0
                print(f"    {name:<38} {human(c['size']):>10}  {pct:5.1f}%")
            print("\n  Largest files:")
            for item in summary["largest"][:10]:
                print(f"    {human(item['size']):>10}  {item['path']}")
        if findings:
            print()
        for f in sorted(findings, key=lambda f: -SEVERITIES.index(f.severity)):
            print(f"{f.severity.upper():<6} [{f.check}] {f.target}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(findings)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
