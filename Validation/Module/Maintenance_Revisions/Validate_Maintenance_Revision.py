import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_MODULE_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_MODULE_DIR, "..", ".."))

sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from main import run_validation

if __name__ == "__main__":
    config_path = os.path.join(_MODULE_DIR, "Config.yaml")
    run_validation(config_path)
