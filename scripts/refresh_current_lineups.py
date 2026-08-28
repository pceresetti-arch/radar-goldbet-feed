#!/usr/bin/env python3
"""Compatibility entrypoint for the resilient Radar lineup pipeline.

Kept so existing workflows/tools that call refresh_current_lineups.py automatically
use the resilient target-discovery implementation without depending on a fresh
BetFlag overview request.
"""
import pathlib
import runpy

HERE = pathlib.Path(__file__).resolve().parent
runpy.run_path(str(HERE / 'refresh_current_lineups_resilient.py'), run_name='__main__')
