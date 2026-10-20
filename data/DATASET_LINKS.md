# Datasets used

Fuel prices: "Prix des carburants en France", Ministry of the Economy (prix-carburants.gouv.fr),
published on data.gouv.fr at
https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1 under the Licence
Ouverte / Open Licence v2.0. I used the yearly history files from
https://donnees.roulez-eco.fr/opendata/annee/2019 up to /2026.

Brent price: "Brent oil price (€/barrel)", monthly, indicator 0014443 of INE Portugal (data from
DGEG and Banco de Portugal), published on data.europa.eu at
https://data.europa.eu/data/datasets/ine-0014443?locale=en under CC BY 4.0. The download script
uses https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0014443&Dim1=T&lang=EN.

Department boundaries: simplified GeoJSON from https://github.com/gregoiredavid/france-geojson,
based on IGN data, Licence Ouverte.

The raw files are not in the zip because they weigh about 250 MB. Running `make data` downloads
them into `data/raw/` and rebuilds `data/processed/`. The data was downloaded on 19 October 2026.
