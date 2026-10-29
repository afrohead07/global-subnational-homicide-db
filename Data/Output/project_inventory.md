# Project inventory

Built from africa, americas, asia, europe, oceania master panel(s).

## Totals

| what | number |
|---|---|
| rows (unit-years) | 29,075 |
| countries | 78 |
| units (country, parent, unit) | 2,854 |
| distinct years | 33 |
| first year | 1993 |
| last year | 2025 |
| layers (source files) | 25 |

## By region

| region | countries | units | rows | first_year | last_year | distinct_years |
|---|---|---|---|---|---|---|
| Africa | 5 | 133 | 449 | 2013 | 2025 | 13 |
| Americas | 27 | 931 | 11,282 | 2000 | 2024 | 25 |
| Asia | 11 | 471 | 1,766 | 2010 | 2025 | 16 |
| Europe | 34 | 1,231 | 14,090 | 2008 | 2024 | 17 |
| Oceania | 1 | 88 | 1,488 | 1993 | 2025 | 33 |

## Units by admin level (the groups you asked about)

admin1 = provinces, states, regions; admin2 = counties, districts, municipalities; city = cities; police_unit = police units.

| admin_level | meaning | units | rows | countries |
|---|---|---|---|---|
| admin1 | provinces / states / regions (first level) | 751 | 7,501 | 38 |
| admin2 | counties / districts / municipalities (second level) | 1,490 | 14,933 | 36 |
| city | cities | 562 | 6,050 | 56 |
| police_unit | police units | 51 | 591 | 2 |

## Units by region and admin level

| region | admin_level | units | rows |
|---|---|---|---|
| Africa | admin1 | 133 | 449 |
| Americas | admin1 | 425 | 5,761 |
| Americas | city | 506 | 5,521 |
| Asia | admin1 | 185 | 1,027 |
| Asia | admin2 | 257 | 543 |
| Asia | city | 29 | 196 |
| Europe | admin2 | 1,162 | 13,211 |
| Europe | city | 27 | 333 |
| Europe | police_unit | 42 | 546 |
| Oceania | admin1 | 8 | 264 |
| Oceania | admin2 | 71 | 1,179 |
| Oceania | police_unit | 9 | 45 |

## Units by exact unit type

The names the sources use (state, province, county, LGA, prefecture, district, region, city ...).

| admin_level | unit_type | units | rows | countries |
|---|---|---|---|---|
| admin1 | state | 480 | 6,047 | 27 |
| admin1 | province | 87 | 589 | 3 |
| admin1 | county | 59 | 224 | 2 |
| admin1 | prefecture | 47 | 188 | 1 |
| admin1 | region | 43 | 254 | 2 |
| admin1 | city | 10 | 43 | 2 |
| admin1 | district | 9 | 45 | 1 |
| admin1 | metropolitan_city | 8 | 8 | 1 |
| admin1 | federal_capital_territory | 2 | 3 | 2 |
| admin1 | territory | 2 | 66 | 1 |
| admin1 | autonomous_republic | 1 | 16 | 1 |
| admin1 | federal_territory | 1 | 4 | 1 |
| admin1 | municipality | 1 | 3 | 1 |
| admin1 | special_administrative_region | 1 | 11 | 1 |
| admin2 | nuts3_region | 1,162 | 13,211 | 32 |
| admin2 | district | 193 | 479 | 2 |
| admin2 | local government area | 71 | 1,179 | 1 |
| admin2 | city | 62 | 62 | 1 |
| admin2 | county | 2 | 2 | 1 |
| city | city | 518 | 5,694 | 38 |
| city | metropolitan_city | 19 | 171 | 1 |
| city | greater_city | 16 | 162 | 15 |
| city | metropolitan_police_unit | 8 | 8 | 1 |
| city | city_state | 1 | 15 | 1 |
| police_unit | police_force_area | 42 | 546 | 1 |
| police_unit | Police District | 9 | 45 | 1 |

## Reliability tiers

A = reconciled with an independent confirmation and a recent denominator; B = a documented weakness; C = a failed hard check or a proxy.

| reliability_tier | rows | countries | units | share_of_rows |
|---|---|---|---|---|
| A | 11,835 | 39 | 1,454 | 40.7 |
| B | 15,447 | 72 | 1,638 | 53.1 |
| C | 1,793 | 17 | 276 | 6.2 |

## Indicator type

| indicator_type | rows | countries | units |
|---|---|---|---|
| health_registry_deaths | 322 | 4 | 54 |
| police_recorded_cases | 28,753 | 77 | 2,815 |

## What is counted

| count_unit | rows | countries | units |
|---|---|---|---|
| cases | 12,996 | 40 | 1,456 |
| deaths | 322 | 4 | 54 |
| offences | 14,723 | 35 | 1,284 |
| victims | 1,034 | 3 | 75 |

## Layers (one per source file)

| region | layer | countries | units | rows | first_year | last_year |
|---|---|---|---|---|---|---|
| Africa | kenya | 1 | 47 | 188 | 2015 | 2021 |
| Africa | lesotho | 1 | 9 | 45 | 2015 | 2022 |
| Africa | nigeria | 1 | 37 | 37 | 2017 | 2017 |
| Africa | south_africa | 1 | 9 | 117 | 2013 | 2025 |
| Africa | tanzania | 1 | 31 | 62 | 2024 | 2025 |
| Americas | igarape | 27 | 931 | 11,282 | 2000 | 2024 |
| Asia | bangladesh | 1 | 8 | 8 | 2025 | 2025 |
| Asia | china | 1 | 3 | 24 | 2014 | 2024 |
| Asia | india | 1 | 19 | 171 | 2016 | 2024 |
| Asia | japan | 1 | 47 | 188 | 2022 | 2025 |
| Asia | malaysia | 1 | 81 | 317 | 2020 | 2023 |
| Asia | pakistan | 1 | 128 | 222 | 2024 | 2025 |
| Asia | singapore | 1 | 1 | 15 | 2011 | 2025 |
| Asia | south_korea | 1 | 72 | 72 | 2025 | 2025 |
| Asia | taiwan | 1 | 21 | 63 | 2023 | 2025 |
| Asia | thailand | 1 | 77 | 462 | 2017 | 2022 |
| Asia | uzbekistan | 1 | 14 | 224 | 2010 | 2025 |
| Europe | eurostat | 32 | 1,162 | 13,211 | 2008 | 2024 |
| Europe | eurostat_cities | 26 | 27 | 333 | 2008 | 2024 |
| Europe | united_kingdom | 1 | 42 | 546 | 2012 | 2024 |
| Oceania | new_south_wales | 1 | 27 | 591 | 2001 | 2025 |
| Oceania | queensland | 1 | 13 | 288 | 2001 | 2025 |
| Oceania | states | 1 | 8 | 264 | 1993 | 2025 |
| Oceania | victoria | 1 | 31 | 300 | 2016 | 2025 |
| Oceania | western_australia | 1 | 9 | 45 | 2020 | 2025 |

## By country

| region | country | rows | units | first_year | last_year | distinct_years | tiers | admin_levels | layers | span_years |
|---|---|---|---|---|---|---|---|---|---|---|
| Africa | Kenya | 188 | 47 | 2015 | 2021 | 4 | C | admin1 | kenya | 7 |
| Africa | South Africa | 117 | 9 | 2013 | 2025 | 13 | B | admin1 | south_africa | 13 |
| Africa | Tanzania | 62 | 31 | 2024 | 2025 | 2 | B | admin1 | tanzania | 2 |
| Africa | Lesotho | 45 | 9 | 2015 | 2022 | 5 | B | admin1 | lesotho | 8 |
| Africa | Nigeria | 37 | 37 | 2017 | 2017 | 1 | B | admin1 | nigeria | 1 |
| Americas | Argentina | 1,475 | 67 | 2000 | 2024 | 24 | B | admin1, city | igarape | 25 |
| Americas | United States of America | 1,317 | 136 | 2010 | 2024 | 15 | B, C | admin1, city | igarape | 15 |
| Americas | Colombia | 1,270 | 57 | 2000 | 2024 | 25 | B | admin1, city | igarape | 25 |
| Americas | Mexico | 1,208 | 127 | 2015 | 2024 | 10 | B | admin1, city | igarape | 10 |
| Americas | Brazil | 1,192 | 149 | 2017 | 2024 | 8 | B | admin1, city | igarape | 8 |
| Americas | Guatemala | 621 | 27 | 2000 | 2024 | 25 | B | admin1, city | igarape | 25 |
| Americas | Ecuador | 486 | 34 | 2010 | 2024 | 15 | B | admin1, city | igarape | 15 |
| Americas | Dominican Republic | 419 | 37 | 2007 | 2023 | 17 | B, C | admin1, city | igarape | 17 |
| Americas | Honduras | 374 | 20 | 2005 | 2024 | 20 | B, C | admin1, city | igarape | 20 |
| Americas | Canada | 370 | 42 | 2013 | 2024 | 12 | B, C | admin1, city | igarape | 12 |
| Americas | Venezuela (Bolivarian Republic of) | 348 | 41 | 2000 | 2024 | 20 | B, C | admin1, city | igarape | 25 |
| Americas | Paraguay | 278 | 21 | 2006 | 2023 | 17 | B, C | admin1, city | igarape | 18 |
| Americas | Jamaica | 250 | 11 | 2000 | 2024 | 25 | B | admin1, city | igarape | 25 |
| Americas | Nicaragua | 238 | 18 | 2006 | 2022 | 17 | B, C | admin1, city | igarape | 17 |
| Americas | Panama | 229 | 11 | 2002 | 2024 | 23 | B, C | admin1, city | igarape | 23 |
| Americas | Peru | 228 | 38 | 2019 | 2024 | 6 | B, C | admin1, city | igarape | 6 |
| Americas | Bolivia (Plurinational State of) | 203 | 17 | 2010 | 2024 | 15 | B, C | admin1, city | igarape | 15 |
| Americas | Chile | 189 | 27 | 2018 | 2024 | 7 | B | admin1, city | igarape | 7 |
| Americas | El Salvador | 188 | 17 | 2010 | 2021 | 12 | B | admin1, city | igarape | 12 |
| Americas | Costa Rica | 126 | 9 | 2011 | 2024 | 14 | B | admin1, city | igarape | 14 |
| Americas | Uruguay | 119 | 9 | 2011 | 2024 | 14 | B, C | admin1, city | igarape | 14 |
| Americas | Trinidad and Tobago | 67 | 7 | 2015 | 2024 | 10 | B | admin1, city | igarape | 10 |
| Americas | Guyana | 40 | 4 | 2015 | 2024 | 10 | B, C | admin1, city | igarape | 10 |
| Americas | Puerto Rico | 23 | 1 | 2000 | 2024 | 23 | B | city | igarape | 25 |
| Americas | The Bahamas | 13 | 1 | 2012 | 2024 | 13 | B | city | igarape | 13 |
| Americas | Belize | 10 | 2 | 2013 | 2024 | 8 | B | admin1 | igarape | 12 |
| Americas | Haiti | 1 | 1 | 2021 | 2021 | 1 | B | city | igarape | 1 |
| Asia | Thailand | 462 | 77 | 2017 | 2022 | 6 | A, B | admin1 | thailand | 6 |
| Asia | Malaysia | 317 | 81 | 2020 | 2023 | 4 | A, B | admin1, admin2 | malaysia | 4 |
| Asia | Uzbekistan | 224 | 14 | 2010 | 2025 | 16 | B | admin1 | uzbekistan | 16 |
| Asia | Pakistan | 222 | 128 | 2024 | 2025 | 2 | A, B | admin1, admin2, city | pakistan | 2 |
| Asia | Japan | 188 | 47 | 2022 | 2025 | 4 | A | admin1 | japan | 4 |
| Asia | India | 171 | 19 | 2016 | 2024 | 9 | B | city | india | 9 |
| Asia | South Korea | 72 | 72 | 2025 | 2025 | 1 | B | admin1, admin2 | south_korea | 1 |
| Asia | Taiwan | 63 | 21 | 2023 | 2025 | 3 | A, B | admin1 | taiwan | 3 |
| Asia | China | 24 | 3 | 2014 | 2024 | 11 | A, B | admin1 | china | 11 |
| Asia | Singapore | 15 | 1 | 2011 | 2025 | 15 | B | city | singapore | 15 |
| Asia | Bangladesh | 8 | 8 | 2025 | 2025 | 1 | B | city | bangladesh | 1 |
| Europe | Germany | 3,119 | 322 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Italy | 1,680 | 106 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Türkiye | 1,334 | 79 | 2008 | 2024 | 17 | A, B | admin2 | eurostat | 17 |
| Europe | France | 913 | 101 | 2010 | 2024 | 15 | A, B | admin2, city | eurostat, eurostat_cities | 15 |
| Europe | Spain | 900 | 54 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | United Kingdom | 546 | 42 | 2012 | 2024 | 13 | B | police_unit | united_kingdom | 13 |
| Europe | Greece | 524 | 32 | 2008 | 2024 | 17 | A, B, C | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Belgium | 509 | 32 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Austria | 474 | 29 | 2008 | 2024 | 17 | A | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Bulgaria | 460 | 29 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Portugal | 433 | 38 | 2008 | 2024 | 17 | A, B, C | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Romania | 430 | 43 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Finland | 316 | 26 | 2008 | 2024 | 17 | A, B, C | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Switzerland | 304 | 20 | 2009 | 2024 | 16 | A, B | admin2, city | eurostat, eurostat_cities | 16 |
| Europe | Norway | 270 | 32 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Poland | 228 | 74 | 2008 | 2024 | 14 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Serbia | 178 | 23 | 2017 | 2024 | 8 | A, B | admin2 | eurostat | 8 |
| Europe | Hungary | 174 | 21 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Denmark | 173 | 11 | 2008 | 2024 | 17 | A | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Slovakia | 151 | 9 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Slovenia | 137 | 9 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Albania | 129 | 10 | 2012 | 2024 | 13 | A, B | admin2 | eurostat | 13 |
| Europe | Lithuania | 129 | 11 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Croatia | 115 | 29 | 2018 | 2024 | 7 | A, B | admin2 | eurostat | 7 |
| Europe | Czechia | 113 | 15 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Latvia | 91 | 10 | 2008 | 2024 | 17 | A, B, C | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Ireland | 78 | 8 | 2015 | 2024 | 10 | A, B | admin2 | eurostat | 10 |
| Europe | Estonia | 48 | 6 | 2012 | 2024 | 13 | A, B | admin2, city | eurostat, eurostat_cities | 13 |
| Europe | Iceland | 34 | 2 | 2008 | 2024 | 17 | A, B | admin2 | eurostat | 17 |
| Europe | Malta | 28 | 2 | 2008 | 2024 | 17 | A, B | admin2, city | eurostat, eurostat_cities | 17 |
| Europe | Cyprus | 24 | 2 | 2008 | 2022 | 15 | A, B | admin2, city | eurostat, eurostat_cities | 15 |
| Europe | Luxembourg | 19 | 2 | 2008 | 2022 | 15 | A | admin2, city | eurostat, eurostat_cities | 15 |
| Europe | Montenegro | 15 | 1 | 2008 | 2022 | 15 | A | admin2 | eurostat | 15 |
| Europe | Netherlands | 14 | 1 | 2008 | 2024 | 14 | B | city | eurostat_cities | 17 |
| Oceania | Australia | 1,488 | 88 | 1993 | 2025 | 33 | A, B | admin1, admin2, police_unit | new_south_wales, queensland, states, victoria, western_australia | 33 |

## Rows by five-year period

| period | rows | max_countries_in_a_year |
|---|---|---|
| 1990-1994 | 16 | 1 |
| 1995-1999 | 40 | 1 |
| 2000-2004 | 842 | 8 |
| 2005-2009 | 2,117 | 39 |
| 2010-2014 | 5,590 | 55 |
| 2015-2019 | 9,863 | 68 |
| 2020-2024 | 10,222 | 71 |
| 2025-2029 | 385 | 10 |

## The eight thinnest countries

| region | country | rows | units | first_year | last_year |
|---|---|---|---|---|---|
| Americas | Haiti | 1 | 1 | 2021 | 2021 |
| Asia | Bangladesh | 8 | 8 | 2025 | 2025 |
| Americas | Belize | 10 | 2 | 2013 | 2024 |
| Americas | The Bahamas | 13 | 1 | 2012 | 2024 |
| Europe | Netherlands | 14 | 1 | 2008 | 2024 |
| Asia | Singapore | 15 | 1 | 2011 | 2025 |
| Europe | Montenegro | 15 | 1 | 2008 | 2022 |
| Europe | Luxembourg | 19 | 2 | 2008 | 2022 |

## The eight densest countries

| region | country | rows | units | first_year | last_year |
|---|---|---|---|---|---|
| Europe | Germany | 3,119 | 322 | 2008 | 2024 |
| Europe | Italy | 1,680 | 106 | 2008 | 2024 |
| Oceania | Australia | 1,488 | 88 | 1993 | 2025 |
| Americas | Argentina | 1,475 | 67 | 2000 | 2024 |
| Europe | Türkiye | 1,334 | 79 | 2008 | 2024 |
| Americas | United States of America | 1,317 | 136 | 2010 | 2024 |
| Americas | Colombia | 1,270 | 57 | 2000 | 2024 |
| Americas | Mexico | 1,208 | 127 | 2015 | 2024 |
