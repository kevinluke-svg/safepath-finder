import os
import re

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join(WORKSPACE_DIR, "safepath_pro.html")
CSS_PATH = os.path.join(WORKSPACE_DIR, "styles.css")
JS_PATH = os.path.join(WORKSPACE_DIR, "app.js")


def test_top_navigation_links_and_targets_in_html():
    """Priority 1: All top navigation links must have valid target section IDs in safepath_pro.html."""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    expected_sections = [
        "plan",
        "routes",
        "evidence-explorer",
        "community",
        "safety-guidelines"
    ]

    # Verify each target section exists in the DOM
    for section_id in expected_sections:
        assert f'id="{section_id}"' in html, f"Target section #{section_id} is missing from safepath_pro.html"

    # Verify desktop nav links exist
    assert 'href="#plan"' in html
    assert 'href="#routes"' in html
    assert 'href="#evidence-explorer"' in html
    assert 'href="#community"' in html
    assert 'href="#safety-guidelines"' in html

    # Verify mobile drawer links exist
    assert 'data-nav-close' in html


def test_navigation_scroll_offsets_in_css():
    """Priority 1: Fixed/sticky header scroll offsets must be handled via scroll-margin-top in styles.css."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert "scroll-margin-top" in css, "scroll-margin-top rule missing from styles.css"
    assert "#plan" in css and "#routes" in css, "Navigation section IDs missing from CSS scroll-margin rule"


def test_navigation_scrollspy_and_handlers_in_js():
    """Priority 1: Active highlight tracking, scrollspy, and navigation helpers exist in app.js."""
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert "NAV_SECTIONS" in js, "NAV_SECTIONS array missing in app.js"
    assert "setActiveNavLink" in js, "setActiveNavLink function missing in app.js"
    assert "navigateToSection" in js, "navigateToSection function missing in app.js"
    assert "setupScrollSpy" in js, "setupScrollSpy function missing in app.js"
    assert "popstate" in js, "Browser history popstate listener missing in app.js"
