"""Comparisons between départements: map, ranking, density, EV ownership,
catch-up, station map."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import config as C
from sections._ui import chart, compare, headline, n, names, pct, plural, rate
from utils import prep, viz


def _val(col: str, v) -> str:
    if v is None or v != v:
        return "n/a"
    fmt = C.INDICATORS[col][2]
    if fmt == "{:,.0f}" and 0 < abs(v) < 10:
        fmt = "{:,.1f}"
    return fmt.format(v) + ("%" if col == "fast_share" else "")


def _dep_table(t: pd.DataFrame, col: str) -> pd.DataFrame:
    label = C.INDICATORS[col][0]
    cols = list(dict.fromkeys(["dep", "dep_name", "region", "population", "points", col]))
    out = t[cols].sort_values(col, ascending=False)
    return out.rename(columns={"dep": "Code", "dep_name": "Département", "region": "Region",
                               "population": "Population 2023", "points": "Charging points", col: label})


def map_and_ranking(v: dict, geojson: dict) -> None:
    f, t = v["f"], v["t"]
    col = f.indicator
    label, unit, _ = C.INDICATORS[col]
    ref_tot = v["tot_fr"]
    ref = ref_tot.get(col, np.nan) if col != "points" else np.nan
    d = t.dropna(subset=[col])
    st.subheader("Where the gaps are")
    if d.empty:
        st.info(f"'{label}' cannot be computed for this selection. Shares need at least one charging point, "
                "and per-car ratios need a period ending in 2021 or later (the vehicle register starts in "
                "December 2020).")
        return
    top, bot = d.sort_values(col).iloc[-1], d.sort_values(col).iloc[0]
    if len(d) == 1:
        headline(f"{top['dep_name']} scores {_val(col, top[col])} on {label.lower()}, against "
                 f"{_val(col, ref)} for France.")
    else:
        headline(f"On {label.lower()}, {top['dep_name']} leads with {_val(col, top[col])} and "
                 f"{bot['dep_name']} trails with {_val(col, bot[col])}"
                 + (f", against {_val(col, ref)} for France." if ref == ref else "."))
    chart(viz.choropleth(t, col, geojson),
          alt=(f"Map of the selected départements shaded by {label.lower()} ({unit}), darker meaning higher. "
               "Overseas départements are drawn as insets to the west of mainland France. "
               f"Highest: {top['dep_name']} ({_val(col, top[col])}); lowest: {bot['dep_name']} "
               f"({_val(col, bot[col])})."),
          key="choropleth", table=_dep_table(t, col), table_label="Show the values for every département")
    if col in ("per_100_ev", "kw_per_ev"):
        st.caption("Per-car ratios use the vehicle register by the holder's commune. Company and leasing cars "
                   "are registered where the company sits, which inflates the car count of départements "
                   "hosting head offices (Hauts-de-Seine, Yvelines, Paris) and lowers their ratio.")

    if len(d) >= 4:
        below = int((d[col] < ref).sum()) if ref == ref else None
        st.markdown(f"**Ranking: {label.lower()}**")
        if below is not None:
            headline(f"{below} of the {len(d)} départements in the selection "
                     f"{'sits' if below == 1 else 'sit'} below the France figure of {_val(col, ref)}.")
        chart(viz.ranking(d, col, ref),
              alt=(f"Two horizontal bar charts: the départements with the lowest and the highest {label.lower()} "
                   f"in the selection, with a dashed line at the France value ({_val(col, ref)})."),
              key="ranking")


def density(v: dict) -> None:
    g, t = v["density"], v["t"]
    st.subheader("Rural or urban: who has the chargers")
    bands = t.groupby("density_band", observed=True).size()
    if g.empty or len(bands) < 2:
        st.info("This comparison needs départements from at least two density bands. "
                "Widen the area to see it.")
        return
    tot = (t.groupby("density_band", observed=True)
             .apply(lambda x: pd.Series(prep.totals(x)), include_groups=False))
    rural, dense = C.DENSITY_LABELS[0], C.DENSITY_LABELS[-1]
    if rural in tot.index and dense in tot.index:
        r, dn = tot.loc[rural], tot.loc[dense]
        headline(f"Rural départements have {rate(r['per_100k'])} points per 100k inhabitants, "
                 f"{compare(r['per_100k'], dn['per_100k'])} the {rate(dn['per_100k'])} of dense ones, and "
                 f"{rate(r['fast_per_100k'])} fast or ultra-fast points per 100k, "
                 f"{compare(r['fast_per_100k'], dn['fast_per_100k'])} the {rate(dn['fast_per_100k'])} of dense ones.")
    else:
        present = [str(b) for b in bands.index]
        headline(f"The selection covers these density bands: {names(present)}.")
    chart(viz.density_multiples(g),
          alt=("Small multiples, one panel per power class. Each panel has one bar per density band "
               "(rural, intermediate, dense) showing charging points per 100,000 inhabitants. "
               "Each panel has its own vertical scale."),
          key="density",
          table=g.assign(band=g["band"].astype(str), power_class=g["power_class"].astype(str))
                 [["band", "power_class", "points", "population", "per_100k", "n_deps"]]
                 .rename(columns={"band": "Density band", "power_class": "Power class", "points": "Points",
                                  "population": "Population", "per_100k": "Points per 100k inh.",
                                  "n_deps": "Départements"}))
    st.caption(f"Density bands: rural below {C.DENSITY_BINS[1]:.0f} inhabitants per km², dense above "
               f"{C.DENSITY_BINS[2]:.0f}, intermediate between, "
               "measured at département level. A rural département can still concentrate its fast chargers "
               "along one motorway; the file has no road layer, so corridor placement is not measured here.")


def ev_ownership(v: dict) -> None:
    t = v["t"].dropna(subset=["kw_per_ev"])
    st.subheader("Charging measured against EV ownership")
    if t.empty:
        st.info("Vehicle registrations start in December 2020; move the end of the period to 2021 or later.")
        return
    low = t[t["kw_per_ev"] < C.AFIR_KW_PER_PHEV].sort_values("kw_per_ev")
    if len(t) == 1:
        r = t.iloc[0]
        side = "below" if r["kw_per_ev"] < C.AFIR_KW_PER_PHEV else "above"
        headline(f"{r['dep_name']} offers {r['kw_per_ev']:.2f} kW of public charging power per rechargeable car, "
                 f"{side} the lower AFIR reference of {C.AFIR_KW_PER_PHEV} kW.")
    elif len(low):
        headline(f"{len(low)} of the {len(t)} départements offer less than {C.AFIR_KW_PER_PHEV} kW of public "
                 f"charging power per rechargeable car, the lower AFIR reference: {names(low['dep_name'], 6)}.")
    else:
        headline(f"Every département in the selection offers at least {C.AFIR_KW_PER_PHEV} kW of public "
                 f"charging power per rechargeable car; the lowest is {t.sort_values('kw_per_ev').iloc[0]['dep_name']} "
                 f"with {t['kw_per_ev'].min():.2f} kW.")
    chart(viz.ev_scatter(t),
          alt=("Scatter plot, one bubble per département sized by population. Horizontal axis: rechargeable "
               "cars per 1,000 inhabitants. Vertical axis: kW of public charging power per rechargeable car. "
               f"A grey band marks the AFIR fleet-based targets between {C.AFIR_KW_PER_PHEV} and {C.AFIR_KW_PER_BEV} kW per car. "
               "Overseas départements are orange, mainland départements blue."),
          key="scatter",
          table=t[["dep", "dep_name", "ev", "ev_per_1000_inh", "kw_per_ev", "per_100_ev"]]
                 .sort_values("kw_per_ev")
                 .rename(columns={"dep": "Code", "dep_name": "Département", "ev": "Rechargeable cars",
                                  "ev_per_1000_inh": "Cars per 1,000 inh.", "kw_per_ev": "kW per car",
                                  "per_100_ev": "Points per 100 cars"}))
    if len(t) >= 10:
        rho = t[["ev_per_1000_inh", "per_100_ev"]].corr("spearman").iloc[0, 1]
        st.caption(f"Across the selection, départements with more rechargeable cars per inhabitant have "
                   f"{'fewer' if rho < 0 else 'more'} public points per car (Spearman rank correlation "
                   f"{rho:+.2f}). This is a correlation: home and workplace charging, which the file does not "
                   f"cover, are likely more common where ownership is high. AFIR sets {C.AFIR_KW_PER_BEV} kW per battery "
                   f"car and {C.AFIR_KW_PER_PHEV} kW per plug-in hybrid; the register here mixes both, so the band "
                   "is a reference, "
                   "not a compliance test. Company cars registered at head offices inflate car counts in a few "
                   "départements.")


def catch_up(v: dict) -> None:
    f, t, g = v["f"], v["t"], v["conv"]
    st.subheader("Is the gap closing?")
    if g is None:
        st.info("This view needs at least 8 départements and some dated points before the period starts. "
                f"Widen the area or start the period later than {f.start_year}.")
        return
    lo, hi = g.iloc[0], g.iloc[-1]
    r0 = hi["before_100k"] / lo["before_100k"] if lo["before_100k"] > 0 else np.nan
    r1 = hi["after_100k"] / lo["after_100k"] if lo["after_100k"] > 0 else np.nan
    if r0 == r0 and r1 == r1:
        verb = "narrowed" if r1 < r0 else "widened"
        headline(f"At the end of {f.start_year - 1}, the best equipped quarter of départements had "
                 f"{r0:.1f} times more dated points per inhabitant than the least equipped quarter; by "
                 f"{v['end']:%B %Y} the ratio had {verb} to {r1:.1f}.")
    else:
        headline(f"The least equipped quarter had no dated points at the end of {f.start_year - 1}, so the "
                 "ratio cannot be computed.")
    chart(viz.convergence_dumbbell(g, f"End of {f.start_year - 1}", f"{v['end']:%b %Y}"),
          alt=(f"Dumbbell chart with one row per quarter of départements, grouped by their dated points per "
               f"100,000 inhabitants at the end of {f.start_year - 1}. Each row links the level then (light dot) "
               f"to the level at {v['end']:%B %Y} (dark dot)."),
          key="convergence",
          table=g[["quartile", "n", "before_100k", "after_100k", "added_100k", "names"]]
                 .rename(columns={"quartile": "Group", "n": "Départements", "before_100k": "Start (per 100k)",
                                  "after_100k": "End (per 100k)", "added_100k": "Added (per 100k)",
                                  "names": "Examples"}))
    st.caption("Groups are formed on dated points only, so départements whose operators omit dates look less "
               "equipped than they are. Both ends of each row use the same dated subset, which keeps the "
               "comparison fair.")

    ref = v["tot_fr"]["per_100k"]
    tt = t.assign(years=prep.years_to_reach(t, ref))
    lag = tt[tt["per_100k"] < ref].sort_values("years", ascending=False, na_position="first")
    if lag.empty:
        return
    stalled = lag[lag["pace_per_100k_year"] < 1]
    moving = lag[lag["pace_per_100k_year"] >= 1].dropna(subset=["years"])
    msg = []
    if len(moving):
        w = moving.iloc[0]
        msg.append(f"At its {f.start_year}-{f.end_year} pace of {w['pace_per_100k_year']:.1f} dated points per "
                   f"100k inhabitants a year, {w['dep_name']} would need {w['years']:.0f} years to reach "
                   f"today's France level of {n(ref)}")
    if len(stalled):
        msg.append(f"{names(stalled['dep_name'])} added less than one dated point per 100k inhabitants a year, "
                   "so at that pace the gap does not close")
    headline("; ".join(msg) + ".")
    show = lag.head(15)[["dep_name", "per_100k", "pace_per_100k_year", "years"]].copy()
    show["years"] = [("no progress" if y != y else "over 100" if y > 100 else f"{y:.0f}") for y in show["years"]]
    show = show.rename(columns={
        "dep_name": "Département", "per_100k": "Points per 100k now",
        "pace_per_100k_year": "Dated points added per 100k per year", "years": "Years to reach France level"})
    st.markdown(f"**The {len(show)} départements furthest from the France level at their current pace**")
    st.dataframe(show, hide_index=True, column_config={
        "Points per 100k now": st.column_config.NumberColumn(format="%.0f"),
        "Dated points added per 100k per year": st.column_config.NumberColumn(format="%.1f"),
    })
    st.caption("A projection under stated assumptions, not a forecast: the pace counts only dated points, so the "
               "true pace is higher and these durations are upper bounds; the France level is held at today's "
               "value.")


def station_map(v: dict) -> None:
    s, snap = v["sample"], v["snap"]
    st.subheader("Station map")
    if s.empty:
        st.info("No point with valid coordinates matches these filters.")
        return
    ultra = snap[snap["power_class"] == C.POWER_CLASSES[3]]
    if len(ultra):
        share = (ultra["siting"] == "Dedicated fast-charging station").mean() * 100
        headline(f"{pct(share)} of the {plural(len(ultra), 'ultra-fast point')} in the selection sit in stations "
                 "dedicated to fast charging; the rest are in car parks or on the street.")
    note = (f"A random sample of {n(len(s))} of the {n(len(snap))} points (seed {C.SEED}) keeps the map fast."
            if len(snap) > len(s) else f"All {n(len(s))} points with valid coordinates are shown.")
    chart(viz.points_map(s),
          alt=("Street map with one dot per charging point, colored by power class from light blue (slow) to "
               "dark blue (ultra-fast). " + note),
          key="pointmap")
    st.caption(note + " Basemap © OpenStreetMap contributors, © CARTO.")


def render(v: dict, tables: dict) -> None:
    st.header("2. Deep dives", anchor="deep-dives")
    if v["tot"]["points"] == 0 and v["t"]["population"].sum() == 0:
        return
    map_and_ranking(v, tables["geojson"])
    density(v)
    ev_ownership(v)
    catch_up(v)
    station_map(v)
