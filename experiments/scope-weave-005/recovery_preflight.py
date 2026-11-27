#!/usr/bin/env python3
"""Offline FM-1 recovery evidence inventory. Never opens a device or approves flashing.

Usage: python recovery_preflight.py --template > evidence.json
       python recovery_preflight.py evidence.json
       python recovery_preflight.py --self-test

Keep evidence and backup files private. Relative artifact paths resolve under the
manifest directory. Stock package provenance and backup format/scope require
human verification; hashes establish integrity only, not authenticity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

PIN = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
CHIPS = {"856014": "Puya P25Q80", "B36014": "UC25HQ80"}
ROLES = ("stock_restore_package", "backup", "identity_receipt", "revision_receipt", "recovery_receipt")


def template():
    return {"schema": 1, "device": {"model": "", "board_revision": "", "jedec": ""},
            "artifacts": {k: {"path": "", "sha256": "", "source": ""} for k in ROLES},
            "backup_scope": "", "stock_match_evidence": "", "recovery_observation": ""}


def nonempty(x):
    return isinstance(x, str) and bool(x.strip())


def inspect(manifest, root):
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1:
        raise ValueError("unsupported manifest schema")
    missing, invalid, verified = [], [], []
    root = root.resolve()
    device = manifest.get("device")
    if not isinstance(device, dict):
        raise ValueError("device must be an object")
    for field in ("model", "board_revision", "jedec"):
        if not nonempty(device.get(field)):
            missing.append("device." + field)
    if nonempty(device.get("model")) and device["model"].strip().upper() != "FM-1":
        invalid.append("device.model: not FM-1")
    chip = device.get("jedec")
    chip = chip.strip().upper().removeprefix("0X") if nonempty(chip) else ""
    if chip and chip not in CHIPS:
        invalid.append("device.jedec: not in pinned upstream FM-1 allowlist")
    for field in ("backup_scope", "stock_match_evidence", "recovery_observation"):
        if not nonempty(manifest.get(field)):
            missing.append(field)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts must be an object")
    used = set()
    for role in ROLES:
        item = artifacts.get(role)
        if not isinstance(item, dict) or not all(nonempty(item.get(k)) for k in ("path", "sha256", "source")):
            missing.append("artifacts." + role)
            continue
        digest = item["sha256"].strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            invalid.append(role + ": invalid SHA-256")
            continue
        try:
            supplied = Path(item["path"])
            if supplied.is_absolute() or ".." in supplied.parts:
                raise ValueError("path must be relative and contained")
            path = (root / supplied).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("path must be a regular file inside manifest directory")
            st = path.stat()
            key = (st.st_dev, st.st_ino) if st.st_ino else str(path)
            if key in used:
                raise ValueError("same file used for multiple evidence roles")
            used.add(key)
            if st.st_size == 0:
                raise ValueError("empty evidence file")
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(65536), b""):
                    h.update(block)
            if h.hexdigest() != digest:
                raise ValueError("SHA-256 mismatch")
            verified.append({"role": role, "bytes": st.st_size, "sha256": digest})
        except OSError:
            invalid.append(role + ": unreadable or missing file")
        except ValueError as exc:
            invalid.append(role + ": " + str(exc))
    return {"status": "HOLD", "inventory_complete": not missing and not invalid,
            "missing": missing, "invalid": invalid, "verified_files": verified,
            "upstream_chip_lead": CHIPS.get(chip), "upstream_pin": PIN,
            "flash_authorized": False, "physical_recovery_verified": False,
            "limitations": ["Metadata and hashes only; source and device assertions are not independently verified.",
                            "A settings backup is not necessarily a full flash backup.",
                            "An upstream JEDEC match does not identify the exact board revision.",
                            "Static audit, controller fidelity, licensing and physical qualification remain separate gates."]}


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        def filled():
            m = template()
            m["device"] = {"model": "FM-1", "board_revision": "synthetic", "jedec": "0x856014"}
            for k in ("backup_scope", "stock_match_evidence", "recovery_observation"):
                m[k] = "synthetic placeholder"
            for role in ROLES:
                raw = role.encode()
                (root / role).write_bytes(raw)
                m["artifacts"][role] = {"path": role, "sha256": hashlib.sha256(raw).hexdigest(), "source": "synthetic"}
            return m
        good = inspect(filled(), root)
        assert good["inventory_complete"] and not good["flash_authorized"] and good["status"] == "HOLD"
        assert not good["physical_recovery_verified"] and len(good["verified_files"]) == 5
        assert not inspect(template(), root)["inventory_complete"]
        m = filled(); m["device"]["jedec"] = "B36014"; assert inspect(m, root)["inventory_complete"]
        mutations = (
            lambda m: m["device"].update(jedec="EB6014"),
            lambda m: m["device"].update(model="SMK-37"),
            lambda m: m["device"].update(board_revision=""),
            lambda m: m.update(backup_scope=""),
            lambda m: m["artifacts"]["backup"].update(sha256="0" * 64),
            lambda m: m["artifacts"]["backup"].update(sha256="xyz"),
            lambda m: m["artifacts"]["backup"].update(path="../backup"),
            lambda m: m["artifacts"]["backup"].update(path=str(root / "backup")),
            lambda m: m["artifacts"]["backup"].update(path="missing"),
            lambda m: m["artifacts"].update(backup=dict(m["artifacts"]["stock_restore_package"])),
            lambda m: (root / "backup").write_bytes(b""),
            lambda m: (root / "backup").write_bytes(b"corrupted"),
        )
        for mutate in mutations:
            m = filled(); mutate(m); result = inspect(m, root)
            assert not result["inventory_complete"] and not result["flash_authorized"]
        try:
            inspect({"schema": True}, root)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid schema accepted")
    print("16/16 offline synthetic controls passed; no device access")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--template", action="store_true")
    group.add_argument("--self-test", action="store_true")
    group.add_argument("manifest", nargs="?")
    args = p.parse_args()
    if args.self_test:
        self_test(); return 0
    if args.template:
        print(json.dumps(template(), indent=2)); return 0
    try:
        path = Path(args.manifest)
        result = inspect(json.loads(path.read_text(encoding="utf-8")), path.parent)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "HOLD", "inventory_complete": False,
                          "flash_authorized": False, "error": type(exc).__name__}))
        return 2
    print(json.dumps(result, indent=2)); return 0 if result["inventory_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
