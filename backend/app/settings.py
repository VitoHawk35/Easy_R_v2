"""Runtime path settings for the EasyR backend."""
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DATA_DIR = os.path.join(_BACKEND_DIR, "data")

DATA_DIR = os.getenv("EASYR_DATA_DIR", _DEFAULT_DATA_DIR)
DEMO_DATA_PATH = os.getenv("EASYR_DEMO_PATH", os.path.join(_DEFAULT_DATA_DIR, "demo.csv"))
