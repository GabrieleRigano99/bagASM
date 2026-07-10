project = "bagASM"
copyright = "2026, Gabriele Rigano"
author = "Gabriele Rigano"

extensions = [
    "myst_parser",
]

source_suffix = {
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_title = "bagASM"

html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
}
