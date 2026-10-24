"""Download, caching and loading. No cleaning logic here (see utils/prep.py)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config as C

LICENCE_TEXT = (
    "Data: Licence Ouverte / Open Licence 2.0 (Etalab) for the IRVE file, the Insee "
    "population figures and the Agence ORE vehicle counts. Département and région "
    "contours: ODbL 1.0 (data.gouv.fr, from IGN Admin Express). Code: MIT."
)

MANIFEST = C.RAW_DIR / "manifest.json"


# ---- download side (used by data/fetch_data.py) ---------------------------

def resolve_resource(slug: str, title_contains: str, fmt: str | None) -> dict:
    """Ask the data.gouv.fr API for the dataset and pick one resource.

    The IRVE file is regenerated daily under a new URL, so the URL is never
    hardcoded: it is read from the dataset's current resource list.
    """
    import requests
    r = requests.get(C.DATAGOUV_API.format(slug=slug), timeout=60)
    r.raise_for_status()
    ds = r.json()
    for res in ds["resources"]:
        if title_contains.lower() in res["title"].lower() and (fmt is None or (res.get("format") or "").lower() == fmt):
            return {"dataset_title": ds["title"], "dataset_page": ds["page"], "dataset_slug": ds["slug"],
                    "licence": ds.get("license"), "resource_title": res["title"], "url": res["url"],
                    "resource_id": res["id"], "last_modified": res.get("last_modified"),
                    "filesize": res.get("filesize")}
    raise LookupError(f"No resource matching '{title_contains}' in dataset {slug}")


def fetch_and_cache(key: str, force: bool = False) -> Path:
    """Download one source into data/raw unless the cached copy is current.

    A cached file is reused when the manifest shows the same resource URL and
    last_modified stamp as the API currently reports.
    """
    import requests
    spec = C.SOURCES[key]
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    meta = resolve_resource(spec["slug"], spec["title_contains"], spec["format"])
    path = C.RAW_DIR / spec["filename"]
    prev = manifest.get(key, {})
    if (not force and path.exists() and prev.get("url") == meta["url"]
            and prev.get("last_modified") == meta["last_modified"]):
        print(f"[cache] {key}: {path.name} is current ({meta['last_modified']})")
        return path
    print(f"[download] {key}: {meta['url']}")
    with requests.get(meta["url"], stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = path.with_suffix(path.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(path)
    meta["downloaded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta["bytes"] = path.stat().st_size
    manifest[key] = meta
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


def read_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


# ---- app side --------------------------------------------------------------

def load_tables() -> dict:
    """Load the processed tables written by data/fetch_data.py."""
    p = C.PROCESSED_DIR
    missing = [f for f in ["points.parquet", "departements.parquet", "ev_by_dep.parquet",
                           "quality.json", "departements_map.geojson"] if not (p / f).exists()]
    if missing:
        raise FileNotFoundError(
            "Processed data not found: " + ", ".join(missing)
            + ". Run `python data/fetch_data.py` first.")
    return {
        "points": pd.read_parquet(p / "points.parquet"),
        "deps": pd.read_parquet(p / "departements.parquet"),
        "ev": pd.read_parquet(p / "ev_by_dep.parquet"),
        "quality": json.loads((p / "quality.json").read_text(encoding="utf-8")),
        "geojson": json.loads((p / "departements_map.geojson").read_text(encoding="utf-8")),
    }
