#!/usr/bin/env python3
import re, sys
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
            media=data.get("media",{})
            if media.get("policy") != "external": raise ValueError(f"{path}: media.policy must be external")
            for item in media.get("items",[]):
                for key in ("logical_name","filenames","required"):
                    if key not in item: raise ValueError(f"{path}: media item missing {key}")
                if not isinstance(item["filenames"],list) or not item["filenames"]: raise ValueError(f"{path}: media filenames must be non-empty list")
                if any(not isinstance(n,str) or "/" in n or "\\" in n or n in (".","..") for n in item["filenames"]): raise ValueError(f"{path}: unsafe media filename")
                if not isinstance(item["required"],bool): raise ValueError(f"{path}: media required must be bool")
                if item.get("size") is not None and (not isinstance(item["size"],int) or item["size"] < 0): raise ValueError(f"{path}: bad media size")
                if item.get("sha256") is not None and not re.fullmatch(r"[0-9a-fA-F]{64}",item["sha256"]): raise ValueError(f"{path}: bad sha256")
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
