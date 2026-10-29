#!/usr/bin/env python3
"""Oceania master panel: stacks the country files of this folder into <repo>/Data/Output/oceania_master_panel.csv (see Pipelines/master_panel.py for what it adds and the rules for use)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import master_panel as M

EXPECTED = ['australia_all', 'new_zealand']
INCLUDE = ["australia_all_homicide_rate.csv", "new_zealand_homicide_rate.csv"]      # australia_all already holds the five Australian layers: the layer files are not stacked again

if __name__ == "__main__":
    M.main(__file__, "Oceania", EXPECTED, include=INCLUDE)