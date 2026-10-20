"""Chart functions, so that every chart uses the same colours, fonts and annotations.

Each fuel and each price component keeps the same colour in every chart. Maps of a level use
shades of a single blue, maps of a gap use blue for negative and orange for positive values.
Charts are displayed through show(), which adds a written description and the data table,
so nothing relies on colour alone.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import BANDS, EVENTS, FUEL_LABELS

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
FUEL_COLORS = {"Gazole": PALETTE[0], "E10": PALETTE[1], "SP98": PALETTE[2],
               "SP95": PALETTE[3], "E85": PALETTE[5], "GPLc": PALETTE[6]}
COMPONENT_COLORS = {
    "Crude oil (Brent)": "#184f95",
    "Refining, logistics & retail": PALETTE[1],
    "TICPE excise": "#86b6ef",
    "VAT 20%": "#b7b6ae",
    "VAT": "#b7b6ae",
}
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = [[0.0, "#1c5cab"], [0.5, "#e6e5e0"], [1.0, "#c4471a"]]
MUTED = "#8a8984"


def base_layout(fig: go.Figure, title: str, y_title: str, x_title: str = "",
                height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 16},
               "y": 0.98, "yref": "container", "yanchor": "top"},
        height=height, margin={"l": 10, "r": 10, "t": 100 if legend else 50, "b": 10},
        hovermode="x unified", showlegend=legend,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "title": None},
        font={"family": "Inter, system-ui, sans-serif", "size": 13},
    )
    fig.update_xaxes(title=x_title or None, showgrid=False, ticks="outside")
    fig.update_yaxes(title=y_title, gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def add_events(fig: go.Figure, start, end, y_pos: float = 1.0) -> go.Figure:
    """Shaded bands + vertical reference lines for dated context events in the window."""
    for a, b, label in BANDS:
        a, b = max(pd.Timestamp(a), pd.Timestamp(start)), min(pd.Timestamp(b), pd.Timestamp(end))
        if a < b:
            fig.add_vrect(x0=a, x1=b, fillcolor="rgba(235,104,52,0.08)", line_width=0,
                          annotation_text=label, annotation_position="bottom left",
                          annotation_font={"size": 11, "color": MUTED})
    shown = 0
    for d, label in EVENTS:
        ts = pd.Timestamp(d)
        if pd.Timestamp(start) <= ts <= pd.Timestamp(end):
            fig.add_vline(x=ts, line_width=1, line_dash="dot", line_color=MUTED)
            frac = (ts - pd.Timestamp(start)) / (pd.Timestamp(end) - pd.Timestamp(start))
            fig.add_annotation(x=ts, y=y_pos - 0.06 * (shown % 2), yref="paper", text=label,
                               showarrow=False, xanchor="right" if frac > 0.8 else "left", font={"size": 11, "color": MUTED},
                               bgcolor="rgba(255,255,255,0)")
            shown += 1
    return fig


def show(fig: go.Figure, alt: str, data: pd.DataFrame | None = None, key: str | None = None):
    """Render a chart with its alt-text description and an optional accessible table."""
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"displaylogo": False, "toImageButtonOptions": {"scale": 2}})
    st.caption(f"Description: {alt}")
    if data is not None:
        data = data.round({c: 4 for c in data.select_dtypes("number").columns})
        with st.expander("Show the data behind this chart"):
            st.dataframe(data, width="stretch", hide_index=True)


# chart builders
def line_chart(df: pd.DataFrame, y: str, y_title: str, title: str, start, end,
               band: pd.DataFrame | None = None, hover_fmt: str = ".3f") -> go.Figure:
    fig = go.Figure()
    if band is not None and not band.empty:
        fig.add_trace(go.Scatter(x=band["week"], y=band["p90"], line={"width": 0},
                                 hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=band["week"], y=band["p10"], fill="tonexty",
                                 fillcolor="rgba(42,120,214,0.15)", line={"width": 0},
                                 name="80 % of stations (10th to 90th percentile)", hoverinfo="skip"))
    for fuel, g in df.groupby("fuel", observed=True, sort=False):
        fig.add_trace(go.Scatter(
            x=g["week"], y=g[y], mode="lines", name=FUEL_LABELS.get(fuel, fuel),
            line={"width": 2, "color": FUEL_COLORS.get(fuel)},
            hovertemplate=f"%{{y:{hover_fmt}}}",
        ))
    base_layout(fig, title, y_title)
    return add_events(fig, start, end)


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, x_title: str,
              color: str = PALETTE[0], text_fmt: str = ".3f", height: int = 420,
              hover: str | None = None) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], orientation="h", marker={"color": color, "cornerradius": 4},
        text=df[x].map(lambda v: f"{v:{text_fmt}}"), textposition="outside",
        hovertemplate=hover or f"%{{y}}: %{{x:{text_fmt}}}<extra></extra>",
    ))
    base_layout(fig, title, "", x_title, height=height, legend=False)
    fig.update_layout(hovermode="closest", bargap=0.25)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return fig


def stacked_area(dec: pd.DataFrame, components: list[str], title: str) -> go.Figure:
    fig = go.Figure()
    for c in components:
        fig.add_trace(go.Scatter(
            x=dec["month"], y=dec[c], stackgroup="one", name=c, mode="lines",
            line={"width": 0.5, "color": "rgba(255,255,255,0.8)"},
            fillcolor=COMPONENT_COLORS[c], hovertemplate="%{y:.3f} €/L",
        ))
    fig.add_trace(go.Scatter(x=dec["month"], y=dec["pump"], name="Observed pump price (after rebate)",
                             mode="lines", line={"color": "#0b0b0b", "width": 2, "dash": "dot"},
                             hovertemplate="%{y:.3f} €/L"))
    base_layout(fig, title, "€ per litre")
    return add_events(fig, dec["month"].min(), dec["month"].max())


def choropleth(df: pd.DataFrame, geojson: dict, color: str, title: str, legend_title: str,
               diverging: bool = False) -> go.Figure:
    if diverging:
        lim = float(df[color].abs().max() or 0.01)
        scale, rng = DIVERGING, (-lim, lim)
    else:
        scale, rng = SEQUENTIAL, (float(df[color].min()), float(df[color].max()))
    fig = go.Figure(go.Choropleth(
        geojson=geojson, featureidkey="properties.code", locations=df["dept"], z=df[color],
        zmin=rng[0], zmax=rng[1], colorscale=scale, marker={"line": {"width": 0.6, "color": "white"}},
        customdata=df[["name", "region", "price", "n"]],
        hovertemplate=("<b>%{customdata[0]}</b> (%{location}), %{customdata[1]}<br>"
                       "Mean price: %{customdata[2]:.3f} €/L<br>Stations: %{customdata[3]:.0f}"
                       f"<br>{legend_title}: %{{z:.3f}}<extra></extra>"),
        colorbar={"title": legend_title, "thickness": 12, "len": 0.8},
    ))
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(title={"text": title, "x": 0, "font": {"size": 16}}, height=560,
                      margin={"l": 0, "r": 0, "t": 50, "b": 0}, dragmode=False)
    return fig


def small_multiples(df: pd.DataFrame, title: str) -> go.Figure:
    """One mini line chart per region: regional gap to national mean, shared y axis."""
    from plotly.subplots import make_subplots
    regions = sorted(df["region"].unique())
    cols = 4
    rows = -(-len(regions) // cols)
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=regions, shared_xaxes=True,
                        shared_yaxes=True, vertical_spacing=0.08, horizontal_spacing=0.03)
    for i, r in enumerate(regions):
        g = df[df["region"] == r]
        fig.add_trace(go.Scatter(x=g["week"], y=g["gap"] * 100, mode="lines",
                                 line={"width": 1.5, "color": PALETTE[0]}, name=r,
                                 hovertemplate=f"{r}<br>%{{x|%d %b %Y}}: %{{y:+.1f}} c€/L<extra></extra>"),
                      row=i // cols + 1, col=i % cols + 1)
        fig.add_hline(y=0, line_width=1, line_color=MUTED, row=i // cols + 1, col=i % cols + 1)
    fig.update_annotations(font_size=12)
    fig.update_layout(title={"text": title, "x": 0, "font": {"size": 16}}, showlegend=False,
                      height=170 * rows + 60, margin={"l": 10, "r": 10, "t": 70, "b": 10},
                      font={"family": "Inter, system-ui, sans-serif", "size": 12})
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False, matches="y")
    fig.update_yaxes(title_text="c€/L vs national", col=1)
    return fig
