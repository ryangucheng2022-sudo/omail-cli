from setuptools import setup

# The tool itself is a single self-contained file under bin/; install it as a
# command script (pyproject.toml carries all project metadata).
setup(scripts=["bin/omail"])
