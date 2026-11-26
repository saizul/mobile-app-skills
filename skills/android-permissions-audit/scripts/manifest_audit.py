#!/usr/bin/env python3
"""Audit an AndroidManifest.xml for risky permissions and insecure component and app settings.

Checks dangerous and Play-restricted permissions (SMS, call log, background location, all
files access, package visibility, exact alarms, full-screen intents, photo/video access),
legacy storage permissions, permissions without a usage hint in the source tree (with
--source), exported components without a permission, missing android:exported on
components with intent filters, debuggable builds, cleartext traffic, backup settings and
network security config (cleartext, user CAs).

Run it on the merged release manifest for the full picture (libraries add permissions):
  find android/app/build -path '*merged*' -name AndroidManifest.xml

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

A = "{http://schemas.android.com/apk/res/android}"
TOOLS = "{http://schemas.android.com/tools}"
SEVERITIES = ["info", "low", "medium", "high"]

# Runtime ("dangerous") permissions. Value: short purpose used in messages.
DANGEROUS = {
    "ACCESS_FINE_LOCATION": "precise location",
    "ACCESS_COARSE_LOCATION": "approximate location",
    "ACCESS_BACKGROUND_LOCATION": "location in the background",
    "ACCESS_MEDIA_LOCATION": "photo location metadata",
    "CAMERA": "camera",
    "RECORD_AUDIO": "microphone",
    "READ_CONTACTS": "contacts",
    "WRITE_CONTACTS": "contacts",
    "GET_ACCOUNTS": "accounts",
    "READ_CALENDAR": "calendar",
    "WRITE_CALENDAR": "calendar",
    "READ_PHONE_STATE": "phone state",
    "READ_PHONE_NUMBERS": "phone numbers",
    "CALL_PHONE": "phone calls",
    "ANSWER_PHONE_CALLS": "phone calls",
    "READ_CALL_LOG": "call log",
    "WRITE_CALL_LOG": "call log",
    "PROCESS_OUTGOING_CALLS": "call log",
    "ADD_VOICEMAIL": "voicemail",
    "USE_SIP": "SIP calls",
    "SEND_SMS": "SMS",
    "RECEIVE_SMS": "SMS",
    "READ_SMS": "SMS",
    "RECEIVE_MMS": "SMS",
    "RECEIVE_WAP_PUSH": "SMS",
    "BODY_SENSORS": "body sensors",
    "BODY_SENSORS_BACKGROUND": "body sensors in the background",
    "ACTIVITY_RECOGNITION": "physical activity",
    "READ_EXTERNAL_STORAGE": "shared storage",
    "WRITE_EXTERNAL_STORAGE": "shared storage",
    "READ_MEDIA_IMAGES": "photos",
    "READ_MEDIA_VIDEO": "videos",
    "READ_MEDIA_AUDIO": "audio files",
    "READ_MEDIA_VISUAL_USER_SELECTED": "selected photos",
    "BLUETOOTH_SCAN": "nearby devices",
    "BLUETOOTH_CONNECT": "nearby devices",
    "BLUETOOTH_ADVERTISE": "nearby devices",
    "NEARBY_WIFI_DEVICES": "nearby Wi-Fi devices",
    "UWB_RANGING": "nearby devices",
    "POST_NOTIFICATIONS": "notifications",
}

# Permissions that need a Play Console declaration or are restricted by Google Play policy.
RESTRICTED = {
    "READ_SMS": "SMS and Call Log policy: only default SMS/phone/assistant handlers or approved exceptions",
    "SEND_SMS": "SMS and Call Log policy: only default SMS/phone/assistant handlers or approved exceptions",
    "RECEIVE_SMS": "SMS and Call Log policy: use the SMS Retriever / User Consent API for OTPs",
    "RECEIVE_MMS": "SMS and Call Log policy",
    "RECEIVE_WAP_PUSH": "SMS and Call Log policy",
    "READ_CALL_LOG": "SMS and Call Log policy: needs a Permissions Declaration Form",
    "WRITE_CALL_LOG": "SMS and Call Log policy: needs a Permissions Declaration Form",
    "PROCESS_OUTGOING_CALLS": "SMS and Call Log policy: needs a Permissions Declaration Form",
    "ACCESS_BACKGROUND_LOCATION": "background location needs a declaration, a video and a prominent disclosure",
    "MANAGE_EXTERNAL_STORAGE": "All files access: only file managers, backup, antivirus and similar core uses",
    "QUERY_ALL_PACKAGES": "package visibility: declare a core use or use <queries> instead",
    "REQUEST_INSTALL_PACKAGES": "only for apps whose core purpose is installing packages",
    "READ_MEDIA_IMAGES": "Photo and Video Permissions policy: use the Android photo picker for one-off access",
    "READ_MEDIA_VIDEO": "Photo and Video Permissions policy: use the Android photo picker for one-off access",
    "USE_EXACT_ALARM": "only alarm clock and calendar apps; others use SCHEDULE_EXACT_ALARM or inexact alarms",
    "USE_FULL_SCREEN_INTENT": "only calling and alarm apps get it by default on Android 14+",
    "SYSTEM_ALERT_WINDOW": "draw over other apps: users must grant it manually; justify it",
    "BIND_ACCESSIBILITY_SERVICE": "Accessibility API policy: needs a declaration and prominent disclosure",
    "BIND_VPN_SERVICE": "VpnService policy: only for apps whose core feature is a VPN",
    "READ_PRIVILEGED_PHONE_STATE": "system apps only",
    "FOREGROUND_SERVICE_SPECIAL_USE": "special-use foreground service needs a justification in Play Console",
}

# Words that suggest a permission is really used. Searched case-insensitively in source and
# dependency files (Dart, Kotlin, Java, JS/TS, pubspec.yaml, package.json, build.gradle).
USAGE_HINTS = {
    "CAMERA": ["camera", "image_picker", "mobile_scanner", "barcode", "qr_code", "vision-camera", "capture"],
    "RECORD_AUDIO": ["record", "audio", "microphone", "speech", "voice", "mediarecorder"],
    "ACCESS_FINE_LOCATION": ["location", "geolocat", "gps", "fusedlocation", "maps"],
    "ACCESS_COARSE_LOCATION": ["location", "geolocat", "fusedlocation", "maps"],
    "ACCESS_BACKGROUND_LOCATION": ["background_location", "backgroundlocation", "geofenc", "background-geolocation"],
    "READ_CONTACTS": ["contacts", "contactscontract"],
    "WRITE_CONTACTS": ["contacts", "contactscontract"],
    "READ_CALENDAR": ["calendar"],
    "WRITE_CALENDAR": ["calendar"],
    "READ_PHONE_STATE": ["telephonymanager", "phone_state", "device_info", "phonestate"],
    "CALL_PHONE": ["action_call", "tel:", "phone_call", "call_phone"],
    "BLUETOOTH_SCAN": ["bluetooth", "ble", "flutter_blue"],
    "BLUETOOTH_CONNECT": ["bluetooth", "ble", "flutter_blue"],
    "ACTIVITY_RECOGNITION": ["activity_recognition", "pedometer", "step", "health"],
    "BODY_SENSORS": ["sensor", "health", "heart"],
    "READ_MEDIA_IMAGES": ["image_picker", "gallery", "photo", "mediastore", "file_picker"],
    "READ_MEDIA_VIDEO": ["image_picker", "video", "gallery", "mediastore", "file_picker"],
    "READ_MEDIA_AUDIO": ["audio", "music", "mediastore", "file_picker"],
    "POST_NOTIFICATIONS": ["notification", "messaging", "push"],
    "SEND_SMS": ["smsmanager", "sms"],
    "READ_SMS": ["sms"],
    "RECEIVE_SMS": ["sms"],
}
SOURCE_SUFFIXES = {".dart", ".kt", ".java", ".js", ".jsx", ".ts", ".tsx", ".gradle", ".kts", ".yaml", ".json"}
SKIP_DIRS = {"build", "node_modules", ".dart_tool", ".gradle", "Pods", ".git", "ios", ".idea"}


class Finding:
    __slots__ = ("check", "fix", "message", "severity", "target")

    def __init__(self, check, severity, target, message, fix):
        self.check, self.severity, self.target, self.message, self.fix = check, severity, target, message, fix

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "target": self.target,
            "message": self.message,
            "fix": self.fix,
        }


def short(name: str) -> str:
    return name.rsplit(".", 1)[-1] if name.startswith("android.permission.") else name


def target_sdk_from_gradle(path: Path) -> int | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"targetSdk(?:Version)?\s*[=(]?\s*(\d+)", text)
    return int(m.group(1)) if m else None


def find_source_text(root: Path, limit_bytes: int = 30_000_000) -> str:
    chunks, total = [], 0
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES and path.name != "AndroidManifest.xml":
            try:
                data = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            total += len(data)
            if total > limit_bytes:
                break
            chunks.append(data.lower())
    return "\n".join(chunks)


def resolve_xml_resource(manifest: Path, ref: str, res_dir: Path | None) -> Path | None:
    if not ref.startswith("@xml/"):
        return None
    name = ref[5:] + ".xml"
    dirs = [res_dir] if res_dir else []
    dirs += [manifest.parent / "res", manifest.parent.parent / "res", manifest.parent / "main" / "res"]
    for d in dirs:
        if d and (d / "xml" / name).is_file():
            return d / "xml" / name
    return None


def audit_network_config(path: Path) -> list[Finding]:
    out = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [Finding("nsc.parse", "low", path.name, f"cannot parse network security config: {exc}", "fix XML")]
    for elem in root.iter():
        if elem.tag not in ("base-config", "domain-config"):
            continue
        scope = (
            "base-config"
            if elem.tag == "base-config"
            else "domain-config " + ",".join((d.text or "").strip() for d in elem.findall("domain"))
        )
        if elem.get("cleartextTrafficPermitted") == "true":
            local = all(
                (d.text or "").strip() in ("localhost", "10.0.2.2", "127.0.0.1") for d in elem.findall("domain")
            )
            sev = (
                "info" if elem.tag == "domain-config" and local else ("high" if elem.tag == "base-config" else "medium")
            )
            out.append(Finding("nsc.cleartext", sev, scope, "cleartext HTTP permitted", "use HTTPS; limit to debug"))
        for cert in elem.iter("certificates"):
            if cert.get("src") == "user":
                out.append(
                    Finding(
                        "nsc.user_ca",
                        "medium",
                        scope,
                        "trusts user-installed CAs (traffic interception)",
                        'move <certificates src="user"/> into <debug-overrides>',
                    )
                )
    return out


def audit(
    manifest: Path,
    target_sdk: int | None = None,
    source_text: str | None = None,
    res_dir: Path | None = None,
) -> tuple[list[Finding], dict]:
    try:
        tree = ET.parse(manifest)
    except ET.ParseError as exc:
        raise ValueError(f"{manifest}: not a text AndroidManifest.xml ({exc}); decode binary manifests first") from exc
    root = tree.getroot()
    if root.tag != "manifest":
        raise ValueError(f"{manifest}: root element is <{root.tag}>, expected <manifest>")
    out: list[Finding] = []
    uses_sdk = root.find("uses-sdk")
    if target_sdk is None and uses_sdk is not None and uses_sdk.get(A + "targetSdkVersion"):
        try:
            target_sdk = int(uses_sdk.get(A + "targetSdkVersion"))
        except ValueError:
            target_sdk = None

    perms: dict[str, ET.Element] = {}
    for tag in ("uses-permission", "uses-permission-sdk-23"):
        for el in root.findall(tag):
            name = el.get(A + "name")
            if name and el.get(TOOLS + "node") != "remove":
                perms[name] = el
    for name, el in sorted(perms.items()):
        p = short(name)
        max_sdk = el.get(A + "maxSdkVersion")
        if p in RESTRICTED:
            sev = "high" if p not in ("READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO", "SYSTEM_ALERT_WINDOW") else "medium"
            if p == "FOREGROUND_SERVICE_SPECIAL_USE":
                sev = "medium"
            out.append(
                Finding("permission.restricted", sev, p, RESTRICTED[p], "remove it or prepare the Play declaration")
            )
        elif p in DANGEROUS:
            out.append(
                Finding(
                    "permission.dangerous",
                    "info",
                    p,
                    f"runtime permission for {DANGEROUS[p]}",
                    "request it in context, explain why, handle denial",
                )
            )
        if p in ("READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE") and not max_sdk:
            sev = "medium" if (target_sdk or 0) >= 33 else "low"
            out.append(
                Finding(
                    "permission.legacy_storage",
                    sev,
                    p,
                    "legacy storage permission without maxSdkVersion (ignored on Android 13+)",
                    'add android:maxSdkVersion="32" (or 28 for WRITE) and use READ_MEDIA_* / the photo picker',
                )
            )
        if p == "WRITE_EXTERNAL_STORAGE" and max_sdk and int(max_sdk) > 29:
            out.append(
                Finding(
                    "permission.legacy_storage",
                    "low",
                    p,
                    "WRITE_EXTERNAL_STORAGE has no effect on Android 11+",
                    'set android:maxSdkVersion="28" or "29"',
                )
            )
        if source_text is not None and p in USAGE_HINTS:
            if not any(h in source_text for h in USAGE_HINTS[p]):
                out.append(
                    Finding(
                        "permission.unused",
                        "low",
                        p,
                        "no usage hint found in source or dependencies (may come from a library)",
                        'remove it, or tools:node="remove" if a library adds it and you do not need it',
                    )
                )
    has_fg_service = "android.permission.FOREGROUND_SERVICE" in perms
    if (target_sdk or 0) >= 34 and has_fg_service:
        typed = [p for p in perms if short(p).startswith("FOREGROUND_SERVICE_")]
        if not typed:
            out.append(
                Finding(
                    "permission.fgs_type",
                    "medium",
                    "FOREGROUND_SERVICE",
                    "targetSdk 34+ requires a FOREGROUND_SERVICE_<TYPE> permission per service type",
                    "add foregroundServiceType on the service and the matching permission",
                )
            )
    if "android.permission.POST_NOTIFICATIONS" not in perms and (target_sdk or 0) >= 33:
        receivers = " ".join(el.get(A + "name", "") for el in root.iter("service")).lower()
        if "messaging" in receivers or "firebase" in receivers or "push" in receivers:
            out.append(
                Finding(
                    "permission.notifications",
                    "low",
                    "POST_NOTIFICATIONS",
                    "push service declared but POST_NOTIFICATIONS missing (needed on Android 13+)",
                    "declare it and request it at runtime",
                )
            )

    app = root.find("application")
    if app is not None:
        if app.get(A + "debuggable") == "true":
            out.append(
                Finding(
                    "app.debuggable",
                    "high",
                    "application",
                    'android:debuggable="true"',
                    "remove it; the build type sets it (Play rejects debuggable APKs)",
                )
            )
        if app.get(A + "usesCleartextTraffic") == "true":
            out.append(
                Finding(
                    "app.cleartext",
                    "medium",
                    "application",
                    'android:usesCleartextTraffic="true"',
                    "use HTTPS; allow cleartext only for specific hosts in a debug network config",
                )
            )
        elif app.get(A + "usesCleartextTraffic") is None and target_sdk is not None and target_sdk < 28:
            out.append(
                Finding(
                    "app.cleartext",
                    "low",
                    "application",
                    "cleartext allowed by default below targetSdk 28",
                    'raise targetSdk or set usesCleartextTraffic="false"',
                )
            )
        backup = app.get(A + "allowBackup")
        if backup != "false" and not app.get(A + "dataExtractionRules") and not app.get(A + "fullBackupContent"):
            out.append(
                Finding(
                    "app.backup",
                    "low",
                    "application",
                    "backup enabled without rules: tokens and databases go to cloud backup",
                    'set dataExtractionRules / fullBackupContent excluding secrets, or allowBackup="false"',
                )
            )
        nsc = app.get(A + "networkSecurityConfig")
        if nsc:
            path = resolve_xml_resource(manifest, nsc, res_dir)
            if path:
                out += audit_network_config(path)
            else:
                out.append(
                    Finding(
                        "nsc.not_found",
                        "info",
                        nsc,
                        "network security config file not found",
                        "pass --res path/to/res to check it",
                    )
                )
        out += audit_components(app, root, target_sdk)
    info = {
        "package": root.get("package"),
        "target_sdk": target_sdk,
        "permissions": sorted(short(p) for p in perms),
    }
    return out, info


def audit_components(app: ET.Element, root: ET.Element, target_sdk: int | None) -> list[Finding]:
    out: list[Finding] = []
    custom_perms = {el.get(A + "name"): el.get(A + "protectionLevel", "normal") for el in root.findall("permission")}
    for name, level in custom_perms.items():
        if "signature" not in (level or ""):
            out.append(
                Finding(
                    "permission.custom_weak",
                    "low",
                    name,
                    f"custom permission protectionLevel={level}",
                    'use protectionLevel="signature" for app-to-app permissions',
                )
            )
    for kind in ("activity", "activity-alias", "service", "receiver", "provider"):
        for comp in app.findall(kind):
            name = comp.get(A + "name") or comp.get(A + "targetActivity") or "?"
            filters = comp.findall("intent-filter")
            exported = comp.get(A + "exported")
            perm = comp.get(A + "permission") or (comp.get(A + "readPermission") if kind == "provider" else None)
            if filters and exported is None:
                sev = "high" if (target_sdk or 31) >= 31 else "low"
                out.append(
                    Finding(
                        "component.exported_missing",
                        sev,
                        f"{kind} {name}",
                        "has an intent-filter but no android:exported (build fails on targetSdk 31+)",
                        'set android:exported="true" or "false" explicitly',
                    )
                )
            is_exported = exported == "true" or (exported is None and filters and (target_sdk or 31) < 31)
            if kind == "provider" and exported is None and (target_sdk or 17) < 17:
                is_exported = True
            if not is_exported or perm:
                continue
            actions = {a.get(A + "name") for f in filters for a in f.findall("action")}
            cats = {c.get(A + "name") for f in filters for c in f.findall("category")}
            if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in cats:
                continue
            if kind == "provider":
                sev, msg = "high", "exported content provider without read/write permission"
            elif kind in ("activity", "activity-alias") and "android.intent.category.BROWSABLE" in cats:
                sev, msg = "info", "deep-link activity is exported: validate every incoming URI and parameter"
            elif kind == "receiver" and actions and all(a and a.startswith("android.") for a in actions):
                sev, msg = "low", "exported receiver for system broadcasts: check the action before acting"
            elif (
                kind == "service"
                and comp.get(A + "permission") is None
                and any(a and ("firebase" in a.lower() or "messaging" in a.lower()) for a in actions)
            ):
                sev, msg = "info", "messaging service is exported (normal for FCM)"
            else:
                sev, msg = "medium", f"exported {kind} without android:permission: any app can start it"
            out.append(
                Finding(
                    "component.exported",
                    sev,
                    f"{kind} {name}",
                    msg,
                    'set android:exported="false" or protect it with a signature permission',
                )
            )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("manifest", type=Path, help="AndroidManifest.xml (source or merged)")
    p.add_argument("--target-sdk", type=int, help="targetSdk if not in the manifest (Flutter/RN set it in Gradle)")
    p.add_argument("--gradle", type=Path, help="read targetSdk from this build.gradle / build.gradle.kts")
    p.add_argument("--source", type=Path, help="project folder to scan for permission usage hints")
    p.add_argument("--res", type=Path, help="res/ folder for resolving @xml/network_security_config")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        target = args.target_sdk
        if target is None and args.gradle:
            target = target_sdk_from_gradle(args.gradle)
        src = find_source_text(args.source) if args.source else None
        findings, info = audit(args.manifest, target, src, args.res)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rank = SEVERITIES.index(args.min_severity)
    order = {s: i for i, s in enumerate(reversed(SEVERITIES))}
    shown = sorted((f for f in findings if SEVERITIES.index(f.severity) >= rank), key=lambda f: order[f.severity])
    if args.json:
        print(json.dumps({**info, "findings": [f.as_dict() for f in shown]}, indent=2))
    else:
        print(
            f"{args.manifest}: package={info['package'] or '?'} targetSdk={info['target_sdk'] or '?'} "
            f"permissions={len(info['permissions'])}"
        )
        for f in shown:
            print(f"{f.severity.upper():<6} [{f.check}] {f.target}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(shown)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
