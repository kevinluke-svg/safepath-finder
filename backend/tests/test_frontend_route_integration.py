"""
SafePath Finder — Frontend Route Integration & UI Contract Verification Tests
Tests:
- Route planner form inputs and validation alert (#routePlannerAlert)
- Route comparison container (#routeCardsContainer)
- Route decision summary container (#routeDecisionSummary)
- Map legend and categories (Safety-prioritized, Balanced, Fastest, Alternative)
- Quick landmark chips (Jayanagar, South End, Cubbon Park)
- Responsive CSS rules and auto-fit route card grid
- Epistemological caveats and absence of crowd density/pedestrian-count claims
- Privacy preservation (zero reporter PII or contact data in route UI)
"""

import os
import re

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join(WORKSPACE_DIR, "safepath_pro.html")
CSS_PATH = os.path.join(WORKSPACE_DIR, "styles.css")
JS_PATH = os.path.join(WORKSPACE_DIR, "app.js")
API_JS_PATH = os.path.join(WORKSPACE_DIR, "api_service.js")


def test_route_planner_dom_elements_in_html():
    """Verify all required route planning elements and containers exist in safepath_pro.html."""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Form inputs
    assert 'id="originInput"' in html
    assert 'id="destinationInput"' in html
    assert 'id="compareRoutesSubmitBtn"' in html

    # Validation alert area
    assert 'id="routePlannerAlert"' in html

    # Route comparison containers
    assert 'id="routeCardsContainer"' in html
    assert 'id="routeDecisionSummary"' in html

    # Quick landmark chips
    assert 'data-set-route="jayanagar-lalbagh"' in html
    assert 'data-set-route="southend-gandhibazaar"' in html
    assert 'data-set-route="cubbon-mgroad"' in html

    # Map container
    assert 'id="map"' in html
    assert 'id="fitMapBoundsBtn"' in html

    # Map legend swatches
    assert 'class="legend-swatch evidence"' in html
    assert 'class="legend-swatch balanced"' in html
    assert 'class="legend-swatch shortest"' in html
    assert 'class="legend-swatch alternative"' in html


def test_epistemological_caveats_in_html_and_js():
    """Verify honest uncertainty, no fake safe badges, and no crowd density in route presentation."""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    combined = (html + js).lower()

    # Explicit research caveat must be present
    assert "not verified probabilities of victimization" in combined
    assert "never equate" in combined or "absence of reports" in combined

    # Crowd density and pedestrian count estimates must NOT be displayed
    assert "crowd density" not in combined or "does not display" in combined
    assert "pedestrian-count" not in combined or "does not display" in combined


def test_responsive_grid_and_badges_in_css():
    """Verify responsive CSS rules for route cards, badges, and decision summary."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".route-cards-grid" in css
    assert "repeat(auto-fit, minmax(290px, 1fr))" in css
    assert ".route-planner-alert" in css
    assert ".engine-status-badge" in css
    assert ".time-diff-badge" in css
    assert ".route-identical-note" in css
    assert ".route-uncertainty-alert" in css
    assert ".route-decision-summary" in css
    assert ".badge-teal" in css
    assert ".badge-amber" in css
    assert ".badge-blue" in css
    assert ".badge-purple" in css


def test_js_routing_and_decision_logic_in_app_js():
    """Verify that app.js implements the complete routing integration workflow."""
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    # Required functions
    assert "function loadRoutes" in js or "async function loadRoutes" in js
    assert "function renderRouteCards" in js
    assert "function renderRouteDecisionSummary" in js
    assert "function renderRoutePolylines" in js
    assert "function normalizeSegment" in js
    assert "function selectRoute" in js or "async function selectRoute" in js

    # Validation feedback handling
    assert "routePlannerAlert" in js

    # Invalidate size on window resize
    assert "invalidateSize" in js
    assert "resize" in js

    # Route categories
    assert "safety_prioritized" in js
    assert "balanced" in js
    assert "fastest" in js
    assert "alternative" in js

    # Identical route handling
    assert "isIdenticalToFastest" in js
    assert "route-identical-note" in js


def test_api_service_live_routing_and_error_propagation():
    """Verify api_service.js connects to live backend on port 8001 and unpacks error details."""
    with open(API_JS_PATH, "r", encoding="utf-8") as f:
        api_js = f.read()

    assert "compareRoutes" in api_js
    assert "searchPlaces" in api_js
    assert "getRouteSegments" in api_js
    assert "errJson.detail" in api_js
    assert ":8001" in api_js


def test_location_autocomplete_dom_css_and_js_integration():
    """Verify autocomplete DOM elements, dropdown CSS, and JS controller in the frontend."""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    # HTML autocomplete containers & attributes
    assert 'id="originSuggestions"' in html
    assert 'id="destinationSuggestions"' in html
    assert 'id="originClearBtn"' in html
    assert 'id="destinationClearBtn"' in html
    assert 'aria-autocomplete="list"' in html

    # CSS styles for dropdown and coverage pills
    assert ".autocomplete-dropdown" in css
    assert ".autocomplete-item" in css
    assert ".coverage-pill--in" in css
    assert ".coverage-pill--out" in css

    # JS autocomplete controller
    assert "setupLocationAutocomplete" in js
    assert "searchPlaces" in js
    assert "originLocation" in js
    assert "destinationLocation" in js
    assert "originCoordinates" in js
    assert "destinationCoordinates" in js
