# Global subnational homicide database

A harmonised panel of homicide counts and rates below the national level: about 29,000 observations for roughly 2,850 provinces, states, counties, districts, cities and police units in 78 countries,
1993-2025. One re-runnable pipeline per source extracts the figures from police, statistical-office and health-ministry publications (HTML, Excel, CSV, PDF, OCR, APIs) into a common schema, attaches a
population denominator and its age, validates against the source's national totals and independent series, and grades each row A, B or C. Every series carries its counting unit, definition flags and time
basis, and `Docs/DEFINITIONS.md` compares each source's definition of homicide with the UNODC standard. Built for the Development Data Lab.

Author: Yannick Feussi ([@afrohead07](https://github.com/afrohead07)).

## What is in it
- `Data/Output/global_master_panel.csv`: the rows of every country in one file; `Data/Output/<region>_master_panel.csv`: one file per continent; `Data/Output/project_inventory.md`: the number of countries, units, rows and years.
- `Pipelines/<Region>/<country>_homicide_rate.csv`: the output of each country script, in the common format described in `Pipelines/FORMAT.md`.
- `Docs/DEFINITIONS.md` (also `DEFINITIONS.html` and `definitions_matrix.csv`): what each source counts as homicide, compared with the UNODC definition, with the source of every statement.

## How to read a row
- `homicide_cases` is what the source counts: victims, offences or cases (`count_unit` in the panels, `definition_flags` in every file); `population` and its age (`population_age_years`) come from the source's own
  denominator or an official estimate or census, named in `population_method`.
- `reliability_tier`: A = reconciled, independently confirmed and a recent denominator (age of 3.5 years or less); B = a documented weakness; C = a failed hard check or a proxy. The reason is in `validation`.
- `year` is the calendar year unless `year_basis` says financial year (then it is the start year).
- Rates are comparable only within one `comparable_within` key. Rows of different admin levels are never added (a state and its districts are the same people). A victim count, a case count and a proxy are not
  compared without reading the notes in `Docs/DEFINITIONS.md`. Counts below 10 carry `flag_low_count`; a population that jumps (a new census) carries `flag_population_break`.

## Layout
- `Pipelines/<Region>/<country>_homicide_rate.py`: one script per country or source layer. `inspect` shows what a source contains; `build` downloads it into `Data/Raw/<Region>/<Country>/` (dated), reconciles it and
  writes one CSV next to the script.
- `Pipelines/homicide_format.py`: the shared output format and its validator; every CSV is validated before it is written.
- `Pipelines/<Region>/<region>_master_panel.py` and `Pipelines/global_master_panel.py`: stack the country CSVs into the panels. `Pipelines/project_inventory.py` counts them.
- `Pipelines/refresh_all.py`: rebuilds everything in order. `Pipelines/build_docs.py` writes `Docs/`. `Pipelines/tidy_repo.py` and `Pipelines/release_check.py` keep and check the folder.

## Running
```
python -m pip install -r requirements.txt
cd Pipelines
python refresh_all.py --reuse            # every country script, then the panels, the inventory and the documentation (--reuse: use the saved downloads; --fresh: download again)
python Africa/kenya_homicide_rate.py build        # one country
python Africa/africa_master_panel.py              # one regional panel
python global_master_panel.py                     # the world panel
python release_check.py                           # the checks to run before publishing
```

## Limits of the data
- Police-recorded series reflect reporting and recording, not only violence; health-registry series reflect cause-of-death certification (South Africa's registry covers about a third of police-recorded murders).
- Several denominators are old or projected (Nigeria: a projection of the 2006 census; Lesotho: the 2016 census; Kenya: the 2009 census up to 2017 and the 2019 census from 2021).
- The Americas are covered through the Igarape Institute's Homicide Monitor, a compilation in which every row cites its official source (`igarape_source_1`, `igarape_source_2`); those rows are never tier A.
- Sources that publish no sub-national homicide figures were examined and not used: Tunisia, Mozambique, Sierra Leone, Zimbabwe, Uganda, Botswana.
- South Australia and New Zealand are not covered.

## Licence and citation
Code: MIT (`LICENSE`). Data and documentation: Creative Commons Attribution 4.0 (`LICENSE-DATA.md`). How to cite the database: `CITATION.cff`. The figures come from the official sources named in every row
(`source_url`); the terms of those sources apply to their content.
