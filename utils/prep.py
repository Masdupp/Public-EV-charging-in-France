"""Cleaning, feature engineering and aggregation.

Two halves:
* build_* functions run once in data/fetch_data.py on the raw downloads and
  produce the small tables written to data/processed/.
* filter_points / aggregate_* functions run in the app on those tables.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

import config as C

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dep_from_insee(code: pd.Series) -> pd.Series:
    """Département code from an INSEE commune code (5 characters).

    Overseas codes start with 97 and use three characters. Codes starting with
    "20" are Corsican postal codes typed in place of INSEE codes (2A/2B), so
    they cannot be resolved and return NaN.
    """
    code = code.astype("string").str.strip().str.upper()
    valid = code.str.fullmatch(r"(\d{5}|2[AB]\d{3})")
    dep = code.str[:2].where(~code.str.startswith("97"), code.str[:3])
    dep = dep.where(valid & (dep != "20"))
    return dep


def power_class(kw: pd.Series) -> pd.Series:
    out = pd.Series(C.UNKNOWN_POWER, index=kw.index, dtype="object")
    out[kw < C.SLOW_MAX] = C.POWER_CLASSES[0]
    out[(kw >= C.SLOW_MAX) & (kw <= C.NORMAL_MAX)] = C.POWER_CLASSES[1]
    out[(kw > C.NORMAL_MAX) & (kw < C.FAST_MAX)] = C.POWER_CLASSES[2]
    out[kw >= C.FAST_MAX] = C.POWER_CLASSES[3]
    out[kw.isna()] = C.UNKNOWN_POWER
    return pd.Categorical(out, categories=C.POWER_CLASSES + [C.UNKNOWN_POWER], ordered=True)


def clean_operator(name: pd.Series) -> pd.Series:
    s = name.astype("string").str.replace(r"\s*\|.*$", "", regex=True).str.strip().str.upper()
    s = s.replace(C.OPERATOR_ALIASES)
    return s.fillna(C.UNKNOWN_OPERATOR).replace("", C.UNKNOWN_OPERATOR)


_MOJIBAKE = {"ŕ": "à", "ā": "à", "\x88": "à", "\x8e": "é", "\x8f": "è"}
IMPLANTATION_EN = {
    "Voirie": "On-street",
    "Parking public": "Public car park",
    "Parking privé à usage public": "Private car park open to the public",
    "Parking privé réservé à la clientèle": "Customer-only car park",
    "Station dédiée à la recharge rapide": "Dedicated fast-charging station",
}


def clean_implantation(s: pd.Series) -> pd.Series:
    s = s.astype("string")
    for bad, good in _MOJIBAKE.items():
        s = s.str.replace(bad, good, regex=False)
    return s.map(IMPLANTATION_EN).fillna("Not declared")


def _area_km2(geom) -> float:
    """Approximate area of a lon/lat polygon: equirectangular scaling at its
    centroid latitude. Error stays under 1% at département size."""
    lat = geom.centroid.y
    kx = 111.320 * math.cos(math.radians(lat))
    ky = 110.574
    return geom.area * kx * ky


# ---------------------------------------------------------------------------
# Build step (offline)
# ---------------------------------------------------------------------------

def load_dep_shapes(geojson_path):
    from shapely.geometry import shape
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    rows = []
    for ft in gj["features"]:
        p = ft["properties"]
        rows.append({"dep": p["code"], "dep_name": p["nom"], "reg": p.get("region"),
                     "geometry": shape(ft["geometry"])})
    return pd.DataFrame(rows)


def assign_dep_spatial(lon: np.ndarray, lat: np.ndarray, shapes: pd.DataFrame) -> pd.Series:
    """Point-in-polygon lookup of each coordinate in the département shapes."""
    import shapely
    pts = shapely.points(lon, lat)
    tree = shapely.STRtree(shapes["geometry"].values)
    idx_pt, idx_poly = tree.query(pts, predicate="within")
    out = np.full(len(pts), None, dtype=object)
    out[idx_pt] = shapes["dep"].values[idx_poly]
    return pd.Series(out, dtype="string")


def in_france_bbox(lon: pd.Series, lat: pd.Series) -> pd.Series:
    ok = pd.Series(False, index=lon.index)
    for x0, y0, x1, y1 in C.FRANCE_BBOXES:
        ok |= lon.between(x0, x1) & lat.between(y0, y1)
    return ok


def build_points(raw: pd.DataFrame, shapes: pd.DataFrame, scope_deps: set, today: str):
    """Clean the raw IRVE table. Returns (points, quality) where quality holds
    every count shown in the data quality section of the app."""
    q: dict = {"raw_rows": int(len(raw)), "raw_columns": int(raw.shape[1]), "steps": []}
    blank = raw.apply(lambda s: s.isna() | s.astype("string").str.strip().eq(""))
    q["missing_share"] = {c: round(float(v), 4) for c, v in blank.mean().items()}

    df = raw.copy()
    df["date_maj_ts"] = pd.to_datetime(df["date_maj"], errors="coerce")
    df["last_modified_ts"] = pd.to_datetime(df["last_modified"], errors="coerce", utc=True)

    # 1. Deduplicate. The schema allows the literal "Non concerné" as an ID for
    # points outside roaming networks; those rows are distinct points, so they
    # are deduplicated on their content instead of on the ID.
    placeholder = df["id_pdc_itinerance"].str.strip().str.lower().eq("non concerné")
    q["placeholder_id_rows"] = int(placeholder.sum())
    df = df.sort_values(["date_maj_ts", "last_modified_ts"], ascending=False, na_position="last")
    dup_id = df["id_pdc_itinerance"].duplicated() & ~placeholder.reindex(df.index)
    content_key = ["nom_operateur", "id_station_itinerance", "id_pdc_local", "coordonneesXY", "puissance_nominale"]
    dup_content = placeholder.reindex(df.index) & df.duplicated(subset=content_key)
    q["dup_groups"] = int(df.loc[~placeholder.reindex(df.index), "id_pdc_itinerance"]
                          .value_counts().gt(1).sum())
    real = df.loc[~placeholder.reindex(df.index)]
    groups = real[real["id_pdc_itinerance"].duplicated(keep=False)].groupby("id_pdc_itinerance")
    q["dup_cross_source_share"] = round(float(groups["datagouv_dataset_id"].nunique().gt(1).mean()), 4)
    q["steps"].append({"step": "Duplicate id_pdc_itinerance (kept most recent date_maj)",
                       "rows_removed": int(dup_id.sum())})
    q["steps"].append({"step": "Duplicate rows among 'Non concerné' IDs (same content)",
                       "rows_removed": int(dup_content.sum())})
    df = df[~(dup_id | dup_content)].copy()

    # 2. Power: kW expected; values >= WATT_THRESHOLD are read as watts.
    p = pd.to_numeric(df["puissance_nominale"], errors="coerce")
    in_watts = p >= C.WATT_THRESHOLD
    q["power_watts_converted"] = int(in_watts.sum())
    p = p.where(~in_watts, p / 1000)
    q["power_zero_or_tiny"] = int((p < C.POWER_MIN_KW).sum())
    p = p.where(p >= C.POWER_MIN_KW)
    q["power_suspicious_high"] = int((p > C.POWER_SUSPICIOUS_KW).sum())
    q["power_missing_after"] = int(p.isna().sum())
    df["power_kw"] = p.astype("float32")
    df["power_class"] = power_class(df["power_kw"])

    # 3. Commissioning date: outside [DATE_MIN, today] is treated as missing.
    d = pd.to_datetime(df["date_mise_en_service"], errors="coerce")
    q["date_missing_raw"] = int(d.isna().sum())
    q["date_before_min"] = int((d < C.DATE_MIN).sum())
    q["date_in_future"] = int((d > today).sum())
    d = d.where((d >= C.DATE_MIN) & (d <= today))
    q["date_missing_after"] = int(d.isna().sum())
    df["commissioned"] = d

    # 4. Département: INSEE commune code first, coordinates as fallback.
    lon = pd.to_numeric(df["consolidated_longitude"], errors="coerce")
    lat = pd.to_numeric(df["consolidated_latitude"], errors="coerce")
    bbox_ok = in_france_bbox(lon, lat)
    q["coords_outside_france"] = int((~bbox_ok).sum())
    dep_insee = dep_from_insee(df["code_insee_commune"])
    dep_insee = dep_insee.where(dep_insee.isin(shapes["dep"]))
    dep_geo = assign_dep_spatial(lon.fillna(0).values, lat.fillna(0).values, shapes)
    dep_geo.index = df.index
    dep_geo = dep_geo.where(bbox_ok)
    both = dep_insee.notna() & dep_geo.notna()
    q["dep_check_rows"] = int(both.sum())
    q["dep_check_agree"] = round(float((dep_insee[both] == dep_geo[both]).mean()), 4)
    df["dep"] = dep_insee.fillna(dep_geo)
    df["dep_method"] = np.where(dep_insee.notna(), "INSEE code",
                                np.where(dep_geo.notna(), "Coordinates", "None"))
    q["dep_by_insee"] = int((df["dep_method"] == "INSEE code").sum())
    q["dep_by_coords"] = int((df["dep_method"] == "Coordinates").sum())

    no_dep = df["dep"].isna()
    q["steps"].append({"step": "No usable commune code and coordinates outside every département",
                       "rows_removed": int(no_dep.sum())})
    df = df[~no_dep]
    out_scope = ~df["dep"].isin(scope_deps)
    q["out_of_scope_deps"] = sorted(df.loc[out_scope, "dep"].unique().tolist())
    q["steps"].append({"step": "Located in a département with no Insee 2023 population (Mayotte)",
                       "rows_removed": int(out_scope.sum())})
    df = df[~out_scope]

    # 5. Operator and siting.
    df["operator"] = clean_operator(df["nom_operateur"])
    top = df["operator"][df["operator"] != C.UNKNOWN_OPERATOR].value_counts().head(C.TOP_N_OPERATORS).index
    df["operator_group"] = df["operator"].where(df["operator"].isin(top), C.OTHER_OPERATORS)
    df["siting"] = clean_implantation(df["implantation_station"])
    q["operators_distinct"] = int(df["operator"].nunique())
    q["top_operators"] = list(top)

    df["lon"] = lon.reindex(df.index).astype("float32")
    df["lat"] = lat.reindex(df.index).astype("float32")
    df.loc[~bbox_ok.reindex(df.index), ["lon", "lat"]] = np.nan

    q["clean_rows"] = int(len(df))
    points = df[["dep", "power_kw", "power_class", "commissioned", "operator_group", "siting",
                 "dep_method", "lon", "lat"]].reset_index(drop=True)
    for col in ["dep", "operator_group", "siting", "dep_method"]:
        points[col] = points[col].astype("category")
    points["commissioned"] = points["commissioned"].astype("datetime64[ms]")
    return points, q


def build_population(pop_csv) -> pd.DataFrame:
    pop = pd.read_csv(pop_csv, sep=";", dtype=str)
    pop = pop[(pop["GEO_OBJECT"] == "DEP") & (pop["POPREF_MEASURE"] == "PMUN")]
    return pd.DataFrame({"dep": pop["GEO"].str.strip(),
                         "population": pd.to_numeric(pop["OBS_VALUE"]).astype("int64"),
                         "pop_year": pd.to_numeric(pop["TIME_PERIOD"]).astype("int64")})


def build_ev(ev_csv) -> tuple[pd.DataFrame, dict]:
    ev = pd.read_csv(ev_csv, dtype={"CODGEO": str}, encoding="cp1252",
                     usecols=["CODGEO", "DATE_ARRETE", "NB_VP_RECHARGEABLES_EL", "NB_VP"])
    ev["dep"] = dep_from_insee(ev["CODGEO"])
    q = {"ev_rows": int(len(ev)), "ev_rows_no_dep": int(ev["dep"].isna().sum()),
         "ev_quarters": int(ev["DATE_ARRETE"].nunique())}
    ev = ev.dropna(subset=["dep"])
    out = (ev.groupby(["dep", "DATE_ARRETE"], as_index=False)[["NB_VP_RECHARGEABLES_EL", "NB_VP"]].sum()
             .rename(columns={"DATE_ARRETE": "date", "NB_VP_RECHARGEABLES_EL": "ev", "NB_VP": "cars"}))
    out["date"] = pd.to_datetime(out["date"])
    return out, q


def build_departements(shapes: pd.DataFrame, pop: pd.DataFrame, ev: pd.DataFrame,
                       region_names: dict) -> pd.DataFrame:
    dep = shapes[["dep", "dep_name", "reg"]].copy()
    dep["region"] = dep["reg"].map(region_names)
    dep["area_km2"] = shapes["geometry"].map(_area_km2).round(1)
    dep = dep.merge(pop[["dep", "population"]], on="dep", how="inner")
    latest = ev["date"].max()
    last = ev[ev["date"] == latest][["dep", "ev", "cars"]]
    dep = dep.merge(last, on="dep", how="left")
    dep["ev_date"] = latest
    dep["density"] = dep["population"] / dep["area_km2"]
    return dep.drop(columns=["reg"]).sort_values("dep").reset_index(drop=True)


# Overseas départements are moved next to metropolitan France on the map,
# a common inset layout. (dep, x offset, y offset, scale) in degrees.
_INSETS = {
    "971": (-9.0, 44.6, 1.6),
    "972": (-9.0, 43.0, 2.4),
    "973": (-9.0, 41.0, 0.45),
    "974": (-6.5, 41.4, 1.4),
    "976": (-6.5, 43.0, 2.4),
}


def build_map_geojson(geojson_path, scope_deps: set) -> dict:
    from shapely import affinity
    from shapely.geometry import mapping, shape
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    feats = []
    for ft in gj["features"]:
        code = ft["properties"]["code"]
        if code not in scope_deps:
            continue
        g = shape(ft["geometry"])
        if code in _INSETS:
            x, y, s = _INSETS[code]
            c = g.centroid
            g = affinity.scale(g, s, s, origin=c)
            g = affinity.translate(g, x - c.x, y - c.y)
        g = g.simplify(0.005, preserve_topology=True)
        feats.append({"type": "Feature", "id": code,
                      "properties": {"code": code, "nom": ft["properties"]["nom"]},
                      "geometry": _round_coords(mapping(g))})
    return {"type": "FeatureCollection", "features": feats}


def _round_coords(geom: dict, nd: int = 3) -> dict:
    def rnd(x):
        if isinstance(x, (list, tuple)):
            if x and isinstance(x[0], (int, float)):
                return [round(v, nd) for v in x]
            return [rnd(v) for v in x]
        return x
    return {"type": geom["type"], "coordinates": rnd(geom["coordinates"])}




# ---------------------------------------------------------------------------
# App-side filtering and aggregation
# ---------------------------------------------------------------------------
# Date semantics used everywhere in the app:
#   * "snapshot" views (KPIs, map, ranking) show the network as it stood at the
#     end of the selected period: dated points commissioned up to that date,
#     plus undated points when the user keeps them (only possible when the
#     period ends in the current year, since an undated point cannot be placed
#     in the past).
#   * "additions" are dated points commissioned inside the period.

def base_mask(points: pd.DataFrame, deps, classes, operators) -> pd.Series:
    return (points["dep"].isin(deps) & points["power_class"].isin(classes)
            & points["operator_group"].isin(operators))


def period_bounds(start_year: int, end_year: int, data_date: str):
    start = pd.Timestamp(year=start_year, month=1, day=1)
    end = min(pd.Timestamp(year=end_year, month=12, day=31), pd.Timestamp(data_date))
    years = max((end - start).days + 1, 1) / 365.25
    return start, end, years


def snapshot(points: pd.DataFrame, mask: pd.Series, end: pd.Timestamp, include_undated: bool) -> pd.DataFrame:
    c = points["commissioned"]
    keep = mask & ((c <= end) | (c.isna() & include_undated))
    return points[keep]


def additions(points: pd.DataFrame, mask: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    c = points["commissioned"]
    return points[mask & c.between(start, end)]


def dated_before(points: pd.DataFrame, mask: pd.Series, start: pd.Timestamp) -> pd.DataFrame:
    return points[mask & (points["commissioned"] < start)]


def ev_at(ev: pd.DataFrame, end: pd.Timestamp) -> tuple[pd.Series, pd.Timestamp | None]:
    """Rechargeable-car stock per département at the last quarter on or before `end`."""
    avail = ev[ev["date"] <= end]
    if avail.empty:
        return pd.Series(dtype="float64"), None
    d = avail["date"].max()
    return avail[avail["date"] == d].set_index("dep")["ev"].astype("float64"), d


def _count_by_dep(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["dep", "points", "fast_points", "kw_total"])
    fast = df["power_class"].isin(C.FAST_CLASSES)
    out = pd.DataFrame({"dep": df["dep"].astype(str).values, "fast": fast.values,
                        "kw": df["power_kw"].fillna(0).values})
    return out.groupby("dep").agg(points=("fast", "size"), fast_points=("fast", "sum"),
                                  kw_total=("kw", "sum")).reset_index()


def dep_indicators(snap: pd.DataFrame, added: pd.DataFrame, deps_tbl: pd.DataFrame,
                   ev_dep: pd.Series, years: float) -> pd.DataFrame:
    """One row per département with every indicator offered in the app."""
    t = deps_tbl.merge(_count_by_dep(snap), on="dep", how="left")
    add = _count_by_dep(added)[["dep", "points"]].rename(columns={"points": "added"})
    t = t.merge(add, on="dep", how="left")
    t[["points", "fast_points", "kw_total", "added"]] = t[["points", "fast_points", "kw_total", "added"]].fillna(0)
    t["ev"] = t["dep"].map(ev_dep)
    t["per_100k"] = t["points"] / t["population"] * 1e5
    t["fast_per_100k"] = t["fast_points"] / t["population"] * 1e5
    t["per_100_ev"] = t["points"] / t["ev"] * 100
    t["kw_per_ev"] = t["kw_total"] / t["ev"]
    t["fast_share"] = (t["fast_points"] / t["points"].where(t["points"] > 0)) * 100
    t["added_per_100k"] = t["added"] / t["population"] * 1e5
    t["pace_per_100k_year"] = t["added_per_100k"] / years
    t["ev_per_1000_inh"] = t["ev"] / t["population"] * 1000
    t["density_band"] = density_band(t["density"])
    t["overseas"] = t["dep"].str.startswith("97")
    return t


def totals(t: pd.DataFrame) -> dict:
    """Aggregate ratios over a set of départements (ratio of sums, not mean of ratios)."""
    pop, pts, fast = t["population"].sum(), t["points"].sum(), t["fast_points"].sum()
    ev = t["ev"].sum(min_count=1)
    return {"points": int(pts), "population": int(pop), "fast_points": int(fast),
            "per_100k": pts / pop * 1e5 if pop else np.nan,
            "fast_per_100k": fast / pop * 1e5 if pop else np.nan,
            "per_100_ev": pts / ev * 100 if ev and ev == ev else np.nan,
            "kw_per_ev": t["kw_total"].sum() / ev if ev and ev == ev else np.nan,
            "fast_share": fast / pts * 100 if pts else np.nan,
            "added": int(t["added"].sum()),
            "added_per_100k": t["added"].sum() / pop * 1e5 if pop else np.nan,
            "ev": float(ev) if ev == ev else np.nan}


def growth(n_before: int, n_added: int) -> float:
    return n_added / n_before * 100 if n_before >= C.MIN_STOCK_FOR_GROWTH else np.nan


def timeline(dated: pd.DataFrame) -> pd.DataFrame:
    """Monthly cumulative count of dated points by power class."""
    if dated.empty:
        return pd.DataFrame(columns=["month", "power_class", "cumulative"])
    month = dated["commissioned"].dt.to_period("M").dt.to_timestamp()
    cls = dated["power_class"].astype(str)
    m = pd.crosstab(month, cls)
    months = pd.date_range(m.index.min(), m.index.max(), freq="MS")
    order = [c for c in C.POWER_CLASSES + [C.UNKNOWN_POWER] if c in m.columns]
    m = m.reindex(index=months, columns=order, fill_value=0).cumsum()
    m.index.name = "month"
    return m.reset_index().melt(id_vars="month", var_name="power_class", value_name="cumulative")


def yearly(dated: pd.DataFrame) -> pd.Series:
    return dated["commissioned"].dt.year.value_counts().sort_index()


def density_band(d: pd.Series) -> pd.Series:
    return pd.cut(d, bins=C.DENSITY_BINS, labels=C.DENSITY_LABELS)


def by_density_and_class(snap: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Points per 100k inhabitants for each density band x power class."""
    band_of = t.set_index("dep")["density_band"]
    pop = t.groupby("density_band", observed=True)["population"].sum()
    s = snap.assign(band=snap["dep"].astype(str).map(band_of))
    g = s.groupby(["band", "power_class"], observed=True).size().rename("points").reset_index()
    g = g[g["power_class"] != C.UNKNOWN_POWER]
    ndeps = t.groupby("density_band", observed=True).size()
    g["population"] = g["band"].astype(str).map({str(k): v for k, v in pop.items()}).astype(float)
    g["per_100k"] = g["points"] / g["population"] * 1e5
    g["n_deps"] = g["band"].astype(str).map({str(k): v for k, v in ndeps.items()})
    return g


def convergence(points: pd.DataFrame, mask: pd.Series, t: pd.DataFrame,
                start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    """Group départements into quartiles of dated points per 100k at the start
    of the period, then compare each quartile's level at the start and the end."""
    if len(t) < 8:
        return None
    dated = points[mask & points["commissioned"].notna()]
    dep = dated["dep"].astype(str)
    before = dep[dated["commissioned"] < start].value_counts()
    after = dep[dated["commissioned"] <= end].value_counts()
    x = t[["dep", "dep_name", "population"]].copy()
    x["before"] = x["dep"].map(before).fillna(0)
    x["after"] = x["dep"].map(after).fillna(0)
    if x["before"].sum() < C.MIN_STOCK_FOR_GROWTH:
        return None
    rate = x["before"] / x["population"] * 1e5
    x["quartile"] = pd.qcut(rate.rank(method="first"), 4, labels=C.QUARTILE_LABELS)
    g = x.groupby("quartile", observed=True).agg(population=("population", "sum"), before=("before", "sum"),
                                                 after=("after", "sum"), n=("dep", "size"),
                                                 names=("dep_name", lambda s: ", ".join(sorted(s)[:6])))
    g["before_100k"] = g["before"] / g["population"] * 1e5
    g["after_100k"] = g["after"] / g["population"] * 1e5
    g["added_100k"] = g["after_100k"] - g["before_100k"]
    return g.reset_index()


def years_to_reach(t: pd.DataFrame, target: float) -> pd.Series:
    """Years each département needs, at its pace over the period, to reach
    `target` points per 100k. NaN when already above or when pace is zero."""
    gap = target - t["per_100k"]
    yrs = gap / t["pace_per_100k_year"].where(t["pace_per_100k_year"] > 0)
    return yrs.where(gap > 0)


def sample_points(snap: pd.DataFrame, n: int) -> pd.DataFrame:
    s = snap.dropna(subset=["lon", "lat"])
    if len(s) > n:
        s = s.sample(n, random_state=C.SEED)
    return s


def story_numbers(points: pd.DataFrame, deps_tbl: pd.DataFrame, ev: pd.DataFrame, data_date: str) -> dict:
    """National figures quoted in the intro and conclusions. Computed on the
    full clean table (no sidebar filter) so the story stays the same while
    the user explores."""
    all_mask = pd.Series(True, index=points.index)
    end = pd.Timestamp(data_date)
    pivot = pd.Timestamp(year=C.DEFAULT_START_YEAR, month=1, day=1)
    _, _, yrs = period_bounds(C.DEFAULT_START_YEAR, end.year, data_date)
    ev_now, ev_date = ev_at(ev, end)
    t = dep_indicators(points, additions(points, all_mask, pivot, end), deps_tbl, ev_now, yrs)
    fr = totals(t)
    main, over = t[~t["overseas"]], t[t["overseas"]]
    s = {"fr": fr, "main": totals(main), "over": totals(over), "t": t, "ev_date": ev_date}
    s["lowest"] = t.sort_values("per_100k").iloc[0]
    s["lowest_main"] = main.sort_values("per_100k").iloc[0]
    s["highest"] = t.sort_values("per_100k").iloc[-1]

    bands = {}
    for b, grp in t.groupby("density_band", observed=True):
        bands[str(b)] = totals(grp) | {"n": len(grp)}
    s["bands"] = bands
    main_bands = {str(b): totals(g) | {"n": len(g)} for b, g in main.groupby("density_band", observed=True)}
    s["main_bands"] = main_bands

    dated = points[points["commissioned"].notna()]
    s["dated_share"] = len(dated) / len(points) * 100
    y = yearly(dated)
    s["yearly"] = y
    full_years = y[y.index < end.year]
    s["peak_year"], s["peak_n"] = int(full_years.idxmax()), int(full_years.max())
    s["last_full_year"], s["last_full_n"] = int(full_years.index.max()), int(full_years.iloc[-1])
    s["n2020"], s["n2021"] = int(y.get(2020, 0)), int(y.get(2021, 0))

    e = ev.groupby("date")["ev"].sum()
    s["ev_first_date"], s["ev_first"] = e.index.min(), float(e.iloc[0])
    s["ev_last_date"], s["ev_last"] = e.index.max(), float(e.iloc[-1])

    conv = convergence(points, all_mask, t, pivot, end)
    s["conv"] = conv
    s["conv_ratio_before"] = conv["before_100k"].iloc[-1] / conv["before_100k"].iloc[0]
    s["conv_ratio_after"] = conv["after_100k"].iloc[-1] / conv["after_100k"].iloc[0]

    t2 = t.assign(years=years_to_reach(t, fr["per_100k"]))
    s["slowest_main"] = t2[~t2["overseas"]].dropna(subset=["years"]).sort_values("years").iloc[-1]
    s["n_below_fr"] = int((t["per_100k"] < fr["per_100k"]).sum())
    s["over_added"] = int(over["added"].sum())
    s["main_pace"] = main["added"].sum() / main["population"].sum() * 1e5 / yrs
    s["over_pace"] = over["added"].sum() / over["population"].sum() * 1e5 / yrs
    low_ev = t[t["kw_per_ev"] < C.AFIR_KW_PER_PHEV].sort_values("kw_per_ev")
    s["below_afir"] = low_ev
    ranked = t.sort_values("points", ascending=False).head(10)
    s["top10_points_share"] = ranked["points"].sum() / t["points"].sum() * 100
    s["top10_pop_share"] = ranked["population"].sum() / t["population"].sum() * 100
    s["top10_names"] = list(ranked["dep_name"])
    dense = main[main["density_band"] == C.DENSITY_LABELS[-1]]
    s["dense_low"] = dense.sort_values("per_100k").iloc[0] if len(dense) else None
    s["dense_low_ev"] = dense.sort_values("per_100_ev").head(3)
    paris = t[t["dep"] == "75"]
    s["paris"] = paris.iloc[0] if len(paris) else None
    s["pivot_year"] = C.DEFAULT_START_YEAR - 1
    s["end_year"] = end.year
    return s
