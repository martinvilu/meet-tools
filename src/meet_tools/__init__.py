"""Meet Tools."""

from importlib.metadata import PackageNotFoundError, version as _metadata_version

try:
    __version__ = _metadata_version("meet-tools")
except PackageNotFoundError:
    __version__ = "desconocida"
