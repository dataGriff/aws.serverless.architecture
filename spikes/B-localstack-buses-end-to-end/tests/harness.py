"""Spike B's harness is platform_testing (platform/platform_testing), pointed at this spike's Terraform env and
at Spike A's catalog. Everything the tests import from `harness` comes from there."""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PLATFORM_STATE_DIR", str(_ROOT))
os.environ.setdefault("PLATFORM_TF_DIR", str(_ROOT / "terraform" / "envs" / "local"))
os.environ.setdefault("PLATFORM_CATALOG", str(_ROOT.parent / "A-catalog-source-of-truth" / "catalog"))
sys.path.insert(0, str(_ROOT.parents[1] / "platform"))

from platform_testing import *  # noqa: E402,F401,F403
from platform_testing import _cfg, _find, _globs, _partition, _tf_output  # noqa: E402,F401
