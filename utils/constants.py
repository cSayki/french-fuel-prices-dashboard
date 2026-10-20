"""Constants used across the project: sources, licences, fuels and tax assumptions.

The assumptions (tax rates, rebate calendar) are kept here so they are all in one place.
The cleaning thresholds are in seeds.json.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SEEDS = json.loads((ROOT / "seeds.json").read_text())

YEARS = list(range(SEEDS["first_year"], SEEDS["last_year"] + 1))

# sources
SOURCES = {
    "fuel": {
        "title": "Prix des carburants en France, flux annuel",
        "publisher": "Ministère de l'Économie (prix-carburants.gouv.fr)",
        "portal": "data.gouv.fr",
        "page": "https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1",
        "url_template": "https://donnees.roulez-eco.fr/opendata/annee/{year}",
        "licence": "Licence Ouverte / Open Licence v2.0 (Etalab)",
    },
    "brent": {
        "title": "Brent oil price in euros per barrel, monthly (indicator 0014443)",
        "publisher": "INE Portugal, from DGEG and Banco de Portugal data",
        "portal": "data.europa.eu",
        "page": "https://data.europa.eu/data/datasets/ine-0014443?locale=en",
        "url": "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0014443&Dim1=T&lang=EN",
        "licence": "CC BY 4.0 (INE open data)",
    },
    "geo": {
        "title": "Contours des départements, simplified version",
        "publisher": "france-geojson by G. David, based on IGN ADMIN EXPRESS",
        "portal": "GitHub",
        "url": "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
        "licence": "Licence Ouverte (IGN)",
    },
}

# fuels
FUELS = ["Gazole", "E10", "SP98", "SP95", "E85", "GPLc"]
FUEL_LABELS = {
    "Gazole": "Diesel (Gazole)",
    "E10": "Unleaded SP95-E10",
    "SP98": "Unleaded SP98",
    "SP95": "Unleaded SP95 (E5)",
    "E85": "Bioethanol E85",
    "GPLc": "LPG (GPLc)",
}
# fuels that come from crude oil and follow the standard taxes, so the breakdown makes sense
DECOMPOSABLE = ["Gazole", "E10", "SP98", "SP95"]

# TICPE excise in €/L for metropolitan France, national rate plus the regional part that
# most regions apply. Rates have not changed since 1 January 2018 (douane.gouv.fr, UFIP).
# I assume they stayed constant over 2019-2026; they can be changed in the scenarios tab.
TICPE_EUR_L = {"Gazole": 0.6075, "SP95": 0.6829, "SP98": 0.6829, "E10": 0.6629}
VAT = 0.20
LITRES_PER_BARREL = 158.987

# 2022 "remise carburant" in €/L, VAT included (décret 2022-423 and the following ones).
# Prices declared by stations already include it, so it is added back in the breakdown.
REBATES_2022 = [
    ("2022-04-01", "2022-08-31", 0.18),
    ("2022-09-01", "2022-11-15", 0.30),
    ("2022-11-16", "2022-12-31", 0.10),
]

# events drawn on the charts for context
EVENTS = [
    ("2020-03-17", "COVID-19 lockdown"),
    ("2022-02-24", "Ukraine war"),
    ("2022-09-27", "Refinery strikes"),
    ("2026-02-28", "Iran war / Hormuz"),
]
# periods drawn as shaded areas
BANDS = [("2022-04-01", "2022-12-31", "State fuel rebate")]
# for the 2026 event see the Wikipedia page "2026 Iran war fuel crisis" and CNBC,
# 31 March 2026, "Brent oil price surges more than 60% in March"

# geography
REGIONS = {
    "Auvergne-Rhône-Alpes": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],
    "Bourgogne-Franche-Comté": ["21", "25", "39", "58", "70", "71", "89", "90"],
    "Bretagne": ["22", "29", "35", "56"],
    "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
    "Corse": ["2A", "2B"],
    "Grand Est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "Hauts-de-France": ["02", "59", "60", "62", "80"],
    "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "Normandie": ["14", "27", "50", "61", "76"],
    "Nouvelle-Aquitaine": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],
    "Occitanie": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],
    "Pays de la Loire": ["44", "49", "53", "72", "85"],
    "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
}
DEPT_TO_REGION = {d: r for r, ds in REGIONS.items() for d in ds}
METRO_DEPTS = set(DEPT_TO_REGION)

# rough box around metropolitan France, used to check station coordinates
LAT_RANGE = (41.0, 51.6)
LON_RANGE = (-5.6, 10.0)
