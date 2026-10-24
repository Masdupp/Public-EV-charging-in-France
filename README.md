# Public EV charging in France: where it lags, and how fast the gap is closing

Individual Streamlit project, Data Visualization 2026, EFREI Paris.
Oscar Masdupuy, BIA group.

## The story in one paragraph

The app is written for département and regional planners who draw up local charging plans (SDIRVE). It tests a common assumption: that public charging sped up after 2021 but stayed in big cities and on motorways, leaving rural départements short of fast chargers. The data supports the first half and contradicts the second. Dated commissioning went from 1,895 points in 2020 to 8,897 in 2021 and peaked at 18,256 in 2023. Yet rural mainland départements now have as many points per inhabitant as dense ones (226 against 222 per 100,000) and more fast chargers (87 against 76). The gap between the best and least equipped quarter of départements fell from 5.8 to 2.2 between the end of 2022 and October 2026. The départements left behind are the overseas ones, at 34 points per 100,000 people against 225 on the mainland and almost no new points since 2023, and a few dense départements around Paris once EV ownership is counted (Hauts-de-Seine has 2.5 points per 100 rechargeable cars, France 5.4).

These figures come from the 19 October 2026 build. Inside the app every number is computed from the data at run time, so they update when the data is rebuilt.

## What is in the app

| Section | Content |
|---|---|
| Introduction | Hook, audience, the hypothesis being tested |
| 1. Overview | KPI header tied to the filters; cumulative deployment by power class with four policy dates; points per year; rechargeable car fleet |
| 2. Deep dives | Choropleth by département (seven indicators); top and bottom 10 ranking; small multiples by power class and density band; kW per car against EV ownership with the AFIR reference band; catch-up dumbbell and years-to-reach table; sampled station map |
| 3. Data quality | Rows removed at each step, validation checks, missingness per field, known limits |
| 4. Conclusions | Insights, implications for planners, next steps (national figures, unaffected by filters) |

Sidebar controls: area (France, mainland, overseas, each region), départements, commissioning period, whether to count undated points, power class, operators (top 12 plus "Other operators"), and the indicator shown on the map and ranking. Empty selections show a message instead of a chart.

## Data sources

All sources are listed on data.gouv.fr and resolved through its API at download time. Exact URLs, resource names and download dates are in [data/SOURCES.md](data/SOURCES.md).

| Dataset | Publisher | Licence | Use |
|---|---|---|---|
| [Base nationale des IRVE, consolidated static file](https://www.data.gouv.fr/fr/datasets/fichier-consolide-des-bornes-de-recharge-pour-vehicules-electriques/) (schema [etalab/schema-irve-statique](https://schema.data.gouv.fr/etalab/schema-irve-statique/)) | data.gouv.fr | Licence Ouverte / Open Licence 2.0 (Etalab) | One row per charging point |
| [Voitures particulières immatriculées par commune et par type de recharge](https://www.data.gouv.fr/datasets/voitures-particulieres-immatriculees-par-commune-et-par-type-de-recharge-jeu-de-donnees-aaadata) | Agence ORE, from the SDES vehicle register | Licence Ouverte 2.0 | Rechargeable cars per commune, quarterly since December 2020 |
| [Populations de référence](https://www.data.gouv.fr/datasets/populations-de-reference) | Insee | Licence Ouverte 2.0 | 2023 municipal population per département |
| [Contours administratifs](https://www.data.gouv.fr/datasets/contours-administratifs) | data.gouv.fr, from IGN Admin Express | ODbL 1.0 | Département shapes (map and point-in-polygon), région names |

About the vehicle data: the brief asked for the SDES dataset of registered electric cars. The version on data.gouv.fr is published by Agence ORE, built from the SDES register, at commune level. It joined cleanly on the INSEE commune code (0 rows without a département), so the app uses both population and EV ownership. Its count of "rechargeable" cars mixes battery-electric and plug-in hybrid cars; the split is not in this file.

## Run it locally

Python 3.11 is the tested version.

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python data/fetch_data.py          # downloads about 170 MB into data/raw/, rebuilds data/processed/
streamlit run app.py
```

`data/processed/` is committed, so `streamlit run app.py` works straight after `pip install` if you skip the download. `fetch_data.py` keeps a manifest of what it downloaded and reuses a raw file when the API still reports the same URL and modification date. `python data/fetch_data.py --force` downloads everything again. The Agence ORE file is served from a live endpoint whose metadata on data.gouv.fr is not always refreshed, so use `--force` to be sure of the latest quarter.

`requirements.txt` pins the direct dependencies. `requirements-lock.txt` pins the full environment the app was tested in. A `Makefile` wraps the same three steps (`make venv data run`).

## Deploy on Streamlit Community Cloud

1. Create a public GitHub repository and push this folder to it. The `.gitignore` already excludes `data/raw/` and `.venv/`; check that `data/processed/` (about 1 MB) is included.
   ```bash
   git init
   git add .
   git commit -m "IRVE data storytelling app"
   git branch -M main
   git remote add origin https://github.com/<your-user>/<your-repo>.git
   git push -u origin main
   ```
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, then **Deploy a public app from GitHub**.
4. Choose the repository, branch `main`, and main file path `app.py`.
5. Open **Advanced settings** and select Python 3.11. No secrets are needed.
6. Click **Deploy**. The first build installs the requirements (a few minutes). After that the app loads from the parquet files in a few seconds and never downloads data at startup.
7. To refresh the data later, run `python data/fetch_data.py` locally, commit the new `data/processed/` and `data/SOURCES.md`, and push. Streamlit Cloud redeploys on push.

## Cleaning decisions and their effect on row counts

Build of 19 October 2026, IRVE file `consolidation-etalab-schema-irve-statique-v-2.3.1-20261019.csv`.

| Step | Rows removed | Rows left |
|---|---:|---:|
| Raw file | | 157,460 |
| Duplicate `id_pdc_itinerance`: 7,276 IDs appeared more than once, every time in two or more different source files (typically an aggregator and the operator publishing the same point). Kept the row with the latest `date_maj`. | 7,919 | 149,541 |
| Rows with the schema placeholder ID "Non concerné" (119) were deduplicated on their content instead of their ID | 0 | 149,541 |
| No usable commune code and coordinates outside every département | 213 | 149,328 |
| Département without an Insee population figure (Mayotte) | 0 | 149,328 |

Changes that keep the row but alter a value:

- **Power.** The schema says kW. 4 values of 1,000 or more were read as watts and divided by 1,000 (22000 becomes 22). 2,709 points declared 0 kW and were set to "Unknown power". 289 points above 400 kW were kept as ultra-fast and flagged in the app.
- **Power classes.** Slow below 7.4 kW; normal from 7.4 to 22 kW inclusive, so standard 22 kW wallboxes count as normal; fast above 22 and below 150 kW; ultra-fast 150 kW and above.
- **Commissioning date.** 33 dates before 2010 (1900, 1947, 2002) and 1 date in 2028 were set to missing. In total 65,211 points (44%) have no usable date. They count in snapshot views and are left out of every time-based view.
- **Département.** Taken from the first two characters of the INSEE commune code (three for overseas) for 87,439 points. The code is missing for 41% of raw rows, so for 61,889 points the département comes from a point-in-polygon test of the coordinates against the département shapes. On the 87,197 points where both methods work, they agree 99.0% of the time.
- **Operators.** Upper-cased, roaming suffixes such as "| FR*FR1" removed, and a few obvious aliases merged (the two TotalEnergies entities, for example). 292 distinct operators remain; the top 12 are kept and the rest grouped.
- **Siting.** Fixed encoding errors in `implantation_station` (five spellings of "Parking privé à usage public") and translated the categories.

All thresholds live in `config.py`. Change one and rerun `python data/fetch_data.py`.

Derived indicators: points per 100,000 inhabitants, fast and ultra-fast points per 100,000, points per 100 rechargeable cars, kW of public power per rechargeable car, share of fast points, points commissioned in the period per 100,000. Density bands use population over area at département level: rural below 60 inhabitants per km², dense above 150. The area is approximated from the polygons (error under 1%).

## Limitations

- Publication is declarative. Operators publish their own files, some late or not at all. A low figure can mean missing data rather than missing chargers, which is the first thing to check for the overseas départements.
- 44% of points have no commissioning date. The timeline and the catch-up comparison use dated points only. Points taken out of service are not in the file, so the timeline cannot show closures.
- The jump in 2021 coincides with the arrêté of 4 May 2021 that made publication on data.gouv.fr mandatory, so part of it may reflect better reporting rather than more chargers.
- Vehicles are counted at the holder's address. Company and leasing cars registered at head offices inflate the car count of a few départements (Hauts-de-Seine, Yvelines, Paris) and lower their per-car ratios.
- Battery-electric and plug-in hybrid cars are not separated, so the AFIR fleet targets (1.3 kW per battery car, 0.8 kW per plug-in hybrid) are shown as a reference band, not a compliance test.
- The file has no road layer, so the motorway-corridor part of the hypothesis is not tested. The share of ultra-fast points in stations dedicated to fast charging (44%) is the closest proxy.
- Département averages hide what happens inside a département. EPCI or commune level would be the next step.
- Mayotte is excluded: the Insee 2023 reference population file has no figure for it.
- The "years to reach the France level" table is a projection under stated assumptions (constant pace, fixed target, dated points only), not a forecast.
- Relations between EV ownership and charging density are correlations. The app makes no causal claim.
- data.gouv.fr announces that this consolidated file will be replaced by the national base on transport.data.gouv.fr and removed after 31 December 2026. After that date `config.py` will need the new dataset slug.

## Project layout

```
app.py                 entry point: sidebar, caching, section order
config.py              every constant: sources, thresholds, palette, policy dates, seed
sections/              intro, overview, deep_dives, quality, conclusions (+ _ui helpers)
utils/io.py            data.gouv.fr API lookup, cached download, loading, licence text
utils/prep.py          cleaning, feature engineering, aggregation, story numbers
utils/viz.py           Plotly chart builders with one shared style
data/fetch_data.py     download + rebuild script
data/processed/        parquet and GeoJSON read by the app (committed)
data/SOURCES.md        dataset URLs and download dates (generated)
assets/                app icon
.streamlit/config.toml light theme matching the chart palette
```

## Accessibility

Every chart has a text description under it and, where useful, a data table in an expander, so no value depends on color alone. Power classes use a single-hue ordinal blue ramp and maps use a single-hue sequential scale, both checked for color-vision deficiency and contrast against the white background. All axes carry a label and a unit.

## Licence

Code: MIT (see `LICENSE`). Data: Licence Ouverte / Open Licence 2.0 for the IRVE file, the Insee population and the Agence ORE vehicle counts; ODbL 1.0 for the administrative contours.
