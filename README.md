# What really drives fuel prices in France, 2019 to 2026

Individual student project, Data Storytelling Dashboard with Streamlit, EFREI 2026.

This Streamlit app looks at the prices that every French petrol station has declared to the
government since January 2019, about 36 million price updates in total, and compares them with
the monthly price of Brent crude. The idea came from the 2026 price spike: in September 2026 diesel
averaged 2.40 € per litre, more than at the 2022 peak, and the explanation usually given is simply
that oil got more expensive. I wanted to see how much of the pump price really comes from oil, how
much from taxes and how much from the rest, whether prices go up faster than they come down, and
how much the price changes from one place to another.

## The story

The app is split into seven tabs that follow the order of the story. The introduction starts from
the 2026 record and explains who the dashboard is for (drivers, local journalists, people following
the debate on fuel taxes) and what questions it tries to answer. The overview puts that record next
to the two previous shocks, the COVID collapse in 2020 and the war in Ukraine in 2022, and also
shows the stock-outs during the October 2022 refinery strikes.

The third tab is the core of the project. It splits the price of a litre into crude oil, the
excise tax (TICPE), VAT and what is left, which covers refining, transport, storage and the
station margin. On average crude oil is only about 25 % of the price of diesel and taxes about
54 %. The part that is left grew from about 23 cents per litre in 2019 to 2021 to about 56 cents
over the last twelve months, which is the least visible change in the data and probably the most
lasting one. The same tab tests the "rockets and feathers" idea, that prices rise faster than they
fall. For diesel the estimates are 1.62 for increases and 0.85 for decreases, but the confidence
intervals overlap, so I cannot claim the effect is real with monthly data.

The regions tab compares departments on a map, ranks the most and least expensive ones, shows each
region against the national average in small charts on the same scale and measures how much more
motorway stations charge (around 9 cents per litre recently, 15 on average since 2019). The
scenarios tab lets the user change the Brent price, the excise, VAT and the refining part, and
see the effect on a yearly fuel bill. The data quality tab explains the cleaning, and the last tab
sums up the findings and what they mean.

The storyboard is in `docs/storyboard.md` and the script I used for the demo video is in
`docs/demo_script.md`.

## Data

The main dataset is "Prix des carburants en France" published by the Ministry of the Economy on
data.gouv.fr (https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1)
under the Licence Ouverte 2.0. I used the yearly history files for 2019 to 2026, downloaded from
https://donnees.roulez-eco.fr/opendata/annee/2019 and the following years. They are XML files of
about 400 MB each once unzipped, with every price update, the location of each station, whether it
is on a motorway and the stock-outs it declared.

The Brent price comes from INE Portugal, indicator 0014443, published on data.europa.eu
(https://data.europa.eu/data/datasets/ine-0014443?locale=en) under CC BY 4.0. It is a monthly
average in euros per barrel. The department boundaries for the map come from the france-geojson
project (https://github.com/gregoiredavid/france-geojson), based on IGN data under the Licence
Ouverte.

The dates of the events drawn on the charts (COVID lockdown, invasion of Ukraine, 2022 rebates,
refinery strikes, war in Iran) are public facts and are only there for context. The tax rates I
assumed are listed in `utils/constants.py`. All links are also in `data/DATASET_LINKS.md`.

## Running the app

It needs Python 3.11 or later. I tested it in a fresh virtual environment with Python 3.14.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The processed tables (about 3 MB of parquet files in `data/processed/`) are included, so the app
starts straight away. To rebuild them from the raw open data, which means downloading about
250 MB and takes around a minute, run `make data`. `make run` starts the app and `make test` runs
a quick headless test of every tab. If `data/processed/` is missing, the app runs the download and
build scripts by itself the first time it loads. To deploy it on Streamlit Community Cloud, point it
at `app.py`; no secrets are needed.

## How the code is organised

```
app.py                     page setup, sidebar filters and tabs
sections/
  intro.py                 introduction, audience, questions, caveats, licences
  overview.py              key figures, weekly trend, yearly averages, stock-outs
  deep_dives.py            price breakdown and pass-through, regions, scenarios
  data_quality.py          cleaning steps, coverage, checks, missing values, limits
  conclusions.py           findings, implications, next steps
utils/
  constants.py             sources, fuels, tax assumptions, events, regions
  io.py                    data loading with st.cache_data
  prep.py                  filters, key figures, breakdown, regression, scenarios
  viz.py                   chart functions with shared colours and layout
scripts/
  download_data.py         downloads the raw files (skips files already there)
  build_dataset.py         turns the XML into the processed tables
tests/smoke_test.py        renders every tab with a few tricky filter choices
data/processed/            processed tables, quality report and map file
docs/                      storyboard and demo script
seeds.json                 cleaning thresholds and random seed
```

## Method

The build script reads each yearly XML line by line with regular expressions. Until 2021 prices
were published in thousandths of a euro, so they are converted first. Then it removes exact
duplicates, prices below 0.50 or above 3.50 € per litre, and prices more than 35 % away from the
national median of the same fuel that week, which catches typos such as 0.71 typed instead of
1.71. Overall 0.14 % of the rows are removed. Stations only send an update when their price
changes, so for each station, fuel and week I keep the last price and carry it forward for up to
three weeks if nothing new arrives.

The results are stored as the sum of prices and the number of stations for every department, road
type, fuel and week. This way the app can compute an exact average for any combination of filters
without going back to the station level. The script also produces national weekly figures with
the 10th and 90th percentiles, a snapshot of the latest price at each station, a monthly series
joined with Brent and a report of what the cleaning removed.

For the price breakdown, I add the 2022 State rebate back to the observed price, take VAT out
(one sixth of the price), subtract the excise at its official rate and convert Brent to euros per
litre (one barrel is 158.987 litres). What remains is the refining, logistics and retail part.
The pass-through is an ordinary least squares regression of the monthly change in the pre-tax
price on the change in crude, with increases and decreases as separate variables, the current and
previous month, robust standard errors and a test on the difference between the two.

All the heavy work is done once offline, so the app only reads small files, and both the loading
and the filter calculations are cached with `st.cache_data`. For accessibility, each fuel keeps
the same colour everywhere, the palette was checked for colour blindness, every chart has a short
written description and a table with its data, and every axis shows its unit.

## Limits

The averages give the same weight to every station because the volume sold by each station is not
published. Prices are declared by the stations themselves, and some declare late. Brent is a
monthly average, and since the data has no prices for refined diesel or gasoline, the part left
after crude and taxes mixes refinery and station margins. The tax rates are assumed constant, and
regional variations, biofuel incentives and company discounts are not modelled. Overseas
departments are excluded because their prices are regulated, and Corsica has its own tax rates.
Finally, the events on the charts give context but are not proof of what caused the changes.

## Still to do before submitting

The deployed app URL, the repository link and the link to the demo video still have to be added
here.

## Licences

The code is under the MIT licence (see `LICENSE`). The data keeps its original licences: Licence
Ouverte 2.0 for the fuel prices and the department boundaries, CC BY 4.0 for the Brent series.
