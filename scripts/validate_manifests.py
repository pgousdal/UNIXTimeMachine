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
                for key in ("logical_name","required"):
                    if key not in item: raise ValueError(f"{path}: media item missing {key}")
                names=item.get("filenames")
                if names is None:
                    if item.get("operator_path") != "explicit": raise ValueError(f"{path}: media item without filenames requires explicit operator path")
                elif not isinstance(names,list) or not names: raise ValueError(f"{path}: media filenames must be non-empty list")
                elif any(not isinstance(n,str) or "/" in n or "\\" in n or n in (".","..") for n in names): raise ValueError(f"{path}: unsafe media filename")
                if not isinstance(item["required"],bool): raise ValueError(f"{path}: media required must be bool")
                if item.get("size") is not None and (not isinstance(item["size"],int) or item["size"] < 0): raise ValueError(f"{path}: bad media size")
                if item.get("sha256") is not None and not re.fullmatch(r"[0-9a-fA-F]{64}",item["sha256"]): raise ValueError(f"{path}: bad sha256")
                if item.get("sha1") is not None and not re.fullmatch(r"[0-9a-fA-F]{40}",item["sha1"]): raise ValueError(f"{path}: bad sha1")
                bootstrap_copy=item.get("bootstrap_copy_filename")
                if bootstrap_copy is not None and (not isinstance(bootstrap_copy,str) or not bootstrap_copy or "/" in bootstrap_copy or "\\" in bootstrap_copy or bootstrap_copy in (".","..")): raise ValueError(f"{path}: unsafe bootstrap copy filename")
                if bootstrap_copy is not None and not item.get("install_token"): raise ValueError(f"{path}: bootstrap copy requires install_token")
            prepared=data.get("prepared")
            disks=prepared.get("disks",[]) if prepared is not None else []
            if prepared is not None and (not isinstance(disks,list) or not disks): raise ValueError(f"{path}: prepared.disks must be a non-empty list")
            seen_ids=set(); seen_units=set(); seen_files=set(); seen_tokens=set()
            for disk in disks:
                for key in ("id","unit","device","golden_filename","session_filename","runtime_token"):
                    if not isinstance(disk.get(key),str) or not disk[key]: raise ValueError(f"{path}: prepared disk missing {key}")
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*",disk["id"]): raise ValueError(f"{path}: unsafe disk id")
                if not re.fullmatch(r"(?:RP[0-7]|RQ[0-3])",disk["unit"]): raise ValueError(f"{path}: unsupported disk unit")
                if not re.fullmatch(r"@[A-Z0-9_]+@",disk["runtime_token"]): raise ValueError(f"{path}: bad runtime token")
                if any("/" in disk[k] or "\\" in disk[k] for k in ("golden_filename","session_filename")): raise ValueError(f"{path}: unsafe disk filename")
                if disk["id"] in seen_ids or disk["unit"] in seen_units or disk["runtime_token"] in seen_tokens: raise ValueError(f"{path}: duplicate prepared disk identity")
                if disk["golden_filename"] in seen_files or disk["session_filename"] in seen_files: raise ValueError(f"{path}: duplicate prepared disk filename")
                seen_ids.add(disk["id"]); seen_units.add(disk["unit"]); seen_tokens.add(disk["runtime_token"])
                seen_files.update((disk["golden_filename"],disk["session_filename"]))
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
