# -*- coding: utf-8 -*-
"""
themes.py — theme tagging (spec §1 priority themes) + AI exposure score (spec §7).

AI exposure (0..10):
  10 = core AI infrastructure (the compute/accelerator core)
   9 = AI semiconductors
   8 = AI networking / optics / datacenter picks-and-shovels
   7 = AI cloud infrastructure
   6 = AI software
   5 = AI users (applies AI but isn't an AI company)
   0 = no meaningful AI exposure

We combine a curated ticker map (precise for well-known names) with a
keyword classifier over sector/industry/summary (covers the long tail).
"""

PRIORITY_THEMES = [
    "ai", "semiconductors", "data_centers", "cloud", "cybersecurity",
    "robotics", "defense_tech", "digital_health", "energy_infrastructure",
    "critical_materials", "space",
]

# Curated map: ticker -> (ai_exposure 0..10, [themes])
CURATED = {
    # core AI infra / accelerators
    "NVDA": (10, ["ai", "semiconductors", "data_centers"]),
    "AMD":  (9,  ["ai", "semiconductors", "data_centers"]),
    "AVGO": (9,  ["ai", "semiconductors", "data_centers", "cloud"]),
    "TSM":  (9,  ["ai", "semiconductors"]),
    "ARM":  (9,  ["ai", "semiconductors"]),
    "MRVL": (8,  ["ai", "semiconductors", "data_centers"]),
    "ALAB": (8,  ["ai", "semiconductors", "data_centers"]),
    "CRDO": (8,  ["ai", "semiconductors", "data_centers"]),
    "ANET": (8,  ["ai", "data_centers", "cloud"]),
    "COHR": (8,  ["ai", "semiconductors", "data_centers"]),
    "LITE": (8,  ["ai", "data_centers"]),
    "FN":   (8,  ["ai", "data_centers"]),
    "MU":   (9,  ["ai", "semiconductors", "data_centers"]),
    "VRT":  (8,  ["ai", "data_centers", "energy_infrastructure"]),
    "VICR": (8,  ["ai", "semiconductors", "data_centers", "energy_infrastructure"]),
    "MPWR": (8,  ["ai", "semiconductors", "data_centers"]),
    "ONTO": (8,  ["ai", "semiconductors"]),
    "NBIS": (7,  ["ai", "cloud", "data_centers"]),
    "CRWV": (10, ["ai", "cloud", "data_centers"]),
    "ORCL": (7,  ["ai", "cloud", "data_centers"]),
    "MSFT": (7,  ["ai", "cloud", "cybersecurity"]),
    "GOOGL":(7,  ["ai", "cloud"]),
    "AMZN": (7,  ["ai", "cloud"]),
    "NOW":  (6,  ["ai", "cloud"]),
    "PLTR": (6,  ["ai", "defense_tech"]),
    "SNOW": (6,  ["ai", "cloud"]),
    "MDB":  (6,  ["ai", "cloud"]),
    "DDOG": (6,  ["ai", "cloud", "cybersecurity"]),
    "MNDY": (6,  ["ai", "cloud"]),
    "HUBS": (6,  ["ai", "cloud"]),
    "APP":  (6,  ["ai", "cloud"]),
    "TTWO": (5,  ["ai"]),
    "DLO":  (5,  ["cloud"]),
    # cybersecurity
    "CRWD": (6,  ["cybersecurity", "ai", "cloud"]),
    "PANW": (6,  ["cybersecurity", "ai", "cloud"]),
    "ZS":   (5,  ["cybersecurity", "cloud"]),
    "FTNT": (5,  ["cybersecurity"]),
    "S":    (6,  ["cybersecurity", "ai"]),
    "NET":  (6,  ["cybersecurity", "cloud", "ai"]),
    "TENB": (4,  ["cybersecurity"]),
    "OKTA": (4,  ["cybersecurity", "cloud"]),
    # space / defense
    "RKLB": (3,  ["space", "defense_tech"]),
    "ASTS": (2,  ["space"]),
    "RDW":  (2,  ["space", "defense_tech"]),
    "BWXT": (2,  ["defense_tech", "energy_infrastructure"]),
    "AXON": (5,  ["defense_tech", "ai"]),
    "KTOS": (3,  ["defense_tech"]),
    "LMT":  (3,  ["defense_tech"]),
    # robotics / industrial automation
    "ISRG": (5,  ["robotics", "digital_health"]),
    "TER":  (6,  ["robotics", "semiconductors", "ai"]),
    "ROK":  (4,  ["robotics"]),
    "PATH": (6,  ["robotics", "ai", "cloud"]),
    "SYM":  (6,  ["robotics", "ai"]),
    # digital health
    "TEM":  (7,  ["digital_health", "ai"]),
    "HIMS": (3,  ["digital_health"]),
    "DOCS": (5,  ["digital_health", "ai"]),
    "VEEV": (4,  ["digital_health", "cloud"]),
    "DXCM": (2,  ["digital_health"]),
    "PODD": (2,  ["digital_health"]),
    "KRYS": (0,  ["digital_health"]),
    "ALNY": (0,  ["digital_health"]),
    # energy infrastructure / power for AI
    "GEV":  (4,  ["energy_infrastructure", "ai"]),
    "OKLO": (3,  ["energy_infrastructure"]),
    "SMR":  (3,  ["energy_infrastructure"]),
    "CEG":  (4,  ["energy_infrastructure", "ai"]),
    "VST":  (4,  ["energy_infrastructure", "ai"]),
    "ETN":  (5,  ["energy_infrastructure", "ai", "data_centers"]),
    "POWL": (4,  ["energy_infrastructure", "data_centers"]),
    "NXT":  (2,  ["energy_infrastructure"]),
    "FSLR": (2,  ["energy_infrastructure"]),
    "ENPH": (2,  ["energy_infrastructure"]),
    # critical materials
    "MP":   (1,  ["critical_materials"]),
    "ALB":  (1,  ["critical_materials"]),
    "FCX":  (1,  ["critical_materials"]),
    "UEC":  (1,  ["critical_materials", "energy_infrastructure"]),
}

# Keyword classifier — (theme, [keywords])
_KW = {
    "ai": ["artificial intelligence", "ai", "machine learning", "generative ai",
           "large language", "neural", "inference", "deep learning", "ai model"],
    "semiconductors": ["semiconductor", "chip", "wafer", "foundry", "integrated circuit",
                       "fabless", "memory chip", "logic chip", "asic", "fpga"],
    "data_centers": ["data center", "datacenter", "hyperscale", "server", "interconnect",
                     "optical transceiver", "rack", "colocation"],
    "cloud": ["cloud", "saas", "software as a service", "platform as a service",
              "infrastructure as a service", "subscription software"],
    "cybersecurity": ["cybersecurity", "cyber security", "endpoint security", "firewall",
                      "threat", "zero trust", "identity security", "security platform"],
    "robotics": ["robot", "robotic", "robotics", "automation", "autonomous", "actuator"],
    "defense_tech": ["defense", "defence", "missile", "military", "warfare", "weapon"],
    "digital_health": ["digital health", "telehealth", "medical device", "diagnostic",
                       "genomic", "health platform", "biotech", "therapeutic", "medtech"],
    "energy_infrastructure": ["power grid", "electrical equipment", "nuclear", "utility",
                              "energy infrastructure", "transmission", "solar", "battery storage"],
    "critical_materials": ["rare earth", "lithium", "copper", "uranium", "critical mineral",
                           "mining", "specialty material"],
    # NOTE: bare "space" matches "living space"/"retail space" — require specific terms
    "space": ["satellite", "launch vehicle", "orbital", "aerospace", "spacecraft",
              "space exploration", "low earth orbit", "space technology"],
}

# AI exposure floor by theme presence when ticker isn't curated
_THEME_AI_FLOOR = {
    "semiconductors": 7, "data_centers": 7, "cloud": 6, "cybersecurity": 5,
    "robotics": 5, "ai": 6, "defense_tech": 2, "digital_health": 2,
    "energy_infrastructure": 2, "critical_materials": 1, "space": 1,
}

import re


def _has(blob, kw):
    """Word-boundary match with optional trailing plural 's'.
    Leading boundary blocks 'retail'->'ai'; trailing 's?' keeps 'medical device'->
    'medical devices', 'semiconductor'->'semiconductors', 'diagnostic'->'diagnostics'."""
    return re.search(r"(?<![a-z])" + re.escape(kw.lower()) + r"s?(?![a-z])", blob) is not None


# Cyclical / commodity-driven names: their booming numbers track commodity prices
# (gold, oil, memory-chip prices), NOT durable secular demand. Flagged so they are
# not ranked as compounders/accelerators/future-leaders (a real fix — gold spiking
# in a crisis is a HEDGE, not a growth compounder).
_CYCLICAL_SECTORS = {"basic materials", "energy"}
# industry/name keywords for cyclical businesses across sectors (autos, airlines,
# homebuilders, shipping, oil-services, banks, steel, chemicals, etc.)
_CYCLICAL_KW = ["gold", "silver", "mining", "miner", "metals", "oil", "gas", "coal",
                "copper", "steel", "aluminum", "uranium", "fertilizer", "commodity",
                "chemicals", "paper", "lumber", "airline", "airlines",
                "auto manufacturer", "auto parts", "automotive", "homebuilder",
                "residential construction", "building materials", "cruise",
                "shipping", "marine", "trucking", "freight", "drilling", "refining",
                "oil & gas equipment", "semiconductor equipment", "bank", "banks",
                "capital markets", "consumer finance"]
_CYCLICAL_TICKERS = {"MU", "STX", "WDC", "SNDK"}   # memory/storage = price-cycle driven


def is_cyclical(rec):
    sym = rec.get("ticker", "").upper()
    if sym in _CYCLICAL_TICKERS:
        return True
    sector = str(rec.get("sector") or "").lower()
    if sector in _CYCLICAL_SECTORS:
        return True
    blob = " ".join(str(rec.get(k) or "").lower() for k in ("industry", "name"))
    return any(_has(blob, k) for k in _CYCLICAL_KW)


def classify(rec):
    """Set rec['themes'], rec['primary_theme'], rec['ai_exposure_score'], rec['cyclical']."""
    rec["cyclical"] = is_cyclical(rec)
    sym = rec.get("ticker", "").upper()
    if sym in CURATED:
        ai, themes = CURATED[sym]
        rec["ai_exposure_score"] = ai
        rec["themes"] = list(themes)
        rec["primary_theme"] = themes[0] if themes else None
        return rec

    blob = " ".join(str(rec.get(k) or "").lower()
                    for k in ("sector", "industry", "summary", "name"))
    themes = []
    for theme, kws in _KW.items():
        if any(_has(blob, k) for k in kws):
            themes.append(theme)

    ai = 6 if (_has(blob, "ai") or "artificial intelligence" in blob or "machine learning" in blob) else 0
    for th in themes:
        if th in ("semiconductors", "data_centers", "cloud", "cybersecurity", "robotics", "ai"):
            ai = max(ai, _THEME_AI_FLOOR.get(th, 0))
    rec["ai_exposure_score"] = min(10, ai)
    rec["themes"] = themes
    rec["primary_theme"] = themes[0] if themes else None
    return rec


def theme_bonus(rec, cfg):
    """Small bonus for priority-theme exposure, capped by config."""
    tw = cfg.get("theme_weights", {}) or {}
    cap = cfg.get("theme_bonus_max", 6)
    if not rec.get("themes"):
        return 0.0
    best = max((tw.get(t, 0.0) for t in rec["themes"]), default=0.0)
    # AI exposure scales the bonus
    ai_scale = (rec.get("ai_exposure_score", 0) or 0) / 10.0
    bonus = cap * best * (0.4 + 0.6 * ai_scale)
    return round(min(cap, bonus), 2)
