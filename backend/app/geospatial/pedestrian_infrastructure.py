"""
SafePath Finder — Pedestrian Infrastructure Evidence Processor
Evaluates and preserves evidence for:
- Footpath / sidewalk availability (both, left, right, separate, none, unmapped)
- Pedestrian crossings (traffic_signals, marked, unmarked, none, unmapped)
- Crossing accessibility (tactile paving, wheelchair accessibility, audible signals)
- Road-crossing difficulty (low, moderate, high, unknown based on road hierarchy & controls)
- Construction or obstruction hazards (reconciled from community reports and tags)
Preserves unknown states: missing tags reflect survey gaps, NOT proven absence.
Keeps pedestrian infrastructure as an identifiable evaluation dimension.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class EdgeInfrastructureClassification:
    """Classified pedestrian infrastructure evidence for a single network edge."""
    edge_u: int
    edge_v: int
    edge_key: int
    sidewalk_status: str  # "both", "left", "right", "separate", "none", "unmapped"
    crossing_status: str  # "traffic_signals", "marked", "unmarked", "none", "unmapped"
    has_tactile_paving: Optional[bool]  # True, False, or None (unmapped)
    wheelchair_accessible: str  # "yes", "limited", "no", "unmapped"
    crossing_difficulty: str  # "low", "moderate", "high", "unknown"
    has_construction_hazard: bool
    construction_hazard_notes: Optional[str]
    data_state: str  # "present", "missing", "conflicting"
    sources: List[str]
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PedestrianInfrastructureProcessor:
    """
    Evaluates pedestrian infrastructure attributes on network edges.
    Enforces strict epistemological standards:
    - Never assumes missing sidewalk tag proves no sidewalk exists.
    - Separates mapped physical infrastructure from community observations.
    """

    SIDEWALK_AFFIRMATIVE = {"both", "yes", "separate", "left", "right"}
    SIDEWALK_NEGATIVE = {"no", "none"}

    HIGH_DIFFICULTY_ROADS = {"primary", "primary_link", "trunk", "trunk_link", "motorway", "motorway_link"}
    MODERATE_DIFFICULTY_ROADS = {"secondary", "secondary_link", "tertiary", "tertiary_link"}
    LOW_DIFFICULTY_ROADS = {"residential", "living_street", "pedestrian", "footway", "path", "service", "cycleway"}

    def __init__(self):
        pass

    def classify_edge_infrastructure(
        self,
        edge_data: Dict[str, Any],
        edge_u: int,
        edge_v: int,
        edge_key: int = 0,
        incident_nodes_data: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None,
        community_reports: Optional[List[Dict[str, Any]]] = None
    ) -> EdgeInfrastructureClassification:
        reports = community_reports or []
        u_data, v_data = incident_nodes_data or ({}, {})

        sources = ["OpenStreetMap Pedestrian Attributes"]
        limitations = [
            "Absence of sidewalk or crossing tags reflects survey coverage gaps on OpenStreetMap, not physical absence.",
            "Sidewalk surface smoothness and curb-ramp slopes require field measurement."
        ]

        # 1. Sidewalk Status
        # Check dedicated footway/pedestrian road type first
        highway = edge_data.get("highway")
        if isinstance(highway, list):
            highway = highway[0] if highway else "unclassified"
        highway = str(highway).lower().strip()

        sidewalk_raw = edge_data.get("sidewalk")
        if isinstance(sidewalk_raw, list):
            sidewalk_raw = sidewalk_raw[0] if sidewalk_raw else None
        sidewalk_val = str(sidewalk_raw).strip().lower() if sidewalk_raw else None

        if highway in {"footway", "pedestrian", "path"}:
            sidewalk_status = "separate"
        elif sidewalk_val in {"both", "yes"}:
            sidewalk_status = "both"
        elif sidewalk_val in {"left", "right"}:
            sidewalk_status = sidewalk_val
        elif sidewalk_val in self.SIDEWALK_NEGATIVE:
            sidewalk_status = "none"
        else:
            sidewalk_status = "unmapped"

        # 2. Crossing Status & Accessibility
        # Check incident nodes for crossing tags
        u_crossing = u_data.get("crossing") or u_data.get("highway") == "crossing"
        v_crossing = v_data.get("crossing") or v_data.get("highway") == "crossing"
        edge_crossing = edge_data.get("crossing")

        crossing_type = None
        for c in [edge_crossing, u_data.get("crossing"), v_data.get("crossing")]:
            if c:
                crossing_type = str(c).strip().lower()
                break

        if crossing_type in {"traffic_signals", "pelican", "toucan"}:
            crossing_status = "traffic_signals"
        elif crossing_type in {"zebra", "marked", "controlled"}:
            crossing_status = "marked"
        elif crossing_type in {"uncontrolled", "unmarked"}:
            crossing_status = "unmarked"
        elif u_crossing or v_crossing:
            crossing_status = "marked"
        else:
            crossing_status = "unmapped"

        # Tactile paving
        tactile_raw = edge_data.get("tactile_paving") or u_data.get("tactile_paving") or v_data.get("tactile_paving")
        if tactile_raw in {"yes", "true", "1"}:
            has_tactile = True
        elif tactile_raw in {"no", "false", "0"}:
            has_tactile = False
        else:
            has_tactile = None

        # Wheelchair accessibility
        wheelchair_raw = edge_data.get("wheelchair")
        if wheelchair_raw in {"yes", "designated"}:
            wheelchair_acc = "yes"
        elif wheelchair_raw in {"limited"}:
            wheelchair_acc = "limited"
        elif wheelchair_raw in {"no"}:
            wheelchair_acc = "no"
        else:
            wheelchair_acc = "unmapped"

        # 3. Crossing Difficulty
        if highway in self.HIGH_DIFFICULTY_ROADS:
            if crossing_status == "traffic_signals":
                crossing_diff = "moderate"
            else:
                crossing_diff = "high"
        elif highway in self.MODERATE_DIFFICULTY_ROADS:
            if crossing_status in {"traffic_signals", "marked"}:
                crossing_diff = "low"
            else:
                crossing_diff = "moderate"
        elif highway in self.LOW_DIFFICULTY_ROADS:
            crossing_diff = "low"
        else:
            crossing_diff = "unknown"

        # 4. Community Hazard / Construction Reports
        hazard_reports = [
            r for r in reports
            if r.get("category") in {"construction_hazard", "blocked_footpath"}
            or "construction" in str(r.get("description", "")).lower()
            or "blocked" in str(r.get("description", "")).lower()
        ]
        has_hazard = len(hazard_reports) > 0 or highway == "construction" or edge_data.get("construction") is not None
        hazard_notes = None
        if has_hazard:
            sources.append("Community Hazard Reports")
            notes_list = [r.get("description", "") for r in hazard_reports if r.get("description")]
            hazard_notes = "; ".join(notes_list) if notes_list else "Reported footpath construction or physical obstruction."

        # Data State
        if sidewalk_status != "unmapped" or crossing_status != "unmapped":
            data_state = "present"
        else:
            data_state = "missing"

        return EdgeInfrastructureClassification(
            edge_u=edge_u,
            edge_v=edge_v,
            edge_key=edge_key,
            sidewalk_status=sidewalk_status,
            crossing_status=crossing_status,
            has_tactile_paving=has_tactile,
            wheelchair_accessible=wheelchair_acc,
            crossing_difficulty=crossing_diff,
            has_construction_hazard=has_hazard,
            construction_hazard_notes=hazard_notes,
            data_state=data_state,
            sources=sources,
            limitations=limitations
        )

    def process_network_infrastructure(
        self,
        graph: nx.MultiDiGraph,
        edge_to_reports_map: Optional[Dict[Tuple[int, int, int], List[Dict[str, Any]]]] = None
    ) -> Dict[Tuple[int, int, int], EdgeInfrastructureClassification]:
        """Classifies pedestrian infrastructure across all network edges."""
        reports_map = edge_to_reports_map or {}
        results: Dict[Tuple[int, int, int], EdgeInfrastructureClassification] = {}

        for u, v, k, data in graph.edges(keys=True, data=True):
            reports = reports_map.get((u, v, k), [])
            u_node = graph.nodes.get(u, {})
            v_node = graph.nodes.get(v, {})

            cls = self.classify_edge_infrastructure(
                edge_data=data,
                edge_u=u,
                edge_v=v,
                edge_key=k,
                incident_nodes_data=(u_node, v_node),
                community_reports=reports
            )
            results[(u, v, k)] = cls

        return results

    @staticmethod
    def evaluate_infrastructure_deficiency(
        sidewalk_status: str = "unmapped",
        crossing_status: str = "unmapped",
        crossing_difficulty: str = "unknown",
        has_tactile_paving: Optional[bool] = None,
        wheelchair_accessible: str = "unmapped",
        has_construction_hazard: bool = False,
        r_unknown_prior: float = 0.50
    ) -> Tuple[float, float, List[str]]:
        """
        Computes the normalized pedestrian infrastructure deficiency indicator P(e) in [0.0, 1.0]
        and its evidence quality/coverage q_p(e) in [0.0, 1.0].
        P(e) = 0.0 denotes superior, accessible pedestrian infrastructure.
        P(e) = 1.0 denotes severe physical deficiency or hazard.
        Unmapped infrastructure strictly preserves uncertainty: q_p = 0.0, P(e) = r_unknown_prior.
        """
        limitations: List[str] = []
        q_sidewalk = 0.0
        p_sidewalk = r_unknown_prior

        sw = (sidewalk_status or "unmapped").lower().strip()
        if sw in ("both", "separate", "yes"):
            p_sidewalk = 0.10
            q_sidewalk = 1.0
        elif sw in ("left", "right"):
            p_sidewalk = 0.30
            q_sidewalk = 1.0
        elif sw in ("none", "no"):
            p_sidewalk = 0.85
            q_sidewalk = 1.0
            limitations.append("Confirmed absence of dedicated sidewalk; pedestrians share road space.")
        else:
            p_sidewalk = r_unknown_prior
            q_sidewalk = 0.0
            limitations.append("Sidewalk presence unmapped on OpenStreetMap; uncertainty preserved.")

        q_crossing = 0.0
        p_crossing = r_unknown_prior

        cr = (crossing_status or "unmapped").lower().strip()
        if cr in ("traffic_signals", "pelican", "toucan"):
            p_crossing = 0.10
            q_crossing = 1.0
        elif cr in ("marked", "zebra", "controlled"):
            p_crossing = 0.20
            q_crossing = 1.0
        elif cr in ("unmarked", "uncontrolled"):
            p_crossing = 0.60
            q_crossing = 0.80
        elif cr in ("none", "no"):
            p_crossing = 0.85
            q_crossing = 0.80
        else:
            p_crossing = r_unknown_prior
            q_crossing = 0.0

        diff = (crossing_difficulty or "unknown").lower().strip()
        diff_modifier = 0.0
        if diff == "high":
            diff_modifier = 0.20
            limitations.append("High road-crossing difficulty due to traffic volume/speed.")
        elif diff == "moderate":
            diff_modifier = 0.05
        elif diff == "low":
            diff_modifier = -0.05

        acc_bonus = 0.0
        if has_tactile_paving is True:
            acc_bonus += 0.05
        if (wheelchair_accessible or "").lower().strip() == "yes":
            acc_bonus += 0.05

        hazard_penalty = 0.0
        if has_construction_hazard:
            hazard_penalty = 0.30
            limitations.append("Active construction or physical obstruction hazard reported.")

        # Compute coverage q_p
        if q_sidewalk > 0 or q_crossing > 0 or has_construction_hazard:
            coverage_q = max(q_sidewalk * 0.60 + q_crossing * 0.40, 0.50 if has_construction_hazard else 0.0)
            coverage_q = min(max(round(coverage_q, 4), 0.0), 1.0)
            # Weighted observed deficiency
            raw_p = (p_sidewalk * 0.60 + p_crossing * 0.40) + diff_modifier + hazard_penalty - acc_bonus
            deficiency_p = min(max(round(raw_p, 4), 0.05), 1.0)
        else:
            coverage_q = 0.0
            deficiency_p = r_unknown_prior

        return deficiency_p, coverage_q, limitations

    @staticmethod
    def compute_route_infrastructure_summary(
        segments: List[Dict[str, Any]],
        total_distance_meters: float
    ) -> Dict[str, Any]:
        """
        Calculates route-level pedestrian infrastructure metrics, maintaining clear distinction
        between verified sidewalk coverage, unmapped gaps, and crossing accessibility.
        """
        if total_distance_meters <= 0.0:
            total_dist = sum(float(s.get("lengthMeters") or s.get("length_meters") or 100.0) for s in segments)
        else:
            total_dist = total_distance_meters

        sidewalk_doc_m = 0.0
        sidewalk_unmapped_m = 0.0
        sidewalk_none_m = 0.0
        crossing_count = 0
        signalized_crossings = 0
        tactile_count = 0
        high_diff_crossings = 0
        hazards_count = 0
        wheelchair_count = 0

        for s in segments:
            seg_len = float(s.get("lengthMeters") or s.get("length_meters") or 100.0)
            infra = s.get("infrastructure") or s.get("infrastructure_summary") or {}
            sw = infra.get("sidewalkStatus") or s.get("sidewalk_status") or "unmapped"
            cr = infra.get("crossingStatus") or s.get("crossing_status") or "unmapped"
            diff = infra.get("crossingDifficulty") or s.get("crossing_difficulty") or "unknown"
            tactile = infra.get("hasTactilePaving") if "hasTactilePaving" in infra else s.get("has_tactile_paving")
            hazard = infra.get("hasConstructionHazard") if "hasConstructionHazard" in infra else s.get("has_construction_hazard", False)
            wc = infra.get("wheelchairAccessible") if "wheelchairAccessible" in infra else s.get("wheelchair_accessible")

            if sw in {"both", "left", "right", "separate"}:
                sidewalk_doc_m += seg_len
            elif sw == "none":
                sidewalk_none_m += seg_len
            else:
                sidewalk_unmapped_m += seg_len

            if cr in {"traffic_signals", "marked", "unmarked"}:
                crossing_count += 1
            if cr == "traffic_signals":
                signalized_crossings += 1
            if tactile is True:
                tactile_count += 1
            if wc in {"yes", "designated"}:
                wheelchair_count += 1
            if diff == "high":
                high_diff_crossings += 1
            if hazard:
                hazards_count += 1

        effective_dist = max(total_dist, 1.0)
        doc_pct = round((sidewalk_doc_m / effective_dist) * 100.0, 1)
        unmapped_pct = round((sidewalk_unmapped_m / effective_dist) * 100.0, 1)
        none_pct = round((sidewalk_none_m / effective_dist) * 100.0, 1)

        explanation = (
            f"Pedestrian Infrastructure: {doc_pct}% ({int(sidewalk_doc_m)}m) of this route has documented "
            f"sidewalks/dedicated footpaths, and {unmapped_pct}% has unmapped footpath status on OpenStreetMap. "
            f"{crossing_count} pedestrian crossing point(s) mapped ({signalized_crossings} signalized). "
            f"SafePath Finder does not assume missing footpath tags indicate lack of walking space."
        )

        guidance = []
        if doc_pct >= 60.0:
            guidance.append("High proportion of documented pedestrian paths or sidewalks.")
        if unmapped_pct >= 50.0:
            guidance.append("Footpath data is predominantly unmapped; expect standard urban street verges.")
        if high_diff_crossings > 0:
            guidance.append(f"Contains {high_diff_crossings} major road traversal(s) requiring crossing caution.")
        if hazards_count > 0:
            guidance.append(f"{hazards_count} active construction or footpath obstruction report(s) noted.")

        return {
            "totalDistanceMeters": round(total_dist, 1),
            "sidewalkDocumentedLengthMeters": round(sidewalk_doc_m, 1),
            "sidewalkDocumentedPercentage": doc_pct,
            "sidewalkUnmappedLengthMeters": round(sidewalk_unmapped_m, 1),
            "sidewalkUnmappedPercentage": unmapped_pct,
            "sidewalkAbsentLengthMeters": round(sidewalk_none_m, 1),
            "sidewalkAbsentPercentage": none_pct,
            "crossingCount": crossing_count,
            "signalizedCrossingCount": signalized_crossings,
            "tactilePavingCount": tactile_count,
            "highDifficultyCrossingsCount": high_diff_crossings,
            "constructionHazardsCount": hazards_count,
            "wheelchairAccessibleCount": wheelchair_count,
            "sidewalkCoveragePercentage": doc_pct,
            "knownSidewalkDistanceMeters": round(sidewalk_doc_m, 1),
            "unmappedSidewalkDistanceMeters": round(sidewalk_unmapped_m, 1),
            "absentSidewalkDistanceMeters": round(sidewalk_none_m, 1),
            "highDifficultyCrossings": high_diff_crossings,
            "explanation": explanation,
            "guidance": guidance,
            "dataLimitation": "Sidewalk presence on OpenStreetMap is incomplete in developing urban corridors; missing data is preserved as unmapped."
        }


# Module-level aliases for ease of import
compute_route_infrastructure_summary = PedestrianInfrastructureProcessor.compute_route_infrastructure_summary
evaluate_infrastructure_deficiency = PedestrianInfrastructureProcessor.evaluate_infrastructure_deficiency

