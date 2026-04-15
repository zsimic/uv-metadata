from runez.conftest import cli, ClickRunner

from uv_metadata import main

__all__ = ["cli"]

ClickRunner.default_main = main
