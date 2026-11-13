"""
SafePath Finder — Street Lighting Evidence Processor
Implements strict epistemological rules for street lighting:
Differentiates lit, unlit, conflicting, and unmapped conditions.
Reconciles OpenStreetMap way tags, mapped pole assets, and community reports.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class EdgeLightingClassification:
    """Classified lighting evidence state for a single network edge."""
    edge_u: int
    edge_v: int
    edge_key: int
    lit_status: str  # "lit", "unlit", "conflicting", "unmapped"
    data_state: str  # "present", "missing", "conflicting"
    confidence: str  # "high", "moderate", "low"
    osm_lit_value: Optional[str]
    mapped_streetlamps_count: int
    has_conflicting_community_report: bool
    sources: List[str]
    notes: str
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LightingProcessor:
    """
    Evaluates and reconciles street lighting evidence.
    Refuses to infer complete street illumination from single point assets.
    Treats missing OSM tags as unmapped uncertainty rather than dark conditions.
    """

    LIT_AFFIRMATIVE = {"yes", "24/7", "dusk-dawn", "sunset-sunrise", "operating_times"}
    LIT_NEGATIVE = {"no", "disused"}

    def __init__(self):
        pass

    def classify_edge_lighting(
        self,
        edge_data: Dict[str, Any],
        edge_u: int,
        edge_v: int,
        edge_key: int = 0,
        associated_lamp_count: int = 0,
        community_lighting_reports: Optional[List[Dict[str, Any]]] = None
    ) -> EdgeLightingClassification:
        """
        Classifies lighting on a street segment by reconciling OSM attributes
        with approved community reports and streetlight points.
        """
        community_reports = community_lighting_reports or []

        # 1. Parse OSM way lit tag
        lit_raw = edge_data.get("lit")
        if isinstance(lit_raw, list):
            lit_raw = lit_raw[0] if lit_raw else None

        osm_lit = lit_raw.strip().lower() if isinstance(lit_raw, str) else None

        # 2. Inspect Community Reports for lighting issues
        has_broken_report = any(
            r.get("category") in {"lighting", "lighting_concern"} and
            "broken" in (r.get("description", "") + r.get("subcategory", "")).lower()
            for r in community_reports
        )
        has_affirmative_report = any(
            r.get("category") in {"lighting", "lighting_concern"} and
            "well_lit" in (r.get("description", "") + r.get("subcategory", "")).lower()
            for r in community_reports
        )

        sources = ["OpenStreetMap Pedestrian Network"]
        limitations = [
            "Mapped streetlight status does not guarantee power grid operation or luminaire bulb functionality.",
            "Vegetation canopy or high-rise architecture may obstruct luminaire ground illumination."
        ]

        # 3. Apply Decision Matrix
        if osm_lit in self.LIT_AFFIRMATIVE:
            if has_broken_report:
                lit_status = "conflicting"
                data_state = "conflicting"
                confidence = "moderate"
                sources.append("Community Reports (Broken Luminaire)")
                notes = (
                    f"Conflict detected: OpenStreetMap tags edge as '{osm_lit}', "
                    "but approved community reports document broken or non-functioning lighting."
                )
            else:
                lit_status = "lit"
                data_state = "present"
                confidence = "high"
                notes = f"Mapped as lit via OpenStreetMap way tag: lit={osm_lit}. (Cartographic tag; not field-verified operational)."

        elif osm_lit in self.LIT_NEGATIVE:
            if has_affirmative_report or associated_lamp_count >= 2:
                lit_status = "conflicting"
                data_state = "conflicting"
                confidence = "moderate"
                sources.append("Municipal/Community Assets")
                notes = (
                    f"Conflict detected: OpenStreetMap tags edge as '{osm_lit}', "
                    f"but {associated_lamp_count} streetlamp points or community corroboration exist."
                )
            else:
                lit_status = "unlit"
                data_state = "present"
                confidence = "high"
                notes = f"Mapped as unlit via OpenStreetMap way tag: lit={osm_lit}."

        else:
            # Missing or unmapped OSM tag
            if has_broken_report:
                lit_status = "unlit"
                data_state = "present"
                confidence = "moderate"
                sources.append("Community Reports")
                notes = "Unmapped on OSM, but approved community report confirms absence/failure of lighting."
            elif has_affirmative_report:
                lit_status = "lit"
                data_state = "present"
                confidence = "moderate"
                sources.append("Community Reports")
                notes = "Unmapped on OSM, but approved community report confirms active street illumination."
            else:
                lit_status = "unmapped"
                data_state = "missing"
                confidence = "low"
                notes = (
                    "Unknown/unmapped on OpenStreetMap. "
                    "SafePath Finder preserves uncertainty; this segment is NOT assumed to be dark."
                )
                limitations.append(
                    "Informational gap: Absence of lighting tag reflects survey omission, not physical darkness."
                )

        return EdgeLightingClassification(
            edge_u=edge_u,
            edge_v=edge_v,
            edge_key=edge_key,
            lit_status=lit_status,
            data_state=data_state,
            confidence=confidence,
            osm_lit_value=osm_lit,
            mapped_streetlamps_count=associated_lamp_count,
            has_conflicting_community_report=(lit_status == "conflicting"),
            sources=sources,
            notes=notes,
            limitations=limitations
        )

    def process_network_lighting(
        self,
        graph: nx.MultiDiGraph,
        edge_to_reports_map: Optional[Dict[Tuple[int, int, int], List[Dict[str, Any]]]] = None
    ) -> Dict[Tuple[int, int, int], EdgeLightingClassification]:
        """
        Processes lighting classifications across all edges in the graph.
        """
        reports_map = edge_to_reports_map or {}
        classifications: Dict[Tuple[int, int, int], EdgeLightingClassification] = {}

        for u, v, k, data in graph.edges(keys=True, data=True):
            associated_reports = reports_map.get((u, v, k), [])
            # Count lamps on incident nodes
            lamp_count = 0
            if graph.nodes[u].get("highway") == "street_lamp":
                lamp_count += 1
            if graph.nodes[v].get("highway") == "street_lamp":
                lamp_count += 1

            cls = self.classify_edge_lighting(
                edge_data=data,
                edge_u=u,
                edge_v=v,
                edge_key=k,
                associated_lamp_count=lamp_count,
                community_lighting_reports=associated_reports
            )
            classifications[(u, v, k)] = cls

        return classifications
