#!/usr/bin/env python3
from collections import defaultdict
from manifestlib import system_manifests
def main():
    g=defaultdict(list)
    for _,d in system_manifests(): g[d["track"]].append(d)
    print("UNIX TIME MACHINE\n=================")
    for key,label in [("unix","UNIX"),("unixish","UNIXISH"),("beyond-unix","BEYOND UNIX")]:
        print(f"\n{label}\n{'-'*len(label)}")
        rows=sorted(g[key], key=lambda x:(x["year"],x["name"]))
        if not rows: print("  (no implemented systems yet)")
        for d in rows:
            print(f"  {d['year']}  {d['short_name']:<18} {d['machine']['model']:<18} [{d['status']}]")
    return 0
if __name__ == "__main__": raise SystemExit(main())
