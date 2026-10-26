# Configuration file for the Sphinx documentation builder.
#
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------

project = "Flask-Quickstart"
author = "Fictive Kin LLC"
copyright = f"%Y, {author}"

try:
    release = get_version("flask-quickstart")
except PackageNotFoundError:
    release = "unknown"
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
]

exclude_patterns = ["_build"]

autodoc_member_order = "bysource"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "flask": ("https://flask.palletsprojects.com/en/stable/", None),
    "werkzeug": ("https://werkzeug.palletsprojects.com/en/stable/", None),
}

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"
