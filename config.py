"""Every constant the pipeline and the app depend on lives here.

Change a threshold here and rerun `python data/fetch_data.py` to rebuild the
processed tables; the app reads the same values for its labels.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # large downloads, git-ignored
PROCESSED_DIR = DATA_DIR / "processed"  # small parquet/json files, committed
SOURCES_MD = DATA_DIR / "SOURCES.md"

DATAGOUV_API = "https://www.data.gouv.fr/api/1/datasets/{slug}/"

# Each source is resolved through the data.gouv.fr API at download time, so a
# regenerated file (new URL, new date in its name) is picked up automatically.
# `title_contains` / `format` select one resource among those listed.
SOURCES = {
    "irve": {
        "slug": "fichier-consolide-des-bornes-de-recharge-pour-vehicules-electriques",
        "title_contains": "dernière version",
        "format": "csv",
        "filename": "irve.csv",
        "label": "Base nationale des IRVE (consolidated static file, schema etalab/schema-irve-statique)",
        "publisher": "data.gouv.fr (Etalab / DINUM)",
    },
    "ev": {
        "slug": "voitures-particulieres-immatriculees-par-commune-et-par-type-de-recharge-jeu-de-donnees-aaadata",
        "title_contains": "Fichier csv",
        "format": "csv",
        "filename": "ev.csv",
        "label": "Voitures particulières immatriculées par commune et par type de recharge",
        "publisher": "Agence ORE, built from the SDES vehicle register (RSVERO)",
    },
    "population": {
        "slug": "populations-de-reference",
        "title_contains": "Populations de référence",
        "format": None,
        "filename": "population.zip",
        "label": "Populations de référence 2023 (populations légales, in force on 1 January 2026)",
        "publisher": "Insee",
    },
    "departements_fine": {
        "slug": "contours-administratifs",
        "title_contains": "Départements 2025 100m (format GeoJSON)",
        "format": None,
        "filename": "departements-100m.geojson",
        "label": "Contours administratifs: départements 2025, 100 m generalisation (used for point-in-polygon)",
        "publisher": "data.gouv.fr (Etalab), from IGN Admin Express",
    },
    "departements_map": {
        "slug": "contours-administratifs",
        "title_contains": "Départements 2025 1000m (format GeoJSON)",
        "format": None,
        "filename": "departements-1000m.geojson",
        "label": "Contours administratifs: départements 2025, 1000 m generalisation (used for the choropleth)",
        "publisher": "data.gouv.fr (Etalab), from IGN Admin Express",
    },
    "regions": {
        "slug": "contours-administratifs",
        "title_contains": "Régions 2025 1000m (format GeoJSON)",
        "format": None,
        "filename": "regions-1000m.geojson",
        "label": "Contours administratifs: régions 2025 (used for region names)",
        "publisher": "data.gouv.fr (Etalab), from IGN Admin Express",
    },
}

# ---- Cleaning thresholds -------------------------------------------------
# Schema says puissance_nominale is in kW. Values at or above this are read as
# watts and divided by 1000 (22000 -> 22 kW, 160000 -> 160 kW).
WATT_THRESHOLD = 1000
# A value of 0 kW cannot be a working charging point: treated as unknown power.
POWER_MIN_KW = 0.5
# Above this a value is kept (it is still ultra-fast) but flagged as suspicious.
POWER_SUSPICIOUS_KW = 400

# Power classes in kW. 22 kW AC wallboxes belong to "normal", so the upper
# edge of "normal" is inclusive and "fast" starts strictly above 22 kW.
SLOW_MAX = 7.4      # slow:       power < 7.4
NORMAL_MAX = 22.0   # normal:     7.4 <= power <= 22
FAST_MAX = 150.0    # fast:       22 < power < 150 ; ultra-fast: power >= 150
POWER_CLASSES = ["Slow (<7.4 kW)", "Normal (7.4-22 kW)", "Fast (22-150 kW)", "Ultra-fast (≥150 kW)"]
UNKNOWN_POWER = "Unknown power"
FAST_CLASSES = POWER_CLASSES[2:]

# Commissioning dates outside this window are treated as missing.
DATE_MIN = "2010-01-01"   # first public IRVE in France date from the early 2010s

# Bounding boxes used to reject impossible coordinates before point-in-polygon.
FRANCE_BBOXES = [
    (-5.5, 41.0, 10.0, 51.5),     # metropolitan France and Corsica
    (-62.0, 15.8, -60.9, 16.6),   # Guadeloupe
    (-61.3, 14.3, -60.7, 15.0),   # Martinique
    (-54.7, 2.0, -51.5, 6.0),     # Guyane
    (55.1, -21.5, 55.9, -20.8),   # La Réunion
    (44.9, -13.1, 45.4, -12.5),   # Mayotte
]

# Operators: names are upper-cased, the roaming suffix "| FR*XXX" is removed,
# then these aliases merge obvious variants of the same company.
OPERATOR_ALIASES = {
    "TOTALENERGIES CHARGING SERVICES": "TOTALENERGIES",
    "TOTALENERGIES MARKETING FRANCE": "TOTALENERGIES",
    "GREENFLUX ASSETS B.V.": "GREENFLUX",
    "DRIVECO PARTNER NETWORK": "DRIVECO",
    "TESLA FRANCE SARL": "TESLA",
    "LIDL FRANCE": "LIDL",
    "ALDI SARL": "ALDI",
    "GROUPE INDIGO": "INDIGO",
}
TOP_N_OPERATORS = 12
OTHER_OPERATORS = "Other operators"
UNKNOWN_OPERATOR = "Not declared"

# ---- App constants ---------------------------------------------------------
SEED = 42
MAP_POINT_SAMPLE = 12000          # points drawn on the station map
MIN_STOCK_FOR_GROWTH = 50         # below this, growth % is not shown
DEFAULT_START_YEAR = 2023      # convergence is measured from the end of 2022
RANK_N = 10                       # top/bottom départements in the ranking chart

# Population density bands (inhabitants per km²). The edges sit close to the
# terciles of the 100 départements (60 and 134 inh./km²), rounded.
DENSITY_BINS = [0, 60, 150, float("inf")]
DENSITY_LABELS = ["Rural (<60 inh./km²)", "Intermediate (60-150)", "Dense (>150 inh./km²)"]
QUARTILE_LABELS = ["Least equipped quarter", "Second quarter", "Third quarter", "Best equipped quarter"]

# Indicators offered for the map and the ranking. (column, label, unit, format)
INDICATORS = {
    "per_100k": ("Charging points per 100,000 inhabitants", "points per 100k inh.", "{:,.0f}"),
    "fast_per_100k": ("Fast and ultra-fast points per 100,000 inhabitants", "points per 100k inh.", "{:,.0f}"),
    "per_100_ev": ("Charging points per 100 rechargeable cars", "points per 100 cars", "{:,.1f}"),
    "kw_per_ev": ("Public charging power per rechargeable car", "kW per car", "{:,.2f}"),
    "fast_share": ("Share of fast and ultra-fast points", "% of points", "{:,.0f}"),
    "added_per_100k": ("Points commissioned in the period per 100,000 inhabitants", "points per 100k inh.", "{:,.0f}"),
    "points": ("Charging points", "points", "{:,.0f}"),
}

# Policy milestones drawn on the deployment timeline. All checked against
# official or primary sources (links shown in the app caption).
POLICY_EVENTS = [
    {"date": "2019-12-24", "label": "LOM mobility law",
     "detail": "Loi n° 2019-1428 d'orientation des mobilités: creates local IRVE master plans (SDIRVE)",
     "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000039666574"},
    {"date": "2021-05-04", "label": "Open-data duty",
     "detail": "Arrêté du 4 mai 2021: operators must publish IRVE data on data.gouv.fr",
     "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043475441"},
    {"date": "2023-05-05", "label": "100,000 public points (national count)",
     "detail": "Avere-France / ministry barometer announces the 100,000 target reached",
     "url": "https://www.avere-france.org/wp-content/uploads/2023/05/CP-100-000-points-de-recharge.pdf"},
    {"date": "2024-04-13", "label": "EU AFIR applies",
     "detail": "Regulation (EU) 2023/1804: fast-charging pools along the TEN-T network",
     "url": "https://eur-lex.europa.eu/eli/reg/2023/1804/oj"},
]

# AFIR fleet-based targets (art. 3): 1.3 kW of public power per battery car,
# 0.8 kW per plug-in hybrid. The EV count used here mixes both, so the app
# shows the range as a reference band, not a pass/fail line.
AFIR_KW_PER_PHEV = 0.8
AFIR_KW_PER_BEV = 1.3

# ---- Palette (validated: ordinal, single hue, colorblind-safe) -------------
POWER_COLORS = dict(zip(POWER_CLASSES, ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]))
POWER_COLORS[UNKNOWN_POWER] = "#a3a29c"
ACCENT = "#2a78d6"
ACCENT_2 = "#eb6834"      # second categorical slot, used for "France average" marks
MUTED = "#52514e"
PERIOD_SHADE = "#86b6ef"   # background band for the selected period on the timeline
SEQUENTIAL_SCALE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
