import importlib.util
import yaml
from pathlib import Path
from robots.base import Robot

def load_robot(robot_dir: Path) -> Robot:
    manifest_path = robot_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.yaml no encontrado en {robot_dir}")

    manifest = yaml.safe_load(manifest_path.read_text())
    strategy_file = robot_dir / "strategy.py"

    spec = importlib.util.spec_from_file_location(
        f"robots.{manifest['name']}", strategy_file
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cls = getattr(mod, manifest["entry_class"])
    instance = cls(**manifest.get("params", {}))
    instance.name = manifest["name"]
    instance.version = manifest["version"]
    instance.magic = manifest["magic"]
    instance.symbols = manifest["symbols"]
    instance.timeframes = manifest["timeframes"]
    instance.broker_compat = manifest.get("broker_compat", ["Generic"])

    return instance

def list_robots(robots_dir: Path) -> list[dict]:
    robots = []
    for d in robots_dir.iterdir():
        if d.is_dir() and (d / "manifest.yaml").exists():
            m = yaml.safe_load((d / "manifest.yaml").read_text())
            robots.append({"name": m["name"], "version": m["version"], "path": str(d)})
    return robots