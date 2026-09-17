import importlib

import pytest


def test_package_exposes_version() -> None:
    try:
        catchain = importlib.import_module("catchain")
    except ModuleNotFoundError:
        pytest.fail("catchain package is not importable", pytrace=False)

    assert catchain.__version__ == "0.1.0"
