#!/usr/bin/env python3
"""Asia master panel: stacks the country files of this folder into <repo>/Data/Output/asia_master_panel.csv (see Pipelines/master_panel.py for what it adds and the rules for use)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import master_panel as M

EXPECTED = ['china', 'japan', 'india', 'bangladesh', 'south_korea', 'malaysia', 'pakistan', 'singapore', 'taiwan', 'thailand', 'uzbekistan']

if __name__ == "__main__":
    M.main(__file__, "Asia", EXPECTED)