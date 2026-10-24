"""Insights, implications and next steps. Uses the national figures only."""
from __future__ import annotations

import streamlit as st

import config as C
from sections._ui import headline, n, names, pct


def render(s: dict) -> None:
    st.header("4. What this means for planners", anchor="conclusions")
    st.caption("All figures in this section use the full national file, whatever the sidebar shows.")
    fr, main, over = s["fr"], s["main"], s["over"]
    mb = s["main_bands"]
    rural, dense = mb.get(C.DENSITY_LABELS[0]), mb.get(C.DENSITY_LABELS[-1])
    slow = s["slowest_main"]
    paris = s["paris"]

    dle_names = names(s["dense_low_ev"]["dep_name"]) if len(s["dense_low_ev"]) else "none"
    headline(f"Mainland charging is spread more evenly than the starting hypothesis assumed; the clearest gaps "
             f"are the overseas départements, at {n(over['per_100k'])} points per 100k inhabitants against "
             f"{n(main['per_100k'])} on the mainland, and dense départements such as {dle_names} once EV "
             "ownership is counted.")

    st.markdown("**Key insights**")
    lines = []
    slowdown = s["last_full_n"] < s["peak_n"]
    lines.append(
        f"The first half of the hypothesis holds. Dated commissioning went from {n(s['n2020'])} points in 2020 "
        f"to {n(s['n2021'])} in 2021 and peaked at {n(s['peak_n'])} in {s['peak_year']}."
        + (f" It has eased since, to {n(s['last_full_n'])} in {s['last_full_year']}, although late "
           "publication may explain part of the drop." if slowdown else ""))
    lines.append(
        f"Deployment is less concentrated than expected. The 10 départements with the most points "
        f"({names(s['top10_names'], 3)}) hold {pct(s['top10_points_share'])} of all points for "
        f"{pct(s['top10_pop_share'])} of the population.")
    if rural and dense:
        lines.append(
            f"The second half does not hold: rural mainland départements are not behind. They have {n(rural['per_100k'])} points and "
            f"{n(rural['fast_per_100k'])} fast or ultra-fast points per 100k inhabitants; dense ones have "
            f"{n(dense['per_100k'])} and {n(dense['fast_per_100k'])}. Per rechargeable car the rural figure is "
            f"higher still: {rural['per_100_ev']:.1f} points per 100 cars against {dense['per_100_ev']:.1f}.")
    lines.append(
        f"The gap between départements is closing on dated points. At the end of {s['pivot_year']} the best "
        f"equipped quarter had {s['conv_ratio_before']:.1f} times more points per inhabitant than the least "
        f"equipped quarter; by {s['end_year']} the ratio was {s['conv_ratio_after']:.1f}.")
    lines.append(
        f"The overseas départements are not catching up. Together they added {n(s['over_added'])} dated points "
        f"since {C.DEFAULT_START_YEAR}, {s['over_pace']:.1f} per 100k inhabitants a year against "
        f"{s['main_pace']:.1f} on the mainland. {s['lowest']['dep_name']} lists {n(s['lowest']['points'])} "
        f"charging point{'s' if s['lowest']['points'] != 1 else ''}.")
    dl, dle = s["dense_low"], s["dense_low_ev"]
    if dl is not None:
        txt = (f"Dense départements have their own gap. {dl['dep_name']} has {n(dl['per_100k'])} points per 100k "
               f"inhabitants, the lowest of any dense département. Per rechargeable car the lowest dense figures "
               f"are in {names(dle['dep_name'])} ({', '.join(f'{x:.1f}' for x in dle['per_100_ev'])} points per "
               f"100 cars, France {fr['per_100_ev']:.1f}), partly because company cars are registered there.")
        if paris is not None:
            txt += (f" Paris has {n(paris['per_100k'])} points per 100k, but only {pct(paris['fast_share'])} "
                    "of them are fast.")
        lines.append(txt)
    for i, line in enumerate(lines, 1):
        st.markdown(f"{i}. {line}")

    st.markdown("**Implications**")
    st.markdown(
        f"Outside the overseas départements, the national question has moved from 'is there a charger' to "
        f"'is there the right charger in the right place'. France as a whole offers {fr['kw_per_ev']:.1f} kW "
        f"of public power per rechargeable car, above the AFIR fleet references of {C.AFIR_KW_PER_PHEV} to "
        f"{C.AFIR_KW_PER_BEV} kW. Only {len(s['below_afir'])} départements fall below {C.AFIR_KW_PER_PHEV} kW per car "
        f"({names(s['below_afir']['dep_name'], 6)}), so a département-level average will rarely flag a shortage "
        "on the mainland. "
        "Planners writing or revising an SDIRVE will learn more from the commune or EPCI scale, from fast "
        "charging in dense areas where many drivers cannot charge at home, and from usage data."
    )
    st.markdown(
        f"For the overseas départements the first step is to check the data. Their {n(over['points'])} listed "
        f"points for {n(over['population'])} inhabitants may reflect operators that do not publish on "
        "data.gouv.fr as much as a real shortage. A prefecture or regional energy syndicate can ask local "
        "operators whether their points are declared."
    )
    if slow is not None:
        st.markdown(
            f"On the mainland the slowest catch-up is in {slow['dep_name']}: at its pace since "
            f"{C.DEFAULT_START_YEAR}, {slow['pace_per_100k_year']:.1f} dated points per 100k a year, it would "
            f"take {slow['years']:.0f} years to reach today's national level of {n(fr['per_100k'])}. That figure "
            "is an upper bound, because undated points are not counted in the pace."
        )

    st.markdown("**Next steps**")
    st.markdown(
        "- Join the dynamic IRVE feed (live availability) to measure use, not only presence.\n"
        "- Split the vehicle register into battery-electric and plug-in hybrid cars to apply the two AFIR "
        "ratios properly.\n"
        "- Add the national road network to test whether fast charging follows motorway corridors.\n"
        "- Repeat the analysis at EPCI level, where most SDIRVE are written."
    )
    st.divider()
    st.caption("Built by Oscar Masdupuy, EFREI Paris, Data Visualization 2026. "
               "Code and method: see README.md in the repository.")
