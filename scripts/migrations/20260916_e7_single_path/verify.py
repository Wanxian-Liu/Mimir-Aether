#!/usr/bin/env python3
"""E7 迁移复现闸：现行 home 脚本 sha256 必须等于 MANIFEST 记录的 post_sha256；审计 writer 面必须为 0。"""
import json, hashlib, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
M = json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))
HOME = pathlib.Path("/home/rayliu/.mimiraether")
bad = []
for f in M["files"]:
    if "post_sha256" not in f:
        continue
    p = HOME / "scripts" / f["name"]
    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"
    if got != f["post_sha256"]:
        bad.append((f["name"], f["post_sha256"][:12], got[:12]))
print(f"sha256 比对：{len([f for f in M['files'] if 'post_sha256' in f]) - len(bad)} 件一致 / {len(bad)} 件漂移")
for b in bad:
    print("  DRIFT", b)
r = subprocess.run([str(pathlib.Path("/home/rayliu/src/MimirAether/.venv/bin/python3")),
                    "scripts/audit_send_paths.py"], cwd="/home/rayliu/src/MimirAether",
                   capture_output=True, text=True)
out = r.stdout
ok_audit = "VERDICT: PASS" in out
print("审计 writer 面 = 0 ?", ok_audit)
sys.exit(0 if (not bad and ok_audit) else 1)
