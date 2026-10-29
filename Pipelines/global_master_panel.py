#!/usr/bin/env python3
"""World master panel: stacks the five continental panels of <repo>/Data/Output into global_master_panel.csv (see Pipelines/master_panel.py). Run the continental scripts first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import master_panel as M

if __name__ == "__main__":
    M.main_global(__file__)