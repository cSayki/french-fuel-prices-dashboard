"""Headless smoke test: render every tab with default and edge-case filters.

Usage: python tests/smoke_test.py   (exit code 1 on any exception)
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def run(label, setup=None):
    at = AppTest.from_file(APP, default_timeout=180).run()
    if setup:
        setup(at)
        at.run()
    errors = [e.value for e in at.exception]
    print(f"{'OK ' if not errors else 'ERR'} {label} {errors or ''}")
    return not errors


cases = [
    ("default view", None),
    ("rare fuel (E85)", lambda at: at.sidebar.multiselect[0].set_value(["E85"])),
    ("Brittany + motorway (no station)", lambda at: (at.sidebar.multiselect[1].set_value(["Bretagne"]),
                                                     at.sidebar.radio[0].set_value("Motorway"))),
    ("year-on-year measure", lambda at: at.sidebar.selectbox[1].set_value("Year-on-year change (%)")),
]
ok = all([run(label, fn) for label, fn in cases])
sys.exit(0 if ok else 1)
