"""Main datbase initialization/installation script."""

from . import fred, indices, mixed, sec, yfinance


def run(install_features: bool = False) -> None:
    """Run all installation scripts for all submodules."""
    fred.install.run(install_features=install_features)
    indices.install.run()
    sec.install.run(install_features=install_features)
    yfinance.install.run(install_features=install_features)
    if install_features:
        mixed.install.run()
