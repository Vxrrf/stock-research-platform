# -*- coding: utf-8 -*-
"""
config_loader.py — load config.yaml + external_lists.yaml once, expose CFG.

Resolution order for the FMP key: config.yaml `data.fmp_api_key`, else the
FMP_API_KEY environment variable. Everything else comes from config.yaml with
safe fallbacks so a partially-edited config never crashes a run.
"""

import os
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)                      # mazer-system/
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
LOCAL_CONFIG_PATH = os.path.join(ROOT, "config.local.yaml")   # git-ignored secrets/overrides
EXTERNAL_LISTS_PATH = os.path.join(ROOT, "data", "external_lists.yaml")
HALAL_OVERRIDES_PATH = os.path.join(ROOT, "data", "halal_overrides.yaml")


def _deep_merge(base, over):
    """Recursively merge `over` into `base` (over wins)."""
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _load_yaml(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or (default if default is not None else {})
    except FileNotFoundError:
        return default if default is not None else {}
    except Exception as e:  # corrupt yaml shouldn't kill the run
        print(f"⚠️  could not parse {os.path.basename(path)}: {e}")
        return default if default is not None else {}


def load_config():
    cfg = _load_yaml(CONFIG_PATH, default={})
    # git-ignored local overrides (real secrets live here, not in config.yaml)
    local = _load_yaml(LOCAL_CONFIG_PATH, default={})
    if local:
        _deep_merge(cfg, local)
    # FMP key resolution priority: env var > config.local.yaml > config.yaml
    key = os.environ.get("FMP_API_KEY", "") or (cfg.get("data", {}) or {}).get("fmp_api_key") or ""
    cfg.setdefault("data", {})["fmp_api_key"] = key.strip()
    cfg["_root"] = ROOT
    return cfg


def load_external_lists():
    """Returns dict: list_name -> set(upper tickers)."""
    raw = _load_yaml(EXTERNAL_LISTS_PATH, default={})
    out = {}
    for name, items in (raw or {}).items():
        if isinstance(items, list):
            out[name] = {str(t).strip().upper() for t in items if str(t).strip()}
        else:
            out[name] = set()
    return out


def load_halal_overrides():
    """Your manual Zoya/Musaffa verdicts → {TICKER: {status, source, note}}.
    These OVERRIDE the automatic screen (you verified it yourself)."""
    raw = _load_yaml(HALAL_OVERRIDES_PATH, default={}) or {}
    ov = raw.get("overrides") or {}
    out = {}
    for sym, v in ov.items():
        if not isinstance(v, dict):
            continue
        st = str(v.get("status") or "").strip().lower()
        if st not in ("pass", "fail", "unknown"):
            continue
        out[str(sym).strip().upper()] = {
            "status": st,
            "source": str(v.get("source") or "manual").strip(),
            "note": str(v.get("note") or "").strip(),
        }
    return out


def output_dir(cfg):
    d = os.path.join(ROOT, (cfg.get("output", {}) or {}).get("dir", "output"))
    os.makedirs(d, exist_ok=True)
    return d


def state_dir(cfg):
    d = os.path.join(ROOT, "data", "_state")
    os.makedirs(d, exist_ok=True)
    return d


# convenience getter with dotted path + default
def cfg_get(cfg, dotted, default=None):
    node = cfg
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


CFG = load_config()
