"""
SafePath Finder — Comprehensive Geospatial Evidence Processing Pipeline
Coordinates pedestrian network indexing, lighting classification, assistance facility routing,
historical crime evidence ingestion, and community reports matching into database records.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

import networkx as nx
import osmnx as ox

from app.models.evidence import StreetSegment, EvidenceObservation, EvidenceSource
from app.geospatial.study_area import StudyArea
from app.geospatial.network_adapter import OsmNetworkAdapter
from app.geospatial.spatial_matcher import SpatialMatcher
from app.geospatial.lighting_processor import LightingProcessor, EdgeLightingClassification
from app.geospatial.facilities_adapter import OsmFacilityAdapter, FacilityPoint
from app.geospatial.facility_router import FacilityRouter
from app.geospatial.crime_processor import CrimeProcessor, ValidatedCrimeRecord
from app.geospatial.community_processor import CommunityProcessor, ProcessedCommunityObservation

logger = logging.getLogger(__name__)


class EvidencePipeline:
    """
    Coordinates and persists street-segment evidence and atomic observations.
    Ensures missing data is preserved as unmapped/uncertainty rather than zero risk.
    Guarantees that reporter identity is never persisted in evidence records.
    """

    def __init__(
        self,
        study_area: Optional[StudyArea] = None,
        spatial_tolerance_meters: float = 30.0,
        historical_crime_days: int = 365,
        stale_report_days: int = 180
    ):
        self.study_area = study_area or StudyArea.from_settings()
        self.spatial_tolerance_meters = spatial_tolerance_meters
        self.historical_crime_days = historical_crime_days
        self.stale_report_days = stale_report_days

        self.net_adapter = OsmNetworkAdapter()
        self.facility_adapter = OsmFacilityAdapter()
        self.lighting_processor = LightingProcessor()
        self.crime_processor = CrimeProcessor(
            historical_window_days=historical_crime_days,
            spatial_tolerance_meters=spatial_tolerance_meters
        )
        self.community_processor = CommunityProcessor(
            stale_threshold_days=stale_report_days,
            spatial_tolerance_meters=spatial_tolerance_meters
        )

    def run_pipeline(
        self,
        db: Session,
        crime_file_path: Optional[str] = None,
        custom_graph: Optional[nx.MultiDiGraph] = None,
        custom_facilities: Optional[List[FacilityPoint]] = None
    ) -> Dict[str, Any]:
        """
        Executes the complete evidence ingestion, spatial matching, and persistence pipeline.
        Returns execution metrics, match statistics, and coverage summary.
        """
        start_time = time.time()
        logger.info(f"Starting EvidencePipeline execution for '{self.study_area.name}'...")

        # 1. Retrieve Pedestrian Graph
        if custom_graph is not None:
            graph = custom_graph
        else:
            net_res = self.net_adapter.get_pedestrian_network(self.study_area)
            graph = net_res.graph

        total_edges = len(graph.edges)
        logger.info(f"Pedestrian network loaded: {len(graph.nodes)} nodes, {total_edges} edges.")

        # 2. Build Spatial Matcher
        matcher = SpatialMatcher(
            graph=graph,
            default_tolerance_meters=self.spatial_tolerance_meters
        )

        # 3. Community Reports Processing
        community_obs, edge_community_map = self.community_processor.process_community_reports(
            db=db,
            study_area=self.study_area,
            matcher=matcher
        )

        # 4. Lighting Classification (Reconciled with Community Reports)
        lighting_map = self.lighting_processor.process_network_lighting(
            graph=graph,
            edge_to_reports_map=edge_community_map
        )

        # 5. Assistance Facilities Routing (Police & Hospitals)
        if custom_facilities is not None:
            all_facilities = custom_facilities
        else:
            fac_audit = self.facility_adapter.get_facilities(self.study_area)
            all_facilities = fac_audit.police_stations + fac_audit.hospitals

        router = FacilityRouter(graph=graph)
        police_prox = router.compute_facility_distances_for_nodes(all_facilities, "police")
        hospital_prox = router.compute_facility_distances_for_nodes(all_facilities, "hospital")

        # 6. Crime Evidence Ingestion & Spatial Snapping
        crime_records: List[ValidatedCrimeRecord] = []
        edge_crime_map: Dict[Tuple[int, int, int], List[ValidatedCrimeRecord]] = {}
        crime_summary = None

        if crime_file_path:
            try:
                crime_records, crime_summary = self.crime_processor.ingest_csv(
                    crime_file_path,
                    study_area=self.study_area
                )
                crime_records, edge_crime_map = self.crime_processor.match_records_to_network(
                    crime_records,
                    matcher=matcher
                )
            except Exception as e:
                logger.error(f"Crime dataset processing failed: {e}")

        # 7. Persist or Update Street Segments and Observations in Database
        persisted_obs_count = 0
        persisted_segments_count = 0

        # Create or update synthetic route identifier for study area segments
        study_area_route_id = f"route-{self.study_area.slug}"

        # Clean prior pipeline observations for this route to prevent unbounded duplication
        existing_seg_ids = [
            s.id for s in db.query(StreetSegment.id).filter(StreetSegment.route_id == study_area_route_id).all()
        ]
        if existing_seg_ids:
            db.query(EvidenceObservation).filter(EvidenceObservation.segment_id.in_(existing_seg_ids)).delete(synchronize_session=False)
            db.query(StreetSegment).filter(StreetSegment.id.in_(existing_seg_ids)).delete(synchronize_session=False)
            db.flush()

        now_utc = datetime.now(timezone.utc)

        # Iterate over edges and create StreetSegment records
        for u, v, k, data in graph.edges(keys=True, data=True):
            edge_key = (u, v, k)
            segment_id = f"seg-{self.study_area.slug}-{u}-{v}-{k}"

            # Street Name
            raw_name = data.get("name")
            if isinstance(raw_name, list):
                street_name = ", ".join(str(n) for n in raw_name)
            elif raw_name:
                street_name = str(raw_name)
            else:
                street_name = f"Unnamed Pathway ({data.get('highway', 'pedestrian')})"

            # Geometry
            geom = data.get("geometry")
            if geom:
                # Convert LineString (lon, lat) to [[lat, lon], ...]
                coords = [[round(lat, 6), round(lon, 6)] for lon, lat in geom.coords]
            else:
                u_node = graph.nodes[u]
                v_node = graph.nodes[v]
                coords = [
                    [round(u_node.get("y", 0.0), 6), round(u_node.get("x", 0.0), 6)],
                    [round(v_node.get("y", 0.0), 6), round(v_node.get("x", 0.0), 6)]
                ]

            edge_len = float(data.get("length", 100.0))

            # Lighting
            light_cls = lighting_map.get(edge_key)
            lit_status = light_cls.lit_status if light_cls else "unmapped"

            # Facilities
            edge_fac = router.get_edge_facility_proximity(u, v, police_prox, hospital_prox)
            pol = edge_fac["police"]
            hosp = edge_fac["hospital"]

            pol_dist = pol.distance_meters if pol else None
            pol_time = pol.walking_time_minutes if pol else None
            hosp_dist = hosp.distance_meters if hosp else None
            hosp_time = hosp.walking_time_minutes if hosp else None

            # Crime
            matched_crimes = edge_crime_map.get(edge_key, [])
            crime_cnt, crime_rate, crime_info = self.crime_processor.calculate_segment_crime_indicator(
                matched_crimes,
                segment_length_meters=edge_len
            )

            # Community Reports
            matched_reports = edge_community_map.get(edge_key, [])
            comm_cnt = len(matched_reports)

            # State & Freshness Determination
            if lit_status in {"lit", "unlit"} and (pol is not None or hosp is not None):
                coverage = "adequate"
                state = "available"
            elif lit_status == "conflicting":
                coverage = "limited"
                state = "limited"
            else:
                coverage = "insufficient"
                state = "insufficient"

            limitations = []
            if light_cls:
                limitations.extend(light_cls.limitations)
            if lit_status == "unmapped":
                limitations.append("Street lighting is unmapped on OpenStreetMap; darkness is not assumed.")
            if pol and pol.is_straight_line:
                limitations.append("Police access distance is Euclidean straight-line due to disconnected network graph.")
            if hosp and hosp.is_straight_line:
                limitations.append("Hospital access distance is Euclidean straight-line due to disconnected network graph.")

            ev_summary = {
                "lighting": light_cls.to_dict() if light_cls else {"litStatus": "unmapped"},
                "policeAccess": pol.to_dict() if pol else None,
                "hospitalAccess": hosp.to_dict() if hosp else None,
                "crime": crime_info,
                "communityReportsCount": comm_cnt
            }

            segment = StreetSegment(
                id=segment_id,
                route_id=study_area_route_id,
                street_name=street_name,
                source="SafePath Geospatial Pipeline",
                observed_at=now_utc,
                coverage=coverage,
                freshness="fresh",
                state=state,
                risk_estimate=f"Evidence state: {state}; Lighting: {lit_status}; Crimes: {crime_cnt}",
                limitations=limitations,
                attributes=ev_summary,
                timeline=[],
                geometry=coords,
                edge_u=u,
                edge_v=v,
                edge_key=k,
                length_meters=round(edge_len, 1),
                lit_status=lit_status,
                nearest_police_distance_meters=pol_dist,
                nearest_police_walking_minutes=pol_time,
                nearest_hospital_distance_meters=hosp_dist,
                nearest_hospital_walking_minutes=hosp_time,
                crime_count=crime_cnt,
                crime_rate_per_km=crime_rate,
                community_reports_count=comm_cnt,
                evidence_summary=ev_summary
            )
            db.add(segment)
            persisted_segments_count += 1

            # Atomic Evidence Observation for Lighting
            if light_cls and light_cls.lit_status != "unmapped":
                obs_light = EvidenceObservation(
                    id=f"obs-lit-{segment_id}",
                    source_id=f"osm-way-{u}-{v}",
                    source_type="osm_lighting",
                    category="lighting",
                    subcategory=f"lighting_{light_cls.lit_status}",
                    latitude=coords[0][0] if coords else None,
                    longitude=coords[0][1] if coords else None,
                    geometry={"type": "LineString", "coordinates": [[c[1], c[0]] for c in coords]},
                    segment_id=segment_id,
                    edge_u=u,
                    edge_v=v,
                    edge_key=k,
                    match_distance_meters=0.0,
                    match_method="way_attribute",
                    match_status="matched",
                    observed_at=now_utc,
                    ingested_at=now_utc,
                    source_attribution="© OpenStreetMap contributors",
                    verification_status="official_osm_attribute",
                    severity=None,
                    confidence=light_cls.confidence,
                    data_state=light_cls.data_state,
                    provenance="OpenStreetMap Pedestrian Way Tags",
                    limitations=light_cls.limitations,
                    attributes={"osm_lit": light_cls.osm_lit_value, "lit_status": light_cls.lit_status}
                )
                db.add(obs_light)
                persisted_obs_count += 1

            # Atomic Evidence Observations for Matched Crimes
            for cr in matched_crimes:
                obs_crime = EvidenceObservation(
                    id=f"obs-cr-{cr.incident_id}",
                    source_id=cr.incident_id,
                    source_type="crime_dataset",
                    category="crime",
                    subcategory=cr.category,
                    latitude=cr.latitude,
                    longitude=cr.longitude,
                    geometry={"type": "Point", "coordinates": [cr.longitude, cr.latitude]},
                    segment_id=segment_id,
                    edge_u=u,
                    edge_v=v,
                    edge_key=k,
                    match_distance_meters=cr.match_result.distance_meters if cr.match_result else None,
                    match_method="strtree_project",
                    match_status="matched",
                    observed_at=cr.timestamp,
                    ingested_at=now_utc,
                    source_attribution=cr.source_name,
                    verification_status="documented_crime_record",
                    severity=cr.severity,
                    confidence="moderate",
                    data_state="present",
                    provenance=cr.source_name,
                    limitations=[
                        "Historical crime count normalized by street length.",
                        "Does not imply direct individual victimization probability."
                    ],
                    attributes={"category": cr.category, "severity": cr.severity}
                )
                db.add(obs_crime)
                persisted_obs_count += 1

            # Atomic Evidence Observations for Matched Community Reports
            for cm in matched_reports:
                obs_comm = EvidenceObservation(
                    id=f"obs-cm-{cm.report_id}",
                    source_id=cm.report_id,
                    source_type="community_report",
                    category=cm.evidence_category,
                    subcategory=cm.subcategory,
                    latitude=cm.latitude,
                    longitude=cm.longitude,
                    geometry={"type": "Point", "coordinates": [cm.longitude, cm.latitude]} if cm.longitude else {},
                    segment_id=segment_id,
                    edge_u=u,
                    edge_v=v,
                    edge_key=k,
                    match_distance_meters=cm.match_result.distance_meters if cm.match_result else None,
                    match_method="strtree_project",
                    match_status="matched",
                    observed_at=cm.observed_at,
                    ingested_at=cm.submitted_at,
                    source_attribution="SafePath Community Contributor (PII Stripped)",
                    verification_status=cm.verification_status,
                    severity=None,
                    confidence=cm.confidence,
                    data_state=cm.data_state,
                    provenance="Community Report Submission",
                    limitations=cm.limitations,
                    attributes={"description": cm.description_summary, "corroborations": cm.corroborations_count}
                )
                db.add(obs_comm)
                persisted_obs_count += 1

        db.commit()
        execution_time = round(time.time() - start_time, 2)
        logger.info(
            f"EvidencePipeline completed in {execution_time}s: "
            f"{persisted_segments_count} segments, {persisted_obs_count} observations persisted."
        )

        # 8. Compute Coverage Metrics
        lit_count = sum(1 for c in lighting_map.values() if c.lit_status == "lit")
        unlit_count = sum(1 for c in lighting_map.values() if c.lit_status == "unlit")
        conflicting_count = sum(1 for c in lighting_map.values() if c.lit_status == "conflicting")
        unmapped_count = sum(1 for c in lighting_map.values() if c.lit_status == "unmapped")
        known_lighting = lit_count + unlit_count
        lighting_pct = round((known_lighting / total_edges * 100.0), 2) if total_edges > 0 else 0.0

        police_acc_count = sum(1 for p in police_prox.values() if p.distance_meters <= 1500.0)
        total_nodes = len(graph.nodes)
        police_acc_pct = round((police_acc_count / total_nodes * 100.0), 2) if total_nodes > 0 else 0.0

        hosp_acc_count = sum(1 for h in hospital_prox.values() if h.distance_meters <= 2000.0)
        hosp_acc_pct = round((hosp_acc_count / total_nodes * 100.0), 2) if total_nodes > 0 else 0.0

        crime_matched_count = sum(len(crimes) for crimes in edge_crime_map.values())
        comm_matched_count = sum(len(reports) for reports in edge_community_map.values())

        coverage = {
            "studyAreaName": self.study_area.name,
            "totalEdges": total_edges,
            "edgesWithLighting": known_lighting,
            "lightingCoveragePercentage": lighting_pct,
            "litEdgesCount": lit_count,
            "unlitEdgesCount": unlit_count,
            "conflictingLightingEdgesCount": conflicting_count,
            "unmappedLightingEdgesCount": unmapped_count,
            "policeStationsCount": len([f for f in all_facilities if f.facility_type == "police"]),
            "policeAccessibleEdgesCount": police_acc_count,
            "policeAccessiblePercentage": police_acc_pct,
            "hospitalsCount": len([f for f in all_facilities if f.facility_type == "hospital"]),
            "hospitalAccessibleEdgesCount": hosp_acc_count,
            "hospitalAccessiblePercentage": hosp_acc_pct,
            "crimeIncidentsMatched": crime_matched_count,
            "communityReportsMatched": comm_matched_count,
            "dataStateBreakdown": {
                "present": known_lighting + crime_matched_count + comm_matched_count,
                "missing": unmapped_count,
                "conflicting": conflicting_count,
                "stale": sum(1 for r in community_obs if r.data_state == "stale")
            },
            "dataGaps": [
                f"{unmapped_count} street segments ({round(unmapped_count/max(total_edges,1)*100, 1)}%) lack explicit OpenStreetMap lighting tags.",
                "Police incident records lack open street-level GPS point publication in this jurisdiction.",
                "Facility operational hours and staffed status are unverified in OpenStreetMap POIs."
            ],
            "caveats": [
                "Missing data is preserved as unmapped/uncertainty and never converted to zero risk or safe lighting.",
                "Proximity to police stations and hospitals does not guarantee immediate availability or absence of crime.",
                "Community reports reflect subjective perceptions and do not constitute absolute ground-truth proof."
            ]
        }

        return {
            "studyAreaName": self.study_area.name,
            "edgesProcessed": persisted_segments_count,
            "observationsPersisted": persisted_obs_count,
            "crimeObservationsMatched": crime_matched_count,
            "lightingObservationsRecorded": known_lighting,
            "facilitiesMapped": len(all_facilities),
            "communityReportsMatched": comm_matched_count,
            "executionTimeSeconds": execution_time,
            "status": "success",
            "coverage": coverage
        }
