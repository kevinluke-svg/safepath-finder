/**
 * SafePath Finder - API Service & Data Layer
 * Compatible with SafePath backend contract (/api/v1).
 * Supports both Live API Mode and Local Demo / Fixture Mode with clear service boundaries.
 */

(function (window) {
  'use strict';

  // Storage Keys
  const STORAGE_KEYS = {
    SESSION: 'safepath_session',
    PREFERENCES: 'safepath_preferences',
    SAVED_PLANS: 'safepath_saved_plans',
    JOURNEY_HISTORY: 'safepath_journey_history',
    SAVED_PLACES: 'safepath_saved_places',
    COMMUNITY_REPORTS: 'safepath_community_reports',
    REPORT_MODERATION: 'safepath_report_moderation', // id -> { status, reason, reviewedAt, reviewer }
    TRUSTED_CONTACTS: 'safepath_trusted_contacts',
    ADMIN_USERS: 'safepath_admin_users',
    AUDIT_LOG: 'safepath_audit_log',
    SYSTEM_SETTINGS: 'safepath_system_settings',
    FEEDBACK: 'safepath_feedback',
    API_CONFIG: 'safepath_api_config'
  };


  // Safe localStorage helper
  const storage = {
    get(key, fallback) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : fallback;
      } catch (e) {
        console.warn('Storage read failed:', key, e);
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (e) {
        console.warn('Storage write failed:', key, e);
        return false;
      }
    },
    remove(key) {
      try {
        localStorage.removeItem(key);
      } catch (e) {}
    }
  };

  // Realistic sample Bengaluru coordinates and street segments
  const SAMPLE_ROUTES = {
    'route-evidence': {
      id: 'route-evidence',
      name: 'Evidence-led Route',
      category: 'evidence_led',
      distanceMeters: 1850,
      durationSeconds: 1440, // 24 mins @ 4.6 km/h
      characteristics: ['Primary commercial road', 'Continuous pedestrian footpaths', 'Municipal LED lighting records'],
      evidenceSummary: {
        coverage: 'adequate',
        coveragePercentage: 78,
        freshestObservationDays: 8,
        freshnessState: 'fresh',
        riskEstimate: 'Moderate environmental context'
      },
      explanation: 'Prioritizes street segments with corroborated lighting observations and active commercial frontages. Geometry follows 10th Main Road and South End Road. Evidence availability is moderate to high, though gaps remain in alleyway connections.',
      tradeoffs: 'Adds ~5 minutes (350 meters) compared to the direct route to keep to streets with documented lighting assets and daytime commercial activity.',
      geometry: [
        [12.9257, 77.5833], // Jayanagar 4th Block
        [12.9290, 77.5831], // 10th Main Road
        [12.9330, 77.5832], // South End Circle
        [12.9370, 77.5835], // Ashoka Pillar
        [12.9410, 77.5842], // Siddapura Junction
        [12.9450, 77.5846], // Lalbagh South Gate approach
        [12.9501, 77.5847]  // Lalbagh West Gate
      ],
      segments: [
        {
          id: 'seg-101',
          streetName: '10th Main Road (4th Block to 3rd Block)',
          coordinates: [[12.9257, 77.5833], [12.9290, 77.5831]],
          source: 'BBMP Municipal Streetlight Survey 2026',
          observedAt: '2026-10-18T18:30:00Z',
          lastUpdated: '2026-10-19T09:15:00Z',
          coverage: 'adequate',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'available',
          missingInfo: ['Late-night vendor activity levels', 'CCTV coverage status'],
          conflictingObservations: [],
          riskEstimate: { level: 'Moderate', caveat: 'Documented lighting exists. Lack of incident records does not imply risk-free.' },
          plainExplanation: 'Well-documented corridor with municipal street lamp asset IDs verified within the last 10 days. Pedestrian walkway is elevated and separated from vehicular lanes.',
          limitations: 'Data reflects physical lighting presence; bulb lumen output and power fluctuations are unmonitored in real-time.',
          timeline: [
            { date: '2026-10-18', actor: 'Municipal Audit', note: 'Pole #J4-102 inspected; LED luminaire functional.', status: 'approved' },
            { date: '2026-09-02', actor: 'Community Reporter', note: 'Footpath clear of construction debris.', status: 'approved' }
          ]
        },
        {
          id: 'seg-102',
          streetName: 'South End Road & Circle',
          coordinates: [[12.9290, 77.5831], [12.9330, 77.5832]],
          source: 'Bengaluru Pedestrian Infrastructure Audit + Community Corroboration',
          observedAt: '2026-10-10T12:00:00Z',
          lastUpdated: '2026-10-12T14:20:00Z',
          coverage: 'adequate',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'available',
          missingInfo: ['Rainy season sidewalk ponding depth'],
          conflictingObservations: [
            '2026-09-28: Report #48 noted tree branch obscuring pole lamp near bus shelter; pruned 2026-10-05.'
          ],
          riskEstimate: { level: 'Moderate', caveat: 'High vehicular traffic; crossing aids present.' },
          plainExplanation: 'Active junction with high natural surveillance during transit hours. Signalized pedestrian crossing available.',
          limitations: 'Noise levels and heavy traffic may make audio awareness challenging.',
          timeline: [
            { date: '2026-10-10', actor: 'City Transit Observer', note: 'Traffic signal timings include 25s pedestrian phase.', status: 'approved' },
            { date: '2026-09-28', actor: 'Community Member', note: 'Tree branch trimmed away from streetlight.', status: 'approved' }
          ]
        },
        {
          id: 'seg-103',
          streetName: 'Ashoka Pillar Road Corridor',
          coordinates: [[12.9330, 77.5832], [12.9370, 77.5835], [12.9410, 77.5842]],
          source: 'SafePath Community Observations (Corroborated)',
          observedAt: '2026-10-01T20:15:00Z',
          lastUpdated: '2026-10-03T11:00:00Z',
          coverage: 'adequate',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'available',
          missingInfo: ['Police booth staffing schedule'],
          conflictingObservations: [],
          riskEstimate: { level: 'Moderate', caveat: 'Wide open promenade; shops close around 21:30.' },
          plainExplanation: 'Tree-lined boulevard with continuous lighting and occasional evening walkers. Police outpost located at north junction.',
          limitations: 'After 22:00, pedestrian density drops sharply once storefront shutters close.',
          timeline: [
            { date: '2026-10-01', actor: 'Community Reporter', note: 'Public lights illuminated at sunset; sidewalk clear.', status: 'approved' }
          ]
        },
        {
          id: 'seg-104',
          streetName: 'Lalbagh West Gate Approach Lane',
          coordinates: [[12.9410, 77.5842], [12.9450, 77.5846], [12.9501, 77.5847]],
          source: 'Volunteer Walk Audit & Municipal Records',
          observedAt: '2026-09-20T19:00:00Z',
          lastUpdated: '2026-09-22T08:30:00Z',
          coverage: 'limited',
          freshness: 'stale',
          verificationStatus: 'approved',
          state: 'limited',
          missingInfo: ['Boundary wall lighting consistency', 'Gate closing guard schedule'],
          conflictingObservations: [
            'Conflicting reports: Report #82 noted dark stretch near nursery gate, while Report #91 noted working perimeter floodlight.'
          ],
          riskEstimate: { level: 'Uncertain', caveat: 'Park perimeter has fewer commercial eye-on-the-street sources.' },
          plainExplanation: 'Moderate lighting along botanical perimeter wall. Low commercial density means fewer bystander eyes after botanical garden closing hours.',
          limitations: 'Survey is over 35 days old. Condition changes may have occurred.',
          timeline: [
            { date: '2026-09-20', actor: 'Local Resident', note: 'Perimeter floodlight operational on weekdays.', status: 'approved' },
            { date: '2026-08-11', actor: 'Volunteer Survey', note: 'Walkway uneven near botanical entry gate.', status: 'approved' }
          ]
        }
      ]
    },
    'route-shortest': {
      id: 'route-shortest',
      name: 'Shortest Sample Route',
      category: 'shortest',
      distanceMeters: 1510,
      durationSeconds: 1140, // 19 mins
      characteristics: ['Direct residential cut-through', 'Narrow secondary lanes', 'Sparse public observations'],
      evidenceSummary: {
        coverage: 'insufficient',
        coveragePercentage: 35,
        freshestObservationDays: 48,
        freshnessState: 'stale',
        riskEstimate: 'High uncertainty due to evidence gaps'
      },
      explanation: 'Direct straight-line geometry through residential cross streets. While saving ~5 minutes of walking time, over 65% of this path lacks verified street lighting or sidewalk audit records.',
      tradeoffs: 'Saves 340 meters and 5 minutes, but traverses 3 residential cross-streets with zero verified lighting data and unconfirmed sidewalk continuity.',
      geometry: [
        [12.9257, 77.5833],
        [12.9282, 77.5806],
        [12.9330, 77.5803],
        [12.9372, 77.5811],
        [12.9425, 77.5821],
        [12.9466, 77.5834],
        [12.9501, 77.5847]
      ],
      segments: [
        {
          id: 'seg-201',
          streetName: '3rd Cross Residential Cut-Through',
          coordinates: [[12.9257, 77.5833], [12.9282, 77.5806], [12.9330, 77.5803]],
          source: 'Public OpenStreetMap Geometry only (No lighting attributes)',
          observedAt: '2026-06-12T10:00:00Z',
          lastUpdated: '2026-06-12T10:00:00Z',
          coverage: 'insufficient',
          freshness: 'outdated',
          verificationStatus: 'unverified',
          state: 'insufficient',
          missingInfo: ['Street lighting presence', 'Sidewalk accessibility', 'Gated community night access rules', 'Stray animal presence'],
          conflictingObservations: [],
          riskEstimate: { level: 'Unknown', caveat: 'No environmental observations exist. Missing data MUST NOT be assumed safe.' },
          plainExplanation: 'Quiet residential street with single-family compounds and high boundary walls. No municipal lighting audit records have been ingested for this sub-lane.',
          limitations: 'Completely unmapped for pedestrian environmental quality. Gates may be locked after 22:00.',
          timeline: [
            { date: '2026-06-12', actor: 'OSM Contributor', note: 'Street geometry imported without attributes.', status: 'pending' }
          ]
        },
        {
          id: 'seg-202',
          streetName: 'Byrasandra Lane Link',
          coordinates: [[12.9330, 77.5803], [12.9372, 77.5811], [12.9425, 77.5821]],
          source: 'Community Report #12 (Unmoderated)',
          observedAt: '2026-09-08T21:40:00Z',
          lastUpdated: '2026-09-08T21:40:00Z',
          coverage: 'limited',
          freshness: 'stale',
          verificationStatus: 'pending',
          state: 'limited',
          missingInfo: ['Corroboration by independent observers', 'Sidewalk width measurements'],
          conflictingObservations: ['Report mentions construction materials blocking walking path on western shoulder.'],
          riskEstimate: { level: 'Uncertain', caveat: 'Single uncorroborated report from 49 days ago.' },
          plainExplanation: 'Narrow connector road with mixed residential and small auto repair workshops. Single community submission reported poor visibility past 20:00.',
          limitations: 'Single anonymous report; not yet reviewed by moderators or corroborated by municipal data.',
          timeline: [
            { date: '2026-09-08', actor: 'Anonymous Reporter', note: 'Streetlamp near curve dark; road dug up for pipeline.', status: 'pending' }
          ]
        },
        {
          id: 'seg-203',
          streetName: 'Lalbagh Siddapura West Approach',
          coordinates: [[12.9425, 77.5821], [12.9466, 77.5834], [12.9501, 77.5847]],
          source: 'BBMP Ward Baseline 2025',
          observedAt: '2025-11-20T10:00:00Z',
          lastUpdated: '2025-11-20T10:00:00Z',
          coverage: 'insufficient',
          freshness: 'outdated',
          verificationStatus: 'unverified',
          state: 'outdated',
          missingInfo: ['Current infrastructure status (>300 days old)', 'Pedestrian crossing visibility'],
          conflictingObservations: [],
          riskEstimate: { level: 'Unknown', caveat: 'Data is severely outdated. Reality on the ground may have changed significantly.' },
          plainExplanation: 'Legacy data point from last year indicates public streetlamp fixtures, but no recent inspections or community reports have confirmed functioning.',
          limitations: 'Data exceeds the 90-day validity window and is flagged as outdated.',
          timeline: [
            { date: '2025-11-20', actor: 'Ward Engineer', note: 'Sodium vapor lamp recorded in 2025 registry.', status: 'unverified' }
          ]
        }
      ]
    },
    'route-balanced': {
      id: 'route-balanced',
      name: 'Balanced Sample Route',
      category: 'balanced',
      distanceMeters: 1720,
      durationSeconds: 1320, // 22 mins
      characteristics: ['Mixed commercial & residential', 'Secondary avenue', 'Partial lighting coverage'],
      evidenceSummary: {
        coverage: 'limited',
        coveragePercentage: 62,
        freshestObservationDays: 14,
        freshnessState: 'fresh',
        riskEstimate: 'Moderate coverage balance'
      },
      explanation: 'A balanced compromise following 11th Main and Kanakapura Link. Combines moderate documentation with reasonable walking distance, avoiding both the longest detour and unverified alleyways.',
      tradeoffs: 'Only 2 minutes longer than the shortest path; provides verified lighting data along the initial 60% of the journey, with moderate gaps near the terminus.',
      geometry: [
        [12.9257, 77.5833],
        [12.9269, 77.5871],
        [12.9316, 77.5878],
        [12.9367, 77.5871],
        [12.9415, 77.5867],
        [12.9465, 77.5853],
        [12.9501, 77.5847]
      ],
      segments: [
        {
          id: 'seg-301',
          streetName: '11th Main Market Corridor',
          coordinates: [[12.9257, 77.5833], [12.9269, 77.5871], [12.9316, 77.5878]],
          source: 'BBMP Commercial Audit & Merchant Association',
          observedAt: '2026-10-13T16:00:00Z',
          lastUpdated: '2026-10-14T09:30:00Z',
          coverage: 'adequate',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'available',
          missingInfo: ['Sunday closure activity levels'],
          conflictingObservations: [],
          riskEstimate: { level: 'Moderate', caveat: 'High activity until 21:00; quieter thereafter.' },
          plainExplanation: 'Active shopping street with pharmacy, grocery stores, and good ambient storefront lighting. Clear sidewalk with occasional bike parking encroachments.',
          limitations: 'Crowded footpaths during peak evening hours (18:00 - 20:30).',
          timeline: [
            { date: '2026-10-13', actor: 'Merchant Association', note: 'Shop canopy lights remain on until 22:30.', status: 'approved' }
          ]
        },
        {
          id: 'seg-302',
          streetName: 'Kanakapura Link Avenue',
          coordinates: [[12.9316, 77.5878], [12.9367, 77.5871], [12.9415, 77.5867]],
          source: 'Community Volunteer Audit',
          observedAt: '2026-09-30T20:00:00Z',
          lastUpdated: '2026-10-02T10:00:00Z',
          coverage: 'limited',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'limited',
          missingInfo: ['Pedestrian crossing markings at mid-block'],
          conflictingObservations: ['Report #64 noted 2 flickering light poles opposite community hall.'],
          riskEstimate: { level: 'Moderate', caveat: 'Mixed residential; occasional low-visibility tree shadows.' },
          plainExplanation: 'Medium-width avenue with alternating streetlight spacing. Sidewalk exists on the eastern side only.',
          limitations: 'Walkers must cross to the east side for continuous sidewalk.',
          timeline: [
            { date: '2026-09-30', actor: 'Volunteer Auditor', note: 'Eastern sidewalk intact; western side unpaved.', status: 'approved' }
          ]
        },
        {
          id: 'seg-303',
          streetName: 'Lalbagh East Boundary Connection',
          coordinates: [[12.9415, 77.5867], [12.9465, 77.5853], [12.9501, 77.5847]],
          source: 'Community Observations & OpenData BBMP',
          observedAt: '2026-10-05T19:30:00Z',
          lastUpdated: '2026-10-06T11:00:00Z',
          coverage: 'limited',
          freshness: 'fresh',
          verificationStatus: 'approved',
          state: 'limited',
          missingInfo: ['Police patrol frequency'],
          conflictingObservations: [],
          riskEstimate: { level: 'Moderate', caveat: 'Perimeter wall limits escape routes or open doorways.' },
          plainExplanation: 'Connects directly to park entrance with moderate illumination. Limited commercial frontage.',
          limitations: 'Continuous high boundary wall on left side of travel direction.',
          timeline: [
            { date: '2026-10-05', actor: 'Community Reporter', note: 'Streetlamps operational, good visibility along path.', status: 'approved' }
          ]
        }
      ]
    }
  };

  // Initial seed reports
  const SEED_REPORTS = [
    {
      id: 'rep-001',
      category: 'broken_lighting',
      categoryLabel: 'Broken street lighting',
      location: '10th Main Road near 28th Cross, Jayanagar',
      description: 'Streetlight pole #J4-108 has been flickering intermittently since heavy rain on Thursday.',
      createdAt: '2026-10-24T18:45:00Z',
      status: 'pending',
      provenance: 'Community mobile web submission',
      corroborations: 2,
      reporterId: 'usr-demo-travel',
      moderatorNotes: ''
    },
    {
      id: 'rep-002',
      category: 'blocked_footpath',
      categoryLabel: 'Blocked footpath',
      location: 'South End Circle, approach to Metro Pillar #42',
      description: 'Construction sand and granite slabs deposited completely across the pedestrian walkway, forcing pedestrians into the roadway.',
      createdAt: '2026-10-25T08:15:00Z',
      status: 'approved',
      provenance: 'Pedestrian Safety Volunteer audit',
      corroborations: 4,
      reporterId: 'usr-vol-44',
      moderatorNotes: 'Corroborated by photo verification. Passed to municipal ward engineer.'
    },
    {
      id: 'rep-003',
      category: 'poor_visibility',
      categoryLabel: 'Poor visibility / blind curve',
      location: 'Lalbagh West Gate approach near nursery lane',
      description: 'Overgrown banyan branches completely block the illumination from two overhead streetlamps, creating a 40-meter dark shadow.',
      createdAt: '2026-10-26T21:10:00Z',
      status: 'flagged',
      provenance: 'Community mobile web submission',
      corroborations: 1,
      reporterId: 'usr-anon-88',
      moderatorNotes: 'Flagged for on-site inspection. Needs verification whether branches are on private or municipal property.'
    },
    {
      id: 'rep-004',
      category: 'access_facility',
      categoryLabel: 'Access / Public facility',
      location: 'Ashoka Pillar public auto stand',
      description: 'Prepaid auto booth and well-lit bus shelter operational until 23:00. Reliable bystander activity.',
      createdAt: '2026-10-23T14:20:00Z',
      status: 'approved',
      provenance: 'Transit observer verification',
      corroborations: 5,
      reporterId: 'usr-transit-01',
      moderatorNotes: 'Verified against Bangalore Traffic Police official prepaid booth directory.'
    }
  ];

  // Seed data sources for Admin Data Quality Monitoring
  const SEED_DATA_SOURCES = [
    {
      id: 'src-bbmp-lights',
      name: 'Bruhat Bengaluru Mahanagara Palike (BBMP) Streetlight Registry',
      type: 'Municipal GIS GeoJSON',
      coverage: 'South Bengaluru (Ward 151 - 160)',
      lastIngested: '2026-10-22T04:00:00Z',
      refreshFrequency: 'Weekly scheduled sync',
      status: 'active',
      recordsCount: 4280,
      staleWarning: false,
      notes: 'Authoritative municipal asset IDs and lamp wattage ratings. Does not report real-time power outages.'
    },
    {
      id: 'src-osm-pedestrian',
      name: 'OpenStreetMap Pedestrian Way Network',
      type: 'Open Data Extract',
      coverage: 'Greater Bengaluru Urban',
      lastIngested: '2026-10-26T00:00:00Z',
      refreshFrequency: 'Daily automated extract',
      status: 'active',
      recordsCount: 31200,
      staleWarning: false,
      notes: 'Pedestrian tags (sidewalk=both/left/right, surface, lit=yes/no). Attribute completeness is variable.'
    },
    {
      id: 'src-community-obs',
      name: 'SafePath Community Environmental Observations',
      type: 'User Submitted & Moderated',
      coverage: 'Local pilot corridors',
      lastIngested: '2026-10-27T11:30:00Z',
      refreshFrequency: 'Continuous queue',
      status: 'active',
      recordsCount: 142,
      staleWarning: false,
      notes: 'Reviewed against 4-state moderation pipeline (pending, approved, rejected, flagged).'
    },
    {
      id: 'src-city-police-booths',
      name: 'Bengaluru City Police Kiosk & Help Post Directory',
      type: 'Public Safety Registry',
      coverage: 'Bengaluru South Division',
      lastIngested: '2026-08-15T09:00:00Z',
      refreshFrequency: 'Quarterly manual update',
      status: 'stale',
      recordsCount: 34,
      staleWarning: true,
      notes: 'WARNING: Ingestion is >70 days old. Operational staffing hours must be re-verified before reliance.'
    }
  ];

  // Seed users for Admin User Management (Privacy-Minimized)
  const SEED_USERS = [
    { id: 'usr-001', displayName: 'User-usr-001', emailMasked: 'p***a@e***e.test', name: 'Priya Sharma', email: 'priya.sharma@example.test', role: 'traveller', status: 'active', joinedAt: '2026-09-15T10:00:00Z', reportsCount: 4, savedPlansCount: 6 },
    { id: 'usr-002', displayName: 'User-usr-002', emailMasked: 'a***r@e***e.test', name: 'Arun Kumar', email: 'arun.k@example.test', role: 'moderator', status: 'active', joinedAt: '2026-09-20T12:00:00Z', reportsCount: 12, savedPlansCount: 2 },
    { id: 'usr-003', displayName: 'User-usr-003', emailMasked: 'k***a@s***h.test', name: 'Kavitha Rao', email: 'kavitha.admin@safepath.test', role: 'administrator', status: 'active', joinedAt: '2026-08-01T08:00:00Z', reportsCount: 0, savedPlansCount: 0 },
    { id: 'usr-004', displayName: 'User-usr-004', emailMasked: 'g***w@s***h.local', name: 'Dev Guest', email: 'guest.preview@safepath.local', role: 'traveller', status: 'demo', joinedAt: '2026-10-27T00:00:00Z', reportsCount: 1, savedPlansCount: 3 }
  ];

  // Seed feedback items
  const SEED_FEEDBACK = [
    {
      id: 'fb-101',
      userId: 'User-usr-001',
      category: 'lighting_accuracy',
      rating: 5,
      message: 'Lalbagh West Gate streetlights were recently repaired. Verified active luminaire.',
      status: 'resolved',
      createdAt: '2026-10-25T14:30:00Z',
      adminNotes: 'Confirmed with municipal audit #BBMP-401.'
    },
    {
      id: 'fb-102',
      userId: null,
      category: 'safety_concern',
      rating: 2,
      message: 'Sidewalk along 10th Main has construction debris blocking pedestrian access.',
      status: 'new',
      createdAt: '2026-10-27T08:15:00Z',
      adminNotes: null
    }
  ];

  // Seed saved places
  const SEED_PLACES = [
    { id: 'place-home', label: 'Home (Sample)', address: 'Jayanagar 4th Block, 11th Main', icon: 'home' },
    { id: 'place-work', label: 'Office / Campus', address: 'South End Circle Metro Station', icon: 'briefcase' },
    { id: 'place-transit', label: 'Transit Hub', address: 'Lalbagh West Gate Bus Stand', icon: 'bus' }
  ];


  /**
   * SafePath API Client
   */
  const ApiService = {
    // Configuration
    config: {
      baseUrl: '/api/v1',
      mode: 'live', // 'live' is default for real Dijkstra & Yen routing
      token: null,
      timeoutMs: 5000
    },

    init() {
      // Auto-resolve live backend URL: if frontend is served on port 8000 or file://, backend is on port 8001
      let defaultBaseUrl = '/api/v1';
      if (typeof window !== 'undefined' && window.location) {
        const host = window.location.hostname || '127.0.0.1';
        if (window.location.protocol === 'file:' || window.location.port === '8000') {
          defaultBaseUrl = `http://${host === 'localhost' ? '127.0.0.1' : host}:8001/api/v1`;
        }
      }

      this.config.mode = 'live';
      this.config.baseUrl = defaultBaseUrl;

      const session = storage.get(STORAGE_KEYS.SESSION, null);
      if (session && session.accessToken) {
        this.config.token = session.accessToken;
      }

      // Initialize default storage data if missing
      if (!storage.get(STORAGE_KEYS.COMMUNITY_REPORTS, null)) {
        storage.set(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      }
      if (!storage.get(STORAGE_KEYS.SAVED_PLACES, null)) {
        storage.set(STORAGE_KEYS.SAVED_PLACES, SEED_PLACES);
      }
      if (!storage.get(STORAGE_KEYS.ADMIN_USERS, null)) {
        storage.set(STORAGE_KEYS.ADMIN_USERS, SEED_USERS);
      }
      if (!storage.get(STORAGE_KEYS.SYSTEM_SETTINGS, null)) {
        storage.set(STORAGE_KEYS.SYSTEM_SETTINGS, {
          freshnessThresholdDays: 30,
          outdatedThresholdDays: 90,
          autoFlagKeywords: 'harassment, assault, dark, broken, hazard',
          requireModeratorApproval: true,
          evidenceWeightLighting: 50,
          evidenceWeightActivity: 30,
          timeWeight: 20
        });
      }
    },

    setMode(mode) {
      this.config.mode = mode;
      storage.set(STORAGE_KEYS.API_CONFIG, { mode, baseUrl: this.config.baseUrl });
    },

    isDemoMode() {
      return this.config.mode === 'demo';
    },

    isLiveBackend() {
      return this.config.mode === 'live';
    },

    _authHeaders() {
      const headers = { 'Content-Type': 'application/json' };
      if (this.config.token) {
        headers['Authorization'] = `Bearer ${this.config.token}`;
      }
      return headers;
    },

    // Logging audit entries
    logAudit(action, record, actor = 'System', outcome = 'Success') {
      const log = storage.get(STORAGE_KEYS.AUDIT_LOG, []);
      const entry = {
        id: `aud-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        timestamp: new Date().toISOString(),
        action,
        record: typeof record === 'string' ? record : JSON.stringify(record),
        actor,
        outcome,
        environment: this.config.mode === 'demo' ? 'Local Demo' : 'Live API'
      };
      log.unshift(entry);
      storage.set(STORAGE_KEYS.AUDIT_LOG, log.slice(0, 200));
      return entry;
    },

    getAuditLog() {
      return storage.get(STORAGE_KEYS.AUDIT_LOG, []);
    },

    clearAuditLog() {
      storage.set(STORAGE_KEYS.AUDIT_LOG, []);
    },

    // ----------------------------------------------------
    // IDENTITY & AUTH (POST /auth/login, /auth/register, etc.)
    // ----------------------------------------------------
    async register({ name, email, password }) {
      if (!name || !email || !password) {
        throw new Error('Name, email, and password (min 8 characters) are required.');
      }
      if (password.length < 8) {
        throw new Error('Password must be at least 8 characters long.');
      }

      if (this.config.mode === 'live') {
        try {
          const res = await fetch(`${this.config.baseUrl}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.message || `Registration failed (${res.status})`);
          }
          return await res.json();
        } catch (err) {
          throw new Error(`Live registration unavailable: ${err.message}. (Server at ${this.config.baseUrl} not reachable)`);
        }
      }

      // Demo Mode: Mock registration
      const user = {
        id: `usr-${Date.now()}`,
        name: name.trim(),
        email: email.trim().toLowerCase(),
        role: 'traveller',
        createdAt: new Date().toISOString(),
        isDemoAccount: true
      };
      const session = {
        user,
        accessToken: `demo_token_${Date.now()}`,
        isDemo: true
      };
      storage.set(STORAGE_KEYS.SESSION, session);
      this.config.token = session.accessToken;
      this.logAudit('User registered', user.email, user.name);
      return { user, accessToken: session.accessToken, message: 'Local demo account created.' };
    },

    async login({ email, password, role = 'traveller' }) {
      if (!email || !password) {
        throw new Error('Please enter both email address and password.');
      }

      if (this.config.mode === 'live') {
        try {
          const res = await fetch(`${this.config.baseUrl}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.message || `Authentication failed (${res.status})`);
          }
          const data = await res.json();
          this.config.token = data.accessToken;
          storage.set(STORAGE_KEYS.SESSION, data);
          return data;
        } catch (err) {
          throw new Error(`Live authentication failed: ${err.message}. Verify that the backend is running at ${this.config.baseUrl}.`);
        }
      }

      // Demo Mode: Authenticate demo session
      const cleanEmail = email.trim().toLowerCase();
      const user = {
        id: cleanEmail.includes('admin') ? 'usr-demo-admin' : 'usr-demo-traveller',
        name: cleanEmail.includes('admin') ? 'Operations Admin (Demo)' : (role === 'admin' ? 'Demo Admin' : 'Demo Traveller'),
        email: cleanEmail,
        role: role === 'admin' || cleanEmail.includes('admin') ? 'administrator' : 'traveller',
        isDemo: true
      };
      const session = {
        user,
        accessToken: `demo_token_${Date.now()}`,
        isDemo: true
      };
      storage.set(STORAGE_KEYS.SESSION, session);
      this.config.token = session.accessToken;
      this.logAudit('User sign in', user.email, user.name);
      return { user, accessToken: session.accessToken };
    },

    async requestPasswordReset(email) {
      if (!email) throw new Error('Please enter an email address.');
      if (this.config.mode === 'live') {
        try {
          const res = await fetch(`${this.config.baseUrl}/auth/password-reset/request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });
          // Contract requirement: always return 202 without revealing if account exists
          return { status: 202, message: 'If an account matches that email address, password reset instructions have been dispatched.' };
        } catch (err) {
          throw new Error(`Password reset service unavailable: ${err.message}`);
        }
      }
      this.logAudit('Password reset requested', email, 'Anonymous');
      return { status: 202, message: 'If an account matches that email address, password reset instructions have been dispatched. (Demo notice: no email was sent).' };
    },

    async confirmPasswordReset({ token, password }) {
      if (!token || !password) throw new Error('Reset token and new password are required.');
      if (password.length < 8) throw new Error('New password must be at least 8 characters long.');
      if (this.config.mode === 'live') {
        const res = await fetch(`${this.config.baseUrl}/auth/password-reset/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, password })
        });
        if (!res.ok) throw new Error('Invalid or expired reset token.');
        return await res.json();
      }
      this.logAudit('Password reset confirmed', `Token: ${token.slice(0, 6)}...`, 'Anonymous');
      return { success: true, message: 'Password has been reset successfully in demo mode.' };
    },

    async logout() {
      if (this.config.mode === 'live' && this.config.token) {
        try {
          await fetch(`${this.config.baseUrl}/auth/logout`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${this.config.token}` }
          });
        } catch (e) {}
      }
      const session = storage.get(STORAGE_KEYS.SESSION, null);
      if (session && session.user) {
        this.logAudit('User signed out', session.user.email, session.user.name);
      }
      storage.remove(STORAGE_KEYS.SESSION);
      this.config.token = null;
      return { success: true };
    },

    getCurrentUser() {
      const session = storage.get(STORAGE_KEYS.SESSION, null);
      return session ? session.user : null;
    },

    async getMe() {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/me`, { headers: this._authHeaders() });
          if (!res.ok) throw new Error(`Failed to load profile (${res.status})`);
          const user = await res.json();
          const session = storage.get(STORAGE_KEYS.SESSION, {});
          session.user = user;
          storage.set(STORAGE_KEYS.SESSION, session);
          return user;
        } catch (err) {
          throw new Error(`Live getMe failed: ${err.message}`);
        }
      }
      return this.getCurrentUser();
    },

    // ----------------------------------------------------
    // GEOCODING & LOCATION SEARCH (GET /geocoding/search)
    // ----------------------------------------------------
    _searchCache: new Map(),

    async searchPlaces(query, limit = 5) {
      if (!query || typeof query !== 'string' || query.trim().length < 2) {
        return [];
      }
      const clean = query.toLowerCase().trim();
      if (this._searchCache && this._searchCache.has(clean)) {
        return this._searchCache.get(clean);
      }

      if (this.config.mode === 'live') {
        try {
          const url = `${this.config.baseUrl}/geocoding/search?q=${encodeURIComponent(query.trim())}&limit=${limit}`;
          const res = await fetch(url, {
            headers: {
              'Accept': 'application/json',
              ...(this.config.token ? { 'Authorization': `Bearer ${this.config.token}` } : {})
            }
          });
          if (!res.ok) {
            let errDetail = `Location search error (${res.status})`;
            try {
              const errJson = await res.json();
              if (errJson && errJson.detail) errDetail = errJson.detail;
            } catch (e) {}
            throw new Error(errDetail);
          }
          const data = await res.json();
          const results = data.results || [];
          if (!this._searchCache) this._searchCache = new Map();
          this._searchCache.set(clean, results);
          return results;
        } catch (err) {
          if (err.message && err.message.includes('Failed to fetch')) {
            console.warn('Geocoding backend offline; using local fallback.');
          } else {
            throw err;
          }
        }
      }

      // Demo mode fallback locations
      const demoPlaces = [
        { id: 'local_jayanagar', name: 'Jayanagar 4th Block', displayName: 'Jayanagar 4th Block, Bengaluru, Karnataka, India', latitude: 12.9257, longitude: 77.5833, type: 'suburb', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_lalbagh', name: 'Lalbagh West Gate', displayName: 'Lalbagh Botanical Garden (West Gate), Basavanagudi, Bengaluru', latitude: 12.9460, longitude: 77.5844, type: 'attraction', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_southend', name: 'South End Circle', displayName: 'South End Circle Metro & Junction, Jayanagar, Bengaluru', latitude: 12.9370, longitude: 77.5835, type: 'transit', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_gandhibazaar', name: 'Gandhi Bazaar', displayName: 'Gandhi Bazaar Main Road, Basavanagudi, Bengaluru', latitude: 12.9420, longitude: 77.5720, type: 'commercial', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_cubbon', name: 'Cubbon Park', displayName: 'Cubbon Park (Sri Chamarajendra Park), Kasturba Road, Bengaluru', latitude: 12.9770, longitude: 77.5920, type: 'park', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_mgroad', name: 'MG Road', displayName: 'Mahatma Gandhi Road (MG Road), Ashok Nagar, Bengaluru', latitude: 12.9750, longitude: 77.6050, type: 'commercial', inStudyArea: true, studyAreaDistanceMeters: 0 },
        { id: 'local_ecity', name: 'Electronic City', displayName: 'Electronic City, Bengaluru, Bangalore South, Karnataka, 560100, India', latitude: 12.8436, longitude: 77.6687, type: 'suburb', inStudyArea: false, studyAreaDistanceMeters: 10000 },
        { id: 'local_koramangala', name: 'Koramangala', displayName: 'Koramangala, Bengaluru, Bangalore South, Karnataka, India', latitude: 12.9352, longitude: 77.6245, type: 'suburb', inStudyArea: false, studyAreaDistanceMeters: 550 },
        { id: 'local_indiranagar', name: 'Indiranagar', displayName: 'Indiranagar, Bengaluru, Bangalore East, Karnataka, India', latitude: 12.9784, longitude: 77.6408, type: 'suburb', inStudyArea: false, studyAreaDistanceMeters: 2260 },
        { id: 'local_whitefield', name: 'Whitefield', displayName: 'Whitefield, Bengaluru, Bangalore East, Karnataka, India', latitude: 12.9698, longitude: 77.7499, type: 'suburb', inStudyArea: false, studyAreaDistanceMeters: 14000 }
      ];
      const filtered = demoPlaces.filter(p => p.name.toLowerCase().includes(clean) || p.displayName.toLowerCase().includes(clean));
      return filtered.slice(0, limit);
    },

    // ----------------------------------------------------
    // ROUTE COMPARISON & JOURNEYS (POST /routes/compare)
    // ----------------------------------------------------
    async compareRoutes({ origin, destination, originCoordinates = null, destinationCoordinates = null, walkingMode = 'pedestrian', preferences = {} }) {
      if (!origin || !destination) {
        throw new Error('Both starting point and destination are required.');
      }

      if (this.config.mode === 'live') {
        try {
          const reqBody = {
            origin,
            destination,
            walkingMode,
            preferences: {
              ...preferences,
              includeAlternatives: true,
              maxAlternatives: preferences.maxAlternatives || 2
            }
          };
          if (Array.isArray(originCoordinates) && originCoordinates.length === 2) {
            reqBody.originCoordinates = originCoordinates;
          }
          if (Array.isArray(destinationCoordinates) && destinationCoordinates.length === 2) {
            reqBody.destinationCoordinates = destinationCoordinates;
          }

          const res = await fetch(`${this.config.baseUrl}/routes/compare`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(this.config.token ? { 'Authorization': `Bearer ${this.config.token}` } : {})
            },
            body: JSON.stringify(reqBody)
          });
          if (!res.ok) {
            let errorMsg = `Server error (${res.status})`;
            try {
              const errJson = await res.json();
              if (errJson && errJson.detail) {
                errorMsg = typeof errJson.detail === 'string'
                  ? errJson.detail
                  : (errJson.detail[0]?.msg || JSON.stringify(errJson.detail));
              }
            } catch (e) {}
            throw new Error(errorMsg);
          }
          return await res.json();
        } catch (err) {
          // If live request failed due to offline backend, allow user to know
          if (err.message && err.message.includes('Failed to fetch')) {
            throw new Error(`Live routing service offline at ${this.config.baseUrl}. Start the backend via 'PYTHONPATH=. uvicorn app.main:app --port 8001'.`);
          }
          throw err;
        }
      }

      // When live mode is not active or backend is unreachable, do not synthesize or interpolate fake paths
      throw new Error(
        `Live pedestrian routing backend (FastAPI on port 8001) is required to calculate genuine walking routes through the OpenStreetMap street network. SafePath Finder does not synthesize or interpolate artificial route paths.`
      );
    },

    // ----------------------------------------------------
    // EVIDENCE SEGMENTS (GET /evidence/segments?routeId=...)
    // ----------------------------------------------------
    async getRouteSegments(routeId, memorySegments = null) {
      if (!routeId) throw new Error('routeId is required.');
      if (memorySegments && Array.isArray(memorySegments) && memorySegments.length > 0) {
        return {
          routeId,
          routeName: routeId,
          segments: memorySegments
        };
      }
      if (this.config.mode === 'live') {
        try {
          const res = await fetch(`${this.config.baseUrl}/evidence/segments?routeId=${encodeURIComponent(routeId)}`, {
            headers: this.config.token ? { 'Authorization': `Bearer ${this.config.token}` } : {}
          });
          if (res.ok) return await res.json();
        } catch (e) {
          console.warn('Live getRouteSegments failed:', e);
        }
      }

      return {
        routeId: routeId,
        routeName: routeId,
        segments: []
      };
    },

    // ----------------------------------------------------
    // SAVED PLANS & HISTORY (GET, POST, DELETE /journeys)
    // ----------------------------------------------------
    async fetchSavedPlans() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/journeys`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to fetch journeys (${res.status})`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        storage.set(STORAGE_KEYS.SAVED_PLANS, items);
        return items;
      }
      return this.getSavedPlans();
    },

    getSavedPlans() {
      return storage.get(STORAGE_KEYS.SAVED_PLANS, []);
    },

    async savePlan(plan) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/journeys`, {
            method: 'POST',
            headers: this._authHeaders(),
            body: JSON.stringify(plan)
          });
          if (!res.ok) throw new Error(`Live save journey failed (${res.status})`);
          const saved = await res.json();
          const current = this.getSavedPlans();
          current.unshift(saved);
          storage.set(STORAGE_KEYS.SAVED_PLANS, current.slice(0, 25));
          return saved;
        } catch (err) {
          throw new Error(`Save journey failed: ${err.message}`);
        }
      }

      const plans = this.getSavedPlans();
      const newPlan = {
        id: `plan-${Date.now()}`,
        start: plan.start,
        end: plan.end,
        routeId: plan.routeId || 'route-evidence',
        routeName: plan.routeName || 'Evidence-led Route',
        distanceMeters: plan.distanceMeters || 1850,
        durationMinutes: plan.durationMinutes || 24,
        preferences: plan.preferences || {},
        savedAt: new Date().toISOString(),
        isDemo: true
      };
      plans.unshift(newPlan);
      storage.set(STORAGE_KEYS.SAVED_PLANS, plans.slice(0, 25));
      this.logAudit('Saved journey plan', `${newPlan.start} -> ${newPlan.end}`, 'Traveller');
      return newPlan;
    },

    async deletePlan(planId) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/journeys/${encodeURIComponent(planId)}`, {
            method: 'DELETE',
            headers: this._authHeaders()
          });
          if (!res.ok) throw new Error(`Live delete failed (${res.status})`);
        } catch (err) {
          throw new Error(`Delete journey failed: ${err.message}`);
        }
      }
      const plans = this.getSavedPlans();
      const filtered = plans.filter(p => p.id !== planId);
      storage.set(STORAGE_KEYS.SAVED_PLANS, filtered);
      this.logAudit('Deleted journey plan', planId, 'Traveller');
      return true;
    },

    async fetchJourneyHistory() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/journeys/history`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load history (${res.status})`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        storage.set(STORAGE_KEYS.JOURNEY_HISTORY, items);
        return items;
      }
      return this.getJourneyHistory();
    },

    getJourneyHistory() {
      return storage.get(STORAGE_KEYS.JOURNEY_HISTORY, [
        {
          id: 'hist-1',
          origin: 'Jayanagar 4th Block',
          destination: 'Lalbagh West Gate',
          routeChosen: 'Evidence-led Route',
          completedAt: '2026-10-25T19:30:00Z',
          durationMinutes: 25,
          arrivalConfirmed: true,
          sharedWithCount: 1
        },
        {
          id: 'hist-2',
          origin: 'South End Circle',
          destination: 'Gandhi Bazaar',
          routeChosen: 'Balanced Sample Route',
          completedAt: '2026-10-21T18:10:00Z',
          durationMinutes: 16,
          arrivalConfirmed: true,
          sharedWithCount: 0
        }
      ]);
    },

    // ----------------------------------------------------
    // COMMUNITY REPORTS (POST /reports, GET /reports/mine, moderation)
    // ----------------------------------------------------
    async fetchAdminReports({ status, query, page = 1, pageSize = 20 } = {}) {
      if (this.isLiveBackend()) {
        const params = new URLSearchParams();
        if (status && status !== 'all') params.set('status', status);
        if (query) params.set('query', query);
        params.set('page', String(page));
        params.set('pageSize', String(pageSize));
        const res = await fetch(`${this.config.baseUrl}/admin/reports?${params.toString()}`, {
          headers: this._authHeaders()
        });
        if (!res.ok) throw new Error(`Failed to load admin reports (${res.status})`);
        return await res.json();
      }
      return {
        items: this.getReports({ status, query }),
        page,
        pageSize,
        total: this.getReports({ status, query }).length
      };
    },

    getReports(filter = {}) {
      const all = storage.get(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      let list = [...all];
      if (filter.status && filter.status !== 'all') {
        list = list.filter(r => r.status === filter.status);
      }
      if (filter.category && filter.category !== 'all') {
        list = list.filter(r => r.category === filter.category);
      }
      if (filter.query) {
        const q = filter.query.toLowerCase();
        list = list.filter(r =>
          (r.description && r.description.toLowerCase().includes(q)) ||
          (r.location && r.location.toLowerCase().includes(q)) ||
          (r.id && r.id.toLowerCase().includes(q))
        );
      }
      return list.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    },

    async fetchMyReports() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/reports/mine`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load my reports (${res.status})`);
        const data = await res.json();
        return Array.isArray(data) ? data : (data.items || []);
      }
      return this.getMyReports();
    },

    getMyReports() {
      const user = this.getCurrentUser();
      const all = storage.get(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      if (!user) {
        // Return local submissions in demo
        return all.filter(r => r.reporterId === 'usr-demo-travel' || r.isLocalSubmission);
      }
      return all.filter(r => r.reporterId === user.id || r.isLocalSubmission);
    },

    async submitReport({ category, location, description, anonymous = true }) {
      if (!category || !location || !description) {
        throw new Error('Please select an observation category and provide both location and description.');
      }
      if (description.length < 10) {
        throw new Error('Please provide at least 10 characters describing the street condition.');
      }

      if (this.config.mode === 'live') {
        try {
          const res = await fetch(`${this.config.baseUrl}/reports`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(this.config.token ? { 'Authorization': `Bearer ${this.config.token}` } : {})
            },
            body: JSON.stringify({ category, location, description, anonymous })
          });
          if (!res.ok) throw new Error(`Report submission failed (${res.status})`);
          return await res.json();
        } catch (err) {
          throw new Error(`Live reporting unavailable: ${err.message}`);
        }
      }

      // Demo Mode: Save to local storage
      const user = this.getCurrentUser();
      const categoryLabels = {
        broken_lighting: 'Broken street lighting',
        blocked_footpath: 'Blocked footpath',
        poor_visibility: 'Poor visibility / blind curve',
        construction_hazard: 'Construction or pavement hazard',
        access_facility: 'Access or public transit facility',
        other_concern: 'Other street condition'
      };

      const newReport = {
        id: `rep-${Date.now().toString().slice(-5)}`,
        category,
        categoryLabel: categoryLabels[category] || 'Other street condition',
        location: location.trim(),
        description: description.trim(),
        createdAt: new Date().toISOString(),
        status: 'pending', // Contract: pending, approved, rejected, flagged
        provenance: anonymous ? 'Anonymous demo web reporter' : `Reported by ${user ? user.name : 'Traveller'}`,
        corroborations: 1,
        reporterId: user ? user.id : 'usr-demo-travel',
        isLocalSubmission: true,
        moderatorNotes: ''
      };

      const all = storage.get(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      all.unshift(newReport);
      storage.set(STORAGE_KEYS.COMMUNITY_REPORTS, all);

      this.logAudit('Submitted community observation', `${newReport.id}: ${newReport.category}`, user ? user.name : 'Anonymous');
      return newReport;
    },

    async updateReportModeration(reportId, newStatus, reason = '') {
      const allowed = ['pending', 'approved', 'rejected', 'flagged'];
      if (!allowed.includes(newStatus)) {
        throw new Error(`Invalid status "${newStatus}". Must be one of: ${allowed.join(', ')}`);
      }

      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/admin/reports/${encodeURIComponent(reportId)}`, {
            method: 'PATCH',
            headers: this._authHeaders(),
            body: JSON.stringify({ status: newStatus, reason })
          });
          if (!res.ok) throw new Error(`Live update failed (${res.status})`);
        } catch (err) {
          throw new Error(`Moderation update failed: ${err.message}`);
        }
      }

      const all = storage.get(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      const idx = all.findIndex(r => r.id === reportId);
      if (idx === -1) throw new Error(`Report ${reportId} not found.`);

      all[idx].status = newStatus;
      all[idx].moderatorNotes = reason ? reason.trim() : (all[idx].moderatorNotes || '');
      all[idx].reviewedAt = new Date().toISOString();
      storage.set(STORAGE_KEYS.COMMUNITY_REPORTS, all);

      this.logAudit(
        `Moderated report to "${newStatus}"`,
        `${reportId} (Reason: ${reason || 'No reason specified'})`,
        'Administrator'
      );
      return all[idx];
    },

    // ----------------------------------------------------
    // TRUSTED CONTACTS & TRIP SHARING
    // ----------------------------------------------------
    async fetchTrustedContacts() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/trusted-contacts`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load trusted contacts (${res.status})`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        storage.set(STORAGE_KEYS.TRUSTED_CONTACTS, items);
        return items;
      }
      return this.getTrustedContacts();
    },

    getTrustedContacts() {
      return storage.get(STORAGE_KEYS.TRUSTED_CONTACTS, [
        { id: 'ct-1', name: 'Maya S.', relationship: 'Friend / Roommate', phone: '+91 98765 43210', notifyOnStart: true, notifyOnArrival: true },
        { id: 'ct-2', name: 'Ananya R.', relationship: 'Family member', phone: '+91 91234 56789', notifyOnStart: false, notifyOnArrival: true }
      ]);
    },

    async addTrustedContact({ name, relationship, phone }) {
      if (!name) throw new Error('Contact name is required.');

      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/trusted-contacts`, {
            method: 'POST',
            headers: this._authHeaders(),
            body: JSON.stringify({ name, relationship, phone })
          });
          if (!res.ok) throw new Error(`Live add contact failed (${res.status})`);
          const created = await res.json();
          const contacts = this.getTrustedContacts();
          contacts.push(created);
          storage.set(STORAGE_KEYS.TRUSTED_CONTACTS, contacts);
          return created;
        } catch (err) {
          throw new Error(`Failed to add trusted contact: ${err.message}`);
        }
      }

      const contacts = this.getTrustedContacts();
      const newContact = {
        id: `ct-${Date.now()}`,
        name: name.trim(),
        relationship: relationship || 'Friend',
        phone: phone ? phone.trim() : 'Not provided',
        notifyOnStart: true,
        notifyOnArrival: true,
        createdAt: new Date().toISOString()
      };
      contacts.push(newContact);
      storage.set(STORAGE_KEYS.TRUSTED_CONTACTS, contacts);
      this.logAudit('Added trusted contact', newContact.name, 'Traveller');
      return newContact;
    },

    async deleteTrustedContact(contactId) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/trusted-contacts/${encodeURIComponent(contactId)}`, {
            method: 'DELETE',
            headers: this._authHeaders()
          });
          if (!res.ok) throw new Error(`Live delete contact failed (${res.status})`);
        } catch (err) {
          throw new Error(`Failed to remove contact: ${err.message}`);
        }
      }

      const contacts = this.getTrustedContacts();
      const filtered = contacts.filter(c => c.id !== contactId);
      storage.set(STORAGE_KEYS.TRUSTED_CONTACTS, filtered);
      this.logAudit('Removed trusted contact', contactId, 'Traveller');
      return true;
    },

    async shareJourney({ routeName, etaMinutes, destination, contactIds }) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/journey-shares`, {
            method: 'POST',
            headers: this._authHeaders(),
            body: JSON.stringify({ routeName, etaMinutes, destination, contactIds })
          });
          if (!res.ok) throw new Error(`Failed to initiate journey share (${res.status})`);
          return await res.json();
        } catch (err) {
          throw new Error(`Journey share failed: ${err.message}`);
        }
      }

      // API Contract: Requires delivery status from an actual provider; UI must NOT infer delivery
      this.logAudit('Trip share initiated', `Dest: ${destination}, Contacts: ${contactIds.length}`, 'Traveller');
      return {
        deliveryStatus: 'pending_provider_integration',
        providerName: 'None configured (Backend integration required)',
        deliveredCount: 0,
        intendedCount: contactIds.length,
        shareLink: `${window.location.origin}${window.location.pathname}?preview_journey=true&dest=${encodeURIComponent(destination)}`,
        previewMessage: `SafePath Walk preview: I am walking to ${destination} via ${routeName}. Estimated walk duration: ${etaMinutes} mins.`
      };
    },

    async confirmArrival({ destination, journeyId }) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/arrival-confirmations`, {
            method: 'POST',
            headers: this._authHeaders(),
            body: JSON.stringify({ destination, journeyId })
          });
          if (!res.ok) throw new Error(`Arrival confirmation failed (${res.status})`);
          return await res.json();
        } catch (err) {
          throw new Error(`Arrival confirmation service failed: ${err.message}`);
        }
      }

      // API Contract: POST /arrival-confirmations
      this.logAudit('Arrival confirmed by traveller', destination, 'Traveller');
      return {
        arrivalConfirmed: true,
        timestamp: new Date().toISOString(),
        deliveryStatus: 'pending_provider_integration',
        message: 'Arrival recorded on device. Automatic SMS/WhatsApp alerts require SMS gateway integration.'
      };
    },

    // ----------------------------------------------------
    // SAVED PLACES
    // ----------------------------------------------------
    getSavedPlaces() {
      return storage.get(STORAGE_KEYS.SAVED_PLACES, SEED_PLACES);
    },

    addSavedPlace({ label, address, icon = 'place' }) {
      if (!label || !address) throw new Error('Place name and address are required.');
      const places = this.getSavedPlaces();
      const newPlace = {
        id: `plc-${Date.now()}`,
        label: label.trim(),
        address: address.trim(),
        icon
      };
      places.push(newPlace);
      storage.set(STORAGE_KEYS.SAVED_PLACES, places);
      return newPlace;
    },

    deleteSavedPlace(placeId) {
      const places = this.getSavedPlaces();
      const filtered = places.filter(p => p.id !== placeId);
      storage.set(STORAGE_KEYS.SAVED_PLACES, filtered);
      return true;
    },

    // ----------------------------------------------------
    // PREFERENCES & PRIVACY
    // ----------------------------------------------------
    getPreferences() {
      return storage.get(STORAGE_KEYS.PREFERENCES, {
        preferLighting: true,
        preferActivity: true,
        avoidUnknown: true,
        walkingSpeedKmh: 4.6,
        reducedMotion: false,
        highContrast: false,
        evidenceWeightLighting: 50,
        evidenceWeightActivity: 30,
        timeWeight: 20
      });
    },

    savePreferences(prefs) {
      const existing = this.getPreferences();
      const updated = { ...existing, ...prefs };
      storage.set(STORAGE_KEYS.PREFERENCES, updated);
      this.logAudit('Updated route preferences', JSON.stringify(prefs), 'Traveller');
      return updated;
    },

    clearAllUserData() {
      const preserveKeys = [STORAGE_KEYS.API_CONFIG];
      Object.values(STORAGE_KEYS).forEach(k => {
        if (!preserveKeys.includes(k)) {
          storage.remove(k);
        }
      });
      // Re-seed demo structures so app can continue running cleanly
      storage.set(STORAGE_KEYS.COMMUNITY_REPORTS, SEED_REPORTS);
      storage.set(STORAGE_KEYS.SAVED_PLACES, SEED_PLACES);
      storage.set(STORAGE_KEYS.ADMIN_USERS, SEED_USERS);
      this.logAudit('Local demo user data cleared and reseeded', 'Browser storage reset', 'Traveller');
      return true;
    },

    // ----------------------------------------------------
    // ADMIN CAPABILITIES (Users, Data Sources, System Settings)
    // ----------------------------------------------------
    async fetchAdminDataSources() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/data-sources`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load data sources (${res.status})`);
        const data = await res.json();
        return Array.isArray(data) ? data : (data.items || []);
      }
      return this.getAdminDataSources();
    },

    getAdminDataSources() {
      return SEED_DATA_SOURCES;
    },

    async fetchAdminUsers(query = '') {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/users${query ? `?query=${encodeURIComponent(query)}` : ''}`, {
          headers: this._authHeaders()
        });
        if (!res.ok) throw new Error(`Failed to load admin users (${res.status})`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        storage.set(STORAGE_KEYS.ADMIN_USERS, items);
        return items;
      }
      return this.getAdminUsers(query);
    },

    getAdminUsers(query = '') {
      let list = storage.get(STORAGE_KEYS.ADMIN_USERS, SEED_USERS);
      if (query) {
        const q = query.toLowerCase();
        list = list.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || u.role.includes(q));
      }
      return list;
    },

    async updateUserRole(userId, newRole) {
      const allowed = ['traveller', 'moderator', 'administrator'];
      if (!allowed.includes(newRole)) throw new Error(`Role must be one of: ${allowed.join(', ')}`);

      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/admin/users/${encodeURIComponent(userId)}`, {
            method: 'PATCH',
            headers: this._authHeaders(),
            body: JSON.stringify({ role: newRole })
          });
          if (!res.ok) throw new Error(`Live role update failed (${res.status})`);
        } catch (err) {
          throw new Error(`Role update failed: ${err.message}`);
        }
      }

      const users = storage.get(STORAGE_KEYS.ADMIN_USERS, SEED_USERS);
      const user = users.find(u => u.id === userId);
      if (user) {
        user.role = newRole;
        storage.set(STORAGE_KEYS.ADMIN_USERS, users);
      }
      this.logAudit(`User role updated to ${newRole}`, userId, 'Administrator');
      return { id: userId, role: newRole, notice: 'Presentation state updated. Server authorization required in production.' };
    },

    async revealUserIdentity(userId, reason) {
      if (!reason || reason.trim().length < 5) {
        throw new Error('An administrative justification / support ticket ref (min 5 chars) is required.');
      }

      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/users/${encodeURIComponent(userId)}/reveal-identity`, {
          method: 'POST',
          headers: this._authHeaders(),
          body: JSON.stringify({ reason: reason.trim() })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Identity lookup forbidden (${res.status})`);
        }
        return await res.json();
      }

      // Demo Mode fallback
      const users = storage.get(STORAGE_KEYS.ADMIN_USERS, SEED_USERS);
      const user = users.find(u => u.id === userId);
      if (!user) throw new Error('User not found in directory.');

      this.logAudit(`Sensitive user identity revealed for ${userId}`, `Justification: ${reason.trim()}`, 'Administrator');
      return {
        id: user.id,
        name: user.name || 'Demo Traveller',
        email: user.email || 'traveller@example.test',
        role: user.role,
        status: user.status,
        revealedAt: new Date().toISOString(),
        revealedBy: 'Administrator',
        justification: reason.trim()
      };
    },

    // ----------------------------------------------------
    // USER FEEDBACK & SUPPORT
    // ----------------------------------------------------
    async submitFeedback({ category = 'general', message, rating = null }) {
      if (!message || message.trim().length < 5) {
        throw new Error('Feedback message must be at least 5 characters long.');
      }

      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/feedback`, {
          method: 'POST',
          headers: this._authHeaders(),
          body: JSON.stringify({
            category,
            message: message.trim(),
            rating: rating ? parseInt(rating, 10) : null
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Feedback submission failed (${res.status})`);
        }
        return await res.json();
      }

      // Demo Mode
      const list = storage.get(STORAGE_KEYS.FEEDBACK, SEED_FEEDBACK);
      const current = this.getCurrentUser();
      const fbItem = {
        id: `fb-${Date.now()}`,
        userId: current ? `User-${current.id.slice(0, 8)}` : null,
        category,
        message: message.trim(),
        rating: rating ? parseInt(rating, 10) : null,
        status: 'new',
        createdAt: new Date().toISOString(),
        adminNotes: null
      };
      list.unshift(fbItem);
      storage.set(STORAGE_KEYS.FEEDBACK, list);
      this.logAudit('User feedback submitted', `Category: ${category}`, current ? current.name : 'Anonymous');
      return fbItem;
    },

    async fetchAdminFeedback({ category = null, status = null } = {}) {
      if (this.isLiveBackend()) {
        const params = new URLSearchParams();
        if (category && category !== 'all') params.append('category', category);
        if (status && status !== 'all') params.append('status', status);

        const res = await fetch(`${this.config.baseUrl}/admin/feedback?${params.toString()}`, {
          headers: this._authHeaders()
        });
        if (!res.ok) throw new Error(`Failed to load feedback inbox (${res.status})`);
        const data = await res.json();
        return Array.isArray(data) ? data : (data.items || []);
      }
      return this.getAdminFeedback({ category, status });
    },

    getAdminFeedback({ category = null, status = null } = {}) {
      let list = storage.get(STORAGE_KEYS.FEEDBACK, SEED_FEEDBACK);
      if (category && category !== 'all') {
        list = list.filter(f => f.category === category);
      }
      if (status && status !== 'all') {
        list = list.filter(f => f.status === status);
      }
      return list;
    },

    async updateFeedbackStatus(feedbackId, newStatus, adminNotes = null) {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/feedback/${encodeURIComponent(feedbackId)}`, {
          method: 'PATCH',
          headers: this._authHeaders(),
          body: JSON.stringify({ status: newStatus, adminNotes })
        });
        if (!res.ok) throw new Error(`Feedback update failed (${res.status})`);
        return await res.json();
      }

      // Demo Mode
      const list = storage.get(STORAGE_KEYS.FEEDBACK, SEED_FEEDBACK);
      const item = list.find(f => f.id === feedbackId);
      if (item) {
        item.status = newStatus;
        if (adminNotes !== null) item.adminNotes = adminNotes;
        storage.set(STORAGE_KEYS.FEEDBACK, list);
      }
      this.logAudit(`Feedback status updated to ${newStatus}`, feedbackId, 'Administrator');
      return item;
    },


    async fetchAuditLog() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/audit`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load audit trail (${res.status})`);
        const data = await res.json();
        return Array.isArray(data) ? data : (data.items || []);
      }
      return this.getAuditLog();
    },

    async fetchSystemSettings() {
      if (this.isLiveBackend()) {
        const res = await fetch(`${this.config.baseUrl}/admin/settings`, { headers: this._authHeaders() });
        if (!res.ok) throw new Error(`Failed to load system settings (${res.status})`);
        const data = await res.json();
        storage.set(STORAGE_KEYS.SYSTEM_SETTINGS, data);
        return data;
      }
      return this.getSystemSettings();
    },

    getSystemSettings() {
      return storage.get(STORAGE_KEYS.SYSTEM_SETTINGS, {
        freshnessThresholdDays: 30,
        outdatedThresholdDays: 90,
        autoFlagKeywords: 'harassment, assault, dark, broken, hazard',
        requireModeratorApproval: true,
        evidenceWeightLighting: 50,
        evidenceWeightActivity: 30,
        timeWeight: 20
      });
    },

    async saveSystemSettings(settings) {
      if (this.isLiveBackend()) {
        try {
          const res = await fetch(`${this.config.baseUrl}/admin/settings`, {
            method: 'PATCH',
            headers: this._authHeaders(),
            body: JSON.stringify(settings)
          });
          if (!res.ok) throw new Error(`Live save settings failed (${res.status})`);
        } catch (err) {
          throw new Error(`Save settings failed: ${err.message}`);
        }
      }

      const existing = this.getSystemSettings();
      const updated = { ...existing, ...settings };
      storage.set(STORAGE_KEYS.SYSTEM_SETTINGS, updated);
      this.logAudit('Updated system administration settings', JSON.stringify(settings), 'Administrator');
      return updated;
    }
  };

  // Expose to window
  window.SafePathApi = ApiService;
  ApiService.init();

})(window);
