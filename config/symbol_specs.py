"""
symbol_specs.py — Per-symbol risk and execution parameters.
Add new symbols here before trading them. Never hardcode these inline.
"""

SYMBOL_SPECS: dict[str, dict] = {
    "XAUUSD": {
        "max_spread":          35,      # points
        "sl_atr_mult":         1.2,
        "point_value_per_lot": 100.0,   # USD per lot per point
        "min_lot":             0.01,
        "max_lot":             5.0,
        "lot_step":            0.01,
        "corr_basket":         "metals",
    },
    "XAGUSD": {
        "max_spread":          50,
        "sl_atr_mult":         1.3,
        "point_value_per_lot": 50.0,
        "min_lot":             0.01,
        "max_lot":             5.0,
        "lot_step":            0.01,
        "corr_basket":         "metals",
    },
    "NAS100": {
        "max_spread":          120,
        "sl_atr_mult":         1.5,
        "point_value_per_lot": 1.0,
        "min_lot":             0.1,
        "max_lot":             5.0,
        "lot_step":            0.1,
        "corr_basket":         "tech_indices",
    },
    "US30": {
        "max_spread":          200,
        "sl_atr_mult":         1.5,
        "point_value_per_lot": 1.0,
        "min_lot":             0.1,
        "max_lot":             5.0,
        "lot_step":            0.1,
        "corr_basket":         "tech_indices",
    },
    "EURUSD": {
        "max_spread":          12,
        "sl_atr_mult":         1.0,
        "point_value_per_lot": 10.0,
        "min_lot":             0.01,
        "max_lot":             10.0,
        "lot_step":            0.01,
        "corr_basket":         "eur_pairs",
    },
    "GBPUSD": {
        "max_spread":          15,
        "sl_atr_mult":         1.1,
        "point_value_per_lot": 10.0,
        "min_lot":             0.01,
        "max_lot":             10.0,
        "lot_step":            0.01,
        "corr_basket":         "gbp_pairs",
    },
    "USDJPY": {
        "max_spread":          15,
        "sl_atr_mult":         1.0,
        "point_value_per_lot": 7.5,   # approximate; depends on USDJPY rate
        "min_lot":             0.01,
        "max_lot":             10.0,
        "lot_step":            0.01,
        "corr_basket":         "usd_pairs",
    },
    "GBPJPY": {
        "max_spread":          25,
        "sl_atr_mult":         1.3,
        "point_value_per_lot": 7.5,
        "min_lot":             0.01,
        "max_lot":             5.0,
        "lot_step":            0.01,
        "corr_basket":         "gbp_pairs",
    },
    "AUDUSD": {
        "max_spread":          14,
        "sl_atr_mult":         1.0,
        "point_value_per_lot": 10.0,
        "min_lot":             0.01,
        "max_lot":             10.0,
        "lot_step":            0.01,
        "corr_basket":         "commodity_pairs",
    },
}

# Correlated baskets — enforce max 1 open trade per basket
CORRELATED_BASKETS = {
    "metals":         ["XAUUSD", "XAGUSD"],
    "tech_indices":   ["NAS100", "US30"],
    "eur_pairs":      ["EURUSD"],
    "gbp_pairs":      ["GBPUSD", "GBPJPY"],
    "usd_pairs":      ["USDJPY"],
    "commodity_pairs":["AUDUSD"],
}

# Sessions with allowed start/end in UTC hours
SESSIONS = {
    "Sydney":   {"start": 21, "end": 6},   # wraps midnight
    "Tokyo":    {"start": 0,  "end": 9},
    "London":   {"start": 7,  "end": 16},
    "NewYork":  {"start": 12, "end": 21},
}

# High-impact blackout window (minutes before event)
PRE_EVENT_BLACKOUT_MIN = 1
