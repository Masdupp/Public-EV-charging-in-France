"""Data quality: what was removed, what is missing, what was checked."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config as C
from sections._ui import chart, headline, n, pct
from utils import viz


def render(q: dict) -> None:
    st.header("3. Data quality and limits", anchor="data-quality")
    raw, clean = q["raw_rows"], q["clean_rows"]
    dup = q["steps"][0]["rows_removed"]
    date_miss = q["date_missing_after"] / clean * 100
    headline(f"{n(dup)} duplicate records were removed from {n(raw)} rows, and {pct(date_miss)} of the "
             f"{n(clean)} points left have no usable commissioning date, which limits every chart over time.")

    st.markdown("**From raw file to analysis table**")
    steps = [{"Step": "Raw rows in the consolidated file", "Rows removed": None, "Rows left": raw}]
    left_n = raw
    for s in q["steps"]:
        left_n -= s["rows_removed"]
        steps.append({"Step": s["step"], "Rows removed": s["rows_removed"], "Rows left": left_n})
    steps = pd.DataFrame(steps)
    steps["Rows removed"] = steps["Rows removed"].map(lambda x: "" if x != x or x is None else f"{x:,.0f}")
    steps["Rows left"] = steps["Rows left"].map("{:,.0f}".format)
    st.table(steps.set_index("Step"))
    st.caption(f"{n(q['dup_groups'])} charging-point IDs appeared more than once. In "
               f"{pct(q['dup_cross_source_share'] * 100, 1)} of cases the copies came from different source "
               "files, typically an aggregator and the operator publishing the same point. The row with the most "
               f"recent update date was kept. {n(q['placeholder_id_rows'])} rows carry the schema's "
               "placeholder ID 'Non concerné'; they were checked for duplicates on their content instead.")

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Validation checks**")
        checks = pd.DataFrame([
            {"Check": "Département found from the INSEE commune code",
             "Result": f"{n(q['dep_by_insee'])} points"},
            {"Check": "Département found from coordinates (commune code missing or unusable)",
             "Result": f"{n(q['dep_by_coords'])} points"},
            {"Check": "Commune code and coordinates point to the same département",
             "Result": f"{pct(q['dep_check_agree'] * 100, 1)} of {n(q['dep_check_rows'])} points with both"},
            {"Check": "Coordinates outside every French bounding box",
             "Result": f"{n(q['coords_outside_france'])} points"},
            {"Check": f"Power declared in watts (≥ {C.WATT_THRESHOLD}), divided by 1,000",
             "Result": f"{n(q['power_watts_converted'])} points"},
            {"Check": f"Power of 0 or below {C.POWER_MIN_KW} kW, set to unknown",
             "Result": f"{n(q['power_zero_or_tiny'])} points"},
            {"Check": f"Power above {C.POWER_SUSPICIOUS_KW} kW, kept as ultra-fast but suspicious",
             "Result": f"{n(q['power_suspicious_high'])} points"},
            {"Check": f"Commissioning date before {C.DATE_MIN[:4]}, set to missing",
             "Result": f"{n(q['date_before_min'])} points"},
            {"Check": "Commissioning date in the future, set to missing",
             "Result": f"{n(q['date_in_future'])} points"},
            {"Check": "Vehicle register rows with no département", "Result": f"{n(q['ev_rows_no_dep'])} rows"},
        ])
        st.table(checks.set_index("Check"))
    with right:
        st.markdown("**Empty fields in the raw file**")
        miss = pd.Series(q["missing_share"])
        chart(viz.missingness(miss),
              alt=("Horizontal bar chart of the share of raw rows where each field is empty, sorted from the "
                   f"most incomplete. The commune code is empty in {pct(miss['code_insee_commune'] * 100)} of "
                   f"rows and the commissioning date in {pct(miss['date_mise_en_service'] * 100)}."),
              key="missing")

    st.markdown("**Known limits of the dataset**")
    st.markdown(
        f"- Publication is declarative. Operators publish their own files on data.gouv.fr and some publish "
        f"late or not at all, so a low figure can mean missing data rather than missing chargers. This matters "
        f"most for the overseas départements.\n"
        f"- {pct(date_miss)} of points have no commissioning date. Time charts and the catch-up comparison use "
        f"dated points only.\n"
        f"- The file lists points in service today. Points that were removed leave no trace, so the timeline "
        f"cannot show closures.\n"
        f"- 'Public' follows the schema: it includes car parks open to the public (supermarkets, hotels). "
        f"Home and workplace charging are not covered.\n"
        f"- The vehicle register counts battery-electric and plug-in hybrid cars together, located at the "
        f"holder's address. Fleet and leasing cars sit where companies are registered.\n"
        f"- Mayotte is left out because the Insee {q['pop_year']} reference population file has no figure "
        f"for it. Rechargeable cars are from {q['ev_date']}, population from {q['pop_year']}.\n"
        f"- data.gouv.fr announces that this consolidated file will be replaced by the national base on "
        f"transport.data.gouv.fr and removed after 31 December 2026; data/fetch_data.py will need a new slug then."
    )
