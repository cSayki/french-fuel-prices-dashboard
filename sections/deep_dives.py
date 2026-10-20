"""Detailed tabs: price breakdown and pass-through, regional comparison, scenarios."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import DECOMPOSABLE, FUEL_LABELS, LITRES_PER_BARREL, SEEDS, TICPE_EUR_L, VAT
from utils.io import load_geojson
from utils.prep import (asymmetry_significant, decompose, dept_period, lag_correlation,
                        pass_through, region_weekly, road_premium, what_if_price)
from utils.viz import (COMPONENT_COLORS, FUEL_COLORS, MUTED, PALETTE, add_events, bar_chart,
                       base_layout, choropleth, show, small_multiples, stacked_area)

COMPONENTS = ["Crude oil (Brent)", "Refining, logistics & retail", "TICPE excise", "VAT 20%"]


def _decomposable_fuel(f) -> str:
    if f.main_fuel in DECOMPOSABLE:
        return f.main_fuel
    st.info(f"{FUEL_LABELS[f.main_fuel]} is not made from crude oil in the same way and is taxed "
            "differently, so this tab shows diesel instead.")
    return "Gazole"


# oil and pump
def render_drivers(tables: dict, f) -> None:
    fuel = _decomposable_fuel(f)
    dec_all = decompose(tables["monthly_with_brent"], fuel)
    dec = dec_all[dec_all["month"].between(f.start - pd.offsets.MonthBegin(1), f.end)]
    if len(dec) < 6:
        st.warning("This tab needs a date range of at least 6 months.")
        return
    shares = dec[COMPONENTS].div(dec[COMPONENTS].sum(axis=1), axis=0).mean()
    margin = dec_all.set_index("month")["Refining, logistics & retail"]
    m_1921 = margin["2019":"2021"].mean()
    m_last = margin.iloc[-12:].mean()

    st.subheader(f"Crude oil is only about {shares['Crude oil (Brent)'] * 100:.0f} % of the "
                 f"price of {FUEL_LABELS[fuel].lower()}, while taxes make up about "
                 f"{(shares['TICPE excise'] + shares['VAT 20%']) * 100:.0f} %.")
    st.markdown(
        "Each litre sold in France pays a fixed excise tax called TICPE, and then 20 % VAT on the "
        "whole amount, the excise included. What is left is the crude oil itself plus everything "
        "needed to refine it, transport it, store it and sell it, margins included. I rebuilt this "
        "split for every month from the average pump price and the Brent price.")
    with st.expander("Method and assumptions", expanded=False):
        st.markdown(
            f"The crude oil part is the monthly Brent price in euros per barrel divided by "
            f"{LITRES_PER_BARREL} litres. The excise is {TICPE_EUR_L[fuel]:.4f} €/L for "
            f"{FUEL_LABELS[fuel].lower()}, which is the metropolitan rate including the regional "
            "part; it has not changed since 2018 and I assume it stayed constant. VAT is 20 % of "
            "the price before VAT, which means one sixth of the pump price. In 2022 the State paid "
            "a rebate of 18, then 30, then 10 cents per litre, and the prices declared by stations "
            "already include it, so I add it back before splitting the price. The refining, "
            "logistics and retail part is simply what remains. It includes the refining margin, "
            "the cost of blending biofuels, storage obligations, transport and the station's gross "
            "margin, so it should not be read as a profit.")
    fig = stacked_area(dec, COMPONENTS, f"What a litre of {FUEL_LABELS[fuel].lower()} is made of, "
                                        "monthly (€/L)")
    show(fig, alt=(f"Stacked area chart of the monthly price of {FUEL_LABELS[fuel].lower()} split "
                   "into four layers, from bottom to top: crude oil, refining and retail, excise "
                   "and VAT. A dotted line shows the actual pump price, which goes below the stack "
                   "in 2022 because of the State rebate. The excise layer is flat, so almost all "
                   "the variation comes from crude oil and from the refining and retail layer."),
         data=dec[["month", "pump", "rebate"] + COMPONENTS], key="drivers_stack")

    c1, c2, c3 = st.columns(3)
    c1.metric("Refining and retail, 2019 to 2021", f"{m_1921 * 100:.0f} c€/L")
    c2.metric("Refining and retail, last 12 months", f"{m_last * 100:.0f} c€/L",
              f"{(m_last - m_1921) * 100:+.0f} c€/L", delta_color="inverse")
    c3.metric("Taxes per litre, latest month",
              f"{(dec['TICPE excise'].iloc[-1] + dec['VAT 20%'].iloc[-1]):.2f} €")
    st.warning(
        "Oil explains most of the ups and downs, but the part between the barrel and the pump has "
        f"grown from about {m_1921 * 100:.0f} to about {m_last * 100:.0f} cents per litre. For "
        "diesel this fits with the tight European diesel market since 2022, made worse when the EU "
        "stopped importing refined products from Russia in February 2023. The data cannot tell "
        "refinery margins apart from station margins, so this is a limit of the analysis and not an "
        "accusation against anyone.")

    st.markdown("---")
    st.subheader("Do prices rise faster than they fall?")
    st.markdown(
        "Economists call this the rockets and feathers effect: prices would shoot up when oil gets "
        "more expensive and drift down slowly when it gets cheaper. Each dot below is one month.")
    pt = pass_through(dec_all)
    left, right = st.columns([3, 2])
    with left:
        d = pt.data
        d["direction"] = np.where(d["db"] >= 0, "Crude went up", "Crude went down")
        fig = go.Figure()
        for lab, col in [("Crude went up", PALETTE[7]), ("Crude went down", PALETTE[0])]:
            g = d[d["direction"] == lab]
            fig.add_trace(go.Scatter(
                x=g["db"] * 100, y=g["dp"] * 100, mode="markers", name=lab,
                marker={"size": 9, "color": col, "line": {"width": 1.5, "color": "white"}},
                customdata=g["month"].dt.strftime("%b %Y"),
                hovertemplate="%{customdata}<br>Change in crude %{x:+.1f} c€/L<br>"
                              "Change in pre-tax price %{y:+.1f} c€/L<extra></extra>"))
            if len(g) > 2:
                b = np.polyfit(g["db"], g["dp"], 1)
                xs = np.linspace(g["db"].min(), g["db"].max(), 10)
                fig.add_trace(go.Scatter(x=xs * 100, y=np.polyval(b, xs) * 100, mode="lines",
                                         line={"color": col, "width": 2, "dash": "dash"},
                                         name=f"Fit, {lab.lower()} (slope {b[0]:.2f})",
                                         hoverinfo="skip"))
        lim = max(abs(d["db"]).max(), abs(d["dp"]).max()) * 100 * 1.05
        fig.add_trace(go.Scatter(x=[-lim, lim], y=[-lim, lim], mode="lines",
                                 name="Full pass-through (one for one)",
                                 line={"color": MUTED, "width": 1, "dash": "dot"}, hoverinfo="skip"))
        base_layout(fig, "Monthly change in crude cost and in the pre-tax pump price (c€/L)",
                    "Change in pre-tax pump price (c€/L)", "Change in crude oil cost (c€/L)",
                    height=460)
        fig.update_layout(hovermode="closest")
        show(fig, alt=("Scatter plot with one dot per month. The horizontal axis is the change in "
                       "the cost of crude per litre and the vertical axis is the change in the "
                       "pump price before taxes. Red dots are months when crude went up, blue dots "
                       "months when it went down, each group with its own dashed fitted line. The "
                       "dotted diagonal is what full pass-through would look like."),
             data=d[["month", "db", "dp"]].rename(columns={"db": "change in crude €/L",
                                                           "dp": "change in pre-tax price €/L"}),
             key="drivers_scatter")
    with right:
        st.metric("Pass-through when crude rises (same and next month)",
                  f"{pt.up:.2f}", f"± {1.96 * pt.up_se:.2f} (95 % interval)", delta_color="off",
                  help="1.00 means that each cent of increase in crude reaches the pump within "
                       "two months.")
        st.metric("Pass-through when crude falls (same and next month)",
                  f"{pt.down:.2f}", f"± {1.96 * pt.down_se:.2f} (95 % interval)", delta_color="off")
        lc = lag_correlation(dec_all)
        fig = bar_chart(lc.assign(lab=lc["lag_months"].map(
                            lambda k: "same month" if k == 0 else f"{k} month{'s' if k > 1 else ''} later")),
                        "correlation", "lab", "Correlation between pump and crude changes",
                        "correlation coefficient", color=PALETTE[0], text_fmt=".2f", height=280)
        fig.update_xaxes(range=[min(-0.35, lc["correlation"].min() - 0.25), 1.1])
        show(fig, alt="Bars with the correlation between monthly changes in the pump price and "
                      "changes in crude 0 to 4 months earlier. The same-month correlation is much "
                      "higher than the others, so most of the reaction happens within a month.",
             key="drivers_lag")
    if asymmetry_significant(pt):
        verdict = ("The gap between the two is statistically significant (difference "
                   f"{pt.up - pt.down:.2f} ± {1.96 * pt.diff_se:.2f}), which supports the rockets "
                   "and feathers idea, but with monthly data only I would not push it too far.")
    else:
        verdict = ("The two confidence intervals overlap, so with monthly data I cannot really say "
                   "that prices rise faster than they fall.")
    st.info(
        f"Over {pt.n} months of {FUEL_LABELS[fuel].lower()}, increases in crude are passed on at "
        f"{pt.up:.2f} and decreases at {pt.down:.2f}. {verdict} Most of the adjustment happens in "
        "the same month, as the bars on the right show. A value above 1 means that refined fuel "
        "prices moved even more than crude, which is what happened to diesel in 2022.")


# regions
def render_geography(tables: dict, f) -> None:
    fuel = f.main_fuel
    geo = load_geojson()
    names = {ft["properties"]["code"]: ft["properties"]["nom"] for ft in geo["features"]}
    dp = dept_period(tables["dept_road_weekly"], fuel, f.road, f.start, f.end)
    if dp.empty:
        st.warning("No data for this selection.")
        return
    dp["name"] = dp["dept"].map(names).fillna(dp["dept"])
    nat_mean = np.average(dp["price"], weights=dp["n"])
    dp["gap"] = dp["price"] - nat_mean
    dp_view = dp[dp["region"].isin(f.regions)] if f.regions else dp
    if dp_view.empty:
        st.warning("No station matches this region and station type. Brittany for example has no "
                   "toll motorway, so it has no motorway stations. Try another station type.")
        return
    hi, lo = dp_view.loc[dp_view["price"].idxmax()], dp_view.loc[dp_view["price"].idxmin()]
    st.subheader(f"The same litre of {FUEL_LABELS[fuel].lower()} costs "
                 f"{(hi['price'] - lo['price']) * 100:.0f} cents more in {hi['name']} than in "
                 f"{lo['name']}.")
    st.caption(f"Average over the last 4 weeks of the selected period (up to {f.end:%d %b %Y}), "
               f"{'all stations' if f.road == 'All' else f.road.lower() + ' stations'}. Corsica "
               "has its own fuel taxes (VAT is 13 % there) and higher transport costs, so its "
               "position changes a lot over time, as the small charts further down show.")

    view = st.radio("Map shows", ["Gap to national average (c€/L)", "Average price (€/L)",
                                  f"Change since {f.start:%b %Y} (c€/L)"], horizontal=True)
    m = dp_view.copy()
    if view.startswith("Gap"):
        m["z"] = m["gap"] * 100
        fig = choropleth(m, geo, "z", f"{FUEL_LABELS[fuel]}, gap to the national average",
                         "c€/L vs national", diverging=True)
        alt_tail = "Blue departments are cheaper than the national average and orange ones dearer."
    elif view.startswith("Average"):
        m["z"] = m["price"]
        fig = choropleth(m, geo, "z", f"{FUEL_LABELS[fuel]}, average price by department", "€/L")
        alt_tail = "The darker the blue, the more expensive."
    else:
        m["z"] = m["change"] * 100
        fig = choropleth(m, geo, "z", f"{FUEL_LABELS[fuel]}, price change by department", "c€/L",
                         diverging=True)
        alt_tail = "Orange departments went up more than the others, blue ones less."
    left, right = st.columns([3, 2])
    with left:
        show(fig, alt=(f"Map of the {len(m)} metropolitan departments coloured by "
                       f"{view.lower()}. The most expensive is {hi['name']} at "
                       f"{hi['price']:.3f} €/L and the cheapest is {lo['name']} at "
                       f"{lo['price']:.3f} €/L. {alt_tail}"),
             data=m[["dept", "name", "region", "price", "gap", "change", "n"]]
                  .sort_values("price", ascending=False),
             key="geo_map")
    with right:
        n_top = st.slider("Number of departments at each end", 5, 15, 8)
        r = pd.concat([m.nlargest(n_top, "price").assign(kind="Most expensive"),
                       m.nsmallest(n_top, "price").assign(kind="Cheapest")])
        r["label"] = r["name"] + " (" + r["dept"] + ")"
        r["gap_c"] = r["gap"] * 100
        fig = go.Figure()
        for kind, col in [("Most expensive", PALETTE[1]), ("Cheapest", PALETTE[0])]:
            g = r[r["kind"] == kind]
            fig.add_trace(go.Bar(x=g["gap_c"], y=g["label"], orientation="h", name=kind,
                                 marker={"color": col, "cornerradius": 4},
                                 text=g["price"].map(lambda v: f"{v:.3f} €"), textposition="auto",
                                 hovertemplate="%{y}: %{x:+.1f} c€/L vs national<extra></extra>"))
        base_layout(fig, "Departments furthest from the national average", "",
                    "c€/L compared with the national average", height=560)
        fig.update_layout(hovermode="closest")
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        show(fig, alt=f"Bars for the {n_top} most expensive departments (orange, to the right) "
                      f"and the {n_top} cheapest (blue, to the left), measured as the gap to the "
                      "national average in cents per litre. The labels give the actual price.",
             key="geo_rank")

    st.markdown("---")
    st.subheader("How much more you pay on the motorway")
    rp = road_premium(tables["dept_road_weekly"], fuel, f.regions, f.start, f.end)
    if not rp.empty:
        latest = rp["premium"].iloc[-4:].mean()
        c1, c2 = st.columns([1, 3])
        c1.metric("Motorway extra cost, last 4 weeks", f"{latest * 100:.0f} c€/L",
                  f"about {latest * 50:.0f} € for a 50 L tank", delta_color="off")
        c1.caption("Motorway stations are run under concessions, have few competitors and have "
                   "to stay open day and night. The gap is there all the time, not only during "
                   "crises.")
        fig = go.Figure(go.Scatter(x=rp["week"], y=rp["premium"] * 100, mode="lines",
                                   line={"color": FUEL_COLORS.get(fuel, PALETTE[0]), "width": 2},
                                   name="Motorway minus road", hovertemplate="%{y:.1f} c€/L"))
        base_layout(fig, f"Motorway price minus road price, {FUEL_LABELS[fuel].lower()} "
                         "(weekly, c€/L)", "c€/L", legend=False, height=340)
        add_events(fig, f.start, f.end)
        with c2:
            show(fig, alt=f"Line showing the weekly gap between motorway stations and other "
                          f"stations for {FUEL_LABELS[fuel].lower()}. It is currently about "
                          f"{latest * 100:.0f} cents per litre.", data=rp, key="geo_premium")

    st.markdown("---")
    st.subheader("Each region compared with the national average")
    rw = region_weekly(tables["dept_road_weekly"], fuel, f.road, f.start, f.end)
    if f.regions:
        rw = rw[rw["region"].isin(f.regions)]
    if rw.empty:
        return
    fig = small_multiples(rw, f"{FUEL_LABELS[fuel]}, regional price minus national average (c€/L)")
    gaps = rw.groupby("region")["gap"].mean().sort_values()
    show(fig, alt=(f"Grid of {rw['region'].nunique()} small line charts, one per region, all on "
                   "the same scale, showing each week how far the region is from the national "
                   f"average in cents per litre. On average the cheapest region is {gaps.index[0]} "
                   f"({gaps.iloc[0] * 100:+.1f} c€) and the most expensive is {gaps.index[-1]} "
                   f"({gaps.iloc[-1] * 100:+.1f} c€)."),
         data=gaps.mul(100).rename("average gap in c€/L").reset_index(), key="geo_multiples")

    st.markdown("---")
    st.subheader("Station by station, latest price")
    snap = tables["stations_snapshot"]
    s = snap[(snap["fuel"] == fuel) & snap["coords_valid"]]
    if f.regions:
        s = s[s["region"].isin(f.regions)]
    if f.road != "All":
        s = s[s["road"] == f.road]
    if s.empty:
        st.info("No station with a recent price for this selection.")
        return
    c1, c2 = st.columns([2, 1])
    with c2:
        fig = go.Figure(go.Histogram(x=s["price"], xbins={"size": 0.01}, marker={"color": PALETTE[0]},
                                     hovertemplate="%{x} €/L: %{y} stations<extra></extra>"))
        med = s["price"].median()
        fig.add_vline(x=med, line_dash="dot", line_color=MUTED,
                      annotation_text=f"median {med:.3f} €", annotation_position="top right")
        base_layout(fig, "Distribution of station prices", "number of stations", "€ per litre",
                    legend=False, height=380)
        fig.update_layout(hovermode="closest", bargap=0.05)
        show(fig, alt=f"Histogram of the latest price at {len(s):,} stations. The median is "
                      f"{med:.3f} €/L, the 10th percentile {s['price'].quantile(.1):.3f} and the "
                      f"90th percentile {s['price'].quantile(.9):.3f}.", key="geo_hist")
    with c1:
        sample = s.sample(min(len(s), SEEDS["map_sample_stations"]), random_state=SEEDS["random_seed"])
        fig = go.Figure(go.Scattermap(
            lat=sample["lat"], lon=sample["lon"], mode="markers",
            marker={"size": 6, "color": sample["price"],
                    "colorscale": [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]],
                    "cmin": s["price"].quantile(.05), "cmax": s["price"].quantile(.95),
                    "colorbar": {"title": "€/L", "thickness": 12}},
            customdata=np.stack([sample["city"].fillna(""), sample["road"], sample["price"]], axis=1),
            hovertemplate="%{customdata[0]}, %{customdata[1]}<br>%{customdata[2]:.3f} €/L<extra></extra>"))
        fig.update_layout(map={"style": "carto-positron", "center": {"lat": 46.6, "lon": 2.4},
                               "zoom": 4.4}, height=520, margin={"l": 0, "r": 0, "t": 40, "b": 0},
                          title={"text": f"Random sample of {len(sample):,} stations (seed "
                                         f"{SEEDS['random_seed']})", "x": 0, "font": {"size": 16}})
        by_region = s.groupby("region")["price"].median().sort_values()
        show(fig, alt=f"Map of {len(sample):,} stations picked at random and coloured by their "
                      "latest price, darker meaning more expensive. You can zoom in. The region "
                      f"with the highest median is {by_region.index[-1]} "
                      f"({by_region.iloc[-1]:.3f} €/L) and the lowest is {by_region.index[0]} "
                      f"({by_region.iloc[0]:.3f} €/L).", key="geo_stations")


# scenarios
def render_what_if(tables: dict, f) -> None:
    fuel = _decomposable_fuel(f)
    dec = decompose(tables["monthly_with_brent"], fuel)
    last = dec.iloc[-1]
    margin_last = last["Refining, logistics & retail"]
    margin_12m = dec["Refining, logistics & retail"].iloc[-12:].mean()
    margin_1921 = dec.set_index("month")["Refining, logistics & retail"]["2019":"2021"].mean()

    st.subheader("What would your fuel bill look like if things changed?")
    st.markdown(f"The sliders let you build a scenario for {FUEL_LABELS[fuel].lower()}. The "
                "calculation is the same as in the price breakdown: crude, plus refining and "
                "retail, plus excise, with VAT on top. By default everything is set to the latest "
                f"month for which Brent is available ({last['month']:%B %Y}).")
    c1, c2 = st.columns([2, 3])
    with c1:
        brent = st.slider("Brent crude (€/barrel)", 20, 160, int(round(last["brent_eur_bbl"])), 1,
                          help="Between 2019 and 2026 Brent went from about 20 € (April 2020) to "
                               "about 100 € (2022 and 2026).")
        margin_choice = st.radio("Refining and retail part",
                                 [f"Latest month ({margin_last * 100:.0f} c€/L)",
                                  f"Average of the last 12 months ({margin_12m * 100:.0f} c€/L)",
                                  f"2019 to 2021 level ({margin_1921 * 100:.0f} c€/L)", "Custom"])
        if margin_choice.startswith("Latest"):
            margin = margin_last
        elif margin_choice.startswith("Average"):
            margin = margin_12m
        elif margin_choice.startswith("2019"):
            margin = margin_1921
        else:
            margin = st.slider("Custom value (c€/L)", 10, 90, int(margin_last * 100)) / 100
        ticpe = st.slider("TICPE excise (c€/L)", 0.0, 80.0, TICPE_EUR_L[fuel] * 100, 0.5,
                          help="Current metropolitan rate. Lower it to simulate a tax cut.") / 100
        vat = st.slider("VAT rate (%)", 0.0, 20.0, VAT * 100, 0.5) / 100
        st.markdown("**Your driving**")
        km = st.number_input("Kilometres per year", 1000, 60000, 13000, 500,
                             help="A private car in France does around 12 000 to 13 000 km a year.")
        cons = st.number_input("Consumption (L/100 km)", 3.0, 15.0, 6.0, 0.1)

    # the baseline uses the latest month, so it gives back the observed average pump price
    base = what_if_price(last["brent_eur_bbl"], margin_last, TICPE_EUR_L[fuel], VAT)
    scen = what_if_price(brent, margin, ticpe, vat)
    litres = km * cons / 100
    with c2:
        k1, k2, k3 = st.columns(3)
        k1.metric("Scenario pump price", f"{scen['pump']:.3f} €/L",
                  f"{(scen['pump'] - base['pump']) * 100:+.1f} c€ vs {last['month']:%b %Y}",
                  delta_color="inverse")
        k2.metric("Your yearly fuel bill", f"{scen['pump'] * litres:,.0f} €".replace(",", " "),
                  f"{(scen['pump'] - base['pump']) * litres:+,.0f} € per year".replace(",", " "),
                  delta_color="inverse")
        k3.metric("Taxes in that bill", f"{(scen['TICPE excise'] + scen['VAT']) * litres:,.0f} €"
                  .replace(",", " "),
                  f"{(scen['TICPE excise'] + scen['VAT']) / scen['pump'] * 100:.0f} % of the price",
                  delta_color="off")
        parts = ["Crude oil (Brent)", "Refining, logistics & retail", "TICPE excise", "VAT"]
        comp = pd.DataFrame({"component": parts,
                             "Today": [base[c] for c in parts],
                             "Scenario": [scen[c] for c in parts]})
        fig = go.Figure()
        for _, row in comp.iterrows():
            fig.add_trace(go.Bar(y=["Today", "Scenario"],
                                 x=[row["Today"], row["Scenario"]], orientation="h",
                                 name=row["component"],
                                 marker={"color": COMPONENT_COLORS[row["component"]]},
                                 hovertemplate=f"{row['component']}: %{{x:.3f}} €/L<extra></extra>"))
        base_layout(fig, "What the litre is made of (€/L)", "", "€ per litre", height=300)
        fig.update_layout(barmode="stack", hovermode="closest", bargap=0.35)
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
        show(fig, alt=f"Two stacked bars comparing the current price ({base['pump']:.3f} €/L) "
                      f"with the scenario ({scen['pump']:.3f} €/L), each split into crude, "
                      "refining and retail, excise and VAT.",
             data=comp, key="whatif_bars")
        sens = pd.DataFrame({"brent": np.arange(20, 161, 10)})
        sens["pump"] = sens["brent"].map(lambda b: what_if_price(b, margin, ticpe, vat)["pump"])
        fig = go.Figure(go.Scatter(x=sens["brent"], y=sens["pump"], mode="lines+markers",
                                   line={"color": FUEL_COLORS.get(fuel), "width": 2},
                                   marker={"size": 8},
                                   hovertemplate="Brent at %{x} € gives %{y:.3f} €/L<extra></extra>"))
        fig.add_vline(x=brent, line_dash="dot", line_color=MUTED,
                      annotation_text="your scenario", annotation_position="top left")
        base_layout(fig, "Pump price for each Brent level, other settings unchanged",
                    "€ per litre", "Brent crude (€/barrel)", height=300, legend=False)
        fig.update_layout(hovermode="closest")
        show(fig, alt=f"Straight line showing that each extra 10 € per barrel adds about "
                      f"{10 / LITRES_PER_BARREL * (1 + vat) * 100:.1f} cents per litre at the pump.",
             key="whatif_sens")
    st.info(f"As a rough rule, 10 € more on a barrel of Brent adds about "
            f"{10 / LITRES_PER_BARREL * 1.2 * 100:.1f} cents per litre at the pump once VAT is "
            f"included, which is around {10 / LITRES_PER_BARREL * 1.2 * litres:.0f} € a year for "
            "the driver described on the left. Cutting the excise by 10 cents saves 12 cents per "
            "litre because of VAT. The model assumes that the refining and retail part stays fixed "
            "and that crude is passed on in full, which is not always true in practice.")
