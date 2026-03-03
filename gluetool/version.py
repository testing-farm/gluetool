from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('gluetool')

except PackageNotFoundError:
    pass
