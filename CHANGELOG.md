# Changelog

## 1.0.0 - 2026-10-29

First public release.

- 25 source layers in five regions: Africa 5, Americas 1, Asia 11, Europe 3, Oceania 5; one script and one validated CSV per layer, in the common format of `Pipelines/FORMAT.md`.
- Five continental panels, a global panel and an inventory in `Data/Output/`; reliability tiers A, B and C and the counting unit of every row.
- `Docs/DEFINITIONS.md`: for each layer, what the source counts as homicide compared with the UNODC definition (ICCS 0101), element by element, with the source of every statement.
- `Pipelines/refresh_all.py`, `build_docs.py`, `tidy_repo.py` and `release_check.py`: rebuild, document, tidy and check the repository.
- Code under the MIT licence; data and documentation under CC BY 4.0.
