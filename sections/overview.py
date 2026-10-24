"""KPI header and deployment over time."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config as C
from sections._ui import chart, headline, n, pct, plural
from utils import prep, viz


def _delta(v, ref, unit=""):
    if v != v or ref != ref:
        return None
    return f"{v - ref:+,.1f}{unit} vs France"


def kpi_header(v: dict) -> None:
    f, tot, fr = v["f"], v["tot"], v["tot_fr"]
    g = prep.growth(v["n_before"], len(v["added"]))
    is_fr = len(f.deps) == len(v["t_fr"])
    st.subheader(f"{f.scope_label}: the network at {v['end']:%d %B %Y}")
    c = st.columns(5)
    c[0].metric("Charging points", n(tot["points"]),
                help="Points listed in the file for the selection, at the end of the period.")
    c[1].metric("Points per 100k inhabitants", n(tot["per_100k"]),
                None if is_fr else _delta(tot["per_100k"], fr["per_100k"]),
                help="Insee 2023 municipal population. Delta compares with France under the same filters.")
    ev_label = f"{v['ev_date']:%b %Y}" if v["ev_date"] is not None else "n/a"
    c[2].metric("Points per 100 rechargeable cars", n(tot["per_100_ev"], 1),
                None if is_fr else _delta(tot["per_100_ev"], fr["per_100_ev"]),
                help=f"Battery-electric and plug-in hybrid cars registered at {ev_label}. "
                     "The register starts in December 2020.")
    c[3].metric("Fast + ultra-fast share", pct(tot["fast_share"]),
                None if is_fr else _delta(tot["fast_share"], fr["fast_share"], " pts"),
                help="Points above 22 kW, as a share of the points selected.")
    c[4].metric(f"Growth {f.start_year}-{f.end_year}", pct(g),
                f"+{n(len(v['added']))} dated points" if len(v["added"]) else None,
                help=f"Dated points commissioned in the period divided by dated points commissioned before "
                     f"{f.start_year}. Hidden when fewer than {C.MIN_STOCK_FOR_GROWTH} points existed before.")


def render(v: dict, tables: dict) -> None:
    st.header("1. Overview", anchor="overview")
    kpi_header(v)
    if v["tot"]["points"] == 0:
        st.info("No charging point matches these filters. Widen the area, the period or the power classes.")
        return

    dated = v["dated"]
    st.subheader("Deployment over time")
    if dated.empty:
        st.info("None of the selected points has a commissioning date, so no timeline can be drawn.")
        return
    y = prep.yearly(dated)
    this_year = pd.Timestamp(tables["quality"]["build_date"]).year
    full = y[y.index < this_year]
    f = v["f"]
    if y.get(2020, 0) >= C.MIN_STOCK_FOR_GROWTH and len(full) >= 2:
        peak_year = int(full.idxmax())
        headline(f"Dated commissioning went from {plural(y.get(2020, 0), 'point')} in 2020 to "
                 f"{n(y.get(2021, 0))} in 2021, and peaked at {n(full.max())} in {peak_year}; "
                 f"{full.index.max()} added {n(full.iloc[-1])}.")
    else:
        busiest = int(y.idxmax())
        k = len(v["added"])
        headline(f"{plural(k, 'dated point')} in the selection {'was' if k == 1 else 'were'} commissioned in "
                 f"{f.start_year}-{f.end_year}, against {n(v['n_before'])} before; the busiest year was "
                 f"{busiest} with {n(y.max())}.")
    dated_share = len(dated) / max(len(v["snap"]), 1) * 100 if v["undated"] else None
    cum = prep.timeline(dated)
    chart(viz.timeline(cum, v["start"], v["end"]),
          alt=("Stacked area of the cumulative number of dated charging points per month, split by power class "
               "(slow, normal, fast, ultra-fast, unknown), with dotted vertical lines at policy dates: "
               + "; ".join(f"{e['label']} ({pd.Timestamp(e['date']):%b %Y})" for e in C.POLICY_EVENTS)
               + ". The selected period is shaded."),
          key="timeline",
          table=y.rename_axis("Commissioning year").rename("Dated points").reset_index())
    st.caption(
        ("Only " + pct(dated_share) + " of the selected points have a usable commissioning date. " if dated_share else "")
        + "Points taken out of service are not in the file, so the curve shows when today's points were "
        "commissioned, not the size of the network at each date. The May 2023 line marks the national "
        "count of 100,000 public points announced by Avere-France; this file's dated points stay below it "
        "because many records have no date. The jump in 2021 coincides with the duty to publish on "
        "data.gouv.fr, so part of it may reflect better reporting. Sources for each date are listed in "
        "data/SOURCES.md."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Dated points commissioned per year**")
        partial = this_year if this_year in y.index else None
        chart(viz.yearly_bars(y[y.index >= 2014], partial,
                              f"to {pd.Timestamp(tables['quality']['build_date']):%d %b}"),
              alt=("Bar chart of dated charging points commissioned each year from 2014. "
                   f"The {this_year} bar is lighter because the year is not over."),
              key="yearly")
    with right:
        ev = v["ev_sel"]
        st.markdown("**Rechargeable cars registered in the selection**")
        if ev.empty:
            st.info("No vehicle data for this selection.")
        else:
            e = ev.groupby("date")["ev"].sum()
            chart(viz.ev_stock(ev),
                  alt=(f"Line chart of the stock of battery-electric and plug-in hybrid cars, quarterly from "
                       f"{e.index.min():%B %Y} ({n(e.iloc[0])}) to {e.index.max():%B %Y} ({n(e.iloc[-1])})."),
                  key="evstock")
            st.caption(f"The fleet in the selection grew {e.iloc[-1] / e.iloc[0]:.1f}-fold between "
                       f"{e.index.min():%B %Y} and {e.index.max():%B %Y}. The two charts use separate axes on "
                       "purpose: cars and charging points are different units.")
