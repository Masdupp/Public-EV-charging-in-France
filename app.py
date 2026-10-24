"""Public EV charging in France: where it lags and how fast the gap closes.

Run with `streamlit run app.py` after `python data/fetch_data.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

import config as C
from sections import conclusions, deep_dives, intro, overview, quality
from utils import io, prep

st.set_page_config(page_title="EV charging gaps in France", page_icon="assets/icon.png", layout="wide")


@st.cache_data(show_spinner="Loading processed tables")
def get_tables() -> dict:
    return io.load_tables()


@st.cache_data(show_spinner=False)
def get_story(_tables: dict, build_date: str) -> dict:
    t = _tables
    return prep.story_numbers(t["points"], t["deps"], t["ev"], build_date)


@dataclass(frozen=True)
class Filters:
    deps: tuple
    scope_label: str
    start_year: int
    end_year: int
    include_undated: bool
    classes: tuple
    operators: tuple
    indicator: str


@st.cache_data(show_spinner=False)
def compute_view(_tables: dict, f: Filters, build_date: str) -> dict:
    """Everything the sections need for one filter combination."""
    points, deps_tbl, ev = _tables["points"], _tables["deps"], _tables["ev"]
    start, end, years = prep.period_bounds(f.start_year, f.end_year, build_date)
    ev_dep, ev_date = prep.ev_at(ev, end)
    undated = f.include_undated and f.end_year >= pd.Timestamp(build_date).year

    # France reference: same power/operator/date filters, every département.
    fr_mask = prep.base_mask(points, deps_tbl["dep"], f.classes, f.operators)
    t_fr = prep.dep_indicators(prep.snapshot(points, fr_mask, end, undated),
                               prep.additions(points, fr_mask, start, end), deps_tbl, ev_dep, years)

    mask = fr_mask & points["dep"].isin(f.deps)
    snap = prep.snapshot(points, mask, end, undated)
    added = prep.additions(points, mask, start, end)
    before = prep.dated_before(points, mask, start)
    t = t_fr[t_fr["dep"].isin(f.deps)].reset_index(drop=True)
    dated = points[mask & points["commissioned"].notna()]
    return {
        "f": f, "start": start, "end": end, "years": years, "ev_date": ev_date, "undated": undated,
        "snap": snap, "added": added, "n_before": len(before), "t": t, "t_fr": t_fr,
        "tot": prep.totals(t), "tot_fr": prep.totals(t_fr),
        "dated": dated[["commissioned", "power_class", "dep"]],
        "conv": prep.convergence(points, mask, t, start, end),
        "density": prep.by_density_and_class(snap, t),
        "ev_sel": ev[ev["dep"].isin(f.deps)],
        "sample": prep.sample_points(snap, C.MAP_POINT_SAMPLE),
    }


def sidebar(tables: dict, build_date: str) -> Filters | None:
    deps_tbl = tables["deps"]
    points = tables["points"]
    this_year = pd.Timestamp(build_date).year
    with st.sidebar:
        st.header("Filters")
        st.caption("Every chart, KPI and headline below the introduction follows these filters. "
                   "The introduction and conclusions always describe all of France.")
        regions = sorted(deps_tbl["region"].dropna().unique())
        scope = st.selectbox("Area", ["All France", "Mainland France", "Overseas départements"] + regions,
                             help="Pick a region to focus the map, ranking and KPIs on its départements.")
        if scope == "All France":
            pool = deps_tbl
        elif scope == "Mainland France":
            pool = deps_tbl[~deps_tbl["dep"].str.startswith("97")]
        elif scope == "Overseas départements":
            pool = deps_tbl[deps_tbl["dep"].str.startswith("97")]
        else:
            pool = deps_tbl[deps_tbl["region"] == scope]
        labels = dict(zip(pool["dep"], pool["dep"] + " " + pool["dep_name"]))
        chosen = st.multiselect("Départements", list(labels), format_func=labels.get,
                                placeholder="All départements in the area",
                                help="Leave empty to keep every département of the area.")
        deps = tuple(chosen) if chosen else tuple(pool["dep"])
        scope_label = (", ".join(pool.set_index("dep").loc[list(chosen), "dep_name"]) if chosen else scope)

        min_year = int(points["commissioned"].dt.year.min())
        undated_share = points["commissioned"].isna().mean() * 100
        start_year, end_year = st.slider(
            "Commissioning period", min_value=min_year, max_value=this_year,
            value=(C.DEFAULT_START_YEAR, this_year),
            help="KPIs, map and ranking show the network at the end of the period. "
                 "Growth and 'added' figures count points commissioned inside it.")
        can_undated = end_year >= this_year
        include_undated = st.checkbox(
            "Count points with no commissioning date", value=True, disabled=not can_undated,
            help=f"{undated_share:.0f}% of records have no date. They are listed today, but cannot be "
                 "placed in the past, so they are left out when the period ends before " + str(this_year) + ".")
        if not can_undated:
            st.caption(f"Undated points are excluded because the period ends in {end_year}.")

        classes = st.pills("Power class", C.POWER_CLASSES + [C.UNKNOWN_POWER], selection_mode="multi",
                           default=C.POWER_CLASSES + [C.UNKNOWN_POWER],
                           help="Slow < 7.4 kW, normal 7.4 to 22 kW, fast above 22 and below 150 kW, "
                                "ultra-fast 150 kW and more. 'Unknown power' means the declared power was 0.")

        top = list(tables["quality"]["top_operators"])
        op_mode = st.radio("Operators", ["All operators", "Choose operators"], horizontal=True)
        if op_mode == "All operators":
            operators = top + [C.OTHER_OPERATORS]
        else:
            operators = st.multiselect(f"Top {len(top)} operators, the rest grouped", top + [C.OTHER_OPERATORS],
                                       default=top[:3])

        indicator = st.selectbox("Indicator for the map and ranking", list(C.INDICATORS),
                                 format_func=lambda k: C.INDICATORS[k][0])

        st.divider()
        st.caption(io.LICENCE_TEXT)

    if not classes:
        st.warning("No power class is selected. Pick at least one power class in the sidebar to see the charts.")
        return None
    if not operators:
        st.warning("No operator is selected. Pick at least one operator in the sidebar, "
                   "or switch back to 'All operators'.")
        return None
    return Filters(deps=deps, scope_label=scope_label, start_year=start_year, end_year=end_year,
                   include_undated=include_undated, classes=tuple(classes), operators=tuple(operators),
                   indicator=indicator)


def main() -> None:
    try:
        tables = get_tables()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()
    build_date = tables["quality"]["build_date"]
    story = get_story(tables, build_date)

    intro.render(story, tables["quality"])
    f = sidebar(tables, build_date)
    if f is None:
        quality.render(tables["quality"])
        conclusions.render(story)
        return
    view = compute_view(tables, f, build_date)
    overview.render(view, tables)
    deep_dives.render(view, tables)
    quality.render(tables["quality"])
    conclusions.render(story)


main()
