# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Posey Control'
copyright = '2023, Anthony Wertz'
author = 'Anthony Wertz'
release = '1.2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx_immaterial",
    "sphinx_immaterial.apidoc.python.apigen",
    # "sphinx_design",
    # "IPython.sphinxext.ipython_console_highlighting",
    # "IPython.sphinxext.ipython_directive",
    # "ipython_with_reprs",
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_immaterial"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# html_css_files = [
#     "extra.css",
# ]

# # Define a custom inline Python syntax highlighting literal
# rst_prolog = """
# .. role:: python(code)
#    :language: python
#    :class: highlight
# """

# Sets the default role of `content` to :python:`content`, which uses the custom Python syntax highlighting inline literal
# default_role = "python"

html_title = "Posey Control"

# Sphinx Immaterial theme options
html_theme_options = {
    "icon": {
        "repo": "fontawesome/brands/github",
    },
    "site_url": "https://github.com/SML-Posey/posey-ctrl",
    "repo_url": "https://github.com/SML-Posey/posey-ctrl",
    "repo_name": "SML-Posey/posey-ctrl",
    "repo_type": "github",
    "social": [
        {
            "icon": "fontawesome/brands/github",
            "link": "https://github.com/SML-Posey/posey-ctrl",
        },
        {
            "icon": "fontawesome/brands/python",
            "link": "https://pypi.org/SML-Posey/posey-ctrl",
        },
    ],
    "edit_uri": "",
    "globaltoc_collapse": True,
    "features": [
        "navigation.expand",
        # "navigation.tabs",
        # "toc.integrate",
        "navigation.sections",
        # "navigation.instant",
        # "header.autohide",
        "navigation.top",
        # "navigation.tracking",
        # "search.highlight",
        "search.share",
        "toc.follow",
        "toc.sticky",
        "content.tabs.link",
        "announce.dismiss",
    ],
    "palette": [
        {
            "media": "(prefers-color-scheme: light)",
            "scheme": "default",
            "primary": "light-green",
            "accent": "light-blue",
            "toggle": {
                "icon": "material/lightbulb-outline",
                "name": "Switch to dark mode",
            },
        },
        {
            "media": "(prefers-color-scheme: dark)",
            "scheme": "slate",
            "primary": "deep-orange",
            "accent": "lime",
            "toggle": {
                "icon": "material/lightbulb",
                "name": "Switch to light mode",
            },
        },
    ],
}

html_last_updated_fmt = ""
html_use_index = True
html_domain_indices = True

# -- Extension configuration -------------------------------------------------

# Create hyperlinks to other documentation
autodoc_default_options = {
    # "imported-members": True,
    "members": True,
    "undoc-members": True,
    # "special-members": True,
    # "inherited-members": "ndarray",
    # "member-order": "groupwise",
}
autodoc_typehints = "signature"
autodoc_typehints_description_target = "documented"
autodoc_typehints_format = "short"

# -- Sphinx Immaterial configs -------------------------------------------------

# Python apigen configuration
python_apigen_modules = {
    "poseyctrl": "poseyctrl",
}
python_apigen_default_groups = [
    ("class:.*", "Classes"),
    ("data:.*", "Variables"),
    ("function:.*", "Functions"),
    ("classmethod:.*", "Class methods"),
    ("method:.*", "Methods"),
    (r"method:.*\.[A-Z][A-Za-z,_]*", "Constructors"),
    (r"method:.*\.__[A-Za-z,_]*__", "Special methods"),
    (r"method:.*\.__(init|new)__", "Constructors"),
    (r"method:.*\.__(str|repr)__", "String representation"),
    ("property:.*", "Properties"),
    (r".*:.*\.is_[a-z,_]*", "Attributes"),
]
python_apigen_default_order = [
    ("class:.*", 10),
    ("data:.*", 11),
    ("function:.*", 12),
    ("classmethod:.*", 40),
    ("method:.*", 50),
    (r"method:.*\.[A-Z][A-Za-z,_]*", 20),
    (r"method:.*\.__[A-Za-z,_]*__", 28),
    (r"method:.*\.__(init|new)__", 20),
    (r"method:.*\.__(str|repr)__", 30),
    ("property:.*", 60),
    (r".*:.*\.is_[a-z,_]*", 70),
]
python_apigen_order_tiebreaker = "alphabetical"
python_apigen_case_insensitive_filesystem = False
python_apigen_show_base_classes = True

# Python domain directive configuration
python_module_names_to_strip_from_xrefs = ["collections.abc"]

# General API configuration
object_description_options = [
    ("py:.*", dict(include_rubrics_in_toc=True)),
]

sphinx_immaterial_custom_admonitions = [
    {
        "name": "seealso",
        "title": "See also",
        "classes": ["collapsible"],
        "icon": "fontawesome/regular/eye",
        "override": True,
    },
    {
        "name": "star",
        "icon": "octicons/star-fill-24",
        "color": (255, 233, 3),  # Gold
    },
    {
        "name": "fast-performance",
        "title": "Faster performance",
        "icon": "material/speedometer",
        "color": (40, 167, 69),  # Green: --sd-color-success
    },
    {
        "name": "slow-performance",
        "title": "Slower performance",
        "icon": "material/speedometer-slow",
        "color": (220, 53, 69),  # Red: --sd-color-danger
    },
]