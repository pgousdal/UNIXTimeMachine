from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
SYSTEMS_DIR = ROOT / "systems"
INVENTORY_DIR = ROOT / "inventory"
def load_yaml(path):
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict): raise ValueError(f"{path}: top-level YAML must be a mapping")
    return data
def system_manifests():
    return [(p, load_yaml(p)) for p in sorted(SYSTEMS_DIR.glob("*/system.yml"))]

def system_manifest(system_id):
    if not isinstance(system_id, str) or not system_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in system_id):
        raise ValueError(f"unsafe system id: {system_id!r}")
    path = SYSTEMS_DIR / system_id / "system.yml"
    if not path.is_file():
        raise ValueError(f"unknown system: {system_id}")
    data = load_yaml(path)
    if data.get("id") != system_id:
        raise ValueError(f"{path}: id does not match directory")
    return path, data
