"""Chart builders. Every figure goes through `_style` so fonts, grid, hover
labels and margins stay consistent. Colors come from config (validated
ordinal blue ramp for power classes, one sequential blue scale for maps)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config as C

TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3de"
SURFACE = "#ffffff"
PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                 "toImageButtonOptions": {"format": "png", "scale": 2}}


def _style(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color=TEXT),
        margin=dict(l=10, r=10, t=40, b=10), showlegend=legend,
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(color=TEXT, size=13)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None,
                    font=dict(color=TEXT_2)),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, title_font=dict(color=TEXT_2),
                     tickfont=dict(color=TEXT_2))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, title_font=dict(color=TEXT_2),
                     tickfont=dict(color=TEXT_2))
    return fig


def _fmt(col: str, v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return C.INDICATORS[col][2].format(v)


# ---------------------------------------------------------------------------

def choropleth(t: pd.DataFrame, col: str, geojson: dict, height: int = 560) -> go.Figure:
    label, unit, _ = C.INDICATORS[col]
    d = t.copy()
    d["value_txt"] = d[col].map(lambda v: _fmt(col, v))
    fig = go.Figure()
    # Grey base layer so départements with no value (no EV data, empty filter) stay visible.
    all_codes = [f["id"] for f in geojson["features"]]
    fig.add_trace(go.Choropleth(geojson=geojson, locations=all_codes, z=[0] * len(all_codes),
                                featureidkey="properties.code", showscale=False, hoverinfo="skip",
                                colorscale=[[0, "#efeeea"], [1, "#efeeea"]],
                                marker_line_color="white", marker_line_width=0.5))
    v = d.dropna(subset=[col])
    fig.add_trace(go.Choropleth(
        geojson=geojson, locations=v["dep"], z=v[col], featureidkey="properties.code",
        colorscale=[[i / (len(C.SEQUENTIAL_SCALE) - 1), c] for i, c in enumerate(C.SEQUENTIAL_SCALE)],
        zmin=float(v[col].quantile(0.02)) if len(v) else 0, zmax=float(v[col].quantile(0.98)) if len(v) else 1,
        marker_line_color="white", marker_line_width=0.6,
        colorbar=dict(title=dict(text=unit, side="right", font=dict(color=TEXT_2)), thickness=12, len=0.75,
                      tickfont=dict(color=TEXT_2)),
        customdata=np.stack([v["dep_name"], v["value_txt"], v["points"], v["population"],
                             v["region"]], axis=-1),
        hovertemplate=("<b>%{customdata[0]}</b> (%{location}), %{customdata[4]}<br>"
                       f"{label}: <b>%{{customdata[1]}}</b><br>"
                       "Charging points: %{customdata[2]:,.0f}<br>"
                       "Population (2023): %{customdata[3]:,.0f}<extra></extra>"),
    ))
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor=SURFACE)
    fig = _style(fig, height=height, legend=False)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    return fig


def ranking(t: pd.DataFrame, col: str, ref: float, n: int = C.RANK_N) -> go.Figure:
    label, unit, _ = C.INDICATORS[col]
    d = t.dropna(subset=[col]).sort_values(col)
    n = min(n, len(d) // 2) if len(d) >= 2 else len(d)
    low, high = d.head(n), d.tail(n)
    fig = make_subplots(rows=1, cols=2, shared_xaxes=True, horizontal_spacing=0.18,
                        subplot_titles=(f"Lowest {n}", f"Highest {n}"))
    for i, part in enumerate([low.iloc[::-1], high], start=1):
        fig.add_trace(go.Bar(
            y=part["dep_name"], x=part[col], orientation="h", marker_color=C.ACCENT,
            marker_line_width=0, text=part[col].map(lambda v: _fmt(col, v)), textposition="outside",
            textfont=dict(color=TEXT_2, size=12), cliponaxis=False,
            customdata=np.stack([part["dep"], part["points"], part["population"]], axis=-1),
            hovertemplate=("<b>%{y}</b> (%{customdata[0]})<br>" + label + ": %{x:,.2f}<br>"
                           "Charging points: %{customdata[1]:,.0f}<br>"
                           "Population: %{customdata[2]:,.0f}<extra></extra>")), row=1, col=i)
        if ref == ref:
            fig.add_vline(x=ref, line_dash="dash", line_color=TEXT_2, line_width=1.5, row=1, col=i)
    xmax = float(d[col].max()) * 1.18 if len(d) else 1
    fig.update_xaxes(range=[0, max(xmax, ref * 1.1 if ref == ref else 0)], title_text=unit)
    if ref == ref:
        for xref in ("x", "x2"):
            fig.add_annotation(x=ref, y=0, yref="paper", xref=xref, text=f"France {_fmt(col, ref)}",
                               showarrow=False, yanchor="bottom", xanchor="left", xshift=4,
                               font=dict(color=TEXT_2, size=11), bgcolor="rgba(255,255,255,0.85)")
    fig.update_yaxes(title_text=None)
    fig.update_traces(width=0.7)
    fig = _style(fig, height=max(320, 34 * n + 80), legend=False)
    fig.update_layout(bargap=0.25)
    return fig


def timeline(cum: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, height: int = 440) -> go.Figure:
    fig = go.Figure()
    for cls in C.POWER_CLASSES + [C.UNKNOWN_POWER]:
        s = cum[cum["power_class"] == cls]
        if s.empty or s["cumulative"].max() == 0:
            continue
        fig.add_trace(go.Scatter(
            x=s["month"].dt.strftime("%Y-%m-%d"), y=s["cumulative"], name=cls, mode="lines", stackgroup="one",
            line=dict(width=0.5, color="white"), fillcolor=C.POWER_COLORS[cls],
            hovertemplate=f"{cls}: %{{y:,.0f}}<extra></extra>"))
    total = cum.groupby("month")["cumulative"].sum().reset_index()
    if not total.empty:
        fig.add_trace(go.Scatter(x=total["month"].dt.strftime("%Y-%m-%d"), y=total["cumulative"], name="All dated points",
                                 mode="lines", line=dict(color=TEXT, width=2),
                                 hovertemplate="All dated points: %{y:,.0f}<extra></extra>"))
    iso = lambda ts: pd.Timestamp(ts).strftime("%Y-%m-%d")  # noqa: E731  (plain strings serialise as dates)
    fig.add_vrect(x0=iso(start), x1=iso(end), fillcolor=C.PERIOD_SHADE, opacity=0.14, line_width=0,
                  annotation_text="Selected period", annotation_position="bottom left",
                  annotation_font=dict(color=TEXT_2, size=11))
    if not total.empty:
        x0 = total["month"].min()
        for k, ev in enumerate(C.POLICY_EVENTS):
            d = pd.Timestamp(ev["date"])
            if d < x0:
                continue
            fig.add_vline(x=iso(d), line_dash="dot", line_color=TEXT_2, line_width=1.2)
            fig.add_annotation(x=iso(d), y=1 - 0.09 * (k % 3) - 0.08, yref="paper", text=ev["label"],
                               showarrow=False, xanchor="right", xshift=-4,
                               font=dict(color=TEXT, size=11), bgcolor="rgba(255,255,255,0.85)")
    if not total.empty:
        x_start = max(total["month"].min(), pd.Timestamp("2014-01-01"))
        if x_start < total["month"].max():
            fig.update_xaxes(range=[iso(x_start), iso(total["month"].max() + pd.Timedelta(days=31))])
    fig.update_xaxes(title_text="Commissioning date (month)", type="date")
    fig.update_yaxes(title_text="Cumulative dated charging points (count)", rangemode="tozero")
    fig = _style(fig, height=height)
    fig.update_layout(hovermode="x unified")
    return fig


def yearly_bars(y: pd.Series, partial_year: int | None, partial_label: str) -> go.Figure:
    colors = [C.POWER_COLORS[C.POWER_CLASSES[0]] if yr == partial_year else C.ACCENT for yr in y.index]
    fig = go.Figure(go.Bar(x=y.index, y=y.values, marker_color=colors, marker_line_width=0,
                           hovertemplate="%{x}: %{y:,.0f} points<extra></extra>"))
    if partial_year in y.index:
        fig.add_annotation(x=partial_year, y=float(y.loc[partial_year]), text=partial_label,
                           showarrow=False, yanchor="bottom", font=dict(color=TEXT_2, size=11))
    fig.update_xaxes(title_text="Commissioning year", dtick=1)
    fig.update_yaxes(title_text="Dated points commissioned (count)")
    return _style(fig, height=340, legend=False)


def ev_stock(ev: pd.DataFrame) -> go.Figure:
    s = ev.groupby("date")["ev"].sum().reset_index()
    fig = go.Figure(go.Scatter(x=s["date"].dt.strftime("%Y-%m-%d"), y=s["ev"], mode="lines+markers", line=dict(color=C.ACCENT, width=2),
                               marker=dict(size=8, color=C.ACCENT, line=dict(color="white", width=2)),
                               hovertemplate="%{x|%d %b %Y}: %{y:,.0f} cars<extra></extra>"))
    fig.update_xaxes(title_text="Date of the register snapshot (quarterly)", type="date")
    fig.update_yaxes(title_text="Rechargeable cars registered (count)", rangemode="tozero")
    return _style(fig, height=340, legend=False)


def density_multiples(g: pd.DataFrame) -> go.Figure:
    classes = [c for c in C.POWER_CLASSES if c in set(g["power_class"].astype(str))]
    if not classes:
        return _style(go.Figure(), height=200, legend=False)
    fig = make_subplots(rows=1, cols=len(classes), subplot_titles=classes, horizontal_spacing=0.06)
    for i, cls in enumerate(classes, start=1):
        s = g[g["power_class"].astype(str) == cls].sort_values("band")
        fig.add_trace(go.Bar(
            x=[str(b).split(" (")[0] for b in s["band"]], y=s["per_100k"], marker_color=C.POWER_COLORS[cls],
            marker_line_width=0, text=s["per_100k"].map("{:,.0f}".format), textposition="outside",
            textfont=dict(color=TEXT_2, size=12), cliponaxis=False,
            customdata=np.stack([s["band"].astype(str), s["points"], s["n_deps"]], axis=-1),
            hovertemplate=("<b>%{customdata[0]}</b><br>" + cls + ": %{y:,.1f} per 100k inh.<br>"
                           "Points: %{customdata[1]:,.0f} in %{customdata[2]} départements<extra></extra>")),
            row=1, col=i)
        top = float(s["per_100k"].max()) if len(s) else 1
        fig.update_yaxes(range=[0, top * 1.25], row=1, col=i)
    fig.update_yaxes(title_text="Points per 100k inhabitants", row=1, col=1)
    fig.update_xaxes(title_text="Département density band")
    return _style(fig, height=380, legend=False)


def ev_scatter(t: pd.DataFrame) -> go.Figure:
    d = t.dropna(subset=["kw_per_ev", "ev_per_1000_inh"])
    fig = go.Figure()
    fig.add_hrect(y0=C.AFIR_KW_PER_PHEV, y1=C.AFIR_KW_PER_BEV, fillcolor="#a3a29c", opacity=0.22, line_width=0)
    fig.add_annotation(x=0.01, xref="paper", y=C.AFIR_KW_PER_BEV, text=f"AFIR fleet targets: {C.AFIR_KW_PER_PHEV} to {C.AFIR_KW_PER_BEV} kW per car",
                       showarrow=False, xanchor="left", yanchor="bottom", font=dict(color=TEXT_2, size=11))
    for name, grp, color in [("Mainland France", d[~d["overseas"]], C.ACCENT),
                             ("Overseas départements", d[d["overseas"]], C.ACCENT_2)]:
        if grp.empty:
            continue
        size = np.sqrt(grp["population"]) / np.sqrt(d["population"].max()) * 34 + 6
        fig.add_trace(go.Scatter(
            x=grp["ev_per_1000_inh"], y=grp["kw_per_ev"], mode="markers", name=name,
            marker=dict(size=size, color=color, opacity=0.8, line=dict(color="white", width=1.5)),
            customdata=np.stack([grp["dep_name"], grp["dep"], grp["points"], grp["ev"]], axis=-1),
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "Rechargeable cars: %{x:,.1f} per 1,000 inh. (%{customdata[3]:,.0f})<br>"
                           "Public power: %{y:,.2f} kW per car<br>"
                           "Charging points: %{customdata[2]:,.0f}<extra></extra>")))
    fig.update_xaxes(title_text="Rechargeable cars per 1,000 inhabitants")
    fig.update_yaxes(title_text="Public charging power per rechargeable car (kW)", rangemode="tozero")
    return _style(fig, height=460)


def convergence_dumbbell(g: pd.DataFrame, start_label: str, end_label: str) -> go.Figure:
    fig = go.Figure()
    for _, r in g.iterrows():
        fig.add_trace(go.Scatter(x=[r["before_100k"], r["after_100k"]], y=[r["quartile"]] * 2, mode="lines",
                                 line=dict(color="#c3c2b7", width=3), showlegend=False, hoverinfo="skip"))
    for col, name, color in [("before_100k", start_label, C.POWER_COLORS[C.POWER_CLASSES[0]]),
                             ("after_100k", end_label, C.POWER_COLORS[C.POWER_CLASSES[3]])]:
        fig.add_trace(go.Scatter(
            x=g[col], y=g["quartile"], mode="markers+text", name=name,
            marker=dict(size=16, color=color, line=dict(color="white", width=2)),
            text=g[col].map("{:,.0f}".format), textposition="top center", textfont=dict(color=TEXT_2, size=12),
            customdata=np.stack([g["n"], g["names"]], axis=-1),
            hovertemplate=("<b>%{y}</b> (%{customdata[0]} départements)<br>" + name +
                           ": %{x:,.1f} dated points per 100k inh.<br>e.g. %{customdata[1]}<extra></extra>")))
    fig.update_xaxes(title_text="Dated charging points per 100k inhabitants", rangemode="tozero")
    fig.update_yaxes(title_text=None, categoryorder="array", categoryarray=list(g["quartile"]))
    return _style(fig, height=340)


def points_map(s: pd.DataFrame, height: int = 520) -> go.Figure:
    fig = go.Figure()
    for cls in C.POWER_CLASSES + [C.UNKNOWN_POWER]:
        p = s[s["power_class"] == cls]
        if p.empty:
            continue
        fig.add_trace(go.Scattermap(
            lat=p["lat"], lon=p["lon"], mode="markers", name=cls,
            marker=dict(size=7 if cls in C.FAST_CLASSES else 5, color=C.POWER_COLORS[cls], opacity=0.8),
            customdata=np.stack([p["operator_group"].astype(str), p["power_kw"].fillna(np.nan),
                                 p["siting"].astype(str)], axis=-1),
            hovertemplate=(f"<b>{cls}</b><br>Power: %{{customdata[1]}} kW<br>Operator: %{{customdata[0]}}<br>"
                           "Siting: %{customdata[2]}<extra></extra>")))
    # Frame the mainland when most points are there; overseas points stay reachable by panning.
    main = s[s["lon"].between(-6, 10) & s["lat"].between(41, 52)]
    frame = main if len(main) >= 0.5 * len(s) else s
    lat0, lat1 = frame["lat"].quantile([0.01, 0.99]) if len(frame) else (42, 51)
    lon0, lon1 = frame["lon"].quantile([0.01, 0.99]) if len(frame) else (-5, 9)
    span = max(lat1 - lat0, (lon1 - lon0) * 0.7, 0.05)
    zoom = float(np.clip(np.log2(360 / span) - 1.2, 2, 12))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=float((lat0 + lat1) / 2),
                                                                   lon=float((lon0 + lon1) / 2)), zoom=zoom))
    fig = _style(fig, height=height)
    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
    return fig


def missingness(miss: pd.Series) -> go.Figure:
    m = (miss[miss > 0].sort_values() * 100)
    fig = go.Figure(go.Bar(x=m.values, y=m.index, orientation="h", marker_color=C.ACCENT, marker_line_width=0,
                           text=[f"{v:.0f}%" if v >= 1 else "<1%" for v in m.values], textposition="outside",
                           textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}% of raw rows empty<extra></extra>"))
    fig.update_xaxes(title_text="Raw rows with the field empty (%)", range=[0, 100])
    fig.update_yaxes(title_text=None, tickfont=dict(size=11))
    return _style(fig, height=max(300, 18 * len(m) + 60), legend=False)
