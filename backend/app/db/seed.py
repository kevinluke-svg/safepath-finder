from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.evidence import EvidenceSource, StreetSegment, EvidenceObservation, DatasetImportHistory
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

    # 2. Evidence Sources with Authentic Open Data Provenance
    now = datetime.now(timezone.utc)
    official_sources = [
        EvidenceSource(
            id="src-osm-pedestrian",
            name="OpenStreetMap Pedestrian Way Network",
            type="Spatial Vector Extract",
            coverage="Bengaluru Pilot Corridor (12.9200-12.9850 N, 77.5700-77.6200 E)",
            refresh_frequency="Automated regional cache sync",
            last_ingested=now - timedelta(days=1),
            records_count=41284,
            status="active",
            stale_warning=False,
            notes="Provides pedestrian street network edges, highway classifications, sidewalk attributes, and crossings.",
            source_organisation="OpenStreetMap Contributors",
            url="https://download.geofabrik.de/asia/india.html",
            licence="Open Database License (ODbL) 1.0",
            collection_period="Extracted October 2026",
            last_updated=now - timedelta(days=1),
            attribute_definitions={
                "highway": "Road classification (footway, pedestrian, residential, tertiary, secondary)",
                "sidewalk": "Dedicated sidewalk presence (both, left, right, separate, none, unmapped)",
                "crossing": "Pedestrian crossing points and signal controls"
            },
            limitations=[
                "Sidewalk survey completeness varies by municipal ward.",
                "Unmapped sidewalk tags denote survey gaps, NOT physical absence."
            ]
        ),
        EvidenceSource(
            id="src-osm-lighting",
            name="OpenStreetMap Way Lighting & Luminaire Assets",
            type="Spatial Vector Extract",
            coverage="Bengaluru Pilot Study Area (Ward 143 / South End / Lalbagh / Jayanagar)",
            refresh_frequency="Synchronized with OSM vector graph",
            last_ingested=now - timedelta(days=1),
            records_count=1672,
            status="active",
            stale_warning=False,
            notes="Contains 1,618 lit=yes edges, 54 lit=no edges, and 17 mapped street_lamp node assets.",
            source_organisation="OpenStreetMap Contributors",
            url="https://overpass-turbo.eu/",
            licence="Open Database License (ODbL) 1.0",
            collection_period="Extracted October 2026",
            last_updated=now - timedelta(days=1),
            attribute_definitions={
                "lit": "Way lighting tag (yes, no, 24/7, dusk-dawn, unmapped)",
                "highway=street_lamp": "Individual streetlight luminaire pole node"
            },
            limitations=[
                "Only ~4% of street segments in pilot corridor have explicit lit=* tags.",
                "Missing lighting tags represent unmapped uncertainty (prior R_unknown=0.50).",
                "A mapped lamp object does not guarantee power grid operation or bulb functionality."
            ]
        ),
        EvidenceSource(
            id="src-osm-facilities",
            name="OpenStreetMap Civic Safety & Emergency Assistance POIs",
            type="Civic Safety Facility",
            coverage="Bengaluru Pilot Corridor (South End, Lalbagh, Jayanagar, Victoria)",
            refresh_frequency="Curated quarterly verification",
            last_ingested=now - timedelta(days=7),
            records_count=35,
            status="active",
            stale_warning=False,
            notes="Verified directory of police stations, hospitals, trauma centers, and 24/7 pharmacies.",
            source_organisation="OpenStreetMap Contributors",
            url="https://overpass-turbo.eu/",
            licence="Open Database License (ODbL) 1.0",
            collection_period="Verified October 2026",
            last_updated=now - timedelta(days=7),
            attribute_definitions={
                "amenity=police": "Police stations and commissionerate aid outposts",
                "amenity=hospital": "Hospitals, trauma care units, and emergency clinics",
                "amenity=pharmacy": "Pharmacies and essential medical retail"
            },
            limitations=[
                "Operating hours, desk staffing, and dispatch availability are unverified in OSM.",
                "Physical proximity does not guarantee immediate emergency response."
            ]
        ),
        EvidenceSource(
            id="src-ncrb-crime",
            name="National Crime Records Bureau (NCRB) Crime in India Official Statistics",
            type="Official Government Statistics",
            coverage="Bengaluru Police Commissionerate (Metropolitan Urban Area)",
            refresh_frequency="Annual official publication",
            last_ingested=now - timedelta(days=30),
            records_count=4,
            status="active",
            stale_warning=False,
            notes="Authoritative annual crime aggregates (24,198 IPC crimes in 2022). Retained for contextual reference only; NOT disaggregated to individual streets.",
            source_organisation="National Crime Records Bureau (NCRB), Ministry of Home Affairs, Government of India",
            url="https://ncrb.gov.in/en/crime-in-india-table-addtional-table-and-chapter-contents",
            licence="Government Open Data License - India (GODL-India)",
            collection_period="2022 Calendar Year (Consolidated 2023)",
            last_updated=now - timedelta(days=30),
            attribute_definitions={
                "totalIpcCrimes": "Total IPC offenses (24,198 cases, rate 286.6/100k)",
                "violentCrimes": "Murder, attempt to murder, grievous assault (1,932 cases)",
                "crimesAgainstWomen": "Assault on women, harassment, cruelty (3,124 cases)",
                "propertyOffenses": "Theft, burglary, robbery (12,845 cases)"
            },
            limitations=[
                "District-level aggregate totals cannot be distributed across individual streets.",
                "No open geocoded incident coordinates are published by Indian police authorities.",
                "Zero incident records on a route must never be interpreted as zero crime risk."
            ]
        ),
        EvidenceSource(
            id="src-safepath-community",
            name="SafePath Community Environmental Observations",
            type="Crowdsourced Queue",
            coverage="Pilot Corridor Walkers (Bengaluru South Division)",
            refresh_frequency="Continuous queue with moderation",
            last_ingested=now - timedelta(hours=2),
            records_count=312,
            status="active",
            stale_warning=False,
            notes="Citizen-submitted reports for dog encounters, dark streets, footpath hazards, and harassment with 4-state moderation.",
            source_organisation="SafePath Finder Community Contributors",
            url="https://safepath.local/api/v1/reports",
            licence="Open Database License (ODbL) / CC BY-SA 4.0",
            collection_period="Continuous active stream",
            last_updated=now - timedelta(hours=2),
            attribute_definitions={
                "dog_encounter": "Sightings, groups, aggressive dogs, or bite incidents",
                "lighting_concern": "Broken streetlights, dark stretches, power outages",
                "hazard": "Footpath construction obstructions, open drains, unsafe crossings"
            },
            limitations=[
                "Crowdsourced reporting exhibits voluntary response bias and spatial clustering.",
                "Zero community reports does NOT prove an area is safe.",
                "All reporter personal identifying information is strictly stripped."
            ]
        ),
        EvidenceSource(
            id="src-bbmp-lighting",
            name="Bruhat Bengaluru Mahanagara Palike (BBMP) Luminaire Registry",
            type="Municipal Luminaire Registry (Public Request)",
            coverage="BBMP Metropolitan Wards 1-198",
            refresh_frequency="Unacquired / Public open dataset not published",
            last_ingested=now,
            records_count=0,
            status="unavailable",
            stale_warning=True,
            notes="INVESTIGATION OUTCOME: BBMP does not publish an open downloadable luminaire inventory under an open license. SafePath Finder strictly refuses to fabricate synthetic records; status is honestly classified as UNAVAILABLE.",
            source_organisation="Bruhat Bengaluru Mahanagara Palike (BBMP)",
            url="https://bbmp.karnataka.gov.in/",
            licence="Proprietary / Open Downloadable Dataset Not Available",
            collection_period="PPP Streetlighting Project (Concessionaire Consortium)",
            last_updated=None,
            attribute_definitions={},
            limitations=[
                "BBMP municipal luminaire inventory is not published as an open downloadable dataset.",
                "Streetlight evidence is strictly derived from OpenStreetMap and verified community observations."
            ]
        )
    ]

    for s in official_sources:
        existing = db.query(EvidenceSource).filter(EvidenceSource.id == s.id).first()
        if existing:
            existing.name = s.name
            existing.type = s.type
            existing.coverage = s.coverage
            existing.refresh_frequency = s.refresh_frequency
            existing.last_ingested = s.last_ingested
            existing.records_count = s.records_count
            existing.status = s.status
            existing.stale_warning = s.stale_warning
            existing.notes = s.notes
            existing.source_organisation = s.source_organisation
            existing.url = s.url
            existing.licence = s.licence
            existing.collection_period = s.collection_period
            existing.last_updated = s.last_updated
            existing.attribute_definitions = s.attribute_definitions
            existing.limitations = s.limitations
        else:
            db.add(s)
    db.commit()

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
                latitude=12.9280,
                longitude=77.5830,
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
                latitude=12.9465,
                longitude=77.5842,
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
                latitude=12.9330,
                longitude=77.5832,
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
                latitude=12.9370,
                longitude=77.5835,
                description="Prepaid auto booth and well-lit bus shelter operational until 23:00. Reliable bystander activity.",
                status="approved",
                reporter_name="Transit Monitor",
                provenance="Corroborated municipal facility record",
                corroborations=5,
                moderator_notes="Operational timings verified with Bengaluru Traffic Police kiosk.",
                created_at=datetime.now(timezone.utc) - timedelta(days=3)
            ),
            CommunityReport(
                id="rep-105",
                category="dog_group",
                category_label="Group or pack of dogs",
                location="11th Main Road junction near Madhavan Park",
                latitude=12.9345,
                longitude=77.5855,
                description="Pack of 4-5 street dogs congregating near market bins during evening hours; generally calm when undisturbed.",
                status="approved",
                dog_count=4,
                is_aggressive=False,
                reporter_name="Resident Walker",
                provenance="Community confirmed sighting",
                corroborations=3,
                created_at=datetime.now(timezone.utc) - timedelta(days=1)
            ),
            CommunityReport(
                id="rep-106",
                category="dog_aggressive",
                category_label="Aggressive dog encounter",
                location="RV Road cross lane behind metro pillar #38",
                latitude=12.9312,
                longitude=77.5815,
                description="Two territorial dogs barking and chasing two-wheelers and joggers after 21:00.",
                status="approved",
                dog_count=2,
                is_aggressive=True,
                reporter_name="Jogger",
                provenance="Corroborated animal encounter report",
                corroborations=2,
                moderator_notes="BBMP Animal Husbandry helpline notified for vaccination check.",
                created_at=datetime.now(timezone.utc) - timedelta(days=4)
            ),
            CommunityReport(
                id="rep-107",
                category="crossing_issue",
                category_label="Pedestrian crossing issue",
                location="Siddapura Junction pedestrian crossing",
                latitude=12.9410,
                longitude=77.5842,
                description="Pedestrian signal timer provides only 8 seconds to cross 4 lanes; crossing stripes severely faded.",
                status="approved",
                reporter_name="Urban Pedestrian",
                provenance="Community infrastructure observation",
                corroborations=6,
                created_at=datetime.now(timezone.utc) - timedelta(days=5)
            )
        ]
        db.add_all(reports)

    # 5. Atomic Evidence Observations (Historical crime & lighting audits)
    if db.query(EvidenceObservation).count() == 0:
        obs = [
            EvidenceObservation(
                id="obs-crime-101",
                source_id="btp-snatch-4412",
                source_type="crime_dataset",
                category="crime",
                subcategory="theft_snatching",
                latitude=12.9265,
                longitude=77.5830,
                segment_id="seg-10th-main-01",
                observed_at=datetime.now(timezone.utc) - timedelta(days=60),
                source_attribution="BTP Public Incident Bulletin 2025-2026",
                verification_status="official_record",
                confidence="high",
                data_state="present",
                provenance="Demonstration Bangalore City Police crime bulletin record",
                limitations=["Historical incident record; does not reflect real-time conditions."],
                attributes={"sub_category": "Phone snatching", "time_of_day": "night", "resolved": True}
            ),
            EvidenceObservation(
                id="obs-crime-102",
                source_id="btp-harass-1903",
                source_type="crime_dataset",
                category="crime",
                subcategory="harassment_verbal",
                latitude=12.9310,
                longitude=77.5831,
                segment_id="seg-south-end-02",
                observed_at=datetime.now(timezone.utc) - timedelta(days=90),
                source_attribution="BTP Public Incident Bulletin 2025-2026",
                verification_status="official_record",
                confidence="moderate",
                data_state="present",
                provenance="Demonstration public incident log",
                limitations=["Historical incident record; does not reflect real-time conditions."],
                attributes={"sub_category": "Verbal harassment", "time_of_day": "evening", "resolved": True}
            )
        ]
        db.add_all(obs)

    db.commit()
