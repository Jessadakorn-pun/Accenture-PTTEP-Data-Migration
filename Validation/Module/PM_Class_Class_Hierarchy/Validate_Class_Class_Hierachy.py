import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_MODULE_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_MODULE_DIR, "..", ".."))

sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from main import run_validation

if __name__ == "__main__":
    # THMM
    config_path_THMM = os.path.join(_MODULE_DIR, "Config-THMM.yaml")
    run_validation(config_path_THMM)
    
    # MY
    config_path_MY = os.path.join(_MODULE_DIR, "Config-MY.yaml")
    run_validation(config_path_MY)

    # DCT
    # config_path_DCT = os.path.join(_MODULE_DIR, "Config-DCT.yaml")
    # run_validation(config_path_DCT)
