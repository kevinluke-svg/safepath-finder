"""
SafePath Finder — Street Lighting Evidence Adapter & Coverage Audit
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

import networkx as nx

from app.geospatial.study_area import StudyArea

logger = logging.getLogger(__name__)


@dataclass
class LightingAuditResult:
    """Summary of audited street lighting evidence across the study area."""
    study_area_name: str
    total_edges_inspected: int
    explicitly_lit_edges_count: int
    explicitly_unlit_edges_count: int
    unmapped_edges_count: int
    coverage_ratio: float
    data_state: str  # "adequate", "limited", "insufficient"
    street_lamp_nodes_count: int
    sources: List[str]
    retrieved_at: str
    caveat: str
    attribution: str = "© OpenStreetMap contributors, Open Database License (ODbL) 1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "studyAreaName": self.study_area_name,
            "totalEdgesInspected": self.total_edges_inspected,
            "explicitlyLitEdgesCount": self.explicitly_lit_edges_count,
            "explicitlyUnlitEdgesCount": self.explicitly_unlit_edges_count,
            "unmappedEdgesCount": self.unmapped_edges_count,
            "coveragePercentage": round(self.coverage_ratio * 100, 2),
            "dataState": self.data_state,
            "streetLampNodesCount": self.street_lamp_nodes_count,
            "sources": self.sources,
            "retrievedAt": self.retrieved_at,
            "caveat": self.caveat,
            "attribution": self.attribution
        }


class BaseLightingAdapter(ABC):
    """Abstract interface for lighting evidence collection."""

    @abstractmethod
    def audit_lighting(
        self,
        study_area: StudyArea,
        graph: Optional[nx.MultiDiGraph] = None
    ) -> LightingAuditResult:
        """Audits lighting tags on network edges and mapped streetlamps."""
        pass


class OsmLightingAdapter(BaseLightingAdapter):
    """
    Evaluates OpenStreetMap lighting tags ('lit', 'highway=street_lamp').
    Maintains strict epistemological distinction: missing tags indicate
    unmapped uncertainty, NOT proven darkness.
    """

    LIT_AFFIRMATIVE_VALUES = {"yes", "24/7", "dusk-dawn", "sunset-sunrise", "operating_times"}
    LIT_NEGATIVE_VALUES = {"no", "disused"}

    def audit_lighting(
        self,
        study_area: StudyArea,
        graph: Optional[nx.MultiDiGraph] = None
    ) -> LightingAuditResult:
        if graph is None:
            # Empty audit when graph not provided
            return LightingAuditResult(
                study_area_name=study_area.name,
                total_edges_inspected=0,
                explicitly_lit_edges_count=0,
                explicitly_unlit_edges_count=0,
                unmapped_edges_count=0,
                coverage_ratio=0.0,
                data_state="insufficient",
                street_lamp_nodes_count=0,
                sources=["OpenStreetMap"],
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                caveat="No street network graph provided for lighting inspection."
            )

        total_edges = 0
        lit_count = 0
        unlit_count = 0
        unmapped_count = 0

        for u, v, k, data in graph.edges(keys=True, data=True):
            total_edges += 1
            lit_val = data.get("lit")
            if isinstance(lit_val, list):
                lit_val = lit_val[0] if lit_val else None

            if lit_val is not None and isinstance(lit_val, str):
                cleaned = lit_val.strip().lower()
                if cleaned in self.LIT_AFFIRMATIVE_VALUES:
                    lit_count += 1
                elif cleaned in self.LIT_NEGATIVE_VALUES:
                    unlit_count += 1
                else:
                    unmapped_count += 1
            else:
                unmapped_count += 1

        coverage_ratio = ((lit_count + unlit_count) / total_edges) if total_edges > 0 else 0.0

        if coverage_ratio >= 0.70:
            data_state = "adequate"
        elif coverage_ratio >= 0.20:
            data_state = "limited"
        else:
            data_state = "insufficient"

        # Count mapped street lamps on nodes if present
        lamp_count = sum(1 for _, n_data in graph.nodes(data=True) if n_data.get("highway") == "street_lamp")

        return LightingAuditResult(
            study_area_name=study_area.name,
            total_edges_inspected=total_edges,
            explicitly_lit_edges_count=lit_count,
            explicitly_unlit_edges_count=unlit_count,
            unmapped_edges_count=unmapped_count,
            coverage_ratio=coverage_ratio,
            data_state=data_state,
            street_lamp_nodes_count=lamp_count,
            sources=["OpenStreetMap (Way tags 'lit=*', Node tags 'highway=street_lamp')"],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            caveat=(
                "Absence of 'lit' tags on OpenStreetMap edges represents an observational/survey gap, "
                "NOT the physical absence of lighting. SafePath Finder explicitly classifies untagged "
                "segments as unmapped/uncertain rather than assuming dark conditions."
            )
        )
