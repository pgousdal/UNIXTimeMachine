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
