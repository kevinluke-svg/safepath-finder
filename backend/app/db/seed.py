from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.evidence import EvidenceSource, StreetSegment
from app.models.report import CommunityReport
from app.models.settings import SystemSetting
from app.services.evidence_service import DEFAULT_SEGMENTS


def seed_database(db: Session) -> None:
    """Populate database with demonstration fixtures if empty."""
    # 1. System Settings
    if not db.query(SystemSetting).first():
        setting = SystemSetting(
            freshness_threshold_days=30,
            outdated_threshold_days=90,
            auto_flag_keywords="harassment, assault, dark, broken, hazard",
            require_moderator_approval=True,
            evidence_weight_lighting=50,
            evidence_weight_activity=30,
            time_weight=20
        )
        db.add(setting)

    # 2. Evidence Sources
    if db.query(EvidenceSource).count() == 0:
        sources = [
            EvidenceSource(
                id="src-bbmp-lighting",
                name="Bruhat Bengaluru Mahanagara Palike (BBMP) Streetlight Registry",
                type="Municipal Registry",
                coverage="Ward 143 / South End (Pilot Corridor)",
                refresh_frequency="Weekly scheduled sync",
                last_ingested=datetime.now(timezone.utc) - timedelta(days=6),
                records_count=1420,
                status="active",
                stale_warning=False,
                notes="Contains physical lamp asset IDs, wattage, and feeder pillar operational status."
            ),
            EvidenceSource(
                id="src-osm-pedestrian",
                name="OpenStreetMap Pedestrian Way Network",
                type="Spatial Vector Extract",
                coverage="Bengaluru South Division",
                refresh_frequency="Daily automated extract",
                last_ingested=datetime.now(timezone.utc) - timedelta(days=1),
                records_count=8540,
                status="active",
                stale_warning=False,
                notes="Provides road classification, footway tags, surface type, and kerb ramp presence."
            ),
            EvidenceSource(
                id="src-safepath-community",
                name="SafePath Community Environmental Observations",
                type="Crowdsourced Queue",
                coverage="Pilot Corridor Walkers",
                refresh_frequency="Continuous queue",
                last_ingested=datetime.now(timezone.utc) - timedelta(hours=2),
                records_count=312,
                status="active",
                stale_warning=False,
                notes="Citizen-submitted reports subject to four-state moderation."
            ),
            EvidenceSource(
                id="src-bcp-help-kiosks",
                name="Bengaluru City Police Kiosk & Help Post Directory",
                type="Civic Safety Facility",
                coverage="South End & Lalbagh Zones",
                refresh_frequency="Quarterly manual update",
                last_ingested=datetime.now(timezone.utc) - timedelta(days=74),
                records_count=28,
                status="stale",
                stale_warning=True,
                notes="WARNING: Ingestion is >70 days old. Operational staffing hours must be re-verified before reliance."
            )
        ]
        db.add_all(sources)

    # 3. Street Segments
    if db.query(StreetSegment).count() == 0:
        for route_id, segs in DEFAULT_SEGMENTS.items():
            for s in segs:
                segment = StreetSegment(
                    id=s["id"],
                    route_id=route_id,
                    street_name=s["streetName"],
                    source=s["source"],
                    observed_at=s["observedAt"],
                    coverage=s["coverage"],
                    freshness=s["freshness"],
                    state=s["state"],
                    risk_estimate=s.get("riskEstimate"),
                    limitations=s.get("limitations", []),
                    attributes=s.get("attributes", {}),
                    timeline=s.get("timeline", []),
                    geometry=s.get("geometry", [])
                )
                db.add(segment)

    # 4. Community Reports
    if db.query(CommunityReport).count() == 0:
        reports = [
            CommunityReport(
                id="rep-101",
                category="broken_lighting",
                category_label="Broken street lighting",
                location="10th Main Road near 28th Cross, Jayanagar",
                description="Streetlight pole #J4-108 has been flickering intermittently since heavy rain on Thursday.",
                status="pending",
                reporter_name="Citizen Reporter",
                provenance="Demonstration citizen observation",
                corroborations=2,
                created_at=datetime.now(timezone.utc) - timedelta(days=2)
            ),
            CommunityReport(
                id="rep-102",
                category="poor_visibility",
                category_label="Poor visibility / blind curve",
                location="Lalbagh West Gate approach near nursery lane",
                description="Overgrown banyan branches completely block illumination from two overhead streetlamps, creating a 40-meter dark shadow.",
                status="flagged",
                reporter_name="Commuter Observer",
                provenance="Demonstration commuter submission",
                corroborations=1,
                moderator_notes="Flagged for BBMP horticulture branch trim verification.",
                created_at=datetime.now(timezone.utc) - timedelta(hours=16)
            ),
            CommunityReport(
                id="rep-103",
                category="blocked_footpath",
                category_label="Blocked footpath",
                location="South End Circle, approach to Metro Pillar #42",
                description="Construction sand and granite slabs deposited completely across the pedestrian walkway, forcing pedestrians into the roadway.",
                status="approved",
                reporter_name="Verified Pedestrian",
                provenance="Corroborated by on-site field verification",
                corroborations=4,
                moderator_notes="Confirmed on-site. Municipal notice served to contractor.",
                created_at=datetime.now(timezone.utc) - timedelta(days=2)
            ),
            CommunityReport(
                id="rep-104",
                category="access_facility",
                category_label="Access or public transit facility",
                location="Ashoka Pillar public auto stand",
                description="Prepaid auto booth and well-lit bus shelter operational until 23:00. Reliable bystander activity.",
                status="approved",
                reporter_name="Transit Monitor",
                provenance="Corroborated municipal facility record",
                corroborations=5,
                moderator_notes="Operational timings verified with Bengaluru Traffic Police kiosk.",
                created_at=datetime.now(timezone.utc) - timedelta(days=3)
            )
        ]
        db.add_all(reports)

    db.commit()
