#!/usr/bin/env python3
import sys
from manifestlib import INVENTORY_DIR, load_yaml, system_manifests
VALID_TRACKS={"unix","unixish","beyond-unix"}
def main():
    errors=[]; manifests={}
    for path,data in system_manifests():
        try:
            for key in ("id","name","track","year","emulator","session","status"):
                if key not in data: raise ValueError(f"{path}: missing {key}")
            sid=data["id"]
            if path.parent.name != sid: raise ValueError(f"{path}: directory must match id")
            if data["track"] not in VALID_TRACKS: raise ValueError(f"{path}: bad track")
            if not isinstance(data["year"], int): raise ValueError(f"{path}: year must be int")
            if not data["emulator"].get("family"): raise ValueError(f"{path}: emulator.family required")
            if not isinstance(data["session"].get("public_eligible"), bool): raise ValueError(f"{path}: public_eligible bool required")
            manifests[sid]=data
        except Exception as e: errors.append(str(e))
    for p in sorted(INVENTORY_DIR.glob("*.yml")):
        try:
            inv=load_yaml(p); track=inv["track"]
            for sid in inv.get("systems",[]):
                if sid not in manifests: raise ValueError(f"{p}: unknown {sid}")
                if manifests[sid]["track"] != track: raise ValueError(f"{p}: track mismatch for {sid}")
        except Exception as e: errors.append(str(e))
    if errors:
        print("Manifest validation: FAIL", file=sys.stderr)
        [print(" -",e,file=sys.stderr) for e in errors]
        return 1
    print(f"Manifest validation: PASS ({len(manifests)} systems)")
    return 0
if __name__ == "__main__": raise SystemExit(main())
