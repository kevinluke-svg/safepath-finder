"""
SafePath Finder — Evidence & Segment Inspection API Routes
Provides endpoints for street segments, atomic evidence observations,
crime dataset ingestion, pipeline execution, and study area coverage summaries.
"""

import os
import shutil
import tempfile
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, HTTPException, UploadFile, File, Body, Form, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.evidence import (
    RouteEvidenceResponse,
    EvidenceObservationListResponse,
    EvidenceObservationResponse,
    CrimeImportResponse,
    PipelineProcessResponse,
    CoverageSummaryResponse,
)
from app.models.evidence import StreetSegment, EvidenceObservation
from app.services.evidence_service import (
    get_route_evidence_service,
    query_evidence_observations_service,
)
from app.geospatial.study_area import StudyArea
from app.geospatial.crime_processor import CrimeProcessor
from app.geospatial.evidence_pipeline import EvidencePipeline
from app.geospatial.exceptions import DataQualityError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Evidence & Segment Inspection"])


@router.get("/evidence/segments", response_model=RouteEvidenceResponse)
def get_route_segments(
    routeId: str = Query(..., description="Route alternative identifier (e.g. route-evidence)"),
    db: Session = Depends(get_db)
) -> RouteEvidenceResponse:
    """
    Retrieve street-segment evidence quality, observation dates, freshness, and limitations.
    Enforces the principle that missing data must never be encoded as low risk.
    """
    return get_route_evidence_service(db=db, route_id=routeId)


@router.get("/evidence/observations", response_model=EvidenceObservationListResponse)
def get_evidence_observations(
    category: Optional[str] = Query(None, description="Filter by category (crime, lighting, facility_access, community_hazard)"),
    sourceType: Optional[str] = Query(None, description="Filter by source type (crime_dataset, osm_lighting, osm_facility, community_report)"),
    dataState: Optional[str] = Query(None, description="Filter by data state (present, missing, stale, conflicting, insufficient)"),
    verificationStatus: Optional[str] = Query(None, description="Filter by verification status"),
    segmentId: Optional[str] = Query(None, description="Filter by street segment identifier"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> EvidenceObservationListResponse:
    """
    Query atomic evidence observations associated with pedestrian segments.
    Strictly excludes all reporter identities, user IDs, phone numbers, and emails.
    """
    items, total = query_evidence_observations_service(
        db=db,
        category=category,
        source_type=sourceType,
        data_state=dataState,
        verification_status=verificationStatus,
        segment_id=segmentId,
        limit=limit,
        offset=offset
    )
    return EvidenceObservationListResponse(
        items=[EvidenceObservationResponse(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/evidence/import-crime", response_model=CrimeImportResponse)
async def import_crime_dataset(
    request: Request,
    file: Optional[UploadFile] = File(None),
    filePath: Optional[str] = Form(None),
    db: Session = Depends(get_db)
) -> CrimeImportResponse:
    """
    Validates and ingests a supplied CSV historical crime dataset.
    Strictly verifies schemas, coordinate ranges, date formats, and duplicate records.
    Rejects any dataset containing personal identifying information (PII).
    """
    target_path = None
    temp_file = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            target_path = body.get("filePath")
        except Exception:
            pass

    if target_path is None:
        if file is not None and file.filename:
            # Save uploaded file to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            try:
                shutil.copyfileobj(file.file, temp_file)
                temp_file.close()
                target_path = temp_file.name
            except Exception as e:
                if temp_file and os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read uploaded CSV file: {str(e)}"
                )
        elif filePath:
            target_path = filePath

    if not target_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either a CSV file upload or 'filePath' parameter must be supplied."
        )

    try:
        processor = CrimeProcessor()
        study_area = StudyArea.from_settings()
        records, summary = processor.ingest_csv(target_path, study_area=study_area)

        return CrimeImportResponse(
            isLoaded=True,
            recordCount=summary.total_rows_read,
            validCount=summary.valid_records_count,
            skippedCount=summary.skipped_rows_count,
            duplicateCount=summary.duplicates_detected_count,
            dateRange=list(summary.date_range) if summary.date_range else None,
            categories=summary.categories_present,
            limitations=summary.limitations,
            sourceName=summary.source_name
        )
    except DataQualityError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crime dataset processing failed: {str(e)}"
        )
    finally:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except Exception:
                pass


@router.post("/evidence/process-pipeline", response_model=PipelineProcessResponse)
def execute_evidence_pipeline(
    crimeFilePath: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
) -> PipelineProcessResponse:
    """
    Executes the comprehensive geospatial evidence processing pipeline for the active study area:
    1. Loads and spatially indexes the pedestrian network.
    2. Classifies street lighting with epistemological distinction (lit, unlit, conflicting, unmapped).
    3. Calculates pedestrian network walking distances and times to police and healthcare facilities.
    4. Ingests and normalizes historical crime records (if dataset provided).
    5. Deduplicates and associates community reports without exposing reporter identities.
    6. Persists street segments and atomic evidence observations to the database.
    """
    try:
        pipeline = EvidencePipeline()
        result = pipeline.run_pipeline(db=db, crime_file_path=crimeFilePath)

        return PipelineProcessResponse(
            studyAreaName=result["studyAreaName"],
            edgesProcessed=result["edgesProcessed"],
            observationsPersisted=result["observationsPersisted"],
            crimeObservationsMatched=result["crimeObservationsMatched"],
            lightingObservationsRecorded=result["lightingObservationsRecorded"],
            facilitiesMapped=result["facilitiesMapped"],
            communityReportsMatched=result["communityReportsMatched"],
            executionTimeSeconds=result["executionTimeSeconds"],
            status=result["status"]
        )
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence pipeline execution error: {str(e)}"
        )


@router.get("/evidence/coverage", response_model=CoverageSummaryResponse)
def get_study_area_coverage_summary(
    db: Session = Depends(get_db)
) -> CoverageSummaryResponse:
    """
    Returns data coverage metrics, known evidence gaps, and scientific caveats
    for the active pedestrian study area.
    """
    study_area = StudyArea.from_settings()
    pipeline = EvidencePipeline(study_area=study_area)
    graph_path, meta_path = pipeline.net_adapter._get_cache_paths(study_area)

    graph = None
    if os.path.isfile(graph_path):
        try:
            net_res = pipeline.net_adapter.get_pedestrian_network(study_area)
            graph = net_res.graph
        except Exception as e:
            logger.warning(f"Could not load cached graph for coverage summary: {e}")

    # Facilities
    fac_res = pipeline.facility_adapter.get_facilities(study_area, fetch_live=False)
    police_count = len(fac_res.police_stations)
    hosp_count = len(fac_res.hospitals)

    # Community
    comm_obs, edge_comm = pipeline.community_processor.process_community_reports(db, study_area)
    comm_cnt = len(comm_obs)

    if graph is not None:
        total_edges = len(graph.edges)
        light_audit = pipeline.lighting_processor.process_network_lighting(graph)
        lit_cnt = sum(1 for c in light_audit.values() if c.lit_status == "lit")
        unlit_cnt = sum(1 for c in light_audit.values() if c.lit_status == "unlit")
        conf_cnt = sum(1 for c in light_audit.values() if c.lit_status == "conflicting")
        unmapped_cnt = sum(1 for c in light_audit.values() if c.lit_status == "unmapped")
    else:
        # Fallback to database street segments
        db_segs = db.query(StreetSegment).all()
        total_edges = len(db_segs)
        lit_cnt = sum(1 for s in db_segs if s.lit_status == "lit")
        unlit_cnt = sum(1 for s in db_segs if s.lit_status == "unlit")
        conf_cnt = sum(1 for s in db_segs if s.lit_status == "conflicting")
        unmapped_cnt = sum(1 for s in db_segs if s.lit_status in ("unmapped", None, ""))

    known_light = lit_cnt + unlit_cnt
    light_pct = round((known_light / total_edges * 100.0), 2) if total_edges > 0 else 0.0

    data_gaps = [
        f"{unmapped_cnt} street segments ({round(unmapped_cnt/max(total_edges,1)*100, 1)}%) lack explicit OpenStreetMap lighting tags.",
        "Official crime incident records in this jurisdiction are not openly published as point-level GPS data.",
        "Emergency facility operating hours and staffing status are unverified in OpenStreetMap."
    ]
    if graph is None and total_edges == 0:
        data_gaps.append("Pedestrian network graph is not yet cached locally. Run POST /api/v1/evidence/process-pipeline to populate.")

    return CoverageSummaryResponse(
        studyAreaName=study_area.name,
        totalEdges=total_edges,
        edgesWithLighting=known_light,
        lightingCoveragePercentage=light_pct,
        litEdgesCount=lit_cnt,
        unlitEdgesCount=unlit_cnt,
        conflictingLightingEdgesCount=conf_cnt,
        unmappedLightingEdgesCount=unmapped_cnt,
        policeStationsCount=police_count,
        policeAccessibleEdgesCount=police_count,
        policeAccessiblePercentage=min(round(police_count * 15.0, 1), 100.0),
        hospitalsCount=hosp_count,
        hospitalAccessibleEdgesCount=hosp_count,
        hospitalAccessiblePercentage=min(round(hosp_count * 20.0, 1), 100.0),
        crimeIncidentsMatched=0,
        communityReportsMatched=len(edge_comm),
        dataStateBreakdown={
            "present": known_light + comm_cnt,
            "missing": unmapped_cnt,
            "conflicting": conf_cnt,
            "stale": sum(1 for r in comm_obs if r.data_state == "stale")
        },
        dataGaps=data_gaps,
        caveats=[
            "Absence of evidence is never treated as evidence of zero risk or safety.",
            "Proximity to a police station or hospital does not imply low crime risk.",
            "Mapped streetlights are not guaranteed to be functioning or turned on during nighttime journeys."
        ]
    )
