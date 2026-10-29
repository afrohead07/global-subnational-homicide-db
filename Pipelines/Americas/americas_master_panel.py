#!/usr/bin/env python3
"""Americas master panel: stacks the country files of this folder into <repo>/Data/Output/americas_master_panel.csv (see Pipelines/master_panel.py for what it adds and the rules for use)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import master_panel as M

EXPECTED = ['igarape', 'mexico']

if __name__ == "__main__":
    M.main(__file__, "Americas", EXPECTED)