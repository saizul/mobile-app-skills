#!/usr/bin/env python3
"""Pre-release checks for a Flutter, React Native or Expo project before uploading a build.

Reads (never modifies) pubspec.yaml, package.json, app.json, android/app/build.gradle(.kts),
android/gradle.properties and ios/*.xcodeproj/project.pbxproj and reports:
  * version name and build number per platform, and whether they increase over --previous-*
  * mismatched marketing versions between Android, iOS and Xcode build configurations
  * Android release builds signed with the debug key, hard-coded keystore passwords
    (values never printed), keystores and key.properties not covered by .gitignore
  * targetSdk below the Google Play requirement, R8/minify disabled for release

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
MAX_VERSION_CODE = 2100000000
# Google Play target API requirement for new apps and updates (phone/tablet) since 2026-08-31.
DEFAULT_MIN_TARGET_SDK = 36
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class Finding:
    __slots__ = ("check", "fix", "message", "severity", "where")

    def __init__(self, check, severity, where, message, fix):
        self.check, self.severity, self.where, self.message, self.fix = check, severity, where, message, fix

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "where": self.where,
            "message": self.message,
            "fix": self.fix,
        }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def detect(root: Path) -> str:
    pkg = _package_json(root)
    if (root / "pubspec.yaml").is_file():
        return "flutter"
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    if "expo" in deps and not (root / "android").is_dir():
        return "expo"
    if "react-native" in deps:
        return "react-native"
    if "expo" in deps:
        return "expo"
    return "unknown"


def _package_json(root: Path) -> dict:
    try:
        data = json.loads(_read(root / "package.json") or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def gradle_file(root: Path) -> Path | None:
    for name in ("build.gradle.kts", "build.gradle"):
        p = root / "android" / "app" / name
        if p.is_file():
            return p
    return None


def gradle_block(text: str, name: str) -> str:
    """Return the text inside the first `name { ... }` block (brace matched)."""
    m = re.search(rf"\b{re.escape(name)}\s*(?:\([^)]*\))?\s*\{{", text)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end() : i - 1]


def release_block(text: str) -> str:
    bt = gradle_block(text, "buildTypes")
    m = re.search(r"(?:\brelease\b|getByName\(\"release\"\))\s*\{", bt)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(bt) and depth:
        depth += {"{": 1, "}": -1}.get(bt[i], 0)
        i += 1
    return bt[m.end() : i - 1]


def collect_versions(root: Path, kind: str) -> dict:
    v: dict = {"android": {}, "ios": {}}
    if kind == "flutter":
        m = re.search(r"^version:\s*['\"]?([^\s'\"+]+)(?:\+(\d+))?", _read(root / "pubspec.yaml"), re.M)
        if m:
            for plat in ("android", "ios"):
                v[plat] = {"name": m.group(1), "build": int(m.group(2)) if m.group(2) else None, "from": "pubspec.yaml"}
    if kind == "expo" or (root / "app.json").is_file():
        try:
            app = json.loads(_read(root / "app.json") or "{}").get("expo") or {}
        except (json.JSONDecodeError, AttributeError):
            app = {}
        if app.get("version"):
            code = (app.get("android") or {}).get("versionCode")
            build = (app.get("ios") or {}).get("buildNumber")
            v["android"] = v["android"] or {"name": app["version"], "build": _int(code), "from": "app.json"}
            v["ios"] = v["ios"] or {"name": app["version"], "build": _int(build), "from": "app.json"}
    gf = gradle_file(root)
    if gf and v["android"].get("from") != "pubspec.yaml":
        text = _read(gf)
        code = re.search(r"\bversionCode\s*=?\s*(\d+)", text)
        name = re.search(r"\bversionName\s*=?\s*[\"']([^\"']+)[\"']", text)
        if code or name:
            v["android"] = {
                "name": name.group(1) if name else None,
                "build": int(code.group(1)) if code else None,
                "from": str(gf.relative_to(root)),
            }
    for pbx in sorted((root / "ios").glob("*.xcodeproj/project.pbxproj")) if (root / "ios").is_dir() else []:
        text = _read(pbx)
        names = sorted(set(re.findall(r"MARKETING_VERSION = \"?([^;\"]+)\"?;", text)))
        builds = sorted(set(re.findall(r"CURRENT_PROJECT_VERSION = \"?([^;\"]+)\"?;", text)))
        v["ios_configs"] = {"marketing": names, "build": builds, "from": str(pbx.relative_to(root))}
        if not v["ios"].get("from") and (names or builds):
            v["ios"] = {
                "name": names[0] if names else None,
                "build": _int(builds[0]) if builds else None,
                "from": str(pbx.relative_to(root)),
            }
        break
    return v


def _int(x) -> int | None:
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None


def gitignored(root: Path, rel: str) -> bool:
    """Rough .gitignore check: root and nested .gitignore files, basename and path globs."""
    parts = Path(rel).parts
    for i in range(len(parts)):
        gi = root.joinpath(*parts[:i], ".gitignore")
        if not gi.is_file():
            continue
        sub = "/".join(parts[i:])
        for raw in _read(gi).splitlines():
            pat = raw.strip()
            if not pat or pat.startswith("#") or pat.startswith("!"):
                continue
            pat = pat.lstrip("/")
            if fnmatch.fnmatch(sub, pat) or fnmatch.fnmatch(Path(sub).name, pat) or fnmatch.fnmatch(sub, f"**/{pat}"):
                return True
            if pat.endswith("/") and sub.startswith(pat):
                return True
    return False


def check(
    root: Path,
    previous_android: int | None = None,
    previous_ios: int | None = None,
    previous_version: str | None = None,
    min_target_sdk: int = DEFAULT_MIN_TARGET_SDK,
) -> tuple[list[Finding], dict]:
    out: list[Finding] = []
    kind = detect(root)
    versions = collect_versions(root, kind)

    def add(*a):
        out.append(Finding(*a))

    for plat, prev in (("android", previous_android), ("ios", previous_ios)):
        info = versions.get(plat) or {}
        if not info:
            continue
        name, build, src = info.get("name"), info.get("build"), info.get("from")
        if name and not SEMVER_RE.match(name):
            add("version.format", "low", src, f"{plat} version '{name}' is not MAJOR.MINOR.PATCH", "use x.y.z")
        if build is None:
            add("build.missing", "medium", src, f"{plat} build number not found", "set an integer build number")
        else:
            if prev is not None and build <= prev:
                add(
                    "build.not_increased",
                    "high",
                    src,
                    f"{plat} build {build} <= previous {prev}",
                    "increase the build number; stores reject reused numbers",
                )
            if plat == "android" and build > MAX_VERSION_CODE:
                add("build.too_large", "high", src, f"versionCode {build} > {MAX_VERSION_CODE}", "use a smaller scheme")
        if previous_version and name and _version_tuple(name) < _version_tuple(previous_version):
            add(
                "version.decreased",
                "high",
                src,
                f"{plat} version {name} < previous {previous_version}",
                "versions must not go backwards",
            )
    a, i = versions.get("android", {}).get("name"), versions.get("ios", {}).get("name")
    if a and i and a != i and "$(" not in i:
        add("version.mismatch", "low", "android/ios", f"Android {a} vs iOS {i}", "ship the same marketing version")
    cfg = versions.get("ios_configs") or {}
    if len(cfg.get("marketing") or []) > 1 and kind != "flutter":
        add(
            "version.xcode_configs",
            "medium",
            cfg["from"],
            f"MARKETING_VERSION differs: {', '.join(cfg['marketing'])}",
            "set the same value for Debug and Release",
        )

    gf = gradle_file(root)
    if gf:
        text = _read(gf)
        rel = str(gf.relative_to(root))
        rb = release_block(text)
        if re.search(r"signingConfig\s*=?\s*signingConfigs\.(debug\b|getByName\(\"debug\"\))", rb):
            add(
                "signing.debug_key",
                "high",
                rel,
                "release build type is signed with the debug key",
                "create an upload key and a release signingConfig (Play rejects debug-signed bundles)",
            )
        elif rb and "signingConfig" not in rb:
            add(
                "signing.missing",
                "medium",
                rel,
                "release build type has no signingConfig",
                "add a release signingConfig that reads key.properties or environment variables",
            )
        for key in ("storePassword", "keyPassword"):
            if re.search(rf"\b{key}\s*=?\s*[\"'][^\"'$]+[\"']", text):
                add(
                    "signing.hardcoded_password",
                    "high",
                    rel,
                    f"{key} is a literal in Gradle (value hidden)",
                    "read it from key.properties (git-ignored) or CI secrets, and rotate it if committed",
                )
        minify = re.search(r"\b(?:isMinifyEnabled|minifyEnabled)\s*=?\s*(true|false)", rb)
        rn_minify = re.search(r"enableProguardInReleaseBuilds\s*=\s*(true|false)", text)
        if (minify and minify.group(1) == "false") or (rn_minify and rn_minify.group(1) == "false"):
            add(
                "build.minify_off",
                "info",
                rel,
                "R8/minify disabled for release",
                "enable it and test; it shrinks the app",
            )
        target = re.search(r"\btargetSdk(?:Version)?\s*=?\s*(\d+)", text)
        props = _read(root / "android" / "build.gradle") + _read(root / "android" / "gradle.properties")
        if not target:
            target = re.search(r"\btargetSdk(?:Version)?\s*=\s*(\d+)", props)
        if target and int(target.group(1)) < min_target_sdk:
            add(
                "android.target_sdk",
                "high",
                rel,
                f"targetSdk {target.group(1)} < {min_target_sdk} required by Google Play",
                "raise targetSdk and test behaviour changes",
            )
    for pattern in ("key.properties", "keystore.properties"):
        for p in root.joinpath("android").glob(pattern) if (root / "android").is_dir() else []:
            rel = str(p.relative_to(root))
            if not gitignored(root, rel):
                add(
                    "secrets.not_ignored",
                    "high",
                    rel,
                    "signing properties file is not git-ignored",
                    "add it to .gitignore; if it was committed, rotate the passwords",
                )
    for ext in ("*.jks", "*.keystore", "*.p12", "*.p8", "*.mobileprovision"):
        for p in sorted(root.rglob(ext)):
            rel = str(p.relative_to(root))
            if p.name == "debug.keystore" or any(x in p.parts for x in ("node_modules", "build", "Pods")):
                continue
            if not gitignored(root, rel):
                add(
                    "secrets.keystore_in_repo",
                    "high",
                    rel,
                    "signing key or certificate inside the project, not ignored",
                    "move it out of the repo (password manager / CI secret store) and git-ignore it",
                )
    summary = {"project": kind, "versions": versions}
    return out, summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("project", type=Path, nargs="?", default=Path("."), help="project root (default .)")
    p.add_argument("--previous-android", type=int, help="last versionCode uploaded to Google Play")
    p.add_argument("--previous-ios", type=int, help="last build number uploaded to App Store Connect")
    p.add_argument("--previous-version", help="last released marketing version, e.g. 2.3.1")
    p.add_argument("--min-target-sdk", type=int, default=DEFAULT_MIN_TARGET_SDK)
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    if not args.project.is_dir():
        print(f"error: {args.project} is not a directory", file=sys.stderr)
        return 2
    findings, summary = check(
        args.project, args.previous_android, args.previous_ios, args.previous_version, args.min_target_sdk
    )
    if args.json:
        print(json.dumps({**summary, "findings": [f.as_dict() for f in findings]}, indent=2))
    else:
        print(f"Project type: {summary['project']}")
        for plat in ("android", "ios"):
            info = summary["versions"].get(plat) or {}
            if info:
                print(f"  {plat:<8} version {info.get('name')} build {info.get('build')}  ({info.get('from')})")
        for f in sorted(findings, key=lambda f: -SEVERITIES.index(f.severity)):
            print(f"{f.severity.upper():<6} [{f.check}] {f.where}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(findings)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
