"""Hook and context: why the question matters and who it is for."""
from __future__ import annotations

import streamlit as st

from sections._ui import CSS, headline, n


def render(s: dict, q: dict) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    fr, low = s["fr"], s["lowest"]
    st.title("Public EV charging in France: where it lags, and how fast the gap is closing")
    st.caption(f"Data: Base nationale des IRVE (data.gouv.fr), file of {q['build_date']} · Insee population "
               f"{q['pop_year']} · rechargeable cars registered at {s['ev_last_date']:%d %B %Y} (Agence ORE / SDES) "
               "· Licence Ouverte 2.0")

    headline(f"France lists {n(fr['points'])} public charging points, {n(fr['per_100k'])} for every "
             f"100,000 inhabitants, but {low['dep_name']} lists {n(low['points'])} for "
             f"{n(low['population'])} people.")

    growth = s["ev_last"] / s["ev_first"]
    st.markdown(
        f"The number of rechargeable cars on French roads went from {n(s['ev_first'])} in "
        f"{s['ev_first_date']:%B %Y} to {n(s['ev_last'])} in {s['ev_last_date']:%B %Y}, a "
        f"{growth:.1f}-fold increase. Those drivers need somewhere to charge outside home. "
        "Since the 2019 mobility law (LOM), départements, intercommunalities and energy syndicates can "
        "write a local master plan for public charging (SDIRVE), and they need to know where their "
        "territory stands against the rest of the country."
    )
    st.markdown(
        f"This app is written for those planners. It compares the {q['n_departements']} départements on charging points "
        "per inhabitant and per rechargeable car, separates slow and fast charging, and checks whether "
        "the least equipped départements are catching up. Raw counts are never compared directly, "
        "because they mostly reflect population."
    )
    st.markdown(
        "The working hypothesis going in: deployment sped up after 2021 but stayed concentrated in large "
        "metropolitan areas and along motorways, leaving rural départements behind on fast charging. "
        "The sections below test it, and the conclusions say which part holds."
    )
    with st.expander("How to read this app"):
        st.markdown(
            "- The sidebar filters drive every section from the KPI header down to the station map. "
            "Change the area, the commissioning period, the power class or the operators.\n"
            "- The introduction and the conclusions use the full national file, so the story does not "
            "move while you explore.\n"
            "- A *charging point* (point de charge) is one connector position that can charge one car at a "
            "time. A station usually has several.\n"
            "- 'Fast' means above 22 kW and below 150 kW; 'ultra-fast' means 150 kW or more. "
            "In the KPIs, 'fast' covers both."
        )
