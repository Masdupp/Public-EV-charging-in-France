# Public EV charging in France: where it lags, and how fast the gap is closing

Streamlit project, Data Visualization 2026, EFREI Paris. Oscar Masdupuy, BIA.

The app is for département and regional planners. It checks where public charging is thin once population and EV ownership are taken into account, and whether the least equipped départements are catching up.

## Main findings

Figures from the 19 October 2026 data. The app recomputes them from the data.

- Deployment sped up after 2021: 1,895 dated points in 2020, 8,897 in 2021, a peak of 18,256 in 2023.
- Rural mainland départements are not behind. They have 226 points per 100,000 inhabitants against 222 in dense ones, and 87 fast points against 76.
- The gap is closing. The best equipped quarter of départements had 5.8 times more points per inhabitant than the least equipped quarter at the end of 2022, and 2.2 times more in October 2026.
- The gaps that remain are overseas (34 points per 100,000 people against 225 on the mainland, almost nothing added since 2023) and in dense départements around Paris relative to EV ownership (Hauts-de-Seine: 2.5 points per 100 rechargeable cars, France 5.4).

## Using the app

The page reads top to bottom: introduction, overview (KPIs and the timeline), deep dives (map, ranking, rural vs dense, EV ownership, catch-up, station map), data quality, conclusions.

The sidebar filters everything from the KPIs to the station map:

- **Area and départements:** all France, mainland, overseas, a region, or specific départements.
- **Commissioning period:** KPIs, map and ranking show the network at the end of the period. Growth counts points added inside it.
- **Count points with no commissioning date:** only available when the period ends this year.
- **Power class:** slow (<7.4 kW), normal (7.4 to 22 kW), fast (22 to 150 kW), ultra-fast (≥150 kW).
- **Operators:** the top 12, with the rest grouped.
- **Indicator:** the measure shown on the map and the ranking.

The introduction and conclusions always use national figures, so the story stays the same while you filter.

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The processed data is in the repo, so this is enough. To download fresh data and rebuild it (about 170 MB), run `python data/fetch_data.py` before `streamlit run app.py`.

## Documents

- [Report (PDF)](docs/report.pdf): problem, data, cleaning, method, findings and limits.
- [Storyboard (PDF)](docs/storyboard.pdf): the story section by section, with the chart frames.

Both are built from `docs/*.tex`. Every number in them comes from `docs/numbers.tex`, which `python docs/build_figures.py` writes from the processed data along with the figures.

## Data

| Dataset | Licence |
|---|---|
| [Base nationale des IRVE](https://www.data.gouv.fr/fr/datasets/fichier-consolide-des-bornes-de-recharge-pour-vehicules-electriques/): one row per charging point | Licence Ouverte 2.0 |
| [Voitures particulières immatriculées par commune et par type de recharge](https://www.data.gouv.fr/datasets/voitures-particulieres-immatriculees-par-commune-et-par-type-de-recharge-jeu-de-donnees-aaadata) (Agence ORE, from the SDES register) | Licence Ouverte 2.0 |
| [Populations de référence](https://www.data.gouv.fr/datasets/populations-de-reference) (Insee, 2023) | Licence Ouverte 2.0 |
| [Contours administratifs](https://www.data.gouv.fr/datasets/contours-administratifs): département shapes | ODbL 1.0 |

File URLs and download dates are in [data/SOURCES.md](data/SOURCES.md).

## Cleaning

| Step | Rows removed | Rows left |
|---|---:|---:|
| Raw file | | 157,460 |
| Duplicate `id_pdc_itinerance` (same point published by two sources), kept the latest update | 7,919 | 149,541 |
| No commune code and coordinates outside France | 213 | 149,328 |

- **Power:** 4 values in watts were converted to kW. 2,709 points declared 0 kW and are shown as "Unknown power".
- **Dates:** 34 impossible dates (before 2010 or in the future) were set to missing. 44% of points have no commissioning date.
- **Département:** taken from the INSEE commune code when present. Otherwise (41% of rows) it comes from the coordinates. Where both exist, they agree 99.0% of the time.
- **Operators:** names normalised and obvious variants merged, leaving 292 operators.

Thresholds are in `config.py`.

## Limitations

- Operators declare their own points. Some publish late or not at all, so a low figure can mean missing data. Check this first for the overseas départements.
- Time charts use only the 56% of points that have a date. Removed points are not in the file.
- Part of the 2021 jump may come from the May 2021 duty to publish this data, not from new chargers.
- Cars are counted at the owner's address. Company cars registered at head offices lower per-car ratios in Hauts-de-Seine, Yvelines and Paris.
- Battery-electric and plug-in hybrid cars are counted together.
- There is no road layer, so the motorway-corridor question is not tested.
- Mayotte is excluded because it has no 2023 Insee population figure.
- Links between EV ownership and charging are correlations, not causes.
