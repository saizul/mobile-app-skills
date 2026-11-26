#!/usr/bin/env python3
"""Audit an iOS Info.plist for missing or weak privacy usage descriptions and ATS exceptions.

Infers the capabilities the app needs from the plist itself (background modes), an
optional entitlements file and an optional project folder (Flutter pubspec.yaml,
React Native / Expo package.json, Podfile, Swift and Objective-C sources), then reports:
  * missing NS*UsageDescription keys for those capabilities (App Review / crash on access)
  * empty, placeholder or vague purpose strings (guideline 5.1.1)
  * location key combinations, deprecated keys
  * App Transport Security exceptions (arbitrary loads, insecure domains, old TLS)
  * export compliance key, LSApplicationQueriesSchemes count, privacy manifest presence

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]

CAPABILITY_KEYS = {
    "camera": ["NSCameraUsageDescription"],
    "microphone": ["NSMicrophoneUsageDescription"],
    "photos": ["NSPhotoLibraryUsageDescription"],
    "photos-add": ["NSPhotoLibraryAddUsageDescription"],
    "location": ["NSLocationWhenInUseUsageDescription"],
    "location-always": ["NSLocationWhenInUseUsageDescription", "NSLocationAlwaysAndWhenInUseUsageDescription"],
    "contacts": ["NSContactsUsageDescription"],
    "calendars": ["NSCalendarsFullAccessUsageDescription"],
    "reminders": ["NSRemindersFullAccessUsageDescription"],
    "bluetooth": ["NSBluetoothAlwaysUsageDescription"],
    "faceid": ["NSFaceIDUsageDescription"],
    "speech": ["NSSpeechRecognitionUsageDescription"],
    "motion": ["NSMotionUsageDescription"],
    "health": ["NSHealthShareUsageDescription", "NSHealthUpdateUsageDescription"],
    "tracking": ["NSUserTrackingUsageDescription"],
    "local-network": ["NSLocalNetworkUsageDescription"],
    "nfc": ["NFCReaderUsageDescription"],
    "homekit": ["NSHomeKitUsageDescription"],
    "media-library": ["NSAppleMusicUsageDescription"],
    "siri": ["NSSiriUsageDescription"],
}

# Dependency name -> capabilities. Matched as whole package names in pubspec.yaml,
# package.json and Podfile / Podfile.lock.
PACKAGE_CAPS = {
    # Flutter
    "image_picker": ["photos", "camera", "microphone"],
    "camera": ["camera", "microphone"],
    "mobile_scanner": ["camera"],
    "qr_code_scanner": ["camera"],
    "geolocator": ["location"],
    "location": ["location"],
    "google_maps_flutter": [],
    "flutter_background_geolocation": ["location-always", "motion"],
    "permission_handler": [],
    "local_auth": ["faceid"],
    "flutter_contacts": ["contacts"],
    "contacts_service": ["contacts"],
    "device_calendar": ["calendars"],
    "speech_to_text": ["speech", "microphone"],
    "record": ["microphone"],
    "flutter_sound": ["microphone"],
    "flutter_blue_plus": ["bluetooth"],
    "flutter_reactive_ble": ["bluetooth"],
    "health": ["health"],
    "app_tracking_transparency": ["tracking"],
    "photo_manager": ["photos"],
    "gal": ["photos-add"],
    "image_gallery_saver": ["photos-add"],
    "nfc_manager": ["nfc"],
    "pedometer": ["motion"],
    "sensors_plus": [],
    # React Native / Expo
    "react-native-vision-camera": ["camera", "microphone"],
    "react-native-camera": ["camera", "microphone"],
    "expo-camera": ["camera", "microphone"],
    "react-native-image-picker": ["photos", "camera"],
    "react-native-image-crop-picker": ["photos", "camera"],
    "expo-image-picker": ["photos", "camera"],
    "@react-native-camera-roll/camera-roll": ["photos", "photos-add"],
    "expo-media-library": ["photos", "photos-add"],
    "@react-native-community/geolocation": ["location"],
    "react-native-geolocation-service": ["location"],
    "expo-location": ["location"],
    "react-native-background-geolocation": ["location-always", "motion"],
    "react-native-contacts": ["contacts"],
    "expo-contacts": ["contacts"],
    "expo-calendar": ["calendars", "reminders"],
    "react-native-calendar-events": ["calendars"],
    "react-native-ble-plx": ["bluetooth"],
    "react-native-ble-manager": ["bluetooth"],
    "react-native-biometrics": ["faceid"],
    "react-native-touch-id": ["faceid"],
    "expo-local-authentication": ["faceid"],
    "@react-native-voice/voice": ["speech", "microphone"],
    "react-native-audio-recorder-player": ["microphone"],
    "expo-av": ["microphone"],
    "expo-audio": ["microphone"],
    "react-native-health": ["health"],
    "react-native-tracking-transparency": ["tracking"],
    "expo-tracking-transparency": ["tracking"],
    "react-native-nfc-manager": ["nfc"],
    "expo-sensors": ["motion"],
}

# Swift / Objective-C API usage -> capability.
CODE_CAPS = [
    (re.compile(r"\bAVCaptureDevice\b|\bUIImagePickerController\b.*\.camera"), "camera"),
    (re.compile(r"\bAVAudioRecorder\b|\brequestRecordPermission\b|\bAVAudioApplication\b"), "microphone"),
    (re.compile(r"\bPHPhotoLibrary\b(?!.*performChanges)|\bPHAsset\.fetch"), "photos"),
    (re.compile(r"\brequestWhenInUseAuthorization\b"), "location"),
    (re.compile(r"\brequestAlwaysAuthorization\b"), "location-always"),
    (re.compile(r"\bCNContactStore\b"), "contacts"),
    (re.compile(r"\bEKEventStore\b"), "calendars"),
    (re.compile(r"\bCBCentralManager\b|\bCBPeripheralManager\b"), "bluetooth"),
    (re.compile(r"\bLAContext\b"), "faceid"),
    (re.compile(r"\bSFSpeechRecognizer\b"), "speech"),
    (re.compile(r"\bCMMotionActivityManager\b|\bCMPedometer\b"), "motion"),
    (re.compile(r"\bHKHealthStore\b"), "health"),
    (re.compile(r"\bATTrackingManager\b"), "tracking"),
    (re.compile(r"\bNFCNDEFReaderSession\b|\bNFCTagReaderSession\b"), "nfc"),
]

ENTITLEMENT_CAPS = {
    "com.apple.developer.healthkit": "health",
    "com.apple.developer.homekit": "homekit",
    "com.apple.developer.nfc.readersession.formats": "nfc",
    "com.apple.developer.siri": "siri",
}

PLACEHOLDER_RE = re.compile(r"^\s*$|\b(todo|tbd|fixme|lorem|ipsum|placeholder|usage description)\b", re.I)
VAGUE_RE = re.compile(
    r"^\s*(\$\(PRODUCT_NAME\)|this app|the app|app|we)?\s*(needs|requires|would like|wants|uses)\s+"
    r"(access to|to access|permission to use|your)?\s*(the|your)?\s*\w+(\s+\w+)?\s*\.?\s*$",
    re.I,
)
DEPRECATED_KEYS = {
    "NSLocationAlwaysUsageDescription": "only used before iOS 11; add NSLocationAlwaysAndWhenInUseUsageDescription",
    "NSCalendarsUsageDescription": "iOS 17+ uses NSCalendarsFullAccessUsageDescription / WriteOnlyAccess",
    "NSRemindersUsageDescription": "iOS 17+ uses NSRemindersFullAccessUsageDescription",
    "NSBluetoothPeripheralUsageDescription": "replaced by NSBluetoothAlwaysUsageDescription (iOS 13+)",
}
SKIP_DIRS = {"Pods", "build", "node_modules", ".dart_tool", ".git", "DerivedData", ".symlinks", "android"}


class Finding:
    __slots__ = ("check", "fix", "key", "message", "severity")

    def __init__(self, check, severity, key, message, fix):
        self.check, self.severity, self.key, self.message, self.fix = check, severity, key, message, fix

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "key": self.key,
            "message": self.message,
            "fix": self.fix,
        }


def load_plist(path: Path) -> dict:
    try:
        with path.open("rb") as fh:
            data = plistlib.load(fh)
    except (plistlib.InvalidFileException, ValueError) as exc:
        raise ValueError(f"{path}: not a valid plist ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: plist root must be a dictionary")
    return data


def dependency_names(project: Path) -> dict[str, str]:
    """Return {package name: file it was found in} from pubspec.yaml, package.json and Podfiles."""
    found: dict[str, str] = {}
    for pubspec in _files(project, "pubspec.yaml"):
        section = None
        for line in pubspec.read_text(encoding="utf-8", errors="replace").splitlines():
            if re.match(r"^\S", line):
                section = line.split(":")[0].strip()
                continue
            m = re.match(r"^  ([a-z0-9_]+)\s*:", line)
            if m and section in ("dependencies",):
                found.setdefault(m.group(1), str(pubspec.relative_to(project)))
    for pkg in _files(project, "package.json"):
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for name in (data.get("dependencies") or {}) if isinstance(data, dict) else {}:
            found.setdefault(name, str(pkg.relative_to(project)))
    return found


def _files(project: Path, name: str) -> list[Path]:
    out = []
    for p in sorted(project.rglob(name)):
        rel = p.relative_to(project).parts[:-1]
        if not any(part in SKIP_DIRS or part.startswith(".") for part in rel):
            out.append(p)
    return out


def code_capabilities(project: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for suffix in ("*.swift", "*.m", "*.mm"):
        for p in sorted(project.rglob(suffix)):
            if any(part in SKIP_DIRS for part in p.relative_to(project).parts):
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for rx, cap in CODE_CAPS:
                if rx.search(text):
                    found.setdefault(cap, str(p.relative_to(project)))
    return found


def infer_capabilities(info: dict, entitlements: dict | None, project: Path | None) -> dict[str, str]:
    caps: dict[str, str] = {}
    modes = info.get("UIBackgroundModes") or []
    if "location" in modes:
        caps["location-always"] = "UIBackgroundModes: location"
    if "bluetooth-central" in modes or "bluetooth-peripheral" in modes:
        caps.setdefault("bluetooth", "UIBackgroundModes: bluetooth")
    for key, cap in ENTITLEMENT_CAPS.items():
        if entitlements and entitlements.get(key):
            caps.setdefault(cap, f"entitlement {key}")
    if project:
        for name, where in dependency_names(project).items():
            for cap in PACKAGE_CAPS.get(name, []):
                caps.setdefault(cap, f"dependency {name} ({where})")
        for cap, where in code_capabilities(project).items():
            caps.setdefault(cap, f"API use in {where}")
    return caps


def audit_strings(info: dict) -> list[Finding]:
    out = []
    for key, value in info.items():
        if not (key.endswith("UsageDescription") or key == "NFCReaderUsageDescription"):
            continue
        text = value if isinstance(value, str) else ""
        if not text.strip():
            out.append(
                Finding("usage.empty", "high", key, "purpose string is empty", "explain what the data is used for")
            )
        elif PLACEHOLDER_RE.search(text) and len(text) < 60:
            out.append(
                Finding(
                    "usage.placeholder",
                    "medium",
                    key,
                    f"placeholder-like purpose string: {text!r}",
                    "write a specific reason with an example",
                )
            )
        elif VAGUE_RE.match(text) or len(text.strip()) < 20:
            out.append(
                Finding(
                    "usage.vague",
                    "medium",
                    key,
                    f"vague purpose string: {text!r}",
                    "say why and how it is used, e.g. 'Scan receipts to add expenses automatically.'",
                )
            )
        if key in DEPRECATED_KEYS:
            out.append(Finding("usage.deprecated", "low", key, DEPRECATED_KEYS[key], "add the current key"))
    return out


def audit_ats(info: dict) -> list[Finding]:
    out = []
    ats = info.get("NSAppTransportSecurity")
    if not isinstance(ats, dict):
        return out
    if ats.get("NSAllowsArbitraryLoads") is True:
        overridden = any(ats.get(k) for k in ("NSAllowsArbitraryLoadsInWebContent", "NSAllowsArbitraryLoadsForMedia"))
        note = " (ignored on iOS 10+ because a more specific key is set)" if overridden else ""
        out.append(
            Finding(
                "ats.arbitrary_loads",
                "high" if not overridden else "low",
                "NSAllowsArbitraryLoads",
                "ATS disabled for all connections" + note,
                "remove it; add NSExceptionDomains for the specific hosts; App Review asks for a justification",
            )
        )
    for key in ("NSAllowsArbitraryLoadsInWebContent", "NSAllowsArbitraryLoadsForMedia"):
        if ats.get(key) is True:
            out.append(
                Finding(
                    "ats.arbitrary_loads_scoped",
                    "medium",
                    key,
                    f"{key} is true",
                    "keep only if the app shows arbitrary web/media content; be ready to justify it",
                )
            )
    if ats.get("NSAllowsLocalNetworking") is True:
        out.append(
            Finding(
                "ats.local_networking",
                "info",
                "NSAllowsLocalNetworking",
                "local network loads allowed",
                "fine for LAN devices; remove if not needed",
            )
        )
    for domain, conf in (ats.get("NSExceptionDomains") or {}).items():
        if not isinstance(conf, dict):
            continue
        local = domain in ("localhost", "127.0.0.1") or domain.endswith(".local")
        if conf.get("NSExceptionAllowsInsecureHTTPLoads") is True or conf.get(
            "NSThirdPartyExceptionAllowsInsecureHTTPLoads"
        ):
            sub = " and all subdomains" if conf.get("NSIncludesSubdomains") else ""
            out.append(
                Finding(
                    "ats.insecure_domain",
                    "info" if local else "medium",
                    domain,
                    f"plain HTTP allowed for {domain}{sub}",
                    "serve it over HTTPS and remove the exception",
                )
            )
        tls = conf.get("NSExceptionMinimumTLSVersion") or conf.get("NSThirdPartyExceptionMinimumTLSVersion")
        if isinstance(tls, str) and tls in ("TLSv1.0", "TLSv1.1"):
            out.append(Finding("ats.old_tls", "medium", domain, f"minimum TLS {tls}", "require TLS 1.2 or later"))
        if conf.get("NSExceptionRequiresForwardSecrecy") is False:
            out.append(
                Finding(
                    "ats.no_forward_secrecy",
                    "low",
                    domain,
                    "forward secrecy not required",
                    "enable ECDHE ciphers on the server and drop the exception",
                )
            )
    return out


def audit(
    info: dict,
    entitlements: dict | None = None,
    project: Path | None = None,
) -> tuple[list[Finding], dict[str, str]]:
    out: list[Finding] = []
    caps = infer_capabilities(info, entitlements, project)
    for cap, source in sorted(caps.items()):
        for key in CAPABILITY_KEYS[cap]:
            if key not in info:
                if cap == "calendars" and "NSCalendarsUsageDescription" in info:
                    sev = "low"
                else:
                    sev = "high"
                out.append(
                    Finding(
                        "usage.missing",
                        sev,
                        key,
                        f"needed for {cap} ({source}) but missing",
                        "add the key with a specific purpose string; the app crashes on first access without it",
                    )
                )
    reported = {f.key for f in out}
    if (
        "NSLocationAlwaysAndWhenInUseUsageDescription" in info
        and "NSLocationWhenInUseUsageDescription" not in info
        and "NSLocationWhenInUseUsageDescription" not in reported
    ):
        out.append(
            Finding(
                "usage.location_pair",
                "high",
                "NSLocationWhenInUseUsageDescription",
                "Always key present without the When In Use key (both are required)",
                "add it",
            )
        )
    out += audit_strings(info)
    out += audit_ats(info)
    if "ITSAppUsesNonExemptEncryption" not in info:
        out.append(
            Finding(
                "export.encryption",
                "info",
                "ITSAppUsesNonExemptEncryption",
                "not set: App Store Connect asks export compliance questions for every build",
                "set it to false if you only use HTTPS/OS encryption (check the rules for your app)",
            )
        )
    schemes = info.get("LSApplicationQueriesSchemes") or []
    if len(schemes) > 50:
        out.append(
            Finding(
                "schemes.too_many",
                "medium",
                "LSApplicationQueriesSchemes",
                f"{len(schemes)} schemes; canOpenURL only honours the first 50",
                "keep the ones you really check",
            )
        )
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        val = info.get(key)
        if isinstance(val, str) and val and "$(" not in val:
            out.append(
                Finding(
                    "version.hardcoded",
                    "info",
                    key,
                    f"hard-coded {key} = {val}",
                    "use $(FLUTTER_BUILD_NAME)/$(MARKETING_VERSION) style build settings",
                )
            )
    if info.get("UIFileSharingEnabled") is True:
        out.append(
            Finding(
                "files.sharing",
                "low",
                "UIFileSharingEnabled",
                "Documents folder is visible in the Files app and Finder",
                "make sure no tokens or databases are stored in Documents",
            )
        )
    if project is not None:
        manifests = [p for p in project.rglob("PrivacyInfo.xcprivacy") if not ({"Pods", "build"} & set(p.parts))]
        if not manifests:
            out.append(
                Finding(
                    "privacy.manifest_missing",
                    "medium",
                    "PrivacyInfo.xcprivacy",
                    "no app privacy manifest found in the project",
                    "add PrivacyInfo.xcprivacy to the Runner/app target with required-reason APIs",
                )
            )
    return out, caps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("plist", type=Path, help="Info.plist (XML or binary), e.g. ios/Runner/Info.plist")
    p.add_argument("--entitlements", type=Path, help="Runner.entitlements to infer HealthKit/HomeKit/NFC")
    p.add_argument("--project", type=Path, help="project root to infer capabilities from dependencies and code")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        info = load_plist(args.plist)
        ent = load_plist(args.entitlements) if args.entitlements else None
        if args.project and not args.project.is_dir():
            raise ValueError(f"{args.project} is not a directory")
        findings, caps = audit(info, ent, args.project)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rank = SEVERITIES.index(args.min_severity)
    order = {s: i for i, s in enumerate(reversed(SEVERITIES))}
    shown = sorted((f for f in findings if SEVERITIES.index(f.severity) >= rank), key=lambda f: order[f.severity])
    if args.json:
        print(json.dumps({"capabilities": caps, "findings": [f.as_dict() for f in shown]}, indent=2))
    else:
        if caps:
            print("Capabilities inferred:")
            for cap, src in sorted(caps.items()):
                print(f"  {cap:<16} {src}")
            print()
        for f in shown:
            print(f"{f.severity.upper():<6} [{f.check}] {f.key}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(shown)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
