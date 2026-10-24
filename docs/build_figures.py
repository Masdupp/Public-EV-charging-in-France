"""Export the report figures and the numbers quoted in the LaTeX documents.

    pip install -r docs/requirements-docs.txt
    python docs/build_figures.py
    cd docs && latexmk -pdf report.tex storyboard.tex

Every number in report.tex and storyboard.tex is a macro defined in
docs/numbers.tex, written here from data/processed/. Nothing is typed by hand.
Figures use the app's own chart functions with the default filters
(all France, period from config.DEFAULT_START_YEAR to the build date).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C  # noqa: E402
from utils import io, prep, viz  # noqa: E402

OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"


def fmt(v, digits: int = 0) -> str:
    return f"{v:,.{digits}f}"


def default_view(t: dict) -> dict:
    points, deps, ev = t["points"], t["deps"], t["ev"]
    build = t["quality"]["build_date"]
    end_year = pd.Timestamp(build).year
    start, end, years = prep.period_bounds(C.DEFAULT_START_YEAR, end_year, build)
    mask = prep.base_mask(points, deps["dep"], C.POWER_CLASSES + [C.UNKNOWN_POWER],
                          t["quality"]["top_operators"] + [C.OTHER_OPERATORS])
    ev_dep, ev_date = prep.ev_at(ev, end)
    snap = prep.snapshot(points, mask, end, True)
    added = prep.additions(points, mask, start, end)
    tbl = prep.dep_indicators(snap, added, deps, ev_dep, years)
    return {"start": start, "end": end, "years": years, "snap": snap, "added": added, "t": tbl,
            "n_before": len(prep.dated_before(points, mask, start)),
            "dated": points[mask & points["commissioned"].notna()],
            "conv": prep.convergence(points, mask, tbl, start, end),
            "density": prep.by_density_and_class(snap, tbl)}


def export_figures(t: dict, v: dict) -> None:
    FIG.mkdir(exist_ok=True)
    figs = {
        "timeline": (viz.timeline(prep.timeline(v["dated"]), v["start"], v["end"], height=420), 1000, 420),
        "map": (viz.choropleth(v["t"], "per_100k", t["geojson"], height=620), 820, 620),
        "density": (viz.density_multiples(v["density"]), 1000, 380),
        "scatter": (viz.ev_scatter(v["t"]), 1000, 460),
        "convergence": (viz.convergence_dumbbell(v["conv"], f"End of {C.DEFAULT_START_YEAR - 1}",
                                                 f"{v['end']:%b %Y}"), 1000, 340),
        "ranking": (viz.ranking(v["t"].dropna(subset=["per_100k"]), "per_100k",
                                prep.totals(v["t"])["per_100k"]), 1000, 420),
    }
    for name, (fig, w, h) in figs.items():
        fig.write_image(FIG / f"{name}.pdf", width=w, height=h)
        print(f"[figure] docs/figures/{name}.pdf")


def macros(t: dict, v: dict) -> dict:
    q = t["quality"]
    s = prep.story_numbers(t["points"], t["deps"], t["ev"], q["build_date"])
    fr, main, over = s["fr"], s["main"], s["over"]
    mb = s["main_bands"]
    rural, dense = mb[C.DENSITY_LABELS[0]], mb[C.DENSITY_LABELS[-1]]
    dens = v["density"].assign(band=v["density"]["band"].astype(str), pc=v["density"]["power_class"].astype(str))
    ultra = dens[dens["pc"] == C.POWER_CLASSES[3]].set_index("band")["per_100k"]
    conv = s["conv"]
    tt = v["t"]
    ultra_pts = v["snap"][v["snap"]["power_class"] == C.POWER_CLASSES[3]]
    dle = s["dense_low_ev"]
    d = v["dated"]
    ultra_share = (d["power_class"] == C.POWER_CLASSES[3]).groupby(d["commissioned"].dt.year).mean() * 100
    m = {
        # build and sources
        "BuildDate": pd.Timestamp(q["build_date"]).strftime("%-d %B %Y"),
        "EvDate": pd.Timestamp(q["ev_date"]).strftime("%-d %B %Y"),
        "PopYear": str(q["pop_year"]),
        "NDeps": str(q["n_departements"]),
        # cleaning
        "RawRows": fmt(q["raw_rows"]), "RawCols": str(q["raw_columns"]),
        "DupRemoved": fmt(q["steps"][0]["rows_removed"]), "DupGroups": fmt(q["dup_groups"]),
        "DupCrossShare": fmt(q["dup_cross_source_share"] * 100, 0),
        "AfterDup": fmt(q["raw_rows"] - q["steps"][0]["rows_removed"] - q["steps"][1]["rows_removed"]),
        "PlaceholderRows": fmt(q["placeholder_id_rows"]),
        "NoDepRemoved": fmt(q["steps"][2]["rows_removed"]),
        "CleanRows": fmt(q["clean_rows"]),
        "WattsConverted": fmt(q["power_watts_converted"]), "ZeroPower": fmt(q["power_zero_or_tiny"]),
        "SuspiciousPower": fmt(q["power_suspicious_high"]), "SuspiciousKw": fmt(C.POWER_SUSPICIOUS_KW),
        "DateBeforeMin": fmt(q["date_before_min"]), "DateFuture": fmt(q["date_in_future"]),
        "DateMissing": fmt(q["date_missing_after"]),
        "DateMissingPct": fmt(q["date_missing_after"] / q["clean_rows"] * 100),
        "DatedPct": fmt(s["dated_share"]),
        "InseeMissingPct": fmt(q["missing_share"]["code_insee_commune"] * 100),
        "DepByInsee": fmt(q["dep_by_insee"]), "DepByCoords": fmt(q["dep_by_coords"]),
        "DepCheckRows": fmt(q["dep_check_rows"]), "DepAgreePct": fmt(q["dep_check_agree"] * 100, 1),
        "CoordsOutside": fmt(q["coords_outside_france"]),
        "OperatorsDistinct": fmt(q["operators_distinct"]), "TopN": str(C.TOP_N_OPERATORS),
        "EvRows": fmt(q["ev_rows"]), "EvNoDep": fmt(q["ev_rows_no_dep"]), "EvQuarters": str(q["ev_quarters"]),
        # national picture
        "FrPoints": fmt(fr["points"]), "FrPerHundredK": fmt(fr["per_100k"]),
        "FrPerHundredEv": fmt(fr["per_100_ev"], 1), "FrKwPerEv": fmt(fr["kw_per_ev"], 1),
        "FrFastShare": fmt(fr["fast_share"]), "FrFastPerHundredK": fmt(fr["fast_per_100k"]),
        "MainPerHundredK": fmt(main["per_100k"]), "OverPerHundredK": fmt(over["per_100k"]),
        "OverPoints": fmt(over["points"]), "OverPop": fmt(over["population"]),
        "LowestName": s["lowest"]["dep_name"], "LowestPoints": fmt(s["lowest"]["points"]),
        "LowestPop": fmt(s["lowest"]["population"]),
        "HighestName": s["highest"]["dep_name"], "HighestPerHundredK": fmt(s["highest"]["per_100k"]),
        "NBelowFr": str(s["n_below_fr"]),
        "TopTenPointsShare": fmt(s["top10_points_share"]), "TopTenPopShare": fmt(s["top10_pop_share"]),
        # growth
        "EvFirst": fmt(s["ev_first"]), "EvLast": fmt(s["ev_last"]),
        "EvFirstDate": f"{s['ev_first_date']:%B %Y}", "EvLastDate": f"{s['ev_last_date']:%B %Y}",
        "EvFold": fmt(s["ev_last"] / s["ev_first"], 1),
        "NTwentyTwenty": fmt(s["n2020"]), "NTwentyTwentyOne": fmt(s["n2021"]),
        "PeakN": fmt(s["peak_n"]), "PeakYear": str(s["peak_year"]),
        "LastFullN": fmt(s["last_full_n"]), "LastFullYear": str(s["last_full_year"]),
        "StartYear": str(C.DEFAULT_START_YEAR), "PivotYear": str(s["pivot_year"]), "EndYear": str(s["end_year"]),
        "EndMonth": f"{v['end']:%B %Y}",
        "AddedPeriod": fmt(len(v["added"])),
        "GrowthPeriod": fmt(prep.growth(v["n_before"], len(v["added"]))),
        # rural vs dense
        "RuralPerHundredK": fmt(rural["per_100k"]), "DensePerHundredK": fmt(dense["per_100k"]),
        "RuralFastPerHundredK": fmt(rural["fast_per_100k"]), "DenseFastPerHundredK": fmt(dense["fast_per_100k"]),
        "RuralPerHundredEv": fmt(rural["per_100_ev"], 1), "DensePerHundredEv": fmt(dense["per_100_ev"], 1),
        "RuralN": str(rural["n"]), "DenseN": str(dense["n"]),
        "RuralUltra": fmt(ultra.get(C.DENSITY_LABELS[0], float("nan"))),
        "DenseUltra": fmt(ultra.get(C.DENSITY_LABELS[-1], float("nan"))),
        "RuralMax": fmt(C.DENSITY_BINS[1]), "DenseMin": fmt(C.DENSITY_BINS[2]),
        # convergence
        "ConvBefore": fmt(s["conv_ratio_before"], 1), "ConvAfter": fmt(s["conv_ratio_after"], 1),
        "ConvLowBefore": fmt(conv["before_100k"].iloc[0]), "ConvLowAfter": fmt(conv["after_100k"].iloc[0]),
        "ConvHighBefore": fmt(conv["before_100k"].iloc[-1]), "ConvHighAfter": fmt(conv["after_100k"].iloc[-1]),
        "OverAdded": fmt(s["over_added"]), "OverPace": fmt(s["over_pace"], 1), "MainPace": fmt(s["main_pace"], 1),
        "SlowestName": s["slowest_main"]["dep_name"], "SlowestYears": fmt(s["slowest_main"]["years"]),
        "SlowestPace": fmt(s["slowest_main"]["pace_per_100k_year"], 1),
        # EV ownership
        "NBelowAfir": str(len(s["below_afir"])),
        "BelowAfirNames": ", ".join(s["below_afir"]["dep_name"]),
        "AfirLow": str(C.AFIR_KW_PER_PHEV), "AfirHigh": str(C.AFIR_KW_PER_BEV),
        "RhoEv": f"{tt[['ev_per_1000_inh', 'per_100_ev']].corr('spearman').iloc[0, 1]:.2f}".replace("-", "$-$"),
        "DenseLowName": s["dense_low"]["dep_name"], "DenseLowPerHundredK": fmt(s["dense_low"]["per_100k"]),
        "DenseLowEvNames": ", ".join(dle["dep_name"]),
        "DenseLowEvValues": ", ".join(fmt(x, 1) for x in dle["per_100_ev"]),
        "DenseLowEvFirst": dle["dep_name"].iloc[0], "DenseLowEvFirstValue": fmt(dle["per_100_ev"].iloc[0], 1),
        "ParisPerHundredK": fmt(s["paris"]["per_100k"]), "ParisFastShare": fmt(s["paris"]["fast_share"]),
        "UltraDedicatedShare": fmt((ultra_pts["siting"] == "Dedicated fast-charging station").mean() * 100),
        "MapSample": fmt(C.MAP_POINT_SAMPLE), "Seed": str(C.SEED),
        "UltraShareTwentyOne": fmt(ultra_share.get(2021, float("nan"))),
        "UltraShareLastFull": fmt(ultra_share.get(s["last_full_year"], float("nan"))),
    }
    return m


def write_macros(m: dict) -> None:
    lines = ["% Generated by docs/build_figures.py. Do not edit by hand."]
    for k, val in m.items():
        assert k.isalpha(), k
        val = str(val).replace("&", r"\&").replace("%", r"\%")
        lines.append(f"\\newcommand{{\\n{k}}}{{{val}}}")
    (OUT / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[macros] docs/numbers.tex ({len(m)} values)")


if __name__ == "__main__":
    tables = io.load_tables()
    view = default_view(tables)
    export_figures(tables, view)
    write_macros(macros(tables, view))
