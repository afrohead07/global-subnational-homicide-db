# Definitions: what each series in the database counts

How each source in the database defines and counts homicide, compared with the UNODC definition of intentional homicide. Where a statement rests on a specific page or file, its address is given next to it; the sources of every layer are listed under its table. Built from global_master_panel.csv (29,075 rows, 25 layers).

## 1. Reference definition: UNODC / ICCS 0101

**UNODC International Classification of Crime for Statistical Purposes (ICCS 2015), category 0101 'Intentional homicide'**

> Unlawful death inflicted upon a person with the intent to cause death or serious injury.

Three elements make a killing an intentional homicide:

- the killing of a person by another person (objective element);
- the intent of the perpetrator to kill or seriously injure the victim (subjective element);
- the killing is against the law: the law considers the perpetrator liable for the unlawful death (legal element).

Included: murder; honour killing; serious assault leading to death; death as a result of terrorist activities; dowry-related killings; femicide; infanticide; voluntary manslaughter; extrajudicial killings and extra-legal, summary or arbitrary executions; killings caused by excessive use of force by law enforcement officials.

Excluded: death due to legal interventions; justifiable homicide in self-defence; attempted intentional homicide (a separate ICCS category); non-intentional homicide: non-negligent or involuntary manslaughter, negligent killing; assisting suicide, euthanasia; unlawful killing associated with armed conflict (a separate ICCS category).

Public-health registries follow the ICD: deaths coded X85-Y09 (injuries inflicted by another person with intent to injure or kill) and Y87.1 (sequelae of assault) correspond closely to intentional homicide; legal intervention (ICD Y35) is not part of them. UNODC treats the ICD figure and the police figure as two measures of the same phenomenon with different coverage.

Sources: [UNODC, International Classification of Crime for Statistical Purposes (ICCS), 2015](https://www.unodc.org/documents/data-and-analysis/statistics/crime/ICCS/ICCS_English_2016_web.pdf); [UN Statistics Division, SDG indicator 16.1.1 metadata (number of victims of intentional homicide per 100,000 population)](https://unstats.un.org/sdgs/metadata/files/Metadata-16-01-01.pdf); [UNODC, Global Study on Homicide 2019, methodological annex](https://unodc.org/documents/data-and-analysis/statistics/Homicide/homicide2018/Methodology.pdf)

## 2. How to read the tables

Every layer is one source file. For each layer, six elements of the reference definition are compared with what the source counts. The treatment of an element is one of: **counted**, **not counted**, **partly counted**, **not stated** (the source does not say).

The verdict places the series as a whole against the reference:

- **Close**: By its own definition the series is essentially ICCS 0101: murder (and at most voluntary-manslaughter-type categories), no attempts, no non-intentional deaths.
- **Narrower**: Leaves out part of what ICCS 0101 includes (for example voluntary manslaughter reported under another head).
- **Broader**: Includes categories outside ICCS 0101 (attempts, negligent or traffic deaths, suicide, offences 'related to' homicide).
- **Proxy**: A broad category used as a stand-in because nothing narrower is published; reliability tier C.
- **Mixed**: Contains categories outside ICCS 0101 AND leaves out categories that it includes: the net difference has no sign.
- **Undetermined**: The source does not say enough to place the series against the ICCS.

## 3. Summary

yes = counted, no = not counted, partly = partly counted, n.s. = not stated.

| Layer | Counted unit | Murder | Manslaughter | Attempts | Non-intentional | Other | Legal | Verdict |
|---|---|---|---|---|---|---|---|---|
| [South Africa, provinces](#south_africa) | victims | yes | no | no | no | no | no | Close |
| [Nigeria, states](#nigeria) | cases | yes | yes | no | n.s. | no | n.s. | Undetermined |
| [Tanzania, regions](#tanzania) | victims | yes | partly | n.s. | no | n.s. | partly | Close |
| [Lesotho, districts](#lesotho) | cases | yes | no | no | no | no | n.s. | Close |
| [Kenya, counties](#kenya) | cases | yes | yes | n.s. | yes | yes | n.s. | Proxy |
| [Igarape Institute Homicide Monitor (Americas)](#igarape) | cases | n.s. | n.s. | n.s. | n.s. | n.s. | n.s. | Undetermined |
| [Bangladesh, metropolitan police units matched to cities](#bangladesh) | cases | yes | n.s. | n.s. | n.s. | n.s. | n.s. | Undetermined |
| [China: Hong Kong SAR, Shanghai, Beijing, Jiangsu](#china) | cases | yes | yes | no | partly | no | n.s. | Broader |
| [India, the 19 metropolitan cities](#india) | cases | yes | no | no | no | no | n.s. | Narrower |
| [Japan, prefectures](#japan) | cases | yes | no | yes | no | partly | n.s. | Mixed |
| [Malaysia, states and districts](#malaysia) | cases | yes | no | no | no | no | n.s. | Narrower |
| [Pakistan, districts and cities](#pakistan) | cases | yes | n.s. | no | no | no | n.s. | Undetermined |
| [Singapore (a city-state)](#singapore) | cases | yes | n.s. | n.s. | n.s. | n.s. | n.s. | Undetermined |
| [South Korea, cities and counties](#south_korea) | cases | yes | n.s. | yes | no | partly | n.s. | Broader |
| [Taiwan, cities and counties](#taiwan) | cases | yes | no | n.s. | no | no | n.s. | Undetermined |
| [Thailand, provinces](#thailand) | cases | yes | no | no | no | n.s. | n.s. | Close |
| [Uzbekistan, 14 regions](#uzbekistan) | cases | yes | n.s. | yes | no | n.s. | n.s. | Broader |
| [Eurostat, NUTS 3 regions](#eurostat) | offences | yes | partly | no | no | no | no | Close |
| [Eurostat, largest cities](#eurostat_cities) | offences | yes | partly | no | no | no | no | Close |
| [England and Wales, police force areas](#united_kingdom) | offences | yes | yes | no | no | no | n.s. | Broader |
| [Australia, states and territories](#states) | victims | yes | yes | no | partly | partly | partly | Broader |
| [New South Wales, local government areas](#new_south_wales) | victims | yes | yes | no | no | no | n.s. | Broader |
| [Victoria, local government areas](#victoria) | offences | yes | yes | yes | yes | no | n.s. | Broader |
| [Queensland, local government areas](#queensland) | offences | yes | yes | no | no | no | n.s. | Broader |
| [Western Australia, police districts](#western_australia) | offences | yes | yes | no | no | no | n.s. | Broader |

## 4. Cross-cutting issues

**What is counted: victims, cases, offences, incidents.** The UNODC indicator counts victims. Most police series count cases, offences or incidents, and a case with several victims counts once: the number is then lower than a victim count by an amount that depends on how often multiple-victim killings occur. Only three layers count victims (Australia's states, South Africa, Tanzania). A rate from a case-based series is therefore not strictly comparable with one from a victim-based series.

**Attempts.** The ICCS excludes attempted homicide. Japan's police statistics and Uzbekistan's indicator include attempts; Pakistan, Lesotho, New South Wales, Queensland, Western Australia and the Australian states exclude them; for most other series the source does not say. Where attempts are counted the flag `includes_attempts` is set in the rows.

**Manslaughter.** The ICCS includes voluntary manslaughter and excludes involuntary manslaughter. National codes do not draw the line in the same place: some count all manslaughter with murder (England and Wales, Australia), some keep culpable homicide in a separate head (Lesotho, and the penal-code countries of South Asia and Southeast Asia, to verify), and several sources do not say. A series that leaves out 'culpable homicide not amounting to murder' omits killings the ICCS would count.

**Broad categories and proxies.** Kenya's county tables publish a 'Homicide' category in which murder is 60 to 70% of the total (suicide and deaths by dangerous driving make up much of the rest); Victoria publishes 'Homicide and related offences'; Hong Kong's figure can include some non-intentional deaths. These are marked Broader or Proxy and, for Kenya, tier C.

**Police statistics and health registries.** Police series reflect what is reported, recorded and classified as an offence; health series (ICD-10 X85-Y09) reflect cause-of-death certification and exclude legal intervention. They usually differ: in South Africa the health registry records about a third of the police murder count. The database keeps the two apart (`indicator_type`) and uses the health figure only as a cross-check or where a compiler's source is a health body.

**Time reference.** Most series are calendar years of recording. South Africa and the United Kingdom use financial years from April (the panel's `year` is the start year), Western Australia from July. Eurostat's reference year is the year of recording. A killing is dated by when the police recorded it, not necessarily when it happened or when the victim died.

**Legal intervention, terrorism and armed conflict.** The ICCS excludes legal interventions and justifiable homicide, includes killings from terrorist activity and excludes killings in armed conflict. Only Eurostat's metadata states its treatment of these; for every other source it is not stated, and the series may contain, for example, killings by law enforcement or conflict deaths recorded as murders.

**What aggregate data cannot show.** The ICCS legal element (that the law holds the perpetrator liable) and the intent element are properties of each case. A published count cannot be checked against them; the comparison in this document is therefore a comparison of what each source says it counts, not an audit of the underlying cases.

## 5. Layer by layer

### Africa

<a id="south_africa"></a>
#### South Africa, provinces

- Source: South African Police Service (SAPS), annual and quarterly crime statistics workbooks (sheet 'RAW Data'), police stations summed to the 9 provinces
- Term in the source: Murder
- Counted unit: victims. SAPS counts bodies, so the unit is the victim.
- Time reference: Financial year April to March; `year` is the START year (2024 = April 2024 to March 2025).
- Verdict against the reference: **Close**. The SAPS murder category is the unlawful, intentional killing of another person, counted by victim, with attempts and negligent killing in separate categories.
- In the database: 117 rows, 9 units (admin1), 2013-2025; reliability tiers B 117; count unit in the panel: victims; definition flags in the rows: counts_victims

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | SAPS defines murder as the unlawful and intentional killing of another human being. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | SAPS lists culpable homicide, defined as the unlawful negligent causing of death of another human being, as a separate category. Whether SAPS places provoked intentional killings under murder is not stated. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted murder is a separate SAPS category. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Negligent killing is the SAPS category culpable homicide, separate from murder. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | By definition murder is the killing of another human being, so suicide and abortion are not in it. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not counted | By definition only unlawful killings are murder. The source does not say how deaths caused by police action are classified. | [source](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions) |

- Stations, districts, provinces and the national figure reconcile in all 13 years.
- Health cross-check: Statistics South Africa's mortality statistics record about a third of the police murder count as deaths by assault (7,486 against a police figure of the order of 24,000 in 2024); the two measures are informative about each other but not interchangeable.
- The denominator is the Statistics South Africa mid-year estimate of each year; population breaks of more than 3% a year (the 2023/24 census rebase) are flagged.

Sources: [SAPS crime statistics](https://www.saps.gov.za/services/crimestats.php); [Statistics South Africa, mid-year population estimates](https://www.statssa.gov.za); [SAPS crime definitions (Crime Hub reproduction of the SAPS Crime Definition Manual)](https://crimehub.org/analysis/fact-sheets/sa-crime-statistics-definitions)

<a id="nigeria"></a>
#### Nigeria, states

- Source: National Bureau of Statistics (NBS), 'Crime Statistics 2017', sheet 'Offences Against Persons' (police data by state command)
- Term in the source: MURDER and MAN SLAUGHTER (two columns, added)
- Counted unit: cases. Cases recorded by the police commands.
- Time reference: Calendar year 2017 (the only edition read so far).
- Verdict against the reference: **Undetermined**. Murder plus manslaughter of unstated kind.
- In the database: 37 rows, 37 units (admin1), 2017-2017; reliability tiers B 37; count unit in the panel: cases; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | 3,219 cases nationally in 2017. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | 'Man slaughter' (120 cases nationally) is added to murder; whether it is voluntary or involuntary is not stated. | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted Murder is a column of its own in the NBS state tables of offences against persons. | [source](https://nigerianstat.gov.ng/download/786) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not stated | The list of offences against persons has no column for negligent or traffic deaths. Whether the 'Man Slaughter' column contains negligent killings is not stated. | [source](https://nigerianstat.gov.ng/download/786) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | Suicide and Attempted Suicide are columns of their own. The NBS description of offences against persons also names infanticide and concealment of birth, but the state tables give them no column, so where they are recorded is not stated. | [source](https://nigerianstat.gov.ng/download/786) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The NBS tables and its note on the police returns do not discuss legal intervention or justified killings. | [source](https://nigerianstat.gov.ng/download/25) |

- The commands without territory (RAILWAY and PAP in the sheet) are in the national total only.
- The denominator is the NBS population projection from the 2006 census (Demographic Statistics Bulletin 2020), so it is not an independent count.
- The statistics are the returns of the state commands of the Nigeria Police Force: records of alleged or confirmed offences known to the police, which the NBS says cover only what is reported.

Sources: [NBS, Crime Statistics 2017](https://nigerianstat.gov.ng/resource/CRIME%20STATISTICS%202017.xlsx); [NBS, Demographic Statistics Bulletin 2020](https://nigerianstat.gov.ng/download/1241121); [NBS, Crime Statistics: Reported Offences 2017 (report with the state tables)](https://nigerianstat.gov.ng/download/786); [NBS, note on the police crime returns](https://nigerianstat.gov.ng/download/25)

<a id="tanzania"></a>
#### Tanzania, regions

- Source: National Bureau of Statistics (NBS) with the Tanzania Police Force, 'Crime and Traffic Incidents Statistics' (2024, 2025), table 'Number of Reported Murder Cases, Number of Suspects and People Killed by Sex and Reason and Police Region'; police regions aggregated to the 31 administrative regions
- Term in the source: Murder cases and people murdered
- Counted unit: victims. The count used is the people murdered (the report also gives cases).
- Time reference: Calendar year.
- Verdict against the reference: **Close**. A police murder table by region; about 1% of the 2024 total is manslaughter by the report's own reason codes.
- In the database: 62 rows, 31 units (admin1), 2024-2025; reliability tiers B 62; count unit in the panel: victims; definition flags in the rows: counts_victims

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | 2,263 people murdered in 2,193 cases in 2024. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | partly counted | The report lists 'manslaughter' (25 in 2024) among the reasons for the killings it counts, so the table includes some killings the police classify as manslaughter. | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not stated | The report lists murder, rape, unnatural offences and human trafficking in the category of offences against persons; no attempted-murder line is named. | [source](https://www.nbs.go.tz/uploads/statistics/documents/en-1744876106-Crime%20and%20Traffic%20Incidents%20Statistics%20%20January%20-%20December%202024.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Road traffic deaths are tabulated in a separate chapter of the same report (accidents, deaths and injured). Other negligent killings are not addressed. | [source](https://www.nbs.go.tz/uploads/statistics/documents/en-1744876106-Crime%20and%20Traffic%20Incidents%20Statistics%20%20January%20-%20December%202024.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | Suicide and abortion are not named among the offences against persons the report lists. | [source](https://www.nbs.go.tz/uploads/statistics/documents/en-1744876106-Crime%20and%20Traffic%20Incidents%20Statistics%20%20January%20-%20December%202024.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | partly counted | The reasons listed for the killings in the murder table include 'extra judicial incidents' (405 of 2,263 in 2024), and the report has a separate table of extrajudicial killings by region (2015 to 2024). It does not say who the perpetrators are. | [source](https://www.nbs.go.tz/uploads/statistics/documents/en-1744876106-Crime%20and%20Traffic%20Incidents%20Statistics%20%20January%20-%20December%202024.pdf) |

- The marine, railway, airport and port police units have no residents and are in the national total only.
- The denominator is the 2022 census, so rates for 2024 and 2025 use a base 1.9 and 2.9 years old (tier B).

Sources: [NBS, Crime statistics reports](https://www.nbs.go.tz/statistics/topic/crime-statistics); [NBS, Crime and Traffic Incidents Statistics, January to December 2024](https://www.nbs.go.tz/uploads/statistics/documents/en-1744876106-Crime%20and%20Traffic%20Incidents%20Statistics%20%20January%20-%20December%202024.pdf)

<a id="lesotho"></a>
#### Lesotho, districts

- Source: Bureau of Statistics (BOS), 'Crime Statistics Report' (2015, 2019 to 2022), table of serious cases by policing district (police data); the 11 policing districts are aggregated to 10 districts
- Term in the source: Murder (serious case of crime)
- Counted unit: cases. Reported serious cases.
- Time reference: Calendar year.
- Verdict against the reference: **Close**. Murder only; attempted murder and culpable homicide are counted elsewhere in the report.
- In the database: 45 rows, 9 units (admin1), 2015-2022; reliability tiers B 45; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | 944 cases nationally in 2022. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | 'Culpable homicide' is reported as its own category among the general cases (50 in 2019). | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not counted | 'Attempted murder' is a separate line (298 in 2022). | see the sources below |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Culpable homicide is separate. | see the sources below |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The serious-case categories are armed robbery, assault with intent to cause grievous bodily harm, attempted murder, car theft, fraud, house breaking, human trafficking, murder, robbery, sexual offence and stock theft; there is none for suicide or abortion. | [source](https://publiceyenews.com/2021/07/26/lesotho-tops-global-murder-rankings/) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The Bureau's report classifies the police's reported cases and does not discuss legal intervention. | [source](https://www.bos.gov.ls/BoS_reports/Copy%20of%20Demography/2022_Crime_Statistics_report.pdf) |

- Maseru Urban and Maseru Rural are added to form the Maseru district. Qacha's Nek (74,566 residents) is below the project's 100,000 minimum and is in the national total only.
- The denominator is the April 2016 census used unchanged for every year, so it is 0.8 years from 2015 and 6.2 years from 2022.
- The data are the cases the Lesotho Mounted Police Service reports to the Bureau, which compiles and tabulates them; the police classify every reported case as serious or general, and 'culpable homicide' sits among the general cases. Whether it contains intentional killings that the ICCS would count is not stated.

Sources: [BOS crime statistics reports](https://www.bos.gov.ls/BoS_reports/Copy%20of%20Demography/2022_Crime_Statistics_report.pdf); [Press report quoting the Bureau's 2020 report on the serious-case categories](https://publiceyenews.com/2021/07/26/lesotho-tops-global-murder-rankings/)

<a id="kenya"></a>
#### Kenya, counties

- Source: National Police Service (NPS), 'Annual Crime Report' (2015, 2016, 2017, 2021), appendix 'Offences per County'; the national total of each year is checked against the KNBS Statistical Abstract, table 17.1
- Term in the source: 'Homicide' (a police category, broader than murder)
- Counted unit: cases. Cases recorded by the police.
- Time reference: Calendar year of the report.
- Verdict against the reference: **Proxy**. Murder is only 60 to 70% of the category the county table publishes; no county table of murder alone exists, so every row is tier C.
- In the database: 188 rows, 47 units (admin1), 2015-2021; reliability tiers C 188; count unit in the panel: cases; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | Murder was 61.5% of the category in 2021 (2,018 of 3,281) and 70.4% in 2017. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Manslaughter is a component (72 in 2021). | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not stated | Attempted murder is not among the components the NPS and the NCRC list for the Homicide category (murder, manslaughter, infanticide, procuring abortion, concealing birth, suicide, causing death by dangerous driving). | [source](https://www.the-star.co.ke/news/2025-12-11-factors-most-likely-to-cost-you-your-life-report) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | counted | Causing death by dangerous driving (389 of 3,281 in 2021). | see the sources below |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | counted | Suicide (658 in 2021), procuring abortion (32) and concealing birth (70). Infanticide (42) is also in the category but the ICCS includes infanticide. | see the sources below |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The NPS reports and the NCRC study do not discuss legal intervention or justified killings. | [source](https://www.the-star.co.ke/news/2025-12-11-factors-most-likely-to-cost-you-your-life-report) |

- The county figure cannot be split into murder and the rest; the national composition of the year is written into every row.
- The denominator is the police's own county population: the 2009 census for the reports of 2015 to 2017 and the 2019 census for 2021, so the 2017 to 2021 jump in many counties is a census change (flagged).
- The reports of 2018 to 2020 have no county-by-category table and are not in the panel.
- The National Crime Research Centre noted that the NPS figures differ from the Directorate of Criminal Investigation's because the NPS category includes dangerous-driving cases, which the traffic department handles.
- The same study points out that many cases are classified as murder or manslaughter at the recording stage and may not qualify on investigation, and that it is not possible to tell whether an incident is manslaughter until the prosecution stage, yet the category is in the annual statistics.
- Homicide offences are provided for in Division IV of the Penal Code (murder, manslaughter, infanticide and offences connected to suicide).

Sources: [NPS annual crime reports](https://nationalpolice.go.ke/reports-0); [KNBS Statistical Abstract, table 17.1](https://www.knbs.or.ke/wp-content/uploads/2025/02/Governance-Peace-and-Security.xlsx); [The Star on the NCRC homicide study (December 2025)](https://www.the-star.co.ke/news/2025-12-11-factors-most-likely-to-cost-you-your-life-report); [Eastleigh Voice on the same study](https://eastleighvoice.co.ke/national%20crime%20research%20centre/253190/men-are-majority-of-homicide-victims-in-kenya-despite-media-focus-on-women-state-report-reveals); [The Standard on homicide offences under the Penal Code](https://standardmedia.co.ke/business/amp/national/article/2001536230/nairobi-leads-in-1011-homicides-recorded-across-kenya)

### Americas

<a id="igarape"></a>
#### Igarape Institute Homicide Monitor (Americas)

- Source: Igarape Institute (Brazil), Homicide Monitor feature service: a SECONDARY compilation of figures that national and local authorities publish; every row cites the compiler's own official source
- Term in the source: 'Homicide' as defined by each cited source
- Counted unit: cases. A count per city or state and year: police-recorded rows count cases (whether cases or victims depends on the cited source) and health-registry rows count deaths (322 rows in 4 countries).
- Time reference: Calendar year.
- Verdict against the reference: **Undetermined**. A mix of police-recorded cases and health-registry deaths with the definitions of each source; never tier A.
- In the database: 11,282 rows, 931 units (admin1, city), 2000-2024; reliability tiers B 10,425, C 857; count unit in the panel: cases, deaths; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The layer states no definition: each row follows the definition of the source it cites (fields igarape_source_1 and igarape_source_2). | see the sources below |

- Rows whose cited source is an international aggregator (UNODC, Eurostat and similar) are excluded: they are national figures placed on a capital.
- The `indicator_type` of every row says whether the cited source is a police/security body (police_recorded_cases) or a health/forensic body (health_registry_deaths); the table below counts them per country.
- The layer is a secondary compilation: for a country with an official series in this database, the official series is the one to use.
- The layer has no definition of its own: the data feed carries a count and the compiler's citation per row (fields homicide, source_1, source_2), so each series inherits the definition of its cited source.
- Igarape's research director has written that the Monitor limits itself to a tighter selection of authoritative sources than other compilations, uses the urban-agglomeration definition for cities, and that in countries such as Mexico and Brazil police killings fall under a different category and can significantly augment the overall count.

The three sources most cited by each country's rows (the definition of every series is that of its source):

| Country | Most cited sources (rows) |
|---|---|
| Argentina | Ministerio de Seguridad (1,450); Ministerio de Seguridad de la Nación (25) |
| Belize | Belize Police Department (10) |
| Bolivia (Plurinational State of) | Observatorio Nacional de Seguridad (149); Policía Boliviana (54) |
| Brazil | SINESP - Ministério da Justiça e Segurança Pública (1,192) |
| Canada | Statistics Canada (370) |
| Chile | Centro de Estudios de Análisis de Delito -CEAD - Centro para la Prevención de Homicidios y (189) |
| Colombia | Policía Nacional (868); Policía Nacional de Colombia (402) |
| Costa Rica | Organismo de Investigación Judicial (OIJ) (126) |
| Dominican Republic | Policía Nacional (419) |
| Ecuador | Ministerio del Interior/DINASED (486) |
| El Salvador | Dirección de Información y Análsis, Ministerio de Justicia y Seguridad Pública (118); Medicina Legal (70) |
| Guatemala | Policía Nacional Civil (570); Policia Nacional Civil (51) |
| Guyana | Guyana Police Force (40) |
| Haiti | Police Nationale (1) |
| Honduras | Observatorio de la Violencia (265); Policía Nacional (109) |
| Jamaica | Jamaica Constabulary Police Force (250) |
| Mexico | SESNSP -Secretariado del Ejecutivo del Sistema Nacional de Seguridad Pública (1,208) |
| Nicaragua | Policía Nacional (221); Instituto de Medicina Legal - Poder Judicial (17) |
| Panama | Policía Nacional (212); Policia Nacional (15); Policía Nacional/SIEC Homicidio intencional (2) |
| Paraguay | Policía Nacional de Paraguay (239); Policia Nacional de Paraguay (39) |
| Peru | SINADEF - Sistema de Información de Defunciones (228) |
| Puerto Rico | Police of Puerto Rico (10); Health department - Departamento de Salud (7); Policía de Puerto Rico (6) |
| The Bahamas | Royal Bahamas Police Force (13) |
| Trinidad and Tobago | Trinidad and Tobago Police Service (67) |
| United States of America | FBI (833); Police office (150); Police Department. Compilated by Council on Criminal Justice (CCJ) (114) |
| Uruguay | Observatorio Nacional sobre Violencia y Criminalidad (119) |
| Venezuela (Bolivarian Republic of) | Observatorio Venezolano de la Violencia (184); Cuerpo de Investigaciones Científicas, Penales y Criminalísticas (CICPC) (72); Reportes de Incidencia Delictiva CICPC. Incluye resistencia a la autoridad (69) |

Sources: [Igarape Institute Homicide Monitor](https://homicide.igarape.org.br); [Feature service](https://geo.igarape.org.br); [Americas Quarterly: how the Igarape and SJP city rankings differ](https://americasquarterly.org/?p=5093); [Business Insider: why homicide rankings are hard (interview with Igarape's research director)](https://businessinsider.in/3-big-reasons-why-its-so-hard-to-tell-just-how-violent-the-worlds-most-violent-cities-are/amp_articleshow/68713932.cms)

### Asia

<a id="bangladesh"></a>
#### Bangladesh, metropolitan police units matched to cities

- Source: Bangladesh Bureau of Statistics (BBS), Statistical Yearbook, table 'Number of Crimes by Type as Registered with the Police' (source line: Police Headquarters), column 'Total No. of Murder', for the 8 metropolitan police units
- Term in the source: Murder
- Counted unit: cases. Crimes registered with the police.
- Time reference: Calendar year of FILING: the Police Headquarters compiles the statistics from the cases filed at police stations; over 400 of the 1,930 murder cases recorded in the first half of 2025 were filed for incidents of earlier years.
- Verdict against the reference: **Undetermined**. The yearbook gives a column 'Murder' without a definition.
- In the database: 8 rows, 8 units (city), 2025-2025; reliability tiers B 8; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is the 'Murder' category of the Police Headquarters' crime statistics (murder cases filed). | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | The police crime categories published are murder, robbery, dacoity, speedy-trial cases, rioting, violence against women and children, kidnapping, assault on police, burglary, theft and others; none is culpable homicide. | [source](https://mail.morungexpress.com/crime-surge-grips-bangladesh-in-2025-women-and-children-worst-hit) |
| Attempted killings (ICCS: separate category, excluded) | not stated | No attempted-murder category is named in the police headquarters' published list; where such cases are recorded is not stated. | [source](https://mail.morungexpress.com/crime-surge-grips-bangladesh-in-2025-women-and-children-worst-hit) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not stated | No category for deaths by negligence is named in the published list. | [source](https://mail.morungexpress.com/crime-surge-grips-bangladesh-in-2025-women-and-children-worst-hit) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | No category for suicide or abortion is named in the published list. | [source](https://mail.morungexpress.com/crime-surge-grips-bangladesh-in-2025-women-and-children-worst-hit) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The published statistics do not discuss legal intervention or justified killings. | [source](https://en.prothomalo.com/bangladesh/crime-and-law/5tgb7c0r7b) |

- A police unit's jurisdiction is not exactly the matching city corporation's boundary: the match is an approximation stated in every row.
- The denominator is the 2022 census population of the city corporation(s), used unchanged (no growth), so the rate is somewhat high.
- The Police Headquarters compiles national crime statistics from the cases filed at police stations across the country; the figure is the number of murder CASES filed (the press often reports it as people murdered).
- The BBS Statistical Yearbook table carries the Police Headquarters as its source, so these statements describe the same series.

Sources: [BBS Statistical Yearbook](https://bbs.gov.bd); [Prothom Alo on the police headquarters' crime statistics](https://en.prothomalo.com/bangladesh/crime-and-law/5tgb7c0r7b); [Bonik Barta on the same statistics](https://en.bonikbarta.com/bangladesh/G3ICw6vDBOGRX24a); [Asia News Network: murder cases filed over earlier incidents (2025)](https://asianews.network/?p=214475); [IANS: crime categories of the police statistics (2025)](https://mail.morungexpress.com/crime-surge-grips-bangladesh-in-2025-women-and-children-worst-hit)

<a id="china"></a>
#### China: Hong Kong SAR, Shanghai, Beijing, Jiangsu

- Source: Hong Kong Police Force 'Crime Statistics in Detail' (column 'Homicide'); mainland units: the provincial or municipal statistical yearbook table 'Criminal cases recorded by the public security organs' (row 杀人)
- Term in the source: Homicide (HKPF); 杀人 (yearbooks)
- Counted unit: cases. Cases recorded by the police.
- Time reference: Calendar year.
- Verdict against the reference: **Broader**. Murder plus manslaughter, with some non-intentional deaths possible in a given year.
- In the database: 24 rows, 3 units (admin1), 2014-2024; reliability tiers A 21, B 3; count unit in the panel: cases; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is the source's own homicide category: 'Homicide' in the Hong Kong Police Force tables and the 杀人 line of the yearbooks. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | HKPF's 'Homicide' is murder plus manslaughter. | see the sources below |
| Attempted killings (ICCS: separate category, excluded) | not counted | The Hong Kong Year Book police appendix lists 'Attempted murder' as a line of its own next to 'Murder and manslaughter'. | [source](https://hkintexts.histsyn.com/page/1738795) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | partly counted | HKPF's own annual reviews note that the figure can include deaths from, for example, dangerous driving and industrial accidents. | see the sources below |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The violent-crime lines of the police tables (rape, indecent assault, murder and manslaughter, attempted murder, wounding, serious assault, robbery and others) have none for suicide or abortion. | [source](https://hkintexts.histsyn.com/page/1738795) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The police tables and the Year Book notes do not discuss legal intervention. | [source](https://hkintexts.histsyn.com/page/1738795) |

- A single multi-fatality event can raise a year's count in Hong Kong.
- The panel lists which units were built (see the coverage line); the mainland units are added once their table layouts are confirmed (Beijing's table is published only as an image).
- The mainland yearbook's definition of 杀人 is not stated in the tables.
- The HKPF's own crime-situation release for 2025 states that its figure included the 168 deaths in the Tai Po fire, which was classified as manslaughter: the category can contain a very large non-intentional event in one year.
- The statements describe the series of the units listed in the panel for this layer.

Sources: [HKPF crime statistics (data.gov.hk)](https://data.gov.hk); [Shanghai Statistical Yearbook, table 23.3](https://tjj.sh.gov.cn); [Hong Kong Year Book, police crime statistics appendix (a reproduction)](https://hkintexts.histsyn.com/page/1738795); [HKPF, crime situation in Hong Kong 2025](https://gia.info.gov.hk/general/202602/11/P2026021100763_532760_1_1770806232842.pdf)

<a id="india"></a>
#### India, the 19 metropolitan cities

- Source: National Crime Records Bureau (NCRB), 'Crime in India', table 2B.1 'Murder Cases in Metropolitan Cities' (2016 to 2024)
- Term in the source: Murder
- Counted unit: cases. Murder cases registered in each city.
- Time reference: Calendar year (the newest of the three years each edition prints).
- Verdict against the reference: **Narrower**. Murder under section 302 only. Culpable homicide not amounting to murder, dowry deaths and infanticide, which the ICCS counts, are separate NCRB heads.
- In the database: 171 rows, 19 units (city), 2016-2024; reliability tiers B 171; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The NCRB crime head is 'Murder (Sec.302 IPC)'. | [source](https://pcpc.gov.in/files/Ncrb/57.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | 'Culpable Homicide not amounting to Murder (Sec.304 IPC)' is a separate NCRB crime head. Under the Penal Code murder is the part of culpable homicide that has no mitigating exception; killings that fall under an exception of section 300 (grave and sudden provocation is one) are punished under section 304 and therefore sit outside the Murder head. The ICCS counts voluntary manslaughter of that kind as intentional homicide. | [source](https://pcpc.gov.in/files/Ncrb/57.pdf) |
| Attempted killings (ICCS: separate category, excluded) | not counted | 'Attempt to commit Murder (Sec.307 IPC)' and 'Attempt to commit Culpable Homicide (Sec.308 IPC)' are separate heads. | [source](https://pcpc.gov.in/files/Ncrb/57.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | 'Causing Death by Negligence (Sec.304-A IPC)' is a separate head. | [source](https://pcpc.gov.in/files/Ncrb/57.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | Dowry Deaths (Sec.304-B), Infanticide (Sec.315), Foeticide (Sec.316) and Abetment of Suicide (Sec.305/306) are separate heads. The ICCS includes dowry killings and infanticide in intentional homicide, so they are missing from the Murder head. | [source](https://indiastat.com/table/template/Jammu-and-Kashmir-state/crime-law/incidence-violent-crimes-jammu-kashmir-2019-part-i/1394740) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The NCRB tables define the head only by the penal-code section; they do not say how deaths from lawful acts are treated. | [source](https://dataful.in/datasets/23173) |

- Only the 19 cities of the NCRB table are covered, not the states.
- The city population printed in the same table often carries the 2011 census; rows are tier B with the age of that base in `population_age_years`.
- The Indian Penal Code was replaced by the Bharatiya Nyaya Sanhita in 2024 (culpable homicide at section 100, the punishment for culpable homicide not amounting to murder at section 105, formerly 299 and 304); the heads described here are those of the Penal Code.

Sources: [NCRB, Crime in India](https://ncrb.gov.in); [NCRB monthly crime statistics form: the crime heads](https://pcpc.gov.in/files/Ncrb/57.pdf); [NCRB tables by crime head (republished by Dataful)](https://dataful.in/datasets/23173); [NCRB tables by crime head (republished by Indiastat)](https://indiastat.com/table/template/Jammu-and-Kashmir-state/crime-law/incidence-violent-crimes-jammu-kashmir-2019-part-i/1394740); [Supreme Court of India, judgment on murder and culpable homicide (IPC 299, 300, 302, 304)](https://api.sci.gov.in/jonew/judis/39420.pdf); [Bharatiya Nyaya Sanhita concordance with the IPC](https://devgan.in/bns/chapter_06.php)

<a id="japan"></a>
#### Japan, prefectures

- Source: National Police Agency (NPA), crime statistics (確定値), table 6 'Serious crimes and serious thefts by prefecture', block 殺人 (homicide), column 認知件数 (cases recognised by the police), via e-Stat
- Term in the source: 殺人 (homicide, murder)
- Counted unit: cases. Cases, not victims.
- Time reference: Calendar year.
- Verdict against the reference: **Mixed**. Broader because attempts, preparation for murder and assisted suicide are inside; narrower because injury resulting in death and robbery-murder are counted elsewhere.
- In the database: 188 rows, 47 units (admin1), 2022-2025; reliability tiers A 188; count unit in the panel: cases; definition flags in the rows: includes_attempts

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The NPA offence group 殺人 contains 殺人罪 (murder). | [source](https://www.pref.tottori.lg.jp/secure/532570/hannzaitoukeiR02.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | 傷害致死罪 (injury resulting in death) is counted under 傷害 (injury), and 強盗殺人罪 (robbery-murder) under 強盗 (robbery), not under 殺人. The ICCS counts a death from a serious assault and a killing during a robbery as intentional homicide. | [source](https://www.pref.tottori.lg.jp/secure/532570/R6-toikeisyo-00.pdf) |
| Attempted killings (ICCS: separate category, excluded) | counted | Attempts are counted with the completed offence (flag includes_attempts). 殺人予備罪 (preparation for murder) is also listed inside the 殺人 group. | [source](https://www.pref.tottori.lg.jp/secure/532570/hannzaitoukeiR02.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | The Penal Code offence count excludes road-accident offences under article 211; those and the driving-death law are classified as special-law offences (特別法犯), outside the statistics used. | [source](https://www.pref.yamaguchi.lg.jp/uploaded/attachment/192702.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | partly counted | 自殺関与罪 (abetting suicide) is inside the 殺人 group, and the ICCS excludes assisting suicide; 嬰児殺 (infanticide) is inside as well, and the ICCS includes it. | [source](https://www.pref.tottori.lg.jp/secure/532570/hannzaitoukeiR02.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The NPA classification and notes list charges by name and do not discuss legal intervention. | [source](https://www.npa.go.jp/toukei/seianki/R07/r07keihouhantoukeisiryou.pdf) |

- The police cases are cross-checked against the health ministry's homicide deaths (他殺, vital statistics) as a diagnostic only.
- Population is the 1 January resident register (Japanese and foreign residents); the rate of year Y uses the mean of 1 January Y and Y+1.
- The 殺人 group of the NPA classification consists of 殺人罪, 嬰児殺, 殺人予備罪 and 自殺関与罪. The figure used is the number of cases recognised by the police (認知件数) of that group, summed by prefecture.
- Because 傷害致死罪 and 強盗殺人罪 sit in other groups, the Japanese 殺人 count is not a count of every unlawful intentional killing: the health ministry's vital statistics (他殺) are the cross-check.

Sources: [e-Stat, NPA crime statistics](https://www.e-stat.go.jp); [MIC resident register population](https://www.soumu.go.jp); [NPA offence classification as printed in a prefectural police statistics book (Tottori)](https://www.pref.tottori.lg.jp/secure/532570/hannzaitoukeiR02.pdf); [The same, another edition (Tottori)](https://www.pref.tottori.lg.jp/secure/532570/R6-toikeisyo-00.pdf); [Definitions of Penal Code and special-law offences (Yamaguchi)](https://www.pref.yamaguchi.lg.jp/uploaded/attachment/192702.pdf); [NPA, Penal Code offences statistics (殺人 section)](https://www.npa.go.jp/toukei/seianki/R07/r07keihouhantoukeisiryou.pdf)

<a id="malaysia"></a>
#### Malaysia, states and districts

- Source: Royal Malaysia Police (PDRM) crime by district, published by the Department of Statistics Malaysia (DOSM) on data.gov.my, crime type 'murder'
- Term in the source: Murder
- Counted unit: cases. Cases recorded, one row per state, district and year.
- Time reference: Calendar year (2020 to 2023).
- Verdict against the reference: **Narrower**. Murder under section 302 only: culpable homicide not amounting to murder and infanticide, which the ICCS includes, are separate offences monitored elsewhere.
- In the database: 317 rows, 81 units (admin1, admin2), 2020-2023; reliability tiers A 56, B 261; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The police index defines murder by section 300 of the Penal Code (Act 574), the intention-based form of culpable homicide; the police division that monitors murder data does so under section 302. | [source](https://rcastoragev2.blob.core.windows.net/482c2bf3fce06dad4c816688da7569cf/PMC6811922.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | Culpable homicide not amounting to murder (section 304) is a separate offence of the Penal Code and is not in the series, which counts murder under section 302 only. The ICCS counts voluntary manslaughter of that kind as intentional homicide. | [source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9330596) |
| Attempted killings (ICCS: separate category, excluded) | not counted | The series is murder under section 302 only; attempts are other offences (the data feed and the DOSM tables carry 'Murder' as the type). | [source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9330596) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Causing death by negligence (section 304A) is a separate offence and is outside the murder series. | [source](https://www.burgielaw.com/resources/act/?act_title=Penal+Code) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The police data exclude infanticide (section 309A) and child abandonment (section 317), which other police units monitor. The ICCS includes infanticide in intentional homicide, so the series is narrower on that point; suicide and abortion are not murder. | [source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9330596) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The DOSM tables carry notes for rape (section 376) and robbery but none for murder, and no discussion of legal intervention. | [source](https://www.dosm.gov.my/portal-main/release-content/crime-statistics-malaysia-) |

- Two levels, never to be added together: states (all police districts of the state) and districts (a police district matched by name to an administrative district of the same name).
- Kuala Lumpur uses the population of Kuala Lumpur plus Putrajaya.
- A police statement reported in 2025 says that 185 investigation papers, 71% of the murder cases of 2023, led to charges under section 302 of the Penal Code: the police 'murder' category therefore appears to be the classification at investigation, not the final charge.
- DOSM states in its preface that its crime statistics are compiled with guidance from the UNODC's ICCS (version 1.0); the statement is general and does not change how murder is delimited by the police.
- The definition comes from the published description of the police index and from a study of how the police monitor murder.

Sources: [DOSM open data (data.gov.my)](https://data.gov.my); [DOSM, Crime Statistics, Malaysia (2024 edition)](https://storage.dosm.gov.my/crime/crime_2023.pdf); [Malay Mail, police statement on murder cases and section 302 charges](https://www.malaymail.com/news/malaysia/2025/06/16/malaysia-sees-476-murders-in-less-than-two-years-with-selangor-leading-due-to-urban-sprawl-and-foreign-worker-surge/180512); [Data in Brief (2019): definitions of the police index crimes in Malaysia](https://rcastoragev2.blob.core.windows.net/482c2bf3fce06dad4c816688da7569cf/PMC6811922.pdf); [Study of child homicide in Malaysia: how the police monitor murder](https://pmc.ncbi.nlm.nih.gov/articles/PMC9330596); [Penal Code (Act 574), chapter XVI: offences affecting life](https://www.burgielaw.com/resources/act/?act_title=Penal+Code)

<a id="pakistan"></a>
#### Pakistan, districts and cities

- Source: Pakistan Bureau of Statistics (PBS), 'District wise Crime data' (data of the National Police Bureau), one Excel file per province, column 'Murder'
- Term in the source: Murder
- Counted unit: cases. Police-registered murder cases.
- Time reference: Calendar year; only full-year blocks are used (blocks titled with a month or quarter are excluded).
- Verdict against the reference: **Undetermined**. Murder cases with attempted murder excluded; the rest is not stated.
- In the database: 222 rows, 128 units (admin1, admin2, city), 2024-2025; reliability tiers A 210, B 12; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is the 'Murder' column of the provincial police reports. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | The provincial police reports have no column for the other kinds of qatl (qatl-i-khata, qatl-bis-sabab, qatl shibh-i-amd); where such cases are recorded (possibly under Miscellaneous or the accident columns) is not stated, and the files carry no notes. | [source](https://www.pbs.gov.pk/social-statistics-2/) |
| Attempted killings (ICCS: separate category, excluded) | not counted | The column is 'Murder', not 'attempted murder'. | see the sources below |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Every provincial report has a separate column for Traffic Accident (Sindh: Fatal Accident and Non-Fatal Accident). Other negligent killings are not addressed. | [source](https://www.pbs.gov.pk/social-statistics-2/) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | Suicide and Attempted Suicide (spelled 'Socide' in the files) are columns of their own. | [source](https://www.pbs.gov.pk/social-statistics-2/) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The files give no notes or definitions below the tables and do not discuss legal intervention. | [source](https://www.pbs.gov.pk/social-statistics-2/) |

- Most districts stand in for their city and include their rural area (`is_city_proxy`).
- Districts created after the 2023 census are merged into their parent district by an administrative-history table kept in the pipeline, so those rows are never tier A.
- The columns of the provincial 'District wise Crime Report' files are: All Reported, Murder, Attempted Murder, Suicide, Attempted Suicide, Gang Rape, Kidnapping/Abduction, Dacoity, Robbery, Traffic Accident (Sindh: Fatal and Non-Fatal Accident), Burglary, Cattle theft, Motor Vehicle Theft, Other theft, Miscellaneous (and in Sindh Arms Ordinance and Other Local and Special Law). The files state the unit only as '(Number)'.
- The Penal Code, after the Qisas and Diyat reform, distinguishes four kinds of qatl: qatl-i-amd (section 300, punished under 302), qatl shibh-i-amd, qatl-i-khata and qatl-bis-sabab. Police FIR monitoring by FAFEN tabulates murder, attempted murder, hurt and the two involuntary kinds separately, which fits a police 'Murder' column that is qatl-i-amd, but the PBS files themselves do not say so.

Sources: [PBS district-wise crime data](https://www.pbs.gov.pk/social-statistics-2/); [Pakistan Penal Code, offences affecting the human body (study guide)](https://open-exam-prep.com/study-guides/pk-law-gat/ppc-body-property/offences-human-body-ch16); [FAFEN Pakistan Crime Monitor (police FIR categories)](https://demo1.fafen.org/pakistan-crime-monitor-28823-crimes-reported-in-72-districts-during-january-2011/)

<a id="singapore"></a>
#### Singapore (a city-state)

- Source: Department of Statistics Singapore (SingStat) Table Builder, table M890891 'Cases Recorded For Selected Major Offences', series 'Murder'
- Term in the source: Murder
- Counted unit: cases. Cases recorded.
- Time reference: Calendar year of REPORTING: SingStat states that its crime statistics are compiled from the offences reported to the police in the reference period, not from the date of the offence.
- Verdict against the reference: **Undetermined**. The series is labelled murder; the published glossary gives no definition, so it cannot be placed against the ICCS.
- In the database: 15 rows, 1 unit (city), 2011-2025; reliability tiers B 15; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | 'Murder' is named among the selected major offences of the SingStat table. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | SingStat's glossary names murder among the selected major offences and defines none of them. The Penal Code treats culpable homicide not amounting to murder as a distinct offence from murder, but whether the 'Murder' series includes it is not stated. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |
| Attempted killings (ICCS: separate category, excluded) | not stated | Not stated in the table or its glossary. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not stated | Not stated in the table or its glossary. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | Not stated in the table or its glossary. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | Not stated in the table or its glossary. | [source](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained) |

- A single national unit: the series gives no sub-national detail.
- The Court of Appeal treats culpable homicide not amounting to murder (Penal Code section 304) as a separate offence from murder ([2019] SGCA 22). The Singapore Police Force's published statistics do not say whether such cases are counted under 'murder'.

Sources: [SingStat Table Builder](https://tablebuilder.singstat.gov.sg); [SingStat, 'Our data explained' (glossary of public-safety terms)](https://www.singstat.gov.sg/find-data/explore-data-themes/society/public-safety/our-data-explained); [Singapore Court of Appeal, [2019] SGCA 22](https://www.singaporelawwatch.sg/Portals/0/Docs/Judgments/2019/[2019]%20SGCA%2022.pdf)

<a id="south_korea"></a>
#### South Korea, cities and counties

- Source: National Police Agency, 'Violent crime occurrence by police station' (data.go.kr dataset 15084592), column 살인 (murder); police stations grouped into cities from the Ministry of the Interior and Safety (MOIS) list
- Term in the source: 살인 (murder)
- Counted unit: cases. Cases by police station.
- Time reference: Calendar year (only 2025 is saved: the portal offers the newest release only).
- Verdict against the reference: **Broader**. The Korean police homicide count includes attempts, instigation, aiding, preparation and aiding suicide, which the ICCS excludes; the national indicator portal states the difference itself.
- In the database: 72 rows, 72 units (admin1, admin2), 2025-2025; reliability tiers B 72; count unit in the panel: cases; definition flags in the rows: includes_attempts

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The five-crimes series 살인 includes homicide under the Criminal Act. | [source](https://www.ggpolice.go.kr/main/html.do?menu=HF14) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | The police note lists the offences of the homicide chapter; where injury resulting in death and robbery-murder are counted is not stated (the series 폭력 is defined as extortion, damage, injury, assault, confinement, threat, abduction and violence offences). | [source](https://www.ggpolice.go.kr/main/html.do?menu=HF14) |
| Attempted killings (ICCS: separate category, excluded) | counted | The police definition says '미수, 교사, 방조, 예비 등 포함': attempts, instigation, aiding and preparation are included (flag includes_attempts). The national indicator portal says the domestic standard, unlike the international one, includes attempted murder and conspiracy. | [source](https://www.ggpolice.go.kr/main/html.do?menu=HF14) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | The list of included offences (homicide, infanticide, patricide, consent killing, aiding suicide, killing by deceit or force) contains no negligent killing. | [source](https://www.ggpolice.go.kr/main/html.do?menu=HF14) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | partly counted | Instigating or aiding suicide (자살교사·방조) is inside, and the ICCS excludes assisting suicide; infanticide (영아살해) is inside as well, and the ICCS includes it. Consensual killing (촉탁·승낙살인) is inside. | [source](https://www.ggpolice.go.kr/main/html.do?menu=HF14) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The police note and the dataset metadata do not discuss legal intervention. | [source](https://www.data.go.kr/dcat/metadata/15084592) |

- Police-station areas may not coincide with city boundaries; every row names its station-matching rule in `data_notes`.
- Units under 100,000 residents are dropped.
- The definition comes from the police's published five-crimes note (a regional agency prints it as a footnote); the dataset used here is provided by the same division of the National Police Agency (Violent Crimes Investigation Division). The identity of the source is the link between the two.

Sources: [data.go.kr dataset 15084592](https://www.data.go.kr/data/15084592/fileData.do); [Gyeonggi Nambu Police Agency, five-crimes statistics with the definition of 살인](https://www.ggpolice.go.kr/main/html.do?menu=HF14); [Statistics Korea national indicator portal: crime rate and the international standard of homicide](https://www.index.go.kr/unify/idx-info.do?idxCd=4262); [Report on the 'five major crimes' (살인 including attempts)](https://edufp.police.ac.kr/pds/(100).pdf); [data.go.kr metadata of the dataset used](https://www.data.go.kr/dcat/metadata/15084592)

<a id="taiwan"></a>
#### Taiwan, cities and counties

- Source: Statistical Yearbook of the Republic of China (DGBAS), table 31 'All kinds of illegal cases', Homicide (Cases) 'Cases known to the police', by city and county police (original source: National Police Agency)
- Term in the source: Homicide (cases known to the police)
- Counted unit: cases. Cases, not victims.
- Time reference: Calendar year (2023 to 2025).
- Verdict against the reference: **Undetermined**. Intentional homicide with negligent death excluded; serious injury resulting in death is counted under injury, and the table says nothing about attempts.
- In the database: 63 rows, 21 units (admin1), 2023-2025; reliability tiers A 42, B 21; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is 'Homicide, cases known to the police' of the statistical yearbook, taken to be the police item 故意殺人 (see the note below). | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | The police definition of violent crime lists serious injury, 'including injury resulting in death', as an offence type of its own, separate from intentional homicide. | [source](https://www.police.ntpc.gov.tw/dl-9331-e0879a53-b4b7-40f3-a5de-9d93c3c045b4.html) |
| Attempted killings (ICCS: separate category, excluded) | not stated | The police definition says intentional homicide excludes negligent death and says nothing about attempts; the counts are 'cases occurred', which include late-reported cases. | [source](https://www.police.ntpc.gov.tw/dl-35693-3186acaf-9d42-4256-b052-6ca7c26c2770.html) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | The definition of violent crime reads 'intentional homicide (excluding negligent death)'. | [source](https://www.police.ntpc.gov.tw/dl-35693-3186acaf-9d42-4256-b052-6ca7c26c2770.html) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | By definition the item is the intentional killing of another person; the seven types of violent crime (intentional homicide, robbery, snatching, kidnapping for ransom, forcible sexual intercourse, serious extortion, serious injury) include no suicide or abortion. | [source](https://www.police.ntpc.gov.tw/dl-9331-e0879a53-b4b7-40f3-a5de-9d93c3c045b4.html) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The definition does not discuss legal intervention or justified killings. | [source](https://www.police.ntpc.gov.tw/dl-35693-3186acaf-9d42-4256-b052-6ca7c26c2770.html) |

- 22 first-level units; Lienchiang is under the 100,000 minimum and is dropped; national police units are in the national total only.
- The statistical yearbook's English label 'Homicide' is taken to be the police item 'intentional homicide' (故意殺人); the yearbook table itself does not say so, and the police definition above is the one found in the police statistical notes.
- Counts are 'cases occurred' (發生數) and include late-reported cases, which is why a detection rate can exceed 100%.

Sources: [DGBAS statistical yearbook](https://www.dgbas.gov.tw); [New Taipei City Police statistical bulletin (definition of violent crime, National Police Agency series)](https://www.police.ntpc.gov.tw/dl-35693-3186acaf-9d42-4256-b052-6ca7c26c2770.html); [The same, with the seven offence types including serious injury resulting in death](https://www.police.ntpc.gov.tw/dl-9331-e0879a53-b4b7-40f3-a5de-9d93c3c045b4.html)

<a id="thailand"></a>
#### Thailand, provinces

- Source: National Statistical Office (NSO), 'Statistics of Crimes against Person by Type of Crimes and Province: 2017-2022' (data owner: National Police Agency), crime 'Murder', sub-column 'Reported'
- Term in the source: Murder (reported)
- Counted unit: cases. Cases reported (not arrests or accused).
- Time reference: Calendar year (2017 to 2022).
- Verdict against the reference: **Close**. Murder with negligent homicide excluded; the first sub-column of every year is checked to read 'Reported'.
- In the database: 462 rows, 77 units (admin1), 2017-2022; reliability tiers A 414, B 48; count unit in the panel: cases; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is the 'Murder (reported)' count of the National Statistical Office. | see the sources below |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not counted | The Royal Thai Police criminal statistics keep 'Manslaughter' as a line of its own next to murder. | [source](https://oja.go.th/TH/download/18472) |
| Attempted killings (ICCS: separate category, excluded) | not counted | 'Attempted murder/homicide' is a separate line of the police statistics (several thousand cases a year, more than the murder line). | [source](https://oja.go.th/TH/download/18472) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | 'Negligent Homicide' is a separate crime and is excluded. | see the sources below |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | The sources list murder, attempted murder, homicide, manslaughter, assault and rape among the offences against life, body and sex; suicide and abortion are not named. | [source](https://oja.go.th/TH/download/18472) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The police statistics and the NSO table do not discuss legal intervention. | [source](https://oja.go.th/TH/download/18472) |

- The country file also carries Thailand's own regions in the column `country_region`.

Sources: [NSO statistics and indicators](https://www.nso.go.th/nsoweb/nso/statistics_and_indicators); [Office of Justice Affairs journal: crime statistics of the Royal Thai Police by offence](https://oja.go.th/TH/download/18472)

<a id="uzbekistan"></a>
#### Uzbekistan, 14 regions

- Source: National Statistics Committee, 'Crime and Justice' open data, indicator 2.04.09.0036 'Registered murder and attempted murder by regions'
- Term in the source: Murder and attempted murder (registered)
- Counted unit: cases. The indicator is a count of 'holatlari' (cases or incidents) of registered intentional killing and attempted killing, per the Statistics Agency's metadata.
- Time reference: Calendar year.
- Verdict against the reference: **Broader**. Attempted murder is inside the count.
- In the database: 224 rows, 14 units (admin1), 2010-2025; reliability tiers B 224; count unit in the panel: cases; definition flags in the rows: includes_attempts

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The indicator is 'registered intentional murders and attempted murders' (qasddan odam o'ldirish va o'ldirishga suiqasd holatlari; Russian: умышленные убийства и покушения на убийства), indicator 2.04.09.0036. | [source](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | not stated | The indicator's metadata name only intentional killing and attempts; which provisions of the Criminal Code (provoked killing, excess of self-defence, infanticide) are counted as intentional killing is not stated. | [source](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf) |
| Attempted killings (ICCS: separate category, excluded) | counted | Stated in the indicator's own name; flag includes_attempts. | see the sources below |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | The indicator counts intentional killings ('умышленные'): negligent killings are not part of it. | [source](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not stated | The metadata mention neither suicide nor abortion. | [source](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The metadata do not discuss legal intervention. | [source](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf) |

- The portal's page titles are not trusted: a dataset titled 'murders' on the page has metadata saying 'grievous bodily harm', so every indicator name is checked in the file's own metadata.
- Population is 'permanent population' on 1 January; if it includes people registered in an area but living elsewhere, rates are understated there.
- Intentional grievous bodily harm is a separate indicator of the Statistics Agency (2.04.09.0101, 'registered intentional grievous bodily harm'), so deaths recorded under that heading are not in this series.
- The Interior Ministry is reported to have counted 60 murders in 2024 and 31 in 2025, while this indicator gives 363 murders AND attempted murders for 2023: the ministry's figure is of another order, which suggests that attempts form most of the indicator (or that the two count differently). The indicator's split between completed and attempted killings is not published; treat the series as an upper bound for completed murders.

Sources: [National Statistics Committee open data](https://stat.uz); [Statistics Agency of Uzbekistan, indicator 2.04.09.0036 (SDMX metadata and data)](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_807.pdf); [Statistics Agency, indicator 2.04.09.0101 (intentional grievous bodily harm)](https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_908.pdf); [Press report of the Interior Ministry's murder figures for 2024 and 2025](https://anhor.uz/news/criminal-cases-2/)

### Europe

<a id="eurostat"></a>
#### Eurostat, NUTS 3 regions

- Source: Eurostat dataset crim_gen_reg 'Police-recorded offences by NUTS 3 region', ICCS0101 Intentional homicide, number of offences (data supplied by each country's police and statistical authorities)
- Term in the source: Intentional homicide (ICCS0101)
- Counted unit: offences. The police-recorded offence.
- Time reference: Calendar year.
- Verdict against the reference: **Close**. Close by definition. Countries report under the ICCS but may diverge; Eurostat flags such series 'd' (definition differs), and the pipeline puts every flagged row in tier B.
- In the database: 13,211 rows, 1,162 units (admin2), 2008-2024; reliability tiers A 10,358, B 2,105, C 748; count unit in the panel: offences; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is ICCS0101 Intentional homicide, the number of offences supplied by each country's police and statistical authorities. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | partly counted | Eurostat's wording lists manslaughter among the exclusions, while the ICCS itself includes VOLUNTARY manslaughter and excludes involuntary manslaughter: the national treatment decides (see the flag 'd'). | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted homicide is a separate category (ICCS0102). | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Non-intentional homicide is a separate category of the ICCS (ICCS0103) and is not part of ICCS0101. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | Suicide is not part of the series. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not counted | Death due to legal intervention and justifiable homicide in self-defence are excluded; serious assault leading to death and terrorist attacks are included. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table) |

- Counting and recording rules differ between countries (when an offence is counted, how several victims are treated), so rates are not strictly comparable across countries.
- The unit is the offence, not the victim.
- Regions under 100,000 residents are dropped; the NUTS 3 regions differ greatly in size between countries.

Sources: [Eurostat crim_gen_reg](https://ec.europa.eu/eurostat/databrowser/view/crim_gen_reg/default/table); [Eurostat demo_r_gind3 (population)](https://ec.europa.eu/eurostat/databrowser/view/demo_r_gind3/default/table)

<a id="eurostat_cities"></a>
#### Eurostat, largest cities

- Source: Eurostat dataset crim_hom_ocit 'Intentional homicide offences in largest cities'; denominator Urban Audit urb_cpop1
- Term in the source: Intentional homicide
- Counted unit: offences. The police-recorded offence.
- Time reference: Calendar year.
- Verdict against the reference: **Close**. Close by definition, with the same national divergence as the regional series.
- In the database: 333 rows, 27 units (city), 2008-2024; reliability tiers A 152, B 181; count unit in the panel: offences; definition flags in the rows: none

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The series is the number of intentional homicides in the city, as supplied by each country's police and statistical authorities. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | partly counted | As for the regional series. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |
| Attempted killings (ICCS: separate category, excluded) | not counted | As for the regional series: attempted homicide is a separate category (ICCS0102). | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | As for the regional series: non-intentional homicide is a separate category (ICCS0103). | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | As for the regional series: suicide is not part of the series. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not counted | As for the regional series: death due to legal intervention and justifiable homicide in self-defence are excluded. | [source](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table) |

- Each jurisdiction reports its largest cities, in general as the city proper or the greater city; the unit type says which.
- A city above its country's national total is tier C.

Sources: [Eurostat crim_hom_ocit](https://ec.europa.eu/eurostat/databrowser/view/crim_hom_ocit/default/table)

<a id="united_kingdom"></a>
#### England and Wales, police force areas

- Source: Home Office, 'Police recorded crime open data tables', Police Force Area tables (year ending March 2013 onwards), offence subgroup 'Homicide'; population: ONS mid-year estimates by police force area
- Term in the source: Homicide (a Home Office offence subgroup)
- Counted unit: offences. Police-recorded offences, summed over four quarters.
- Time reference: Financial year April to March, paired with the mid-year estimate of the starting year.
- Verdict against the reference: **Broader**. Murder, all manslaughter (including involuntary and corporate) and infanticide: broader than ICCS 0101 by the involuntary and corporate manslaughter.
- In the database: 546 rows, 42 units (police_unit), 2012-2024; reliability tiers B 546; count unit in the panel: offences; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The Home Office Counting Rules classify Murder (code 1) in the Homicide group. | [source](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Manslaughter (4/1) and corporate manslaughter (4/10) are in the Homicide group, so manslaughter of every kind is counted, including involuntary and corporate; the ICCS includes only voluntary manslaughter. | [source](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted murder has its own Home Office offence code (2), separate from Murder (1) and Manslaughter (4/1). | [source](https://moderngov.stockton.gov.uk/Data/Safer%20Stockton%20Partnership/201208140930/Agenda/$att18150.doc.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Deaths caused by unlawful driving form a separate group in the Counting Rules ('Death or Serious Injury - Unlawful Driving'), next to Homicide. | [source](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The Homicide classification lists murder, manslaughter, corporate manslaughter and infanticide; suicide and abortion are not in it. Infanticide is inside, as in the ICCS. | [source](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The Counting Rules' Homicide classification does not discuss legal intervention. | [source](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB) |

- ONS states that the Home Office Homicide Index, not police recorded crime, is the preferred source for homicide counts; every row is tier B for that reason.
- The country label is 'United Kingdom' but the series covers England and Wales only: Scotland and Northern Ireland are separate jurisdictions with their own sources and are not in the panel.
- Non-territorial 'forces' (Action Fraud, British Transport Police and others) have no population and are not rated.
- The descriptions found inside the 'Homicide' subgroup of the open data tables are written into the rows (`indicator`).

Sources: [Home Office police recorded crime open data](https://www.gov.uk/government/statistics/police-recorded-crime-open-data-tables); [ONS police force area population estimates](https://www.ons.gov.uk); [Home Office Counting Rules for Recorded Crime, violence against the person (April 2020; a copy)](https://pdfroom.com/books/home-office-counting-rules-for-violence-against-the-person/kLg8pb73gZB); [Home Office offence codes (listed in a 2012 council paper)](https://moderngov.stockton.gov.uk/Data/Safer%20Stockton%20Partnership/201208140930/Agenda/$att18150.doc.pdf)

### Oceania

<a id="states"></a>
#### Australia, states and territories

- Source: Australian Bureau of Statistics (ABS), 'Recorded Crime - Victims' (victims recorded by state and territory police under the National Crime Recording Standard), cross-checked with ABS 'Causes of Death' (assault, X85-Y09)
- Term in the source: Murder + manslaughter (the ABS category 'Homicide' also contains attempted murder)
- Counted unit: victims. Victims: the unit of the UNODC indicator.
- Time reference: Calendar year: the ABS Recorded Crime - Victims reference period is 1 January to 31 December.
- Verdict against the reference: **Broader**. Murder plus manslaughter victims, attempts and driving deaths excluded; the ANZSOC manslaughter group includes involuntary killings and assisted suicide, so the count is slightly broader than the ICCS. The unit (victims) is that of the UNODC indicator.
- In the database: 264 rows, 8 units (admin1), 1993-2025; reliability tiers A 62, B 202; count unit in the panel: victims; definition flags in the rows: counts_victims, includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | Murder is its own category (ANZSOC). The victim is an individual person; offences later found to be 'no crime' are excluded. | [source](https://www.abs.gov.au/methodologies/recorded-crime-victims-methodology/2024) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | The collection covers manslaughter (ANZSOC 0131), which includes killings without intent through reckless, negligent or dangerous acts other than driving, infanticide, killing by excessive force in self-defence, surviving a suicide pact, assisting suicide and industrial or corporate manslaughter: broader than the ICCS's voluntary manslaughter. | [source](https://www.abs.gov.au/book/export/32860/print) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Murder and attempted murder are separate categories (the one exception to counting attempts with the completed offence); the layer uses murder and manslaughter only. | [source](https://abs.gov.au/AUSSTATS/abs@.nsf/Lookup/4510.0Explanatory%20Notes12015) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | partly counted | Driving causing death (0132) and conspiracy to murder are excluded from the collection's homicide group, but killings without intent by other reckless, negligent or dangerous acts are inside manslaughter. | [source](https://www.abs.gov.au/methodologies/recorded-crime-victims-methodology/2024) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | partly counted | Illegal abortion is coded to another group (1695), but assisting suicide and surviving a suicide pact are coded to manslaughter, which the ICCS excludes; infanticide is coded to manslaughter (the ICCS includes it). | [source](https://www.abs.gov.au/book/export/32860/print) |
| Legal intervention, justifiable homicide (ICCS: excluded) | partly counted | Killing by the use of excessive force in self-defence is coded to manslaughter (counted); lawful self-defence is not an offence. How deaths caused by police action are recorded is not stated. | [source](https://www.abs.gov.au/book/export/32860/print) |

- Police victims and health deaths are compared per state and year (a diagnostic with a band, since deaths are registered by year of registration).
- The ABS national table is not an exact sum of the states; the difference is written into the rows.
- The ABS says the 2010 publication marked a break in series (changes in police recording practices, a revised offence classification and the National Crime Recording Standard) and that data published before it should not be compared with later data. The ABS footnote on the category, "Homicide excludes driving causing death", is identical in every release from 1993 to 2025, and the rows of the years before the break carry the series-break note in `data_notes`.

Sources: [ABS Recorded Crime - Victims](https://www.abs.gov.au/statistics/people/crime-and-justice/recorded-crime-victims); [ABS Causes of Death](https://www.abs.gov.au/statistics/health/causes-death/causes-death-australia); [ABS, Recorded Crime - Victims methodology](https://www.abs.gov.au/methodologies/recorded-crime-victims-methodology/2024); [ABS, ANZSOC third edition, Division 01 (2011)](https://www.abs.gov.au/book/export/32860/print); [ABS, ANZSOC fourth edition, Division 01 (2023)](https://www.abs.gov.au/book/export/36523/print); [ABS, Recorded Crime - Victims: attempts and murder (2015 explanatory notes)](https://abs.gov.au/AUSSTATS/abs@.nsf/Lookup/4510.0Explanatory%20Notes12015); [ABS, Recorded Crime - Victims: break in series (2011 explanatory notes)](https://www.abs.gov.au/AUSSTATS/abs@.nsf/Lookup/4510.0Explanatory%20Notes02011)

<a id="new_south_wales"></a>
#### New South Wales, local government areas

- Source: NSW Bureau of Crime Statistics and Research (BOCSAR), 'Recorded criminal incidents by month - by LGA'
- Term in the source: Murder + manslaughter (the file's own lines)
- Counted unit: victims. BOCSAR counts every offence by criminal incident EXCEPT murder and manslaughter, which it counts by VICTIM (where one murder incident involves a person killing six people, six murder victims are counted).
- Time reference: Calendar year of REPORTING: BOCSAR dates a crime by the day it was reported to or detected by the police, not the day it occurred.
- Verdict against the reference: **Broader**. Murder plus manslaughter victims, attempts and driving deaths excluded; manslaughter of every kind is included but is a small share (about 10 to 20%) of the total.
- In the database: 591 rows, 27 units (admin2), 2001-2025; reliability tiers B 591; count unit in the panel: victims; definition flags in the rows: counts_victims, includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | Murder is the police incident category 'Murder - actual', counted by victim. | [source](https://www.bocsar.nsw.gov.au/Documents/RCS-Annual/OffenceCategories-2023.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Manslaughter is the police category 'Manslaughter - actual' (driving causing death excluded), counted by victim. BOCSAR notes that police counts are very low because the distinction between murder and manslaughter is generally decided in court; in the quarter reports of 2023 manslaughter was 7 to 12 victims a year against 48 to 61 murder victims. | [source](https://bocsar.nsw.gov.au/statistics-dashboards/crime-and-policing/rcs-definitions-and-explanations.html) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted murder (police 'Murder - attempted' and 'Shoot with intent to murder') and murder accessory or conspiracy are separate categories. | [source](https://www.bocsar.nsw.gov.au/Documents/RCS-Annual/OffenceCategories-2023.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Driving causing death is a separate BOCSAR category. Other killings without intent that the police record as manslaughter are inside the manslaughter count. | [source](https://www.bocsar.nsw.gov.au/Documents/RCS-Annual/OffenceCategories-2023.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The Homicide group of BOCSAR's reports consists of murder, attempted murder, murder accessory or conspiracy, manslaughter and driving causing death only. | [source](https://bocsar.nsw.gov.au/documents/publications/rcs/rcs-quarterly/2023q4/NSW_Recorded_Crime_Dec_2023.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | BOCSAR's definitions do not discuss legal intervention or justified killings. | [source](https://bocsar.nsw.gov.au/statistics-dashboards/crime-and-policing/rcs-definitions-and-explanations.html) |

- LGAs of 100,000 or more residents; the LGAs are reconciled to BOCSAR's own all-of-NSW line.

Sources: [BOCSAR open data](https://bocsar.nsw.gov.au); [BOCSAR, crime and policing definitions](https://bocsar.nsw.gov.au/statistics-dashboards/crime-and-policing/rcs-definitions-and-explanations.html); [BOCSAR, offence categories mapped to police incident categories](https://www.bocsar.nsw.gov.au/Documents/RCS-Annual/OffenceCategories-2023.pdf); [BOCSAR, quarterly report with explanatory notes (March 2022; a copy)](https://sifa.net.au/wp-content/uploads/NSW_Recorded_Crime_March_2022.pdf); [BOCSAR, Recorded Crime Statistics 2003 (counting unit for murder and manslaughter)](https://www.bocsar.nsw.gov.au:443/Publications/RCS-Annual/rcs03.pdf); [BOCSAR, quarterly report December 2023](https://bocsar.nsw.gov.au/documents/publications/rcs/rcs-quarterly/2023q4/NSW_Recorded_Crime_Dec_2023.pdf)

<a id="victoria"></a>
#### Victoria, local government areas

- Source: Crime Statistics Agency (CSA) Victoria, 'Data Tables - LGA Recorded Offences', offence subdivision 'A10 Homicide and related offences'
- Term in the source: A10 Homicide and related offences
- Counted unit: offences. Offences recorded by Victoria Police.
- Time reference: Calendar year (year ending December).
- Verdict against the reference: **Broader**. The CSA subdivision A10 contains murder, attempted murder, accessory or conspiracy to murder, manslaughter and driving causing death: it is the broadest of the Australian homicide counts and about three times murder plus manslaughter.
- In the database: 300 rows, 31 units (admin2), 2016-2025; reliability tiers B 300; count unit in the panel: offences; definition flags in the rows: includes_attempts, includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | Group A11 Murder: unlawfully killing another person with intent to kill, or with intent to cause grievous bodily harm knowing that death or grievous harm was probable, or without intent to kill in the course of committing a crime. | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Group A14 Manslaughter: the unlawful killing of another person while deprived of self-control by provocation, or with diminished responsibility, or without intent to kill through a careless, reckless, negligent, unlawful or dangerous act other than driving. It covers voluntary and involuntary manslaughter alike. | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |
| Attempted killings (ICCS: separate category, excluded) | counted | Group A12 Attempted murder and group A13 Accessory or conspiracy to murder are inside the A10 subdivision, so the count includes attempts (flag includes_attempts). | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | counted | Group A15 Driving causing death (an unlawful killing without intent through culpable, reckless or negligent driving) is inside A10, as is manslaughter without intent to kill. | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | A10 consists of the five groups A11 to A15 only; none concerns suicide or abortion. | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The classification defines the groups by offence and does not discuss legal intervention or justified killings. | [source](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf) |

- Counts of 3 or less are masked to the value 2 (a 2 means 1 to 3): such rows are flagged `flag_count_masked` and kept at tier B.
- The tables exclude offences at justice institutions and immigration facilities, in Unincorporated Victoria and with an unknown location.
- The CSA classification is largely based on ANZSOC and modified for Victorian legislation; it codes threats, attempts and conspiracies to the group of the substantive offence unless a specific group exists (attempted murder has its own group, A12). The data tables give the A10 subdivision only: the subgroup label in the workbook is the same A10 label, so murder, manslaughter and the other groups cannot be separated from them.

Sources: [CSA Victoria data tables](https://www.crimestatistics.vic.gov.au/crime-statistics/latest-crime-data-by-area); [CSA Victoria, offence classification (divisions and subdivisions)](https://www.crimestatistics.vic.gov.au/node/538); [CSA Victoria, offence classifications dataset](https://discover.data.vic.gov.au/dataset/crime-statistics-agency-offence-classifications); [CSA Victoria, offence classification (PDF, with the definition of every group)](https://files.crimestatistics.vic.gov.au/2021-07/csaoffenceclassification.pdf); [CSA Victoria, offence classification page](https://www.crimestatistics.vic.gov.au/about-the-data/classifications-and-victorian-map-boundaries/offence-classification)

<a id="queensland"></a>
#### Queensland, local government areas

- Source: Queensland Police Service open data, 'LGA Reported Offences Number'
- Term in the source: Homicide (Murder) + Manslaughter (excl. by driving) + Manslaughter Unlawful Striking Causing Death
- Counted unit: offences. Reported offences (no victims file exists).
- Time reference: Calendar year of REPORTING: the QPS statistics count offences when they are reported, not when they occurred.
- Verdict against the reference: **Broader**. Murder plus manslaughter offences, including an unlawful-striking offence without intent to kill; attempts and driving deaths are kept apart.
- In the database: 288 rows, 13 units (admin2), 2001-2025; reliability tiers A 288; count unit in the panel: offences; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | The QPS category is 'Homicide (Murder)'. | [source](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17.pdf) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Two QPS categories are counted: 'Manslaughter (excl. by Driving & Striking)' and 'Manslaughter - Unlawful Striking Cause Death'. The second is an offence without intent to kill (a death caused by an unlawful strike), counted here with manslaughter. | [source](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17_01%20Queensland%20Crime.pdf) |
| Attempted killings (ICCS: separate category, excluded) | not counted | Attempted Murder and Conspiracy to Murder are QPS categories inside 'Other Homicide' and are kept apart in the layer. | [source](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17.pdf) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | Driving Causing Death is a separate QPS category inside 'Other Homicide' and is kept apart. | [source](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17_01%20Queensland%20Crime.pdf) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | The QPS homicide categories are murder, attempted murder, conspiracy to murder, the two manslaughter categories and driving causing death; there is none for suicide or abortion. 'Other Homicide' is the sum of the categories other than murder (2016-17: 96 = 75 attempted murder + 0 conspiracy + 4 + 5 manslaughter + 12 driving). | [source](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The QPS statistical reviews and the open-data dictionaries (whose description column is empty) do not define the categories or discuss legal intervention. | [source](https://data.qld.gov.au/dataset/offence-numbers-monthly-from-july-1997/resource/609541e9-4ed2-4ea4-8cae-c9f94d428a27) |

- LGAs of 100,000 or more residents; reconciled to the statewide file.

Sources: [Queensland Police open data](https://www.data.qld.gov.au); [QPS Annual Statistical Review 2016-17](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17.pdf); [QPS Annual Statistical Review 2016-17, Queensland crime tables](https://www.police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2016-17_01%20Queensland%20Crime.pdf); [Queensland open data: offence numbers (data dictionary)](https://data.qld.gov.au/dataset/offence-numbers-monthly-from-july-1997/resource/609541e9-4ed2-4ea4-8cae-c9f94d428a27); [QPS Annual Statistical Review 2015-16: reported offences](https://police.qld.gov.au/sites/default/files/2019-01/AnnualStatisticalReview_2015-16_Crime%202015%20-%202016.pdf)

<a id="western_australia"></a>
#### Western Australia, police districts

- Source: WA Police Force, 'Crime time series data' workbook
- Term in the source: Murder + Manslaughter
- Counted unit: offences. Recorded offences.
- Time reference: Financial year July to June; `year` is the START year. The WA Police compile offences by the date they are reported or become known to the police (not the date of the offence), and the count may include offences committed in earlier periods.
- Verdict against the reference: **Broader**. Murder plus manslaughter offences; manslaughter in Western Australia is any unlawful killing that is not murder, so it includes killings without intent. Attempts and driving deaths are kept apart.
- In the database: 45 rows, 9 units (police_unit), 2020-2025; reliability tiers A 44, B 1; count unit in the panel: offences; definition flags in the rows: includes_manslaughter

| Element | Treatment | What the source says | |
|---|---|---|---|
| Murder: completed intentional killing | counted | Murder: unlawfully killing another person with intent to kill, or with intent to cause bodily harm likely to endanger life, or by an act done in the prosecution of an unlawful purpose and likely to endanger life. | [source](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics) |
| Manslaughter (ICCS includes VOLUNTARY manslaughter, excludes involuntary) | counted | Manslaughter: the unlawful killing of another person under circumstances that do not amount to murder. It therefore covers killings without intent as well as provoked ones. | [source](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics) |
| Attempted killings (ICCS: separate category, excluded) | not counted | 'Attempted/Conspiracy to Murder' (the attempted unlawful killing of another person or conspiring to commit murder) is a separate line. | [source](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics) |
| Non-intentional or negligent deaths, incl. traffic (ICCS: excluded) | not counted | 'Driving Causing Death' (an unlawful killing without intent through culpable, reckless or negligent driving) is a separate line. Other killings without intent that are recorded as manslaughter are inside the manslaughter count. | [source](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics) |
| Other deaths outside 0101: suicide, abortion, concealment of birth (ICCS: excluded) | not counted | Murder (section 279) and manslaughter (section 280) are defined as the unlawful killing of another person, so suicide is outside. The WA Police series says nothing about abortion or concealment of birth. | [source](https://www.wa.gov.au/system/files/2026-04/lrc-project-097-final-report-ch3.pdf) |
| Legal intervention, justifiable homicide (ICCS: excluded) | not stated | The glossary and the explanatory notes do not discuss legal intervention or justified killings; offences with the outcome status 'no criminal offence', 'offence substituted', 'false report' or 'entered in error' are excluded. | [source](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics) |

- The police publish no population: it is derived from the monthly reports' own offence counts and rates per 100,000, and its date is measured against the ABS June estimates.
- Since the Criminal Law Amendment (Homicide) Act 2008 the law of Western Australia has two homicide offences, murder (s 279) and manslaughter (s 280); what was wilful murder is murder under section 279(1)(a), for offences after 1 August 2008. The whole series falls under that law.
- Manslaughter (s 280) is the unlawful killing of another in circumstances that do not amount to murder; dangerous driving causing death is a separate offence of the Road Traffic Act, which matches the 'Driving Causing Death' line the layer keeps apart.
- The WA Police publish counts of criminal OFFENCES, not victims or offenders: one offence can have several victims. The offence classification combines ANZSOC 2011, WA legislation and operational reporting requirements, and category names may carry broader or different definitions than the legislation.
- Counting rules follow the National Crime Recording Standard 2008 where practicable, but the WA Police count offences where the standard counts victims. Practice changes of 2017 break the series around May to November 2017 (the layer starts in 2020).

Sources: [WA Police Force crime statistics](https://www.police.wa.gov.au/Crime/Crime-Statistics); [Criminal Law Amendment (Homicide) Act 2008 (WA)](https://www.austlii.edu.au/au/legis/wa/num_act/claa200829o2008309/); [Law Reform Commission of Western Australia, Review of the Law of Homicide: final report, chapter 3 (manslaughter)](https://www.wa.gov.au/system/files/2026-04/lrc-project-097-final-report-ch3.pdf); [WA Police Force, crime statistics: quality statement, explanatory notes and glossary](https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics)

