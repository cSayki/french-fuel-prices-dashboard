"""Analysis functions: filters, key figures, price breakdown, pass-through and scenarios."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

from utils.constants import LITRES_PER_BARREL, REBATES_2022, TICPE_EUR_L, VAT


# filtering
@st.cache_data(show_spinner=False)
def filtered_weekly(grp: pd.DataFrame, fuels: tuple, regions: tuple, road: str,
                    start, end) -> pd.DataFrame:
    """Average price per fuel and week over the stations that match the filters.

    grp stores the sum of prices and the number of stations for each department, road type,
    fuel and week, so dividing the two gives an exact average for any filter instead of an
    average of averages.
    """
    m = grp["fuel"].isin(fuels) & grp["week"].between(pd.Timestamp(start), pd.Timestamp(end))
    if regions:
        m &= grp["region"].isin(regions)
    if road != "All":
        m &= grp["road"] == road
    out = (grp[m].groupby(["fuel", "week"], observed=True)[["sum_price", "n"]].sum()
                 .reset_index())
    out["price"] = out["sum_price"] / out["n"]
    return out[out["n"] > 0].drop(columns="sum_price")


def add_measure(df: pd.DataFrame, measure: str) -> pd.DataFrame:
    """Derive the variable chosen in the sidebar from the weekly mean price."""
    df = df.sort_values(["fuel", "week"]).copy()
    if measure == "Price (€/L)":
        df["value"] = df["price"]
    elif measure == "Index (first week = 100)":
        df["value"] = df["price"] / df.groupby("fuel")["price"].transform("first") * 100
    else:  # Year-on-year change (%)
        prev = df.set_index(["fuel", "week"])["price"]
        lag = df.assign(week=df["week"] - pd.Timedelta(weeks=52)).set_index(["fuel", "week"]).index
        df["value"] = (df["price"].to_numpy() / prev.reindex(lag).to_numpy() - 1) * 100
    return df


@st.cache_data(show_spinner=False)
def dept_period(grp: pd.DataFrame, fuel: str, road: str, start, end) -> pd.DataFrame:
    """Average price per department over the last 4 weeks, and change since the first 4."""
    g = grp[(grp["fuel"] == fuel) & grp["week"].between(pd.Timestamp(start), pd.Timestamp(end))]
    if road != "All":
        g = g[g["road"] == road]
    if g.empty:
        return pd.DataFrame(columns=["dept", "region", "price", "n", "change"])
    weeks = np.sort(g["week"].unique())
    def agg(ws):
        a = (g[g["week"].isin(ws)].groupby(["dept", "region"], observed=True)[["sum_price", "n"]]
               .sum())
        a["price"] = a["sum_price"] / a["n"]
        a["n"] = a["n"] / len(ws)
        return a[["price", "n"]]
    last, first = agg(weeks[-4:]), agg(weeks[:4])
    out = last.join(first["price"].rename("price_start"), how="left")
    out["change"] = out["price"] - out["price_start"]
    out = out[out["n"] > 0].reset_index()
    out["dept"] = out["dept"].astype(str)
    out["region"] = out["region"].astype(str)
    return out


@st.cache_data(show_spinner=False)
def road_premium(grp: pd.DataFrame, fuel: str, regions: tuple, start, end) -> pd.DataFrame:
    g = grp[(grp["fuel"] == fuel) & grp["week"].between(pd.Timestamp(start), pd.Timestamp(end))
            & grp["road"].isin(["Road", "Motorway"])]
    if regions:
        g = g[g["region"].isin(regions)]
    a = g.groupby(["week", "road"], observed=True)[["sum_price", "n"]].sum()
    p = (a["sum_price"] / a["n"]).unstack("road")
    if not {"Road", "Motorway"} <= set(p.columns):
        return pd.DataFrame(columns=["week", "premium"])
    return (p["Motorway"] - p["Road"]).rename("premium").reset_index()


@st.cache_data(show_spinner=False)
def region_weekly(grp: pd.DataFrame, fuel: str, road: str, start, end) -> pd.DataFrame:
    g = grp[(grp["fuel"] == fuel) & grp["week"].between(pd.Timestamp(start), pd.Timestamp(end))]
    if road != "All":
        g = g[g["road"] == road]
    a = g.groupby(["region", "week"], observed=True)[["sum_price", "n"]].sum().reset_index()
    a["price"] = a["sum_price"] / a["n"]
    nat = a.groupby("week")[["sum_price", "n"]].sum()
    a["national"] = a["week"].map(nat["sum_price"] / nat["n"])
    a["gap"] = a["price"] - a["national"]
    return a


# KPIs
@dataclass
class Kpis:
    last_week: pd.Timestamp
    price_now: float
    price_start: float
    peak: float
    peak_week: pd.Timestamp
    low: float
    low_week: pd.Timestamp
    stations: int
    tank_cost: float


def compute_kpis(wk: pd.DataFrame, fuel: str, tank_l: float = 50) -> Kpis | None:
    f = wk[wk["fuel"] == fuel].sort_values("week")
    if f.empty:
        return None
    i_max, i_min = f["price"].idxmax(), f["price"].idxmin()
    return Kpis(
        last_week=f["week"].iloc[-1], price_now=f["price"].iloc[-1],
        price_start=f["price"].iloc[0], peak=f.loc[i_max, "price"],
        peak_week=f.loc[i_max, "week"], low=f.loc[i_min, "price"],
        low_week=f.loc[i_min, "week"], stations=int(f["n"].iloc[-1]),
        tank_cost=f["price"].iloc[-1] * tank_l,
    )


# decomposition
def monthly_rebate(index: pd.DatetimeIndex) -> pd.Series:
    """Average State rebate per litre (VAT included) over each month of index."""
    days = pd.Series(0.0, index=pd.date_range(index.min(), index.max() + pd.offsets.MonthEnd(0)))
    for a, b, v in REBATES_2022:
        days[a:b] = v
    return days.resample("MS").mean().reindex(index).fillna(0.0)


@st.cache_data(show_spinner=False)
def decompose(monthly: pd.DataFrame, fuel: str, ticpe: float | None = None) -> pd.DataFrame:
    """Split the monthly average pump price into crude, refining and retail, excise and VAT.

    The 2022 rebate is added back to the observed price. VAT is the price minus the price
    divided by 1.2, crude is the Brent price divided by the litres in a barrel, and the
    refining and retail part is whatever is left once the excise is removed.
    """
    ticpe = TICPE_EUR_L[fuel] if ticpe is None else ticpe
    x = monthly[monthly["fuel"] == fuel].dropna(subset=["brent_eur_bbl"]).set_index("month")
    out = pd.DataFrame(index=x.index)
    out["pump"] = x["price_mean"]
    out["rebate"] = monthly_rebate(x.index)
    ttc = out["pump"] + out["rebate"]
    ht = ttc / (1 + VAT)
    out["Crude oil (Brent)"] = x["brent_eur_bbl"] / LITRES_PER_BARREL
    out["Refining, logistics & retail"] = ht - ticpe - out["Crude oil (Brent)"]
    out["TICPE excise"] = ticpe
    out["VAT 20%"] = ttc - ht
    out["brent_eur_bbl"] = x["brent_eur_bbl"]
    return out.reset_index()


# pass-through
@dataclass
class PassThrough:
    up: float
    up_se: float
    down: float
    down_se: float
    diff_se: float
    n: int
    data: pd.DataFrame


@st.cache_data(show_spinner=False)
def pass_through(dec: pd.DataFrame) -> PassThrough:
    """Regression of the monthly change in the pre-tax price on the change in crude.

    Increases and decreases of crude are separate variables, each with the current month
    and the previous one. up and down are the sums of the two coefficients, with robust
    (HC0) standard errors. diff_se is the standard error of up minus down, used to test
    whether prices react differently to increases and decreases.
    """
    d = dec.set_index("month")
    pre_tax = d["Crude oil (Brent)"] + d["Refining, logistics & retail"]
    df = pd.DataFrame({"dp": pre_tax.diff(), "db": d["Crude oil (Brent)"].diff()})
    df["up0"], df["dn0"] = df["db"].clip(lower=0), df["db"].clip(upper=0)
    df["up1"], df["dn1"] = df["up0"].shift(), df["dn0"].shift()
    df = df.dropna()
    X = np.column_stack([np.ones(len(df)), df[["up0", "up1", "dn0", "dn1"]].to_numpy()])
    y = df["dp"].to_numpy()
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    xtx = np.linalg.inv(X.T @ X)
    cov = xtx @ (X.T * e**2) @ X @ xtx
    up_v = np.array([0, 1, 1, 0, 0]); dn_v = np.array([0, 0, 0, 1, 1])
    return PassThrough(
        up=float(up_v @ beta), up_se=float(np.sqrt(up_v @ cov @ up_v)),
        down=float(dn_v @ beta), down_se=float(np.sqrt(dn_v @ cov @ dn_v)),
        diff_se=float(np.sqrt((up_v - dn_v) @ cov @ (up_v - dn_v))),
        n=len(df), data=df.reset_index(),
    )


def lag_correlation(dec: pd.DataFrame, max_lag: int = 4) -> pd.DataFrame:
    d = dec.set_index("month")
    dp = (d["Crude oil (Brent)"] + d["Refining, logistics & retail"]).diff()
    db = d["Crude oil (Brent)"].diff()
    return pd.DataFrame({"lag_months": range(max_lag + 1),
                         "correlation": [dp.corr(db.shift(k)) for k in range(max_lag + 1)]})


# what-if
def what_if_price(brent_eur_bbl: float, margin: float, ticpe: float, vat: float) -> dict:
    crude = brent_eur_bbl / LITRES_PER_BARREL
    ht = crude + margin + ticpe
    ttc = ht * (1 + vat)
    return {"Crude oil (Brent)": crude, "Refining, logistics & retail": margin,
            "TICPE excise": ticpe, "VAT": ttc - ht, "pump": ttc}


def asymmetry_significant(pt: PassThrough) -> bool:
    return abs(pt.up - pt.down) > 1.96 * pt.diff_se
