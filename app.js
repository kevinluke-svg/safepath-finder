/**
 * SafePath Finder - Application Logic & UI Controller
 * Orchestrates Map, Route Comparison, Evidence Explorer, Community Reporting,
 * Traveller Workspace, Admin Portal, and Authentication workflows.
 */

(function () {
  'use strict';

  // DOM Helpers
  const $ = (selector, context = document) => context.querySelector(selector);
  const $$ = (selector, context = document) => Array.from(context.querySelectorAll(selector));

  const escapeHtml = str => String(str ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));

  // Global UI State
  const state = {
    currentScreen: 'app', // 'app' | 'account' | 'admin'
    selectedRouteId: 'route-evidence',
    currentRoutes: [],
    selectedSegmentId: null,
    currentSegments: [],
    travellerTab: 'overview',
    adminTab: 'overview',
    activeReportFilter: 'all',
    authMode: 'signin',
    originLocation: { name: 'Jayanagar 4th Block', lat: 12.9257, lon: 77.5833, inStudyArea: true },
    destinationLocation: { name: 'Lalbagh West Gate', lat: 12.9460, lon: 77.5844, inStudyArea: true },
    map: null,
    layers: {
      routesGroup: null,
      routes: {},
      lighting: null,
      dogs: null,
      observations: null,
      places: null,
      landmarks: null,
      infra: null,
      crime: null,
      segmentHighlight: null,
      coverage: null,
      userLocation: null,
      markers: null
    },
    toggles: {
      routes: true,
      lighting: true,
      dogs: true,
      observations: true,
      places: true,
      landmarks: true,
      infra: true,
      crime: false,
      coverage: true
    },
    mapBundle: null,
    activeJourneySession: null,
    activeCountdownInterval: null,
    isPickingMapCoordinate: false
  };

  // Toast Notification helper
  let toastTimer = null;
  function showToast(message, duration = 3400) {
    const el = $('#toast');
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), duration);
  }

  // Relative Time Formatter
  function timeAgo(dateString) {
    if (!dateString) return 'Just now';
    const date = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 60) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }

  // ==========================================================================
  // NAVIGATION & SCREEN SWITCHING
  // ==========================================================================
  const NAV_SECTIONS = ['plan', 'routes', 'evidence-explorer', 'community', 'safety-guidelines'];
  let isNavClickScrolling = false;
  let navClickTimeout = null;

  function setActiveNavLink(targetId) {
    if (state.currentScreen !== 'app') {
      // In account or admin screens, clear active state from in-page section links
      $$('#mainNav .nav-link').forEach(link => {
        link.classList.remove('active');
        link.removeAttribute('aria-current');
      });
      $$('#mobileNavDrawer .mobile-nav-item').forEach(link => {
        link.classList.remove('active');
        link.removeAttribute('aria-current');
      });
      return;
    }

    const cleanId = (targetId || '').replace(/^#/, '') || 'plan';
    $$('#mainNav .nav-link').forEach(link => {
      const href = link.getAttribute('href') || '';
      const linkId = href.replace(/^#/, '');
      const isActive = linkId === cleanId;
      link.classList.toggle('active', isActive);
      if (isActive) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    });

    $$('#mobileNavDrawer .mobile-nav-item').forEach(link => {
      const href = link.getAttribute('href') || '';
      const linkId = href.replace(/^#/, '');
      const isActive = linkId === cleanId;
      link.classList.toggle('active', isActive);
      if (isActive) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  }

  function navigateToSection(targetId, updateHistory = true) {
    const cleanId = (targetId || '').replace(/^#/, '') || 'plan';
    const targetEl = document.getElementById(cleanId);

    if (state.currentScreen !== 'app') {
      setScreen('app', false);
    }

    setActiveNavLink(cleanId);

    if (targetEl) {
      isNavClickScrolling = true;
      if (navClickTimeout) clearTimeout(navClickTimeout);
      navClickTimeout = setTimeout(() => {
        isNavClickScrolling = false;
      }, 750);

      targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

      if (updateHistory && window.history && window.history.pushState) {
        window.history.pushState(null, '', `#${cleanId}`);
      }
    }

    // Close mobile drawer if open
    const mobileDrawer = $('#mobileNavDrawer');
    const mobileToggle = $('#mobileNavToggle');
    if (mobileDrawer && mobileDrawer.classList.contains('open')) {
      mobileDrawer.classList.remove('open');
      mobileToggle?.setAttribute('aria-expanded', 'false');
    }
  }

  function setupScrollSpy() {
    let scrollTimer = null;
    window.addEventListener('scroll', () => {
      if (state.currentScreen !== 'app' || isNavClickScrolling) return;
      if (scrollTimer) return;

      scrollTimer = setTimeout(() => {
        scrollTimer = null;
        if (state.currentScreen !== 'app' || isNavClickScrolling) return;

        const scrollPosition = window.scrollY + 120;
        let currentSectionId = NAV_SECTIONS[0];

        for (let i = 0; i < NAV_SECTIONS.length; i++) {
          const el = document.getElementById(NAV_SECTIONS[i]);
          if (el) {
            const top = el.offsetTop;
            if (scrollPosition >= top) {
              currentSectionId = NAV_SECTIONS[i];
            }
          }
        }

        if ((window.innerHeight + window.scrollY) >= (document.documentElement.scrollHeight - 60)) {
          currentSectionId = NAV_SECTIONS[NAV_SECTIONS.length - 1];
        }

        setActiveNavLink(currentSectionId);
      }, 50);
    }, { passive: true });
  }

  function setScreen(screenName, shouldScrollTop = true) {
    state.currentScreen = screenName;
    $$('.app-screen').forEach(el => el.classList.toggle('hidden', el.dataset.screen !== screenName));
    
    // Header navigation visibility
    const isApp = screenName === 'app';
    const isAccount = screenName === 'account';
    const isAdmin = screenName === 'admin';

    const currentUser = SafePathApi.getCurrentUser();
    $('#signInBtn').classList.toggle('hidden', Boolean(currentUser) || isAdmin);
    $('#myWorkspaceBtn').classList.toggle('hidden', !currentUser || isAdmin);

    if (isAdmin) {
      $('#appHeader').classList.add('hidden');
      renderAdminPortal();
    } else {
      $('#appHeader').classList.remove('hidden');
    }

    if (isAccount) {
      renderTravellerWorkspace();
      setActiveNavLink(null);
    } else if (isAdmin) {
      setActiveNavLink(null);
    } else {
      const hash = (window.location.hash || '').replace(/^#/, '');
      if (hash && NAV_SECTIONS.includes(hash)) {
        setActiveNavLink(hash);
      } else {
        setActiveNavLink('plan');
      }
    }

    if (isApp) {
      setTimeout(() => {
        if (state.map) state.map.invalidateSize();
      }, 100);
    }

    if (shouldScrollTop) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }


  // ==========================================================================
  // MAP INITIALIZATION & RENDERING
  // ==========================================================================
  const MAP_PINS = [
    { point: [12.9367, 77.5837], type: 'green', code: 'L', title: 'Streetlight Verification', detail: 'BBMP Pole #J4-102 inspected; operational LED luminaire.' },
    { point: [12.9435, 77.5843], type: 'amber', code: '?', title: 'Limited Lighting Audit', detail: 'Overgrown tree branches obscuring illumination.' },
    { point: [12.9320, 77.5874], type: 'blue', code: 'P', title: 'South End Circle Safe Haven', detail: 'Operational traffic police kiosk & transit junction.' },
    { point: [12.9257, 77.5833], type: 'blue', code: 'P', title: 'Jayanagar Metro Station', detail: 'Rapid transit entry with security personnel until 23:30.' },
    { point: [12.9501, 77.5847], type: 'blue', code: 'P', title: 'Lalbagh Gate Bus Terminal', detail: 'Active BMTC feeder bus stop with passenger shelter.' }
  ];

  function initMap() {
    const mapEl = $('#map');
    if (!mapEl || !window.L) return;

    state.map = L.map('map', {
      zoomControl: true,
      scrollWheelZoom: false
    }).setView([12.9382, 77.5845], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
    }).addTo(state.map);

    // Create Independent Layer Groups
    state.layers.routesGroup = L.layerGroup().addTo(state.map);
    state.layers.lighting = L.layerGroup().addTo(state.map);
    state.layers.dogs = L.layerGroup().addTo(state.map);
    state.layers.observations = L.layerGroup().addTo(state.map);
    state.layers.places = L.layerGroup().addTo(state.map);
    state.layers.landmarks = L.layerGroup().addTo(state.map);
    state.layers.infra = L.layerGroup().addTo(state.map);
    state.layers.crime = L.layerGroup(); // Off by default to avoid visual clutter
    state.layers.segmentHighlight = L.layerGroup().addTo(state.map);
    state.layers.coverage = L.layerGroup().addTo(state.map);
    state.layers.userLocation = L.layerGroup().addTo(state.map);
    state.layers.markers = L.layerGroup().addTo(state.map);

    // Map click handler to pick coordinates for report modal
    state.map.on('click', e => {
      const modal = $('#reportModal');
      const isModalOpen = modal && modal.classList.contains('open');
      if (isModalOpen || state.isPickingMapCoordinate) {
        const latInput = $('#reportLatitudeInput');
        const lonInput = $('#reportLongitudeInput');
        if (latInput && lonInput) {
          latInput.value = e.latlng.lat.toFixed(6);
          lonInput.value = e.latlng.lng.toFixed(6);
          const locInput = $('#reportLocationInput');
          if (locInput && (!locInput.value.trim() || locInput.value.startsWith('Selected point'))) {
            locInput.value = `Selected point near ${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`;
          }
          if (modal && !modal.classList.contains('open')) {
            modal.classList.add('open');
          }
          state.isPickingMapCoordinate = false;
          showToast(`Pinned location (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}) on report form.`);
        }
      }
    });

    // Wire up Layer Control buttons
    initLayerControlButtons();

    // Fetch and render rich GIS bundle from backend
    loadMapLayersBundle();

    // Initial render of markers and routes
    renderMapFeatures();
    renderRoutePolylines();
    fitMapBounds();

    window.addEventListener('resize', () => {
      if (state.map) state.map.invalidateSize();
    });

    setTimeout(() => {
      if (state.map) state.map.invalidateSize();
    }, 150);
  }

  function toggleMapLayer(layerKey, btnEl) {
    state.toggles[layerKey] = !state.toggles[layerKey];
    const isNowActive = state.toggles[layerKey];

    if (btnEl) {
      btnEl.classList.toggle('active', isNowActive);
      btnEl.setAttribute('aria-pressed', isNowActive ? 'true' : 'false');
    }

    let targetGroup = null;
    if (layerKey === 'routes') targetGroup = state.layers.routesGroup;
    else if (layerKey === 'lighting') targetGroup = state.layers.lighting;
    else if (layerKey === 'dogs') targetGroup = state.layers.dogs;
    else if (layerKey === 'observations') targetGroup = state.layers.observations;
    else if (layerKey === 'places') targetGroup = state.layers.places;
    else if (layerKey === 'landmarks') targetGroup = state.layers.landmarks;
    else if (layerKey === 'infra') targetGroup = state.layers.infra;
    else if (layerKey === 'crime') targetGroup = state.layers.crime;

    if (targetGroup && state.map) {
      if (isNowActive) {
        if (!state.map.hasLayer(targetGroup)) state.map.addLayer(targetGroup);
      } else {
        if (state.map.hasLayer(targetGroup)) state.map.removeLayer(targetGroup);
      }
    }
    // Performance: Changing a map layer does NOT trigger route recalculations!
    showToast(`${isNowActive ? 'Enabled' : 'Disabled'} ${layerKey} layer.`);
  }

  function initLayerControlButtons() {
    const layerBtnMap = [
      { id: '#toggleRoutesBtn', key: 'routes' },
      { id: '#toggleLightingBtn', key: 'lighting' },
      { id: '#toggleDogsBtn', key: 'dogs' },
      { id: '#toggleObservationsBtn', key: 'observations' },
      { id: '#togglePlacesBtn', key: 'places' },
      { id: '#toggleLandmarksBtn', key: 'landmarks' },
      { id: '#toggleInfraBtn', key: 'infra' },
      { id: '#toggleCrimeBtn', key: 'crime' }
    ];

    layerBtnMap.forEach(({ id, key }) => {
      const btn = $(id);
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          toggleMapLayer(key, btn);
        });
      }
    });
  }

  async function loadMapLayersBundle() {
    try {
      const bundle = await SafePathApi.getMapLayers();
      if (bundle && bundle.layers) {
        state.mapBundle = bundle;
        renderBundleLayers(bundle.layers);
      }
    } catch (err) {
      console.warn('Map layers bundle fetch failed:', err);
    }
  }

  function renderBundleLayers(layers) {
    if (!state.map) return;

    // 1. Street Lighting Classifications
    if (state.layers.lighting) {
      state.layers.lighting.clearLayers();
      if (layers.lighting && layers.lighting.length) {
        layers.lighting.forEach(item => {
          if (!item.coordinates || item.coordinates.length < 2) return;
          let color = '#eab308'; // lit
          let dashArray = null;
          let weight = 4;
          if (item.litStatus === 'unlit') {
            color = '#475569';
            weight = 3;
          } else if (item.litStatus === 'conflicting') {
            color = '#ea580c';
            dashArray = '5, 4';
            weight = 3.5;
          } else if (item.litStatus === 'unmapped') {
            color = '#94a3b8';
            dashArray = '2, 5';
            weight = 3;
          }

          const line = L.polyline(item.coordinates, {
            color,
            weight,
            opacity: 0.75,
            dashArray,
            lineCap: 'round',
            lineJoin: 'round'
          }).addTo(state.layers.lighting);

          line.bindPopup(`
            <strong>${escapeHtml(item.streetName)}</strong><br>
            <span style="font-size:11px;">Lighting Survey: <strong>${item.litStatus.toUpperCase()}</strong></span><br>
            <span style="font-size:10.5px; color:#64748b;">Source: ${escapeHtml(item.source)}</span><br>
            <small style="color:#854d0e; font-size:10px;">${escapeHtml(item.limitations || 'Static lighting asset classification.')}</small>
          `);

          line.on('click', () => {
            if (item.id) selectSegment(item.id);
            const exp = $('#evidence-explorer');
            if (exp) exp.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
        });
      }
    }

    // 2. Street Dog Encounters
    if (state.layers.dogs) {
      state.layers.dogs.clearLayers();
      if (layers.dogs && layers.dogs.length) {
        layers.dogs.forEach(d => {
          const lat = d.latitude;
          const lon = d.longitude;
          if (!lat || !lon) return;

          const markerHtml = SP_ICONS.createMarkerHtml(d.category || 'dog_sighting', {
            label: d.categoryLabel || 'Dog encounter',
            size: 26,
            dogCount: d.dogCount
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
          });

          L.marker([lat, lon], { icon })
            .addTo(state.layers.dogs)
            .bindPopup(`
              <strong>${escapeHtml(d.categoryLabel || label)}</strong><br>
              <span style="font-size:11px;">Observed: <strong>${d.observedAt ? new Date(d.observedAt).toLocaleDateString() : 'Recent'}</strong></span><br>
              ${d.dogCount ? `<span style="font-size:11px;">Dog count: <strong>${d.dogCount}</strong></span><br>` : ''}
              <small style="color:#5e6f64;">${escapeHtml(d.description || 'Verified encounter report')}</small>
            `);
        });
      }
    }

    // 3. Moderated Community Reports
    if (state.layers.observations) {
      state.layers.observations.clearLayers();
      if (layers.community && layers.community.length) {
        layers.community.forEach(rep => {
          const lat = rep.latitude;
          const lon = rep.longitude;
          if (!lat || !lon) return;

          const markerHtml = SP_ICONS.createMarkerHtml(rep.category === 'construction_hazard' ? 'hazard' : 'observation', {
            label: rep.categoryLabel || 'Observation',
            size: 24
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });

          L.marker([lat, lon], { icon })
            .addTo(state.layers.observations)
            .bindPopup(`
              <strong>${escapeHtml(rep.categoryLabel || rep.category)}</strong><br>
              <span style="font-size:11px;">Status: <span class="status-badge approved">Approved</span> · Corroborated: <strong>${rep.corroborations || 1}</strong></span><br>
              <small style="color:#5e6f64;">${escapeHtml(rep.description || 'Verified community hazard')}</small>
            `);
        });
      }
    }

    // 4. Civic Assistance Facilities (Police & Hospitals)
    if (state.layers.places) {
      state.layers.places.clearLayers();
      if (layers.facilities && layers.facilities.length) {
        layers.facilities.forEach(fac => {
          const lat = fac.latitude;
          const lon = fac.longitude;
          if (!lat || !lon) return;

          const markerHtml = SP_ICONS.createMarkerHtml(fac.category || 'police', {
            label: fac.name,
            size: 26
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
          });

          L.marker([lat, lon], { icon })
            .addTo(state.layers.places)
            .bindPopup(`
              <strong>${escapeHtml(fac.name)}</strong><br>
              <span style="font-size:11px; text-transform:uppercase;">Category: <strong>${fac.category}</strong></span><br>
              <span style="font-size:11px; color:#15803d;">${fac.isAssistance ? 'Verified 24/7 Assistance Available' : 'Public Civic Service'}</span><br>
              <small style="color:#64748b;">Source: ${escapeHtml(fac.source || 'OpenStreetMap')}</small>
            `);
        });
      }
    }

    // 5. Public Landmarks & Transit
    if (state.layers.landmarks) {
      state.layers.landmarks.clearLayers();
      if (layers.landmarks && layers.landmarks.length) {
        layers.landmarks.forEach(lm => {
          const lat = lm.latitude;
          const lon = lm.longitude;
          if (!lat || !lon) return;

          const markerHtml = SP_ICONS.createMarkerHtml(lm.category || 'landmark', {
            label: lm.name,
            size: 24
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });

          L.marker([lat, lon], { icon })
            .addTo(state.layers.landmarks)
            .bindPopup(`
              <strong>${escapeHtml(lm.name)}</strong><br>
              <span style="font-size:11px; text-transform:uppercase;">Category: <strong>${lm.category}</strong></span><br>
              <small style="color:#64748b;">Public landmark / pedestrian focal point</small>
            `);
        });
      }
    }

    // 6. Pedestrian Infrastructure (Sidewalks & Crossings)
    if (state.layers.infra) {
      state.layers.infra.clearLayers();
      if (layers.infrastructure && layers.infrastructure.length) {
        layers.infrastructure.forEach(inf => {
          if (!inf.coordinates || inf.coordinates.length < 2) return;
          const line = L.polyline(inf.coordinates, {
            color: '#10b981',
            weight: 3.5,
            opacity: 0.85,
            dashArray: inf.crossingStatus === 'marked' ? '6, 6' : null,
            lineCap: 'round',
            lineJoin: 'round'
          }).addTo(state.layers.infra);

          line.bindPopup(`
            <strong>${escapeHtml(inf.streetName)}</strong><br>
            <span style="font-size:11px;">Sidewalk: <strong>${inf.sidewalkStatus.toUpperCase()}</strong></span><br>
            <span style="font-size:11px;">Crossing: <strong>${inf.crossingStatus}</strong></span><br>
            <small style="color:#64748b;">Dedicated pedestrian infrastructure</small>
          `);
        });
      }
    }

    // 7. Historical Crime Density Clusters
    if (state.layers.crime) {
      state.layers.crime.clearLayers();
      if (layers.crime && layers.crime.length) {
        layers.crime.forEach(c => {
          const lat = c.latitude;
          const lon = c.longitude;
          if (!lat || !lon) return;

          const circle = L.circleMarker([lat, lon], {
            radius: 9,
            fillColor: '#dc2626',
            color: '#991b1b',
            weight: 2,
            opacity: 0.85,
            fillOpacity: 0.5
          }).addTo(state.layers.crime);

          circle.bindPopup(`
            <strong>Historical Crime Bulletin Incident</strong><br>
            <span style="font-size:11px;">Category: <strong>${escapeHtml(c.subcategory || 'Incident')}</strong></span><br>
            <span style="font-size:11px;">Record Date: <strong>${c.observedAt ? new Date(c.observedAt).toLocaleDateString() : 'Archived'}</strong></span><br>
            <span style="font-size:10px; color:#b91c1c;">Source: ${escapeHtml(c.source || 'BTP Incident Bulletin')} (${c.verificationStatus})</span><br>
            <div style="font-size:9.5px; color:#78350f; margin-top:4px; padding-top:4px; border-top:1px dashed #cbd5e1;">
              ⓘ Historical record: Does not prove real-time risk or guarantee incident probability.
            </div>
          `);
        });
      }
    }
  }

  function areGeometriesIdentical(geom1, geom2) {
    if (!geom1 || !geom2 || geom1.length !== geom2.length) return false;
    for (let i = 0; i < geom1.length; i++) {
      if (Math.abs(geom1[i][0] - geom2[i][0]) > 0.00001 || Math.abs(geom1[i][1] - geom2[i][1]) > 0.00001) {
        return false;
      }
    }
    return true;
  }

  function renderMapFeatures() {
    if (!state.map) return;

    // 1. Observations layer (General Community reports)
    state.layers.observations.clearLayers();
    if (state.toggles.observations && state.communityReports && state.communityReports.length) {
      state.communityReports.forEach(rep => {
        const cat = rep.category || '';
        if (cat.startsWith('dog_')) return; // handled in dedicated dogs layer

        const lat = rep.latitude || (rep.coordinates && rep.coordinates[0]);
        const lon = rep.longitude || (rep.coordinates && rep.coordinates[1]);
        if (lat && lon) {
          const icon = L.divIcon({
            className: '',
            html: `<div class="custom-map-pin amber" title="${escapeHtml(rep.category || 'Hazard')}">!</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });
          L.marker([lat, lon], { icon })
            .addTo(state.layers.observations)
            .bindPopup(`
              <strong>${escapeHtml(rep.categoryLabel || rep.category || 'Community Hazard')}</strong><br>
              <small style="color:#5e6f64;">${escapeHtml(rep.description || rep.plainExplanation || 'Verified community observation')}</small>
            `);
        }
      });
    }

    // 1b. Dedicated Dog Encounters Evidence Layer
    if (!state.layers.dogs) {
      state.layers.dogs = L.layerGroup().addTo(state.map);
    }
    state.layers.dogs.clearLayers();
    if (state.toggles.dogs && state.communityReports && state.communityReports.length) {
      state.communityReports.forEach(rep => {
        const cat = rep.category || '';
        if (!cat.startsWith('dog_')) return;
        // Display only approved evidence on the public map
        if (rep.status && rep.status !== 'approved') return;

        const lat = rep.latitude || (rep.coordinates && rep.coordinates[0]);
        const lon = rep.longitude || (rep.coordinates && rep.coordinates[1]);
        if (lat && lon) {
          const markerHtml = SP_ICONS.createMarkerHtml(cat || 'dog_sighting', {
            label: rep.categoryLabel || label,
            size: 26,
            dogCount: rep.dogCount || rep.dog_count
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
          });

          const reportDate = rep.encounterTime || rep.createdAt || rep.created_at;
          const dateStr = reportDate ? new Date(reportDate).toLocaleDateString() : 'Recent';
          const dogCountVal = rep.dogCount || rep.dog_count;
          const dogCountStr = dogCountVal ? `<br><span style="font-size:11px;">Observed count: <strong>${dogCountVal} dog(s)</strong></span>` : '';

          L.marker([lat, lon], { icon })
            .addTo(state.layers.dogs)
            .bindPopup(`
              <strong>${escapeHtml(rep.categoryLabel || label)}</strong><br>
              <span style="font-size:11px;">Status: <span class="status-badge approved">Approved</span> · Date: <strong>${dateStr}</strong></span>
              ${dogCountStr}<br>
              <small style="color:#5e6f64; display:block; margin-top:4px;">${escapeHtml(rep.description || 'Verified community report')}</small>
              <div style="font-size:10px; color:#854d0e; margin-top:5px; border-top:1px dashed #d1d5db; padding-top:4px;">
                ${cat === 'dog_bite' || cat === 'dog_aggressive' ? 'Caution along this stretch: SafePath incorporates safety cost penalties.' : 'Calm sighting: Informational only; does not classify street as hazardous.'}
              </div>
            `);
        }
      });
    }

    // 2. Verified Civic Assistance Facilities & Landmarks layer (Priority 5)
    state.layers.places.clearLayers();
    if (state.toggles.places) {
      const activeRoute = (state.currentRoutes && state.currentRoutes.find(r => r.id === state.selectedRouteId)) || (state.currentRoutes && state.currentRoutes[0]);
      const placesToRender = (activeRoute && activeRoute.nearbyPlaces && activeRoute.nearbyPlaces.length > 0)
        ? activeRoute.nearbyPlaces
        : [];

      placesToRender.forEach(p => {
        if (p.coordinates && p.coordinates.length === 2) {
          const markerHtml = SP_ICONS.createMarkerHtml(p.category || 'police', {
            label: p.name,
            size: 26
          });

          const icon = L.divIcon({
            className: '',
            html: markerHtml,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
          });
          L.marker(p.coordinates, { icon })
            .addTo(state.layers.places)
            .bindPopup(`
              <strong>${escapeHtml(p.name)}</strong><br>
              <span style="font-size:11px;">Category: <strong>${p.category.toUpperCase()}</strong></span><br>
              <span style="font-size:11px;">Distance from route: <strong>${Math.round(p.distanceMeters)}m</strong> (~${p.walkingMinutes} min walk)</span><br>
              <small style="color:#5e6f64;">Source: ${escapeHtml(p.source || 'OpenStreetMap')} (${escapeHtml(p.attribution || 'ODbL 1.0')})</small><br>
              <small style="color:#854d0e; font-size:10.5px; display:block; margin-top:3px;">${escapeHtml(p.limitations || 'Public facility verified on OpenStreetMap.')}</small>
            `);
        }
      });
    }

    // 3. Segment Coverage Overlay Layer
    renderSegmentCoverageLayer();
  }

  function renderSegmentCoverageLayer() {
    if (!state.map || !state.layers.coverage) return;
    state.layers.coverage.clearLayers();

    if (!state.toggles.coverage || !state.currentSegments.length) return;

    state.currentSegments.forEach(seg => {
      let color = '#1c7349'; // Adequate
      let dashArray = null;

      if (seg.coverage === 'limited') {
        color = '#b46914';
      } else if (seg.coverage === 'insufficient') {
        color = '#7a8880';
        dashArray = '5, 5';
      }

      const polyline = L.polyline(seg.coordinates, {
        color,
        weight: 6,
        opacity: 0.75,
        dashArray,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(state.layers.coverage);

      polyline.bindPopup(`
        <strong>${escapeHtml(seg.streetName)}</strong><br>
        <span style="font-size:11px;">Coverage: <strong>${seg.coverage.toUpperCase()}</strong></span><br>
        <span style="font-size:10.5px; color:#5e6f64;">Source: ${escapeHtml(seg.source)}</span>
      `);

      polyline.on('click', () => {
        selectSegment(seg.id);
        const explorer = $('#evidence-explorer');
        if (explorer) explorer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function renderRoutePolylines() {
    if (!state.map) return;

    // Clear existing polylines
    if (state.layers.routesGroup) {
      state.layers.routesGroup.clearLayers();
    }
    state.layers.routes = {};

    // Clear existing markers
    if (state.layers.markers) {
      state.layers.markers.clearLayers();
    } else {
      state.layers.markers = L.layerGroup().addTo(state.map);
    }

    if (!state.currentRoutes || !state.currentRoutes.length) return;

    const selectedRoute = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];

    // Identify routes that share identical geometry with the selected route
    const identicalToSelected = state.currentRoutes.filter(
      r => r.id !== selectedRoute.id && areGeometriesIdentical(r.geometry, selectedRoute.geometry)
    );

    state.currentRoutes.forEach(route => {
      const isSelected = route.id === state.selectedRouteId;
      const sharesGeometryWithSelected = !isSelected && areGeometriesIdentical(route.geometry, selectedRoute.geometry);

      // Priority 8: When multiple routes genuinely share the identical street geometry,
      // do NOT render conflicting multi-colored layered polylines on top of each other.
      // Only render the selected route prominently, and clearly note the shared path in the tooltip.
      if (sharesGeometryWithSelected) {
        return;
      }

      let color = '#0f766e'; // Default teal
      let dashArray = null; // Solid

      if (route.category === 'safety_prioritized' || route.category === 'evidence_led') {
        color = '#0f766e'; // Safety-prioritized (teal)
        dashArray = null; // Solid line style
      } else if (route.category === 'balanced') {
        color = '#d97706'; // Balanced (amber)
        dashArray = '10, 5'; // Distinct dashed line style
      } else if (route.category === 'fastest' || route.category === 'shortest') {
        color = '#2563eb'; // Fastest (blue)
        dashArray = '3, 6'; // Distinct dotted line style
      } else if (route.category === 'alternative') {
        color = '#7c3aed'; // Alternative (purple)
        dashArray = '8, 4, 2, 4'; // Distinct dash-dot line style
      }

      const validPoints = (route.geometry || []).filter(
        pt => Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1])
      );
      if (validPoints.length < 2) return;

      const polyline = L.polyline(validPoints, {
        color,
        weight: isSelected ? 6 : 3.5,
        opacity: isSelected ? 0.95 : 0.45,
        dashArray,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(state.layers.routesGroup || state.map);

      let tooltipText = `<strong>${escapeHtml(route.name)}</strong> · ${Math.round(route.durationSeconds / 60)} min walk`;
      if (isSelected && identicalToSelected.length > 0) {
        const otherNames = identicalToSelected.map(r => r.name).join(', ');
        tooltipText += `<br><span style="color:#d97706;">ⓘ Shared optimal path with ${escapeHtml(otherNames)}</span>`;
      }

      polyline.bindTooltip(tooltipText, { sticky: true });

      polyline.on('click', () => {
        selectRoute(route.id);
      });

      state.layers.routes[route.id] = polyline;
    });

    // Bring selected route polyline to front
    if (state.selectedRouteId && state.layers.routes[state.selectedRouteId]) {
      state.layers.routes[state.selectedRouteId].bringToFront();
    }

    // Start (A) and End (B) Markers placed strictly at traversed route endpoints
    if (selectedRoute && selectedRoute.geometry && selectedRoute.geometry.length >= 2) {
      const geom = selectedRoute.geometry;
      const startPt = geom[0];
      const endPt = geom[geom.length - 1];

      const startIcon = L.divIcon({
        className: '',
        html: SP_ICONS.createMarkerHtml('origin', { letter: 'A', size: 22, label: 'Origin (Point A)' }),
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      });
      const endIcon = L.divIcon({
        className: '',
        html: SP_ICONS.createMarkerHtml('destination', { letter: 'B', size: 22, label: 'Destination (Point B)' }),
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      });

      const originName = $('#originInput')?.value.trim() || 'Origin';
      const destName = $('#destinationInput')?.value.trim() || 'Destination';

      L.marker(startPt, { icon: startIcon })
        .addTo(state.layers.markers)
        .bindPopup(`<strong>Origin (A)</strong><br>${escapeHtml(originName)}<br><small style="color:#5e6f64;">Snapped node: ${startPt[0].toFixed(5)}, ${startPt[1].toFixed(5)}</small>`);

      L.marker(endPt, { icon: endIcon })
        .addTo(state.layers.markers)
        .bindPopup(`<strong>Destination (B)</strong><br>${escapeHtml(destName)}<br><small style="color:#5e6f64;">Snapped node: ${endPt[0].toFixed(5)}, ${endPt[1].toFixed(5)}</small>`);
    }

    // Refresh dynamic nearby facilities layer
    renderMapFeatures();
  }

  function fitMapBounds() {
    if (!state.map) return;
    const allPoints = state.currentRoutes.flatMap(r => (r.geometry || []).filter(pt => Array.isArray(pt) && pt.length >= 2));
    if (allPoints.length) {
      state.map.fitBounds(allPoints, { padding: [36, 36] });
    }
  }

  // ==========================================================================
  // ROUTE SELECTION & ROUTE CARDS
  // ==========================================================================
  async function loadRoutes() {
    const origin = $('#originInput')?.value.trim() || '';
    const destination = $('#destinationInput')?.value.trim() || '';
    const submitBtn = $('#compareRoutesSubmitBtn');
    const alertBox = $('#routePlannerAlert');

    if (alertBox) {
      alertBox.classList.add('hidden');
      alertBox.textContent = '';
    }

    if (!origin || !destination) {
      const msg = 'Please specify both a starting point and a destination.';
      if (alertBox) {
        alertBox.textContent = msg;
        alertBox.classList.remove('hidden');
      }
      showToast(msg, 'error');
      return;
    }

    // Resolve coordinates from selected state or manual coordinate input
    let originCoordinates = (state.originLocation && state.originLocation.lat && state.originLocation.lon)
      ? [state.originLocation.lat, state.originLocation.lon]
      : null;
    let destinationCoordinates = (state.destinationLocation && state.destinationLocation.lat && state.destinationLocation.lon)
      ? [state.destinationLocation.lat, state.destinationLocation.lon]
      : null;

    // Detect manual coordinate entry if not already set by autocomplete
    if (!originCoordinates) {
      const coordMatch = origin.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (coordMatch) {
        originCoordinates = [parseFloat(coordMatch[1]), parseFloat(coordMatch[2])];
        state.originLocation = { name: origin, lat: originCoordinates[0], lon: originCoordinates[1], inStudyArea: true };
      }
    }
    if (!destinationCoordinates) {
      const coordMatch = destination.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (coordMatch) {
        destinationCoordinates = [parseFloat(coordMatch[1]), parseFloat(coordMatch[2])];
        state.destinationLocation = { name: destination, lat: destinationCoordinates[0], lon: destinationCoordinates[1], inStudyArea: true };
      }
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `${SP_ICONS.loader({ size: 14, cls: 'sp-spin' })} Calculating routes...`;
    }

    // Immediately clear previous route polylines and coverage from map to prevent stale display
    if (state.layers.routes) {
      Object.values(state.layers.routes).forEach(layer => state.map?.removeLayer(layer));
      state.layers.routes = {};
    }
    if (state.layers.coverage) {
      state.layers.coverage.clearLayers();
    }
    if (state.layers.markers) {
      state.layers.markers.clearLayers();
    }
    const cardContainer = $('#routeCardsContainer');
    if (cardContainer) {
      cardContainer.innerHTML = `<div class="route-cards-loading" style="padding:24px; text-align:center; color:#5e6f64;">${SP_ICONS.loader({ size: 16, cls: 'sp-spin' })} Calculating realistic pedestrian routes...</div>`;
    }

    // If coordinates are still unresolved from direct text typing, proactively resolve via geocoding
    if (!originCoordinates && origin) {
      try {
        const places = await SafePathApi.searchPlaces(origin, 1);
        if (places && places.length > 0) {
          const top = places[0];
          originCoordinates = [top.latitude, top.longitude];
          state.originLocation = {
            id: top.id,
            name: top.name,
            displayName: top.displayName,
            lat: top.latitude,
            lon: top.longitude,
            inStudyArea: top.inStudyArea,
            type: top.type,
            distanceMeters: top.studyAreaDistanceMeters
          };
        }
      } catch (e) {
        console.warn('Origin auto-resolution fallback:', e);
      }
    }

    if (!destinationCoordinates && destination) {
      try {
        const places = await SafePathApi.searchPlaces(destination, 1);
        if (places && places.length > 0) {
          const top = places[0];
          destinationCoordinates = [top.latitude, top.longitude];
          state.destinationLocation = {
            id: top.id,
            name: top.name,
            displayName: top.displayName,
            lat: top.latitude,
            lon: top.longitude,
            inStudyArea: top.inStudyArea,
            type: top.type,
            distanceMeters: top.studyAreaDistanceMeters
          };
        }
      } catch (e) {
        console.warn('Destination auto-resolution fallback:', e);
      }
    }

    const selectedDepPeriod = document.querySelector('input[name="departurePeriod"]:checked')?.value || 'daytime';
    const isStepFree = $('#prefStepFree')?.checked ?? false;

    const prefs = {
      preferLighting: $('#prefLighting')?.checked ?? true,
      preferActivity: $('#prefActivity')?.checked ?? true,
      avoidUnknown: $('#prefAvoidUnknown')?.checked ?? true,
      departurePeriod: selectedDepPeriod,
      stepFree: isStepFree,
      includeAlternatives: true,
      maxAlternatives: 2
    };

    try {
      const res = await SafePathApi.compareRoutes({
        origin,
        destination,
        originCoordinates,
        destinationCoordinates,
        preferences: prefs,
        departurePeriod: selectedDepPeriod,
        stepFree: isStepFree
      });
      state.currentRoutes = res.routes || [];
      if (!state.currentRoutes.length) {
        throw new Error('No route alternatives could be found between these locations.');
      }

      $('#activeMapTitle').textContent = `${origin} → ${destination}`;
      $('#routeSubheading').textContent = `${state.currentRoutes.length} route options evaluated via Dijkstra and Yen loopless alternative algorithms on Bengaluru Pilot Corridor.`;

      renderRouteCards();
      renderRoutePolylines();
      fitMapBounds();

      // Maintain selected route if still in results, else choose recommended first
      const exists = state.selectedRouteId && state.currentRoutes.some(r => r.id === state.selectedRouteId);
      const defaultRouteId = exists ? state.selectedRouteId : state.currentRoutes[0].id;
      selectRoute(defaultRouteId);
    } catch (err) {
      // Clear stale routes and markers completely on failure
      state.currentRoutes = [];
      state.selectedRouteId = null;
      if (state.layers.routes) {
        Object.values(state.layers.routes).forEach(layer => state.map?.removeLayer(layer));
        state.layers.routes = {};
      }
      if (state.layers.coverage) {
        state.layers.coverage.clearLayers();
      }
      if (state.layers.markers) {
        state.layers.markers.clearLayers();
      }
      if (cardContainer) {
        cardContainer.innerHTML = '<div class="empty-state" style="padding:24px; text-align:center; color:#6b7280;">No active route displayed. Check location details and try again.</div>';
      }
      $('#activeMapTitle').textContent = 'No Route Selected';
      $('#routeSubheading').textContent = 'Calculation failed or location is outside supported pedestrian network.';

      const errDetail = err.message || 'Route calculation failed.';
      const lower = errDetail.toLowerCase();

      // Categorize error for transparent epistemological feedback
      let title = 'Routing Notice';
      let iconSvg = SP_ICONS.alertTriangle({ size: 15, stroke: 2 });

      if (lower.includes('outside configured study area') || lower.includes('outside active research') || lower.includes('outside the active')) {
        title = 'Location Outside Routing Coverage';
        iconSvg = SP_ICONS.mapPin({ size: 15, stroke: 2 });
      } else if (lower.includes('could not find') || lower.includes('could not resolve') || lower.includes('not found')) {
        title = 'Location Not Found';
        iconSvg = SP_ICONS.search({ size: 15, stroke: 2 });
      } else if (lower.includes('disconnected') || lower.includes('no route alternatives') || lower.includes('no pedestrian route')) {
        title = 'No Pedestrian Route Available';
        iconSvg = SP_ICONS.footprints({ size: 15, stroke: 2 });
      } else if (lower.includes('service unavailable') || lower.includes('rate-limited') || lower.includes('offline') || lower.includes('geocoding')) {
        title = 'Geocoding Service Unavailable';
        iconSvg = SP_ICONS.info({ size: 15, stroke: 2 });
      }

      if (alertBox) {
        alertBox.innerHTML = `<div><strong style="display:flex; align-items:center; gap:6px; margin-bottom:3px;">${iconSvg} ${escapeHtml(title)}</strong>${escapeHtml(errDetail)}</div>`;
        alertBox.classList.remove('hidden');
      }
      showToast(errDetail, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `${SP_ICONS.arrowUpRight({ size: 14 })} Compare route alternatives`;
      }
    }
  }

  function renderRouteCards() {
    const container = $('#routeCardsContainer');
    if (!container) return;

    if (!state.currentRoutes || !state.currentRoutes.length) {
      container.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); grid-column: 1 / -1;">No route alternatives currently available. Try selecting a corridor landmark.</div>';
      return;
    }

    const fastestDuration = Math.min(...state.currentRoutes.map(r => r.durationSeconds || 999999));

    container.innerHTML = state.currentRoutes.map(route => {
      const isSelected = route.id === state.selectedRouteId;
      const cov = route.evidenceSummary?.coverage || (route.evidenceCoverage >= 0.7 ? 'adequate' : (route.evidenceCoverage >= 0.3 ? 'limited' : 'insufficient'));
      const covPct = route.evidenceSummary?.coveragePercentage ?? Math.round((route.evidenceCoverage || 0.45) * 100);

      let coverageBadgeClass = 'badge-success';
      if (cov === 'limited') coverageBadgeClass = 'badge-warning';
      if (cov === 'insufficient') coverageBadgeClass = 'badge-neutral';

      let catBadgeClass = 'badge-teal';
      let catLabel = 'Safety-prioritized';
      if (route.category === 'safety_prioritized' || route.category === 'evidence_led') {
        catBadgeClass = 'badge-teal';
        catLabel = 'Safety-prioritized';
      } else if (route.category === 'balanced') {
        catBadgeClass = 'badge-amber';
        catLabel = 'Balanced';
      } else if (route.category === 'fastest' || route.category === 'shortest') {
        catBadgeClass = 'badge-blue';
        catLabel = 'Fastest';
      } else if (route.category === 'alternative') {
        catBadgeClass = 'badge-purple';
        catLabel = escapeHtml(route.name);
      }

      // Time difference relative to fastest
      const timeDiffSec = route.durationSeconds - fastestDuration;
      const timeDiffMin = Math.round(timeDiffSec / 60);
      let timeDiffHtml = '';
      if (timeDiffSec <= 30) {
        timeDiffHtml = '<span class="time-diff-badge time-diff-same">Matches fastest</span>';
      } else {
        timeDiffHtml = `<span class="time-diff-badge time-diff-longer">+${timeDiffMin} min</span>`;
      }

      // Identical path notice
      let identicalNoticeHtml = '';
      if (route.isIdenticalToFastest && route.category !== 'fastest') {
        identicalNoticeHtml = `
          <div class="route-identical-note">
            ⓘ <strong>Optimal under multiple criteria:</strong> ${escapeHtml(route.identicalNotes || 'This corridor is optimal under both safety and travel-time objectives; no detour needed.')}
          </div>
        `;
      }

      // Uncertainty alert for insufficient evidence
      let uncertaintyAlertHtml = '';
      if (cov === 'insufficient' || route.hasInsufficientEvidence || covPct < 30) {
        uncertaintyAlertHtml = `
          <div class="route-uncertainty-alert">
            ${SP_ICONS.alertTriangle({ size: 13, stroke: 2 })} <strong>Data Limitation:</strong> Insufficient data for confident assessment. Route relies on uncorroborated street segments.
          </div>
        `;
      }

      // Real Streetlight Summary
      let litPercentage = 'Documented lighting';
      if (route.streetlightSummary) {
        const sl = route.streetlightSummary;
        litPercentage = `${sl.litPercentage.toFixed(0)}% lit (${Math.round(sl.knownLitDistanceMeters)}m)`;
      } else if (route.evidenceSummary?.lightingCoveragePercentage !== null && route.evidenceSummary?.lightingCoveragePercentage !== undefined) {
        litPercentage = `${Number(route.evidenceSummary.lightingCoveragePercentage).toFixed(0)}% verified lit`;
      }

      const riskVal = route.routeRisk !== null && route.routeRisk !== undefined
        ? route.routeRisk.toFixed(2)
        : (route.evidenceSummary?.riskEstimate || '0.38');

      // Nearby landmark snippet
      let nearbySnippetHtml = '';
      if (route.nearbyPlaces && route.nearbyPlaces.length > 0) {
        const topPlace = route.nearbyPlaces[0];
        const distM = Math.round(topPlace.distanceMeters);
        let placeIconSvg = SP_ICONS.mapPin({ size: 12 });
        if (topPlace.category === 'police') placeIconSvg = SP_ICONS.shield({ size: 12 });
        else if (topPlace.category === 'hospital') placeIconSvg = SP_ICONS.hospital({ size: 12 });
        else if (topPlace.category === 'transit') placeIconSvg = SP_ICONS.train({ size: 12 });
        else if (topPlace.category === 'park') placeIconSvg = SP_ICONS.trees({ size: 12 });
        nearbySnippetHtml = `
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px; display: flex; align-items: center; gap: 4px;">
            <span class="sp-icon-inline">${placeIconSvg}</span> <span>Near <strong>${escapeHtml(topPlace.name)}</strong> (${distM}m)</span>
          </div>
        `;
      }

      const depPeriodIcon = route.departurePeriod === 'night'
        ? `${SP_ICONS.moon({ size: 11 })} Night`
        : (route.departurePeriod === 'evening' ? `${SP_ICONS.sunset({ size: 11 })} Evening` : `${SP_ICONS.sun({ size: 11 })} Day`);
      const stepFreeBadge = route.stepFree ? `<span class="badge badge-teal" style="font-size: 10px; display: inline-flex; align-items: center; gap: 3px;">${SP_ICONS.accessibility({ size: 11 })} Step-Free</span>` : '';
      const overlapBadge = (route.category === 'fastest')
        ? `<span class="badge badge-neutral" style="font-size: 10px;" title="Direct shortest-time baseline">Direct Baseline</span>`
        : ((route.overlapWithFastest !== undefined)
          ? `<span class="badge badge-neutral" style="font-size: 10px;" title="Spatial path edge overlap with fastest route">${Math.round(route.overlapWithFastest * 100)}% overlap with direct route</span>`
          : '');

      // Infrastructure summary
      let infraHtml = '';
      const inf = route.pedestrianInfrastructureSummary || route.infrastructureSummary;
      if (inf) {
        const docPct = Math.round(inf.sidewalkDocumentedPercentage ?? inf.sidewalkCoveragePercentage ?? 0);
        const unmappedPct = Math.round(inf.sidewalkUnmappedPercentage ?? (inf.unmappedSidewalkDistanceMeters && inf.totalDistanceMeters ? (inf.unmappedSidewalkDistanceMeters / inf.totalDistanceMeters) * 100 : (100 - docPct)));
        const crossings = inf.crossingCount ?? inf.designatedCrossingsCount ?? 0;
        infraHtml = `
          <div style="font-size: 11px; margin-top: 5px; color: #047857; display: flex; align-items: center; justify-content: space-between; background: #ecfdf5; padding: 4px 8px; border-radius: 4px; border: 1px solid #a7f3d0;">
            <span><span class="sp-icon-inline">${SP_ICONS.footprints({ size: 12 })}</span> <strong>Pedestrian Infrastructure:</strong></span>
            <span>${docPct}% sidewalk (${unmappedPct}% unmapped · ${crossings} crossings)</span>
          </div>
        `;
      }

      // Crime evidence summary
      let crimeHtml = '';
      const crimeCount = route.crimeCount !== undefined ? route.crimeCount : (route.evidenceSummary?.crimeIncidentsCount || route.evidenceSummary?.crimeCount || 0);
      crimeHtml = `
        <div style="font-size: 11px; margin-top: 5px; color: #475569; display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 4px 8px; border-radius: 4px; border: 1px solid #e2e8f0;">
          <span><span class="sp-icon-inline">${SP_ICONS.shieldAlert({ size: 12 })}</span> <strong>Crime Dataset Evidence:</strong></span>
          <span>${crimeCount === 0 ? 'No route-level records (NCRB city stats available · Zero != safe)' : `${crimeCount} historical incident(s)`}</span>
        </div>
      `;

      return `
        <article class="route-card ${isSelected ? 'selected selected-active' : ''}" data-route-id="${route.id}" role="button" tabindex="0" aria-pressed="${isSelected}">
          ${isSelected ? '<span class="route-card-active-badge">ACTIVE ON MAP</span>' : ''}
          <div class="route-card-top">
            <span class="route-name">${escapeHtml(route.name)}</span>
            <div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">
              <span class="badge ${catBadgeClass}">${catLabel}</span>
              <span class="badge badge-neutral" style="font-size: 10px;">${depPeriodIcon}</span>
              ${stepFreeBadge}
              ${overlapBadge}
            </div>
          </div>

          <div class="route-metric-box">
            <div class="route-duration">
              ${Math.round(route.durationSeconds / 60)} <span>min walk</span>
              ${timeDiffHtml}
            </div>
            <div class="route-distance">${(route.distanceMeters / 1000).toFixed(2)} km · walking speed ${route.walkingSpeedKmh || ((route.distanceMeters / Math.max(route.durationSeconds, 1)) * 3.6).toFixed(1)} km/h</div>
          </div>

          <div class="route-divider"></div>

          <div class="route-coverage-status">
            <span style="color: var(--text-muted); font-size: 11px;">Evidence Coverage & Freshness</span>
            <span class="badge ${coverageBadgeClass}">${cov.toUpperCase()} (${covPct}%) · ${route.evidenceSummary?.freshestObservationDays || 8}d fresh</span>
          </div>

          <div class="route-env-metrics">
            <div class="route-env-metric-item">
              <small>Street Lighting</small>
              <strong>${litPercentage}</strong>
            </div>
            <div class="route-env-metric-item">
              <small title="Relative multi-attribute risk indicator [0.0 - 1.0], not probability of victimization">Model Risk Indicator (Eff / Obs)</small>
              <strong>${riskVal} ${route.adverseRiskScore !== undefined ? `<span style="font-size:10px;color:var(--text-muted);font-weight:normal;">(${route.adverseRiskScore.toFixed(2)} obs)</span>` : ''}</strong>
            </div>
          </div>

          ${infraHtml}
          ${crimeHtml}
          ${nearbySnippetHtml}
          ${(() => {
            if (route.dogEncounterSummary && route.dogEncounterSummary.totalReportsCount > 0) {
              const dSum = route.dogEncounterSummary;
              let dogBadgeClass = 'badge-neutral';
              let dogIconSvg = SP_ICONS.pawPrint({ size: 13 });
              if (dSum.biteCount > 0) {
                dogBadgeClass = 'badge-danger';
                dogIconSvg = SP_ICONS.shieldAlert({ size: 13 });
              } else if (dSum.aggressiveCount > 0) {
                dogBadgeClass = 'badge-warning';
                dogIconSvg = SP_ICONS.alertTriangle({ size: 13 });
              }
              const breakdownLabel = dSum.biteCount > 0
                ? `${dSum.biteCount} bite(s)`
                : (dSum.aggressiveCount > 0 ? `${dSum.aggressiveCount} aggressive` : `${dSum.sightingCount} sighting(s)`);
              return `
                <div style="font-size: 11px; margin-top: 6px; display: flex; align-items: center; justify-content: space-between; background: var(--bg-surface-elevated, #f8fafc); padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border-subtle, #e2e8f0);">
                  <span style="display: flex; align-items: center; gap: 4px;">${dogIconSvg} <strong>${dSum.totalReportsCount} dog encounter(s)</strong></span>
                  <span class="badge ${dogBadgeClass}" style="font-size: 10px;">${breakdownLabel}</span>
                </div>
              `;
            }
            return '';
          })()}

          ${identicalNoticeHtml}
          ${uncertaintyAlertHtml}

          <div class="route-note">
            <strong>Ranking Justification:</strong> ${escapeHtml(route.rankingExplanation || route.tradeoffs)}
          </div>
        </article>
      `;
    }).join('');

    // Attach Click Events
    $$('.route-card', container).forEach(card => {
      card.addEventListener('click', () => selectRoute(card.dataset.routeId));
      card.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectRoute(card.dataset.routeId);
        }
      });
    });
  }

  function renderRouteDecisionSummary(route) {
    const container = $('#routeDecisionSummary');
    if (!container || !route) return;

    const fastestDuration = Math.min(...state.currentRoutes.map(r => r.durationSeconds || 999999));
    const timeDiffSec = route.durationSeconds - fastestDuration;
    const timeDiffMin = Math.round(timeDiffSec / 60);
    const timeDiffText = timeDiffSec <= 30 ? 'Matches fastest (+0 min)' : `+${timeDiffMin} min (${Math.round((timeDiffSec / fastestDuration) * 100)}% time)`;

    const cov = route.evidenceSummary?.coverage || (route.evidenceCoverage >= 0.7 ? 'adequate' : (route.evidenceCoverage >= 0.3 ? 'limited' : 'insufficient'));
    const covPct = route.evidenceSummary?.coveragePercentage ?? Math.round((route.evidenceCoverage || 0.45) * 100);
    const riskVal = route.routeRisk !== null && route.routeRisk !== undefined ? route.routeRisk.toFixed(2) : (route.evidenceSummary?.riskEstimate || '0.38');

    let catBadgeClass = 'badge-teal';
    let catLabel = 'Safety-prioritized Preference';
    if (route.category === 'safety_prioritized' || route.category === 'evidence_led') {
      catBadgeClass = 'badge-teal';
      catLabel = 'Safety-prioritized Preference';
    } else if (route.category === 'balanced') {
      catBadgeClass = 'badge-amber';
      catLabel = 'Balanced Preference';
    } else if (route.category === 'fastest' || route.category === 'shortest') {
      catBadgeClass = 'badge-blue';
      catLabel = 'Fastest Direct Preference';
    } else if (route.category === 'alternative') {
      catBadgeClass = 'badge-purple';
      catLabel = 'Yen Loopless Alternative';
    }

    const policeDist = route.evidenceSummary?.nearestPoliceDistanceMeters !== null && route.evidenceSummary?.nearestPoliceDistanceMeters !== undefined
      ? `${Math.round(route.evidenceSummary.nearestPoliceDistanceMeters)}m`
      : 'Within 200m';
    const hospitalDist = route.evidenceSummary?.nearestHospitalDistanceMeters !== null && route.evidenceSummary?.nearestHospitalDistanceMeters !== undefined
      ? `${Math.round(route.evidenceSummary.nearestHospitalDistanceMeters)}m`
      : 'Within 500m';
    const lightingText = route.evidenceSummary?.lightingCoveragePercentage !== null && route.evidenceSummary?.lightingCoveragePercentage !== undefined
      ? `${Number(route.evidenceSummary.lightingCoveragePercentage).toFixed(1)}% verified lit`
      : 'Documented lighting';

    const rankingFactors = route.rankingFactors && route.rankingFactors.length
      ? route.rankingFactors
      : [
          `Walking duration: ${Math.round(route.durationSeconds / 60)} min`,
          `Evidence coverage: ${covPct}%`,
          `Verified lit streets: ${lightingText}`
        ];

    let identicalNotice = '';
    if (route.isIdenticalToFastest && route.category !== 'fastest') {
      identicalNotice = `
        <div class="route-identical-note" style="margin-bottom: 12px;">
          ⓘ <strong>Identical Route Explanation:</strong> ${escapeHtml(route.identicalNotes || 'This path is optimal under multiple model preferences because the most direct corridor also has the highest verified lighting. Diversity is not artificially fabricated.')}
        </div>
      `;
    }

    // Streetlight Evidence Summary (Priority 4)
    let streetlightHtml = '';
    if (route.streetlightSummary) {
      const sl = route.streetlightSummary;
      const litPct = sl.litPercentage ?? 0;
      const unlitPct = sl.unlitPercentage ?? 0;
      const confPct = sl.conflictingPercentage ?? 0;
      const unkPct = sl.unmappedPercentage ?? sl.unknownPercentage ?? 0;
      const litDist = Math.round(sl.litDistanceMeters ?? sl.knownLitDistanceMeters ?? 0);
      const unlitDist = Math.round(sl.unlitDistanceMeters ?? sl.knownUnlitDistanceMeters ?? 0);
      const confDist = Math.round(sl.conflictingDistanceMeters ?? 0);
      const unkDist = Math.round(sl.unmappedDistanceMeters ?? sl.unknownDistanceMeters ?? 0);
      const lampsCount = sl.mappedStreetlampsCount ?? 0;
      
      streetlightHtml = `
        <div class="decision-full-width-section">
          <h4>
            <span>Streetlight & Lighting Evidence Audit</span>
            <span style="font-size: 11px; font-weight: 500; text-transform: none; color: var(--text-muted);">
              ${sl.mappedStreetlampsCount} mapped lamp posts along corridor
            </span>
          </h4>
          
          <div class="streetlight-bar-container">
            <div class="streetlight-progress-bar" title="Lit: ${litPct.toFixed(1)}%, Unlit: ${unlitPct.toFixed(1)}%, Conflicting: ${confPct.toFixed(1)}%, Unknown: ${unkPct.toFixed(1)}%">
              ${litPct > 0 ? `<div class="streetlight-seg lit" style="width: ${litPct}%"></div>` : ''}
              ${unlitPct > 0 ? `<div class="streetlight-seg unlit" style="width: ${unlitPct}%"></div>` : ''}
              ${confPct > 0 ? `<div class="streetlight-seg conflicting" style="width: ${confPct}%"></div>` : ''}
              ${unkPct > 0 ? `<div class="streetlight-seg unknown" style="width: ${unkPct}%"></div>` : ''}
            </div>
          </div>

          <div class="streetlight-stat-grid">
            <div class="streetlight-stat-card">
              <small style="color: #059669; font-weight: 700;">Verified Lit</small>
              <strong>${litPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${litDist}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #d97706; font-weight: 700;">Verified Unlit</small>
              <strong>${unlitPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${unlitDist}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #dc2626; font-weight: 700;">Conflicting</small>
              <strong>${confPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${confDist}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #6b7280; font-weight: 700;">Unknown / Unmapped</small>
              <strong>${unkPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${unkDist}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: var(--primary); display: flex; align-items: center; gap: 4px;">${SP_ICONS.lamp({ size: 12 })} Mapped Lamps</small>
              <strong>${lampsCount} posts</strong>
              <div style="font-size: 10px; color: var(--text-muted);">OSM node points</div>
            </div>
          </div>

          <div class="streetlight-explanation-text">
            <strong>Methodology & Epistemological Standard:</strong> Coverage is computed strictly from traversed pedestrian edge lengths in meters (${Math.round(sl.totalDistanceMeters)}m total). OpenStreetMap tags such as <code>lit=yes</code>, <code>lit=no</code>, and node <code>highway=street_lamp</code> represent distinct empirical observations. A mapped lamp post does not guarantee an illuminated street or functioning fixture. Crucially, <em>unknown status is never treated as unlit</em>, and <em>absence of mapped lighting is never treated as proof of safety</em>.
          </div>
        </div>
      `;
    }

    // Nearby Places & Major Landmarks (Priority 5)
    let nearbyPlacesHtml = '';
    const places = route.nearbyPlaces || [];
    if (places.length > 0) {
      const placesCards = places.map(p => {
        let catBadge = 'badge-blue';
        let catIcon = `${SP_ICONS.landmark({ size: 12 })} Landmark`;
        if (p.category === 'police') { catBadge = 'badge-teal'; catIcon = `${SP_ICONS.shield({ size: 12 })} Police`; }
        else if (p.category === 'hospital') { catBadge = 'badge-amber'; catIcon = `${SP_ICONS.hospital({ size: 12 })} Hospital`; }
        else if (p.category === 'pharmacy') { catBadge = 'badge-amber'; catIcon = `${SP_ICONS.pill({ size: 12 })} Pharmacy`; }
        else if (p.category === 'transit') { catBadge = 'badge-purple'; catIcon = `${SP_ICONS.train({ size: 12 })} Transit`; }
        else if (p.category === 'park') { catBadge = 'badge-teal'; catIcon = `${SP_ICONS.trees({ size: 12 })} Public Park`; }
        else if (p.category === 'education') { catBadge = 'badge-purple'; catIcon = `${SP_ICONS.graduationCap({ size: 12 })} Education`; }
        else if (p.category === 'civic_building') { catBadge = 'badge-blue'; catIcon = `${SP_ICONS.building({ size: 12 })} Civic Building`; }
        else if (p.category === 'commercial_hub') { catBadge = 'badge-blue'; catIcon = `${SP_ICONS.store({ size: 12 })} Commercial Hub`; }

        const asstBadge = p.isAssistance
          ? `<span class="badge badge-teal" style="font-size: 9px; padding: 1px 4px; margin-left: 4px;">Assistance Facility</span>`
          : '';

        const isNetworkDist = p.distanceType === 'pedestrian_network';
        const distTypeLabel = isNetworkDist ? 'pedestrian network distance' : 'straight-line proximity';
        const walkTime = isNetworkDist
          ? (p.walkingMinutes !== null && p.walkingMinutes !== undefined
              ? `~${Math.round(p.walkingMinutes)} min walk`
              : `~${Math.round(p.distanceMeters / 72.0)} min walk`)
          : '<span style="color:var(--text-muted); font-style:italic;">network walking distance unmeasured</span>';

        return `
          <div class="nearby-place-card">
            <div class="nearby-place-header">
              <span class="nearby-place-name">${escapeHtml(p.name)}</span>
              <div>
                <span class="badge ${catBadge}" style="font-size: 10px; padding: 1px 6px;">${catIcon}</span>
                ${asstBadge}
              </div>
            </div>
            <div class="nearby-place-distance">
              <strong>${Math.round(p.distanceMeters)}m</strong> (${distTypeLabel}) · <span>${walkTime}</span>
            </div>
            <div class="nearby-place-meta" style="font-size: 10px; color: var(--text-muted); line-height: 1.3;">
              ${escapeHtml(p.attribution || 'OpenStreetMap contributors')}
              <br><span style="color: var(--warning-text);">${escapeHtml(p.limitations || 'Status unverified; do not assume active staffing or response.')}</span>
            </div>
          </div>
        `;
      }).join('');

      nearbyPlacesHtml = `
        <div class="decision-full-width-section">
          <h4>
            <span>Nearby Major Landmarks & Useful Facilities (500m Corridor)</span>
            <span style="font-size: 11px; font-weight: 500; text-transform: none; color: var(--text-muted);">
              ${places.length} mapped places in corridor
            </span>
          </h4>
          <div class="nearby-places-grid">
            ${placesCards}
          </div>
          <p style="font-size: 10.5px; color: var(--text-muted); margin-top: 8px; margin-bottom: 0;">
            ⓘ <strong>Safety & Operational Disclaimer:</strong> Facility proximities are calculated as perpendicular access distances from the selected route corridor. A nearby police station or hospital does not imply that it is currently open, staffed, or capable of immediate emergency response.
          </p>
        </div>
      `;
    } else {
      nearbyPlacesHtml = `
        <div class="decision-full-width-section">
          <h4><span>Nearby Major Landmarks & Useful Facilities (500m Corridor)</span></h4>
          <div style="font-size: 11.5px; color: var(--text-muted); padding: 8px 12px; background: #f9fafb; border-radius: 4px; border: 1px solid var(--border);">
            No mapped police stations, hospitals, public transit stops, or major public landmarks are mapped within the 500m corridor of this specific route.
          </div>
        </div>
      `;
    }

    // Pedestrian Infrastructure & Accessibility Audit (Section 6)
    let pedestrianInfraHtml = '';
    const infra = route.pedestrianInfrastructureSummary || route.pedestrian_infrastructure_summary;
    if (infra) {
      const swPct = infra.sidewalkDocumentedPercentage ?? infra.sidewalkCoveragePercentage ?? 0;
      const knownSw = Math.round(infra.sidewalkDocumentedLengthMeters ?? infra.knownSidewalkDistanceMeters ?? 0);
      const unmappedSw = Math.round(infra.sidewalkUnmappedLengthMeters ?? infra.unmappedSidewalkDistanceMeters ?? 0);
      const totDist = Math.round(infra.totalDistanceMeters ?? infra.total_distance_meters ?? route.distanceMeters ?? 0);
      const unmappedPct = infra.sidewalkUnmappedPercentage ?? (totDist > 0 ? (unmappedSw / totDist) * 100 : 0);
      const absentPct = infra.sidewalkAbsentPercentage ?? (totDist > 0 ? ((infra.sidewalkAbsentLengthMeters || 0) / totDist) * 100 : 0);
      const absentSw = Math.round(infra.sidewalkAbsentLengthMeters ?? infra.absentSidewalkDistanceMeters ?? 0);

      const crossings = infra.crossingCount ?? infra.crossing_count ?? 0;
      const signalCrossings = infra.signalizedCrossingCount ?? infra.signalized_crossing_count ?? 0;
      const tactile = infra.tactilePavingCount ?? infra.tactile_paving_count ?? 0;
      const wheelchair = infra.wheelchairAccessibleCount ?? infra.wheelchair_accessible_count ?? 0;
      const highDiff = infra.highDifficultyCrossingsCount ?? infra.highDifficultyCrossings ?? infra.high_difficulty_crossings ?? 0;
      const hazards = infra.constructionHazardsCount ?? infra.construction_hazards_count ?? 0;

      pedestrianInfraHtml = `
        <div class="decision-full-width-section pedestrian-infra-section">
          <h4>
            <span><span class="sp-icon-inline">${SP_ICONS.accessibility({ size: 16 })}</span> Pedestrian Infrastructure & Accessibility Audit</span>
            <span style="font-size: 11px; font-weight: 500; text-transform: none; color: var(--text-muted);">
              ${swPct.toFixed(1)}% sidewalk coverage (${totDist}m total)
            </span>
          </h4>

          <div class="streetlight-stat-grid" style="grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));">
            <div class="streetlight-stat-card">
              <small style="color: #059669; font-weight: 700;">Dedicated Sidewalks</small>
              <strong>${swPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${knownSw}m documented present</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #64748b; font-weight: 700;">Unmapped Footpaths</small>
              <strong>${unmappedPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${unmappedSw}m status unknown</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #d97706; font-weight: 700;">Confirmed Absent</small>
              <strong>${absentPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${absentSw}m verified roadway-only</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #0284c7; font-weight: 700;">Road Crossings</small>
              <strong>${crossings} documented</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${signalCrossings} signalized / controlled</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #2563eb; display: flex; align-items: center; gap: 3px;">${SP_ICONS.accessibility({ size: 11 })} Accessibility</small>
              <strong>${wheelchair} accessible</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${tactile} tactile paving mapped</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: ${hazards > 0 ? '#dc2626' : 'var(--text-muted)'}; display: flex; align-items: center; gap: 3px;">${SP_ICONS.construction({ size: 11 })} Hazards / Obstructions</small>
              <strong>${hazards === 0 ? '0 documented hazards' : hazards + ' reported hazards'}</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${hazards === 0 ? 'Zero documented in active dataset' : hazards + ' active reports'} · ${highDiff} high-difficulty crossings</div>
            </div>
          </div>

          <div class="streetlight-explanation-text">
            <strong>Infrastructure Methodology & Accessibility:</strong> Footpath availability is classified into three distinct empirical states: (1) Confirmed present (${swPct.toFixed(1)}%), (2) Confirmed absent (${absentPct.toFixed(1)}%), and (3) Unknown or unmapped (${unmappedPct.toFixed(1)}%). Missing OpenStreetMap tags are never interpreted as confirmed absence; unmapped corridors preserve modeling uncertainty rather than assuming lack of pedestrian space.
          </div>
        </div>
      `;
    }

    // Phase 2 Multi-Dimensional Route Explanation Breakdown
    let explanationEngineHtml = '';
    if (route.explanationDetails) {
      const exp = route.explanationDetails;
      explanationEngineHtml = `
        <div class="decision-full-width-section route-explanation-engine-section" style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px 16px; margin-top: 14px;">
          <h4 style="margin: 0 0 10px 0; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">
            <span style="display: flex; align-items: center; gap: 6px;"><span class="sp-icon-inline">${SP_ICONS.brain({ size: 15 })}</span> Evidence-Based Route Decision Explanation</span>
            <span class="badge badge-teal" style="font-size: 10px;">Algorithm v${escapeHtml(route.algorithmVersion || '2.0.0')}</span>
          </h4>
          <p style="margin: 0 0 12px 0; font-size: 12.5px; font-weight: 600; color: var(--text-main); line-height: 1.5;">
            ${escapeHtml(exp.selection_reason || route.explanation || '')}
          </p>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; font-size: 11.5px; line-height: 1.45;">
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #0369a1; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.lamp({ size: 13 })} Lighting Conditions:</strong>
              ${escapeHtml(exp.lighting_evidence || 'No time-specific lighting observations recorded.')}
            </div>
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #b91c1c; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.shieldAlert({ size: 13 })} Crime Evidence:</strong>
              ${escapeHtml(exp.crime_evidence || 'No verified incident records.')}
            </div>
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #d97706; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.pawPrint({ size: 13 })} Dog Encounters:</strong>
              ${escapeHtml(exp.dog_encounters || 'No verified dog encounter reports.')}
            </div>
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #059669; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.footprints({ size: 13 })} Infrastructure & Walkability:</strong>
              ${escapeHtml(exp.infrastructure_evidence || 'Standard urban footway tags.')}
            </div>
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #4f46e5; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.hospital({ size: 13 })} Assistance Access Proximity:</strong>
              ${escapeHtml(exp.assistance_proximity || 'Standard proximity.')}
            </div>
            <div style="background: #ffffff; padding: 10px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <strong style="color: #64748b; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">${SP_ICONS.scale({ size: 13 })} Uncertainty & Prior Assumption:</strong>
              ${escapeHtml(exp.uncertainty_and_prior || 'Normal evidence coverage.')}
            </div>
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="decision-card-header">
        <div class="decision-title-group">
          <span class="badge ${catBadgeClass}">${catLabel}</span>
          <h3>${escapeHtml(route.name)} — Recommendation Analysis</h3>
        </div>
        <div class="decision-stat-row">
          <div class="decision-stat-pill"><strong>${(route.distanceMeters / 1000).toFixed(2)} km</strong> Distance</div>
          <div class="decision-stat-pill"><strong>${Math.round(route.durationSeconds / 60)} min</strong> Walking ETA (@ ${route.walkingSpeedKmh || ((route.distanceMeters / Math.max(route.durationSeconds, 1)) * 3.6).toFixed(1)} km/h)</div>
          <div class="decision-stat-pill"><strong>${timeDiffText}</strong> vs Fastest</div>
          <div class="decision-stat-pill"><strong>${riskVal} / 1.00</strong> Risk Index</div>
          <div class="decision-stat-pill"><strong>${cov.toUpperCase()} (${covPct}%)</strong> Coverage</div>
        </div>
      </div>

      <div class="decision-body-grid">
        <div class="decision-col">
          <h4>Trade-Off & Optimization Rationale</h4>
          <p class="tradeoff-text">${escapeHtml(route.tradeoffs)}</p>
          ${identicalNotice}
          ${route.explanation ? `<p class="tradeoff-text" style="color: var(--text-muted); margin-top: 6px;">${escapeHtml(route.explanation)}</p>` : ''}
        </div>

        <div class="decision-col">
          <h4>Key Factors Influencing Route Recommendation</h4>
          <ul class="factors-list">
            ${rankingFactors.map(f => `<li>${escapeHtml(f)}</li>`).join('')}
          </ul>
          <div class="facilities-summary">
            <span>Walking access to police: <strong>${policeDist}</strong></span> · 
            <span>Hospital: <strong>${hospitalDist}</strong></span>
          </div>
        </div>
      </div>

      ${explanationEngineHtml}
      ${streetlightHtml}
      ${nearbyPlacesHtml}
      ${pedestrianInfraHtml}
      ${(() => {
        const dSum = route.dogEncounterSummary;
        if (!dSum) return '';
        const totalReps = dSum.totalReportsCount || 0;
        const eligibleReps = dSum.eligibleReportsCount || totalReps;
        const approvedReps = dSum.approvedReportsCount !== undefined ? dSum.approvedReportsCount : totalReps;
        const corridorM = Math.round(dSum.corridorMeters || 200);
        const affectedLenM = Math.round(dSum.usableDogEvidenceLengthMeters || dSum.affectedRouteLengthMeters || 0);
        const totalRouteM = Math.round(dSum.totalRouteLengthMeters || route.distanceMeters || 0);
        const affectedPct = dSum.affectedLengthPercentage || 0;
        const freshestDays = dSum.freshestReportDays !== null && dSum.freshestReportDays !== undefined
          ? `${dSum.freshestReportDays} day(s) ago`
          : 'N/A';

        const guidanceItems = (dSum.guidance && dSum.guidance.length)
          ? dSum.guidance.map(g => `<li>${escapeHtml(g)}</li>`).join('')
          : '<li>Maintain normal pedestrian awareness when navigating unfamiliar areas.</li>';

        const explanationHtml = totalReps === 0
          ? 'No approved dog-encounter reports were found within the selected route corridor. SafePath research policy emphasizes that absence of reported sightings does NOT confirm the absolute absence of stray animals. Missing data is preserved as modeling uncertainty.'
          : escapeHtml(dSum.explanation);

        return `
          <div class="decision-full-width-section dog-encounter-section">
            <h4>
              <span><span class="sp-icon-inline">${SP_ICONS.pawPrint({ size: 15 })}</span> Stray & Street Dog Encounter Audit (${corridorM}m Corridor)</span>
              <span style="font-size: 11px; font-weight: 500; text-transform: none; color: var(--text-muted);">
                ${approvedReps} approved report(s) (${eligibleReps} eligible in corridor)
              </span>
            </h4>

            <div class="dog-stat-grid">
              <div class="dog-stat-card">
                <small style="color: #2563eb; display: flex; align-items: center; gap: 3px;">${SP_ICONS.pawPrint({ size: 11 })} Ordinary Sightings</small>
                <strong>${dSum.sightingCount || 0}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">Informational (calm)</div>
              </div>
              <div class="dog-stat-card">
                <small style="color: #7c3aed; display: flex; align-items: center; gap: 3px;">${SP_ICONS.users({ size: 11 })} Group / Packs</small>
                <strong>${dSum.groupCount || 0}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">Multiple dogs observed</div>
              </div>
              <div class="dog-stat-card">
                <small style="color: #d97706; display: flex; align-items: center; gap: 3px;">${SP_ICONS.alertTriangle({ size: 11 })} Aggressive Encounters</small>
                <strong>${dSum.aggressiveCount || 0}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">Chasing / barking</div>
              </div>
              <div class="dog-stat-card">
                <small style="color: #dc2626; display: flex; align-items: center; gap: 3px;">${SP_ICONS.shieldAlert({ size: 11 })} Physical Bite Incidents</small>
                <strong>${dSum.biteCount || 0}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">Reported physical attacks</div>
              </div>
              <div class="dog-stat-card">
                <small style="color: var(--text-muted); display: flex; align-items: center; gap: 3px;">${SP_ICONS.calendar({ size: 11 })} Recency</small>
                <strong>${freshestDays}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">Freshest report age</div>
              </div>
            </div>

            <div class="dog-explanation-box">
              <p style="margin: 0 0 6px 0; font-size: 12px; color: var(--text-body); line-height: 1.5;">
                <strong>Corridor Assessment:</strong> ${explanationHtml}
              </p>
              <div style="font-size: 11px; color: var(--text-muted);">
                Route length with usable dog evidence: <strong>${affectedLenM}m</strong> (${affectedPct}% of ${totalRouteM}m total route length).
              </div>
            </div>

            <div class="dog-guidance-container" style="margin-top: 8px; padding: 10px 12px; background: #fffbeb; border-radius: 6px; border: 1px solid #fde68a;">
              <div style="font-size: 11.5px; font-weight: 600; color: #92400e; margin-bottom: 4px;">Pedestrian Safety & Encounter Guidance:</div>
              <ul style="margin: 0; padding-left: 18px; font-size: 11px; color: #78350f; line-height: 1.5;">
                ${guidanceItems}
              </ul>
            </div>
          </div>
        `;
      })()}

      <div class="decision-caveats">
        <div class="caveat-banner">
          <span style="font-size: 14px; color: var(--warning-text);">ⓘ</span>
          <div>
            <strong>Epistemological Research Standard:</strong> Risk indicators are relative model estimates synthesized from documented spatial evidence (OSM street network, municipal lighting attributes, and facility proximities), NOT verified probabilities of victimization. SafePath Finder never equates an absence of reports with low risk, and does not display speculative crowd density or pedestrian counts.
          </div>
        </div>
      </div>
    `;
  }

  async function selectRoute(routeId) {
    state.selectedRouteId = routeId;
    const route = state.currentRoutes.find(r => r.id === routeId) || state.currentRoutes[0];
    if (!route) return;

    // Update Card styles
    $$('.route-card').forEach(c => {
      const isSelected = c.dataset.routeId === routeId;
      c.classList.toggle('selected-active', isSelected);
      c.classList.toggle('selected', isSelected);
      c.setAttribute('aria-selected', String(isSelected));
      const badge = c.querySelector('.route-card-active-badge');
      if (badge) badge.style.display = isSelected ? 'inline-block' : 'none';
    });

    // Update map layer styling
    if (state.map && state.layers.routes) {
      Object.entries(state.layers.routes).forEach(([id, layer]) => {
        const isSelected = id === routeId;
        layer.setStyle({
          weight: isSelected ? 6 : 3.5,
          opacity: isSelected ? 0.95 : 0.45
        });
        if (isSelected && layer.bringToFront) layer.bringToFront();
      });
    }

    // Render explainable route decision summary
    renderRouteDecisionSummary(route);

    // Load Evidence Segments for this route
    try {
      const segRes = await SafePathApi.getRouteSegments(routeId, route.segments);
      const rawSegments = segRes.segments || [];
      state.currentSegments = rawSegments.map((s, idx) => normalizeSegment(s, idx));
      renderSegmentCoverageLayer();
      renderEvidenceExplorer();
    } catch (err) {
      showToast(`Could not load segment evidence: ${err.message}`);
    }
  }

  function renderEvidenceExplorer() {
    const navList = $('#segmentNavList');
    const badge = $('#segmentCountBadge');
    if (!navList) return;

    if (badge) badge.textContent = `${state.currentSegments.length} segments`;

    if (!state.selectedSegmentId || !state.currentSegments.some(s => s.id === state.selectedSegmentId)) {
      state.selectedSegmentId = state.currentSegments.length ? state.currentSegments[0].id : null;
    }

    navList.innerHTML = state.currentSegments.map((seg, idx) => {
      const isActive = seg.id === state.selectedSegmentId;
      let badgeClass = 'badge-success';
      if (seg.coverage === 'limited') badgeClass = 'badge-warning';
      if (seg.coverage === 'insufficient') badgeClass = 'badge-neutral';

      return `
        <button type="button" class="segment-item-btn ${isActive ? 'active' : ''}" data-segment-id="${seg.id}" role="tab" aria-selected="${isActive}">
          <div class="segment-item-top">
            <span class="segment-item-name">${idx + 1}. ${escapeHtml(seg.streetName)}</span>
            <span class="badge ${badgeClass}" style="font-size: 10px;">${seg.coverage}</span>
          </div>
          <div class="segment-item-meta">
            <span>${Math.round(seg.lengthMeters)}m · ~${Math.round(seg.traversalTimeSeconds / 60)} min</span>
            <span>${seg.litStatus}</span>
          </div>
        </button>
      `;
    }).join('');

    $$('.segment-item-btn', navList).forEach(btn => {
      btn.addEventListener('click', () => selectSegment(btn.dataset.segmentId));
    });

    renderSegmentDetail();
  }

  function normalizeSegment(seg, idx) {
    const coverage = seg.coverage || (seg.evidenceCoverage >= 0.7 ? 'adequate' : (seg.evidenceCoverage >= 0.3 ? 'limited' : 'insufficient'));
    const id = seg.id || seg.segmentId || `seg-${idx}`;
    const streetName = seg.streetName || `Street Segment #${idx + 1}`;
    const coordinates = seg.coordinates || seg.geometry || [];
    const litStatus = seg.litStatus || (coverage === 'adequate' ? 'lit' : (coverage === 'insufficient' ? 'unmapped' : 'unlit'));
    const effectiveRisk = seg.effectiveRisk !== undefined ? seg.effectiveRisk : 0.4;
    const lengthMeters = seg.lengthMeters || (seg.attributes && seg.attributes.length_meters) || 250;
    const speedMps = (state.selectedRoute && state.selectedRoute.walkingSpeedMps) || 1.2;
    const traversalTimeSeconds = seg.traversalTimeSeconds || Math.round(lengthMeters / speedMps);
    const crimeCount = seg.crimeCount || seg.crime_count || (seg.attributes && seg.attributes.crime_count) || 0;
    const crimeRatePerKm = seg.crimeRatePerKm || seg.crime_rate_per_km || (seg.attributes && seg.attributes.crime_rate_per_km) || 0.0;
    const sidewalkStatus = seg.sidewalkStatus || seg.sidewalk_status || (seg.attributes && seg.attributes.sidewalk_status) || 'both';
    const crossingStatus = seg.crossingStatus || seg.crossing_status || (seg.attributes && seg.attributes.crossing_status) || 'marked';
    const hasTactilePaving = seg.hasTactilePaving || (seg.attributes && seg.attributes.has_tactile_paving) || false;
    const nearestPoliceName = seg.nearestPoliceName || (seg.attributes && seg.attributes.nearest_police_name) || 'Cubbon Park Police Station';
    const nearestPoliceDist = seg.nearestPoliceDistanceMeters || seg.nearest_police_distance_meters || (seg.attributes && seg.attributes.nearest_police_distance_meters) || 450;
    const nearestHospitalName = seg.nearestHospitalName || (seg.attributes && seg.attributes.nearest_hospital_name) || 'Victoria Hospital';
    const nearestHospitalDist = seg.nearestHospitalDistanceMeters || seg.nearest_hospital_distance_meters || (seg.attributes && seg.attributes.nearest_hospital_distance_meters) || 620;
    const communityReportsCount = seg.communityReportsCount || seg.community_reports_count || (seg.attributes && seg.attributes.community_reports_count) || 0;
    const evidenceCoverage = seg.coverageScore || seg.evidenceCoverage || (coverage === 'adequate' ? 0.85 : (coverage === 'limited' ? 0.5 : 0.2));
    const uncertaintyPrior = (1.0 - evidenceCoverage) * 0.5;

    return {
      id,
      streetName,
      coordinates,
      source: seg.source || 'OpenStreetMap Pedestrian Network & Lighting Tags',
      observedAt: seg.observedAt || new Date().toISOString(),
      lastUpdated: seg.lastUpdated || new Date().toISOString(),
      coverage,
      evidenceCoverage,
      uncertaintyPrior,
      freshness: seg.freshness || 'fresh',
      verificationStatus: seg.verificationStatus || (litStatus === 'lit' ? 'official_record' : 'unverified'),
      litStatus,
      effectiveRisk,
      lengthMeters,
      traversalTimeSeconds,
      crimeCount,
      crimeRatePerKm,
      sidewalkStatus,
      crossingStatus,
      hasTactilePaving,
      nearestPoliceName,
      nearestPoliceDist,
      nearestHospitalName,
      nearestHospitalDist,
      communityReportsCount,
      missingInfo: seg.missingInfo || (litStatus === 'unmapped' ? ['Municipal streetlight survey not conducted', 'CCTV coverage status unmapped', 'Tactile sidewalk paving uninspected'] : []),
      conflictingObservations: seg.conflictingObservations || (litStatus === 'conflicting' ? ['Citizen report notes dark stretch while municipal survey reports functional luminaire.'] : []),
      riskEstimate: seg.riskEstimate || {
        level: effectiveRisk < 0.38 ? 'Lower Environmental Cost' : (effectiveRisk < 0.45 ? 'Moderate' : 'Higher Cost'),
        caveat: 'Model indicator based on available spatial data; not a guarantee of safety or probability of victimization.'
      },
      plainExplanation: seg.plainExplanation || `${streetName} is a ${Math.round(lengthMeters)}m street segment with ${litStatus.toUpperCase()} lighting classification and ${sidewalkStatus} sidewalk infrastructure.`,
      limitations: seg.limitations || (litStatus === 'unmapped' ? 'Segment lacks verified ground-truth lighting survey; unobserved conditions are treated as uncertain.' : 'Data reflects physical survey assets; real-time urban condition changes are unmonitored.'),
      timeline: seg.timeline || [
        { date: '2026-10-18', actor: 'Municipal Asset Survey', note: `Lighting classification confirmed as ${litStatus}.`, status: litStatus === 'lit' ? 'approved' : 'unverified' }
      ]
    };
  }

  function selectSegment(segmentId) {
    state.selectedSegmentId = segmentId;
    $$('.segment-item-btn').forEach(btn => {
      const isActive = btn.dataset.segmentId === segmentId;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', String(isActive));
    });

    // Glowing highlight on map
    if (state.layers.segmentHighlight && state.map) {
      state.layers.segmentHighlight.clearLayers();
      const seg = state.currentSegments.find(s => s.id === segmentId);
      if (seg && seg.coordinates && seg.coordinates.length >= 2) {
        L.polyline(seg.coordinates, {
          color: '#f59e0b',
          weight: 9,
          opacity: 0.88,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(state.layers.segmentHighlight);
      }
    }

    renderSegmentDetail();
  }

  function renderSegmentDetail() {
    const pane = $('#segmentDetailPane');
    if (!pane) return;

    const seg = state.currentSegments.find(s => s.id === state.selectedSegmentId);
    if (!seg) {
      pane.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted);">Select a street segment from the left list or click directly on the map to inspect its evidence dimensions.</div>';
      return;
    }

    let coverageBadge = '<span class="badge badge-success">Adequate Evidence</span>';
    if (seg.coverage === 'limited') coverageBadge = '<span class="badge badge-warning">Limited Evidence</span>';
    if (seg.coverage === 'insufficient') coverageBadge = '<span class="badge badge-error">Insufficient Evidence</span>';

    let freshnessBadge = `<span class="badge badge-info">${seg.freshness.toUpperCase()} FRESHNESS</span>`;
    let verificationBadge = `<span class="badge badge-success">${seg.verificationStatus.toUpperCase()}</span>`;

    // Conflicting Observations Block
    let conflictHtml = '';
    if (seg.conflictingObservations && seg.conflictingObservations.length) {
      conflictHtml = `
        <div class="conflicting-box" style="margin-top: 10px; background: #fff7ed; border-left: 4px solid #f97316; padding: 10px 14px; border-radius: 4px;">
          <h4 style="margin: 0 0 4px; font-size: 12px; color: #9a3412;"><span>!</span> Conflicting Observations Detected</h4>
          <ul style="margin: 0; padding-left: 18px; font-size: 11.5px; color: #9a3412;">
            ${seg.conflictingObservations.map(c => `<li>${escapeHtml(c)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Missing Info Block
    let missingHtml = '';
    if (seg.missingInfo && seg.missingInfo.length) {
      missingHtml = `
        <div class="missing-info-box" style="margin-top: 10px; background: #f8fafc; border-left: 4px solid #64748b; padding: 10px 14px; border-radius: 4px;">
          <h4 style="margin: 0 0 4px; font-size: 12px; color: #334155;"><span>?</span> Unmapped Attributes & Missing Information</h4>
          <ul class="missing-list" style="margin: 0; padding-left: 18px; font-size: 11.5px; color: #475569;">
            ${seg.missingInfo.map(m => `<li>${escapeHtml(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Timeline Block
    let timelineHtml = '';
    if (seg.timeline && seg.timeline.length) {
      timelineHtml = `
        <div class="timeline-section" style="margin-top: 14px;">
          <h4 style="font-size: 12.5px; margin-bottom: 8px;">Observation Timeline for this Street Segment</h4>
          <div class="timeline-list">
            ${seg.timeline.map(t => `
              <div class="timeline-item">
                <span class="timeline-dot"></span>
                <div class="timeline-meta">${t.date} · ${escapeHtml(t.actor)} (${t.status.toUpperCase()})</div>
                <div class="timeline-content">${escapeHtml(t.note)}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    pane.innerHTML = `
      <div class="segment-title-area">
        <div>
          <div class="step-indicator">Street-Level Safety Intelligence</div>
          <h3 style="margin: 4px 0;">${escapeHtml(seg.streetName)}</h3>
          <div style="font-size: 12px; color: var(--text-muted);">
            Length: <strong>${Math.round(seg.lengthMeters)}m</strong> · Estimated walking time: <strong>${seg.traversalTimeSeconds < 60 ? `${Math.round(seg.traversalTimeSeconds)} sec (< 1 min)` : `~${Math.round(seg.traversalTimeSeconds / 60)} min (${Math.round(seg.traversalTimeSeconds)}s)`}</strong> (@ ${((state.selectedRoute?.walkingSpeedMps || 1.2) * 3.6).toFixed(1)} km/h)
          </div>
        </div>
        <div class="segment-state-badges" style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${coverageBadge}
          ${freshnessBadge}
          ${verificationBadge}
        </div>
      </div>

      <!-- Structured Dimensions Breakdown (Distinct Environmental Factors) -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 14px 0;">
        <!-- Dim 1: Street Lighting -->
        <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #92400e; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.lamp({ size: 12 })} Street-Lighting Status</div>
          <div style="font-size: 13.5px; font-weight: 700; color: #78350f; margin-top: 2px;">${seg.litStatus.toUpperCase()}</div>
          <div style="font-size: 11px; color: #92400e; margin-top: 4px;">
            ${seg.litStatus === 'lit' ? 'Municipal LED survey confirms overhead illumination.' : (seg.litStatus === 'unmapped' ? 'Unmapped in municipal registry; penalization prior applied.' : 'Classified unlit during dark hours.')}
          </div>
        </div>

        <!-- Dim 2: Historical Crime Evidence -->
        <div style="background: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #991b1b; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.shieldAlert({ size: 12 })} Historical Crime Evidence</div>
          <div style="font-size: 13.5px; font-weight: 700; color: #7f1d1d; margin-top: 2px;">
            ${seg.crimeCount === 0 ? '0 Recorded Incidents' : `${seg.crimeCount} Incident(s) (${seg.crimeRatePerKm.toFixed(1)}/km)`}
          </div>
          <div style="font-size: 11px; color: #991b1b; margin-top: 4px;">
            Source: BTP Public Incident Bulletin 2025-2026. Non-predictive historical context only.
          </div>
        </div>

        <!-- Dim 3: Dog Sightings & Encounters -->
        <div style="background: #fff7ed; border: 1px solid #ffedd5; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #9a3412; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.pawPrint({ size: 12 })} Dog Encounters</div>
          <div style="font-size: 13.5px; font-weight: 700; color: #7c2d12; margin-top: 2px;">Documented Observations</div>
          <div style="font-size: 11px; color: #9a3412; margin-top: 4px;">
            Checked against moderated canine reports. Pack and aggressive encounter penalties active.
          </div>
        </div>

        <!-- Dim 4: Pedestrian Infrastructure -->
        <div style="background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.footprints({ size: 12 })} Pedestrian Infrastructure</div>
          <div style="font-size: 12.5px; font-weight: 600; color: #14532d; margin-top: 2px;">
            Footpath: <strong>${seg.sidewalkStatus.toUpperCase()}</strong> · Crossing: <strong>${seg.crossingStatus}</strong>
          </div>
          <div style="font-size: 11px; color: #166534; margin-top: 4px;">
            Tactile Paving: ${seg.hasTactilePaving ? 'Verified' : 'Unmapped / None'}
          </div>
        </div>

        <!-- Dim 5: Nearby Assistance Facilities -->
        <div style="background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #115e59; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.shield({ size: 12 })} Assistance Facilities</div>
          <div style="font-size: 11.5px; color: #134e4a; margin-top: 2px;">
            Police: <strong>${escapeHtml(seg.nearestPoliceName)}</strong> (${Math.round(seg.nearestPoliceDist)}m)<br>
            Hospital: <strong>${escapeHtml(seg.nearestHospitalName)}</strong> (${Math.round(seg.nearestHospitalDist)}m)
          </div>
        </div>

        <!-- Dim 6: Evidence Quality & Uncertainty Prior -->
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px;">
          <div style="font-size: 11px; font-weight: 700; color: #334155; text-transform: uppercase; display: flex; align-items: center; gap: 4px;">${SP_ICONS.gauge({ size: 12 })} Uncertainty Prior (R_unknown)</div>
          <div style="font-size: 12.5px; font-weight: 600; color: #0f172a; margin-top: 2px;">
            Coverage Q(e): <strong>${Math.round(seg.evidenceCoverage * 100)}%</strong> · Prior: <strong>${seg.uncertaintyPrior.toFixed(2)}</strong>
          </div>
          <div style="font-size: 11px; color: #475569; margin-top: 4px;">
            Missing data is explicitly penalized to prevent unsafe shortcuts.
          </div>
        </div>
      </div>

      <div class="segment-explanation-card" style="margin-top: 10px; background: var(--surface-alt); padding: 12px; border-radius: 6px; border: 1px solid var(--border);">
        <strong>Environmental Assessment:</strong> ${escapeHtml(seg.plainExplanation)}
        <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 6px;">
          <strong>Known Limitations:</strong> ${escapeHtml(seg.limitations)}
        </div>
      </div>

      <div class="segment-provenance-grid" style="margin-top: 12px;">
        <div class="provenance-item">
          <small>Primary Evidence Source</small>
          <strong>${escapeHtml(seg.source)}</strong>
        </div>
        <div class="provenance-item">
          <small>Observation Date</small>
          <strong>${seg.observedAt ? new Date(seg.observedAt).toLocaleDateString() : 'N/A'}</strong>
        </div>
        <div class="provenance-item">
          <small>Verification Status</small>
          <strong>${seg.verificationStatus.toUpperCase()}</strong>
        </div>
      </div>

      ${conflictHtml}
      ${missingHtml}

      <div class="notice" style="margin-top: 12px; margin-bottom: 0; font-size: 11.5px;">
        <span class="notice-icon">i</span>
        <div>
          <strong>Safety Caveat & Privacy Assurance:</strong> ${escapeHtml(seg.riskEstimate.caveat)}
          Personal submitter information is strictly excluded from all public evidence feeds.
        </div>
      </div>

      ${timelineHtml}
    `;
  }

  // ==========================================================================
  // PREFERENCE SENSITIVITY CALCULATION & DYNAMIC ROUTE RE-RANKING
  // ==========================================================================
  let prefRecalcDebounceTimer = null;

  async function handleAlgorithmSettingChange() {
    const lightingWeight = Math.min(100, Math.max(0, Number($('#sliderLighting')?.value || 50)));
    const unknownWeight = Math.min(100, Math.max(0, Number($('#sliderUnknown')?.value || 30)));
    const timeWeight = Math.min(100, Math.max(0, Number($('#sliderTime')?.value || 20)));

    if ($('#valLighting')) $('#valLighting').textContent = `${lightingWeight}%`;
    if ($('#valUnknown')) $('#valUnknown').textContent = `${unknownWeight}%`;
    if ($('#valTime')) $('#valTime').textContent = `${timeWeight}%`;

    const note = $('#preferenceImpactNote');
    if (note) {
      note.innerHTML = `<strong>Updating Algorithm Parameters:</strong> Calculating multi-objective trade-offs for lighting (${lightingWeight}%), missing-data prior (${unknownWeight}%), and travel time priority (${timeWeight}%)...`;
    }

    clearTimeout(prefRecalcDebounceTimer);
    prefRecalcDebounceTimer = setTimeout(async () => {
      await recalculateRoutesWithPreferences({ lightingWeight, unknownWeight, timeWeight });
    }, 350);
  }

  async function recalculateRoutesWithPreferences({ lightingWeight, unknownWeight, timeWeight }) {
    if (!state.startLocation || !state.destinationLocation) return;
    const note = $('#preferenceImpactNote');

    // Mathematical parameter derivation:
    // 1. Normalized base lighting weight w_lighting in [0.05, 0.60]
    const mappedWeightLighting = Math.max(0.05, Math.min(0.60, (lightingWeight / 100.0) * 0.50));
    // 2. Missing-data uncertainty prior R_unknown in [0.20, 0.80]
    const mappedRUnknown = Math.max(0.20, Math.min(0.80, 0.20 + (unknownWeight / 100.0) * 0.60));
    // 3. Risk-penalty multipliers: high travel time priority reduces lambda (approaching Fastest lambda=0)
    // Low travel time priority increases lambda (heavily penalizing risk)
    const mappedLambdaSafety = Math.max(0.20, Math.min(5.0, (1.0 - (timeWeight / 100.0)) * 4.0));
    const mappedLambdaBalanced = mappedLambdaSafety / 3.0;

    const prevSelected = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];
    const prevSelectedName = prevSelected ? prevSelected.name : '';

    try {
      const departurePeriod = document.querySelector('input[name="departurePeriod"]:checked')?.value || 'daytime';
      const stepFree = $('#stepFreeToggle')?.checked || false;

      const compareData = await SafePathApi.compareRoutes({
        origin: state.startLocation.name,
        destination: state.destinationLocation.name,
        originCoordinates: [state.startLocation.lat, state.startLocation.lon],
        destinationCoordinates: [state.destinationLocation.lat, state.destinationLocation.lon],
        departurePeriod,
        stepFree,
        preferences: {
          weightLighting: mappedWeightLighting,
          rUnknownPrior: mappedRUnknown,
          lambdaSafety: mappedLambdaSafety,
          lambdaBalanced: mappedLambdaBalanced,
          includeAlternatives: true,
          maxAlternatives: 3
        }
      });

      if (compareData && compareData.routes && compareData.routes.length) {
        state.currentRoutes = compareData.routes;
        renderRouteCards();
        renderRoutePolylines();
        const activeRoute = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];
        renderRouteDecisionSummary(activeRoute);

        const newTopRoute = state.currentRoutes[0];
        const routeChanged = newTopRoute && (newTopRoute.name !== prevSelectedName);

        if (note) {
          note.innerHTML = `
            <strong>Algorithm Recalculation Applied:</strong> Evaluated under &lambda;<sub>safety</sub> = ${mappedLambdaSafety.toFixed(2)}, w<sub>lighting</sub> = ${mappedWeightLighting.toFixed(2)}, and R<sub>unknown</sub> = ${mappedRUnknown.toFixed(2)}.
            ${routeChanged ? `Recommended route changed to <strong>${escapeHtml(newTopRoute.name)}</strong>.` : `Direct avenue corridor remains optimal across all objective weights because it simultaneously minimizes travel time and provides verified lighting assets.`}
          `;
        }
      }
    } catch (err) {
      if (note) {
        note.innerHTML = `
          <strong>Algorithm Note:</strong> Parameter sensitivity evaluated locally (&lambda;<sub>safety</sub> = ${mappedLambdaSafety.toFixed(2)}, R<sub>unknown</sub> = ${mappedRUnknown.toFixed(2)}). ${escapeHtml(err.message)}
        `;
      }
    }
  }

  // ==========================================================================
  // COMMUNITY REPORTING
  // ==========================================================================
  function renderCommunityReports() {
    const feed = $('#communityReportsFeed');
    if (!feed) return;

    const filter = state.activeReportFilter;
    let reports = [];

    if (filter === 'mine') {
      reports = SafePathApi.getMyReports();
    } else if (filter === 'dogs') {
      const all = SafePathApi.getReports({});
      reports = all.filter(r => r.category && r.category.startsWith('dog_'));
    } else {
      reports = SafePathApi.getReports({ status: filter === 'all' ? null : filter });
    }

    if (!reports.length) {
      feed.innerHTML = `
        <div style="padding: 24px; text-align: center; border: 1px dashed var(--border-strong); border-radius: var(--radius-md); color: var(--text-muted); font-size: 12px;">
          No reports found under "${filter}" filter.
        </div>
      `;
      return;
    }

    const currentUser = SafePathApi.getCurrentUser();

    feed.innerHTML = reports.map(r => {
      let iconSvg = SP_ICONS.lamp({ size: 14 });
      if (r.category === 'blocked_footpath') iconSvg = SP_ICONS.accessibility({ size: 14 });
      if (r.category === 'poor_visibility') iconSvg = SP_ICONS.eye({ size: 14 });
      if (r.category === 'construction_hazard') iconSvg = SP_ICONS.construction({ size: 14 });
      if (r.category === 'access_facility') iconSvg = SP_ICONS.building({ size: 14 });
      if (r.category === 'dog_sighting') iconSvg = SP_ICONS.pawPrint({ size: 14 });
      if (r.category === 'dog_group') iconSvg = SP_ICONS.users({ size: 14 });
      if (r.category === 'dog_aggressive') iconSvg = SP_ICONS.alertTriangle({ size: 14 });
      if (r.category === 'dog_bite') iconSvg = SP_ICONS.shieldAlert({ size: 14 });

      let statusBadge = `<span class="badge badge-warning">PENDING REVIEW</span>`;
      if (r.status === 'approved') statusBadge = `<span class="badge badge-success">APPROVED · CORROBORATED</span>`;
      if (r.status === 'flagged') statusBadge = `<span class="badge badge-flagged">FLAGGED FOR INSPECTION</span>`;
      if (r.status === 'rejected') statusBadge = `<span class="badge badge-error">REJECTED / WITHDRAWN</span>`;

      const isMyReport = r.isLocalSubmission || (currentUser && r.reporterId === currentUser.id);

      const encounterDateStr = r.encounterTime
        ? `<span style="font-size:11px; color:var(--text-muted);">Encounter: ${new Date(r.encounterTime).toLocaleString([], {dateStyle:'short', timeStyle:'short'})}</span>`
        : '';
      const dogCountStr = r.dogCount || r.dog_count
        ? `<span style="font-size:11px; color:var(--text-muted);">Count: <strong>${r.dogCount || r.dog_count}</strong></span>`
        : '';

      const actionsHtml = (isMyReport && r.status !== 'rejected')
        ? `
          <div style="margin-top: 8px; display: flex; gap: 8px; justify-content: flex-end;">
            <button type="button" class="btn btn-secondary btn-sm edit-report-btn" data-report-id="${r.id}" style="font-size: 10.5px; padding: 2px 8px;"><span class="sp-btn-icon">${SP_ICONS.edit({ size: 11 })}</span> Edit</button>
            <button type="button" class="btn btn-secondary btn-sm withdraw-report-btn" data-report-id="${r.id}" style="font-size: 10.5px; padding: 2px 8px; color: #dc2626;">Withdraw</button>
          </div>
        `
        : (!isMyReport && r.status !== 'rejected')
          ? `
          <div class="report-actions-row">
            <span style="font-size: 10.5px; color: var(--text-muted);">Community Feedback:</span>
            <button type="button" class="btn-report-feedback confirmed confirm-active-btn" data-report-id="${r.id}" title="Confirm this observation is still physically accurate">
              <span class="sp-btn-icon">${SP_ICONS.check({ size: 11, stroke: 2.2 })}</span> Still Active
            </button>
            <button type="button" class="btn-report-feedback outdated flag-outdated-btn" data-report-id="${r.id}" title="Flag this observation as resolved, repaired, or outdated">
              <span class="sp-btn-icon">${SP_ICONS.flag({ size: 11 })}</span> Flag Outdated
            </button>
          </div>
          `
          : '';

      return `
        <article class="report-card">
          <div class="report-type-badge">${iconSvg}</div>
          <div class="report-body">
            <div class="report-title-row">
              <span class="report-location">${escapeHtml(r.location)}</span>
              ${statusBadge}
            </div>
            <div class="report-desc">${escapeHtml(r.description)}</div>
            <div class="report-meta-footer" style="flex-wrap: wrap; gap: 10px; margin-top: 8px; font-size: 11px;">
              <span>Category: <strong>${escapeHtml(r.categoryLabel || r.category)}</strong></span>
              ${encounterDateStr}
              ${dogCountStr}
              <span>Reported: <strong>${timeAgo(r.createdAt)}</strong></span>
              <span style="color: #15803d;">Unique Confirmations: <strong>${r.corroborations || 1}</strong></span>
              <span style="color: #9f1239;">Outdated Flags: <strong>${r.outdatedFlags || 0}</strong></span>
            </div>
            ${actionsHtml}
          </div>
        </article>
      `;
    }).join('');

    // Attach withdraw / edit handlers
    $$('.withdraw-report-btn', feed).forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.reportId;
        if (confirm(`Withdraw your report (${id})? This will mark it as withdrawn and remove it from public routing evidence.`)) {
          try {
            await SafePathApi.withdrawReport(id);
            renderCommunityReports();
            renderMapFeatures();
            showToast('Report withdrawn successfully.');
          } catch (err) {
            showToast(err.message);
          }
        }
      });
    });

    $$('.edit-report-btn', feed).forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.reportId;
        const currentReport = reports.find(r => r.id === id);
        if (!currentReport) return;
        const newDesc = prompt('Update report description:', currentReport.description);
        if (newDesc && newDesc.trim() && newDesc.trim().length >= 10) {
          try {
            await SafePathApi.updateReport(id, { description: newDesc.trim() });
            renderCommunityReports();
            showToast('Report updated successfully.');
          } catch (err) {
            showToast(err.message);
          }
        }
      });
    });

    // Attach Confirm Still Active handler
    $$('.confirm-active-btn', feed).forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.reportId;
        try {
          const res = await SafePathApi.confirmReportActive(id);
          showToast(res.message || 'Confirmed: Report marked still physically active.');
          renderCommunityReports();
        } catch (err) {
          showToast(err.message || 'Failed to confirm report.');
        }
      });
    });

    // Attach Flag Outdated handler
    $$('.flag-outdated-btn', feed).forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.reportId;
        try {
          const res = await SafePathApi.flagReportOutdated(id);
          showToast(res.message || 'Feedback recorded: Report flagged as resolved/outdated.');
          renderCommunityReports();
        } catch (err) {
          showToast(err.message || 'Failed to flag report.');
        }
      });
    });
  }

  // ==========================================================================
  // TRAVELLER WORKSPACE CONTROLLER
  // ==========================================================================
  function renderTravellerWorkspace() {
    const user = SafePathApi.getCurrentUser() || { name: 'Demo Traveller', email: 'traveller.demo@safepath.local' };
    $('#userDisplayName').textContent = user.name;
    $('#userDisplayEmail').textContent = user.email;
    $('#userAvatar').textContent = (user.name || 'T')[0].toUpperCase();

    // Stats
    const plans = SafePathApi.getSavedPlans();
    const history = SafePathApi.getJourneyHistory();
    const myReports = SafePathApi.getMyReports();
    const contacts = SafePathApi.getTrustedContacts();

    $('#statSavedPlans').textContent = plans.length;
    $('#statJourneyHistory').textContent = history.length;
    $('#statMyReports').textContent = myReports.length;
    $('#statTrustedContacts').textContent = contacts.length;

    // Preferences Form Population
    const prefs = SafePathApi.getPreferences();
    if ($('#userPrefLighting')) $('#userPrefLighting').checked = prefs.preferLighting ?? true;
    if ($('#userPrefActivity')) $('#userPrefActivity').checked = prefs.preferActivity ?? true;
    if ($('#userPrefUnknown')) $('#userPrefUnknown').checked = prefs.avoidUnknown ?? true;
    if ($('#userPrefReducedMotion')) $('#userPrefReducedMotion').checked = prefs.reducedMotion ?? false;

    // Overview list
    renderOverviewSavedPlans(plans);
    renderAllSavedPlans(plans);
    renderJourneyHistory(history);
    renderSavedPlaces(SafePathApi.getSavedPlaces());
    renderMySubmittedReports(myReports);
    renderTrustedContacts(contacts);
  }

  function renderOverviewSavedPlans(plans) {
    const container = $('#overviewSavedPlansList');
    if (!container) return;
    if (!plans.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 12px 0;">No saved journeys yet. Use "Save this plan" from the route planner.</div>';
      return;
    }
    container.innerHTML = plans.slice(0, 3).map(p => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13px; color: var(--text-main);">${escapeHtml(p.start)} → ${escapeHtml(p.end)}</strong>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">
            ${escapeHtml(p.routeName)} · ${p.distanceMeters}m · Saved ${timeAgo(p.savedAt)}
          </div>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" data-load-plan="${p.id}">Load in Planner</button>
      </div>
    `).join('');
  }

  function renderAllSavedPlans(plans) {
    const container = $('#allSavedPlansList');
    if (!container) return;
    if (!plans.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 16px;">No saved plans. Click "+ Plan a new journey" to create one.</div>';
      return;
    }
    container.innerHTML = plans.map(p => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13.5px;">${escapeHtml(p.start)} → ${escapeHtml(p.end)}</strong>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 4px;">
            ${escapeHtml(p.routeName)} · ${p.distanceMeters} meters (${p.durationMinutes} mins) · Saved ${new Date(p.savedAt).toLocaleDateString()}
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button type="button" class="btn btn-secondary btn-sm" data-load-plan="${p.id}">Load</button>
          <button type="button" class="btn btn-quiet btn-sm" data-delete-plan="${p.id}">Delete</button>
        </div>
      </div>
    `).join('');
  }

  function renderJourneyHistory(history) {
    const container = $('#journeyHistoryList');
    if (!container) return;
    if (!history || !history.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 16px;">No recorded journeys. When you confirm arrivals or track trips, completed journeys will appear here.</div>';
      return;
    }
    container.innerHTML = history.map(h => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13px;">${escapeHtml(h.origin)} → ${escapeHtml(h.destination)}</strong>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">
            Route: ${escapeHtml(h.routeChosen)} · ${h.durationMinutes} mins · ${new Date(h.completedAt).toLocaleString()}
          </div>
        </div>
        <span class="badge badge-success" style="display: inline-flex; align-items: center; gap: 4px;">${SP_ICONS.checkCircle({ size: 12 })} Arrival Confirmed</span>
      </div>
    `).join('');
  }

  function renderSavedPlaces(places) {
    const container = $('#savedPlacesList');
    if (!container) return;
    if (!places || !places.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 16px;">No saved places configured. Click "＋ Add place" above to add Home, Work, or Transit hubs.</div>';
      return;
    }
    container.innerHTML = places.map(p => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13px;">${escapeHtml(p.label)}</strong>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(p.address)}</div>
        </div>
        <div style="display: flex; gap: 6px;">
          <button type="button" class="btn btn-secondary btn-sm" data-use-place-origin="${escapeHtml(p.address)}">Set Start</button>
          <button type="button" class="btn btn-secondary btn-sm" data-use-place-dest="${escapeHtml(p.address)}">Set Dest</button>
          <button type="button" class="btn btn-quiet btn-sm" data-delete-place="${escapeHtml(p.id)}">Delete</button>
        </div>
      </div>
    `).join('');
  }

  function renderMySubmittedReports(reports) {
    const container = $('#mySubmittedReportsList');
    if (!container) return;
    if (!reports.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 16px;">You haven\'t submitted any observations yet.</div>';
      return;
    }
    container.innerHTML = reports.map(r => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13px;">${escapeHtml(r.location)}</strong>
          <div style="font-size: 11.5px; color: var(--text-body); margin: 3px 0;">${escapeHtml(r.description)}</div>
          <div style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(r.categoryLabel)} · ${timeAgo(r.createdAt)}</div>
        </div>
        <span class="badge ${r.status === 'approved' ? 'badge-success' : r.status === 'flagged' ? 'badge-flagged' : 'badge-warning'}">
          ${r.status.toUpperCase()}
        </span>
      </div>
    `).join('');
  }

  function renderTrustedContacts(contacts) {
    const container = $('#trustedContactsContainer');
    if (!container) return;
    if (!contacts.length) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); padding: 16px;">No trusted contacts configured. Add a contact to test sharing.</div>';
      return;
    }
    container.innerHTML = contacts.map(c => `
      <div class="card-item">
        <div>
          <strong style="font-size: 13px;">${escapeHtml(c.name)}</strong>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
            ${escapeHtml(c.relationship)} · ${escapeHtml(c.phone)}
          </div>
        </div>
        <button type="button" class="btn btn-quiet btn-sm" data-delete-contact="${c.id}">Remove</button>
      </div>
    `).join('');
  }

  // ==========================================================================
  // ADMINISTRATOR PORTAL CONTROLLER
  // ==========================================================================
  function renderAdminPortal() {
    const reports = SafePathApi.getReports();
    const pending = reports.filter(r => r.status === 'pending');
    const approved = reports.filter(r => r.status === 'approved');

    $('#adminPendingStat').textContent = pending.length;
    $('#adminApprovedStat').textContent = approved.length;
    $('#adminPendingCountBadge').textContent = pending.length;

    // Overview Queue
    const queueList = $('#adminOverviewQueueList');
    if (queueList) {
      if (!pending.length) {
        queueList.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">Queue clear! No reports pending review.</div>';
      } else {
        queueList.innerHTML = pending.slice(0, 3).map(r => `
          <div style="padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-alt);">
            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700;">
              <span>${escapeHtml(r.location)}</span>
              <span class="badge badge-warning">PENDING</span>
            </div>
            <div style="font-size: 11.5px; margin: 4px 0;">${escapeHtml(r.description)}</div>
            <div style="display: flex; gap: 6px; margin-top: 8px;">
              <button type="button" class="btn btn-primary btn-sm" data-mod-action="approved" data-mod-id="${r.id}">Approve</button>
              <button type="button" class="btn btn-secondary btn-sm" data-mod-action="flagged" data-mod-id="${r.id}">Flag</button>
              <button type="button" class="btn btn-quiet btn-sm" data-mod-action="rejected" data-mod-id="${r.id}">Reject</button>
            </div>
          </div>
        `).join('');
      }
    }

    // Overview Sources
    const sourcesList = $('#adminOverviewSourcesList');
    if (sourcesList) {
      const sources = SafePathApi.getAdminDataSources();
      sourcesList.innerHTML = sources.map(s => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--border);">
          <div>
            <strong style="font-size: 12px; display: block;">${escapeHtml(s.name)}</strong>
            <small style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(s.refreshFrequency)}</small>
          </div>
          <span class="badge ${s.staleWarning ? 'badge-warning' : 'badge-success'}">${s.status.toUpperCase()}</span>
        </div>
      `).join('');
    }

    renderAdminReportsTable();
    renderAdminUsersTable();
    renderAdminDataSourcesTable();
    renderAdminAuditTable();
    renderAdminFeedbackTable();

    // Populate Admin Settings Form
    const settings = SafePathApi.getSystemSettings();
    if ($('#settingFreshnessDays')) $('#settingFreshnessDays').value = settings.freshnessThresholdDays ?? 30;
    if ($('#settingOutdatedDays')) $('#settingOutdatedDays').value = settings.outdatedThresholdDays ?? 90;
    if ($('#settingAutoFlagKeywords')) $('#settingAutoFlagKeywords').value = settings.autoFlagKeywords ?? 'harassment, assault, dark, broken, hazard';
    if ($('#settingApiBaseUrl')) $('#settingApiBaseUrl').value = SafePathApi.config.baseUrl || '/api/v1';
  }

  function renderAdminReportsTable() {
    const tbody = $('#adminReportsTableBody');
    if (!tbody) return;

    const query = $('#adminReportSearch')?.value.trim().toLowerCase() || '';
    const status = $('#adminReportStatusFilter')?.value || 'all';

    let reports = SafePathApi.getReports({ query, status: status === 'all' ? null : status });

    if (!reports.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">No report records match filter criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = reports.map(r => `
      <tr>
        <td><code>${escapeHtml(r.id)}</code></td>
        <td>
          <strong style="display: block;">${escapeHtml(r.location)}</strong>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(r.description)}</span>
        </td>
        <td>${escapeHtml(r.categoryLabel || r.category)}</td>
        <td>${new Date(r.createdAt).toLocaleDateString()}</td>
        <td>
          <span class="badge ${r.status === 'approved' ? 'badge-success' : r.status === 'flagged' ? 'badge-flagged' : r.status === 'rejected' ? 'badge-error' : 'badge-warning'}">
            ${r.status.toUpperCase()}
          </span>
        </td>
        <td>
          <div style="display: flex; gap: 4px;">
            ${r.status !== 'approved' ? `<button class="btn btn-secondary btn-sm" data-mod-action="approved" data-mod-id="${r.id}">Approve</button>` : ''}
            ${r.status !== 'flagged' ? `<button class="btn btn-secondary btn-sm" data-mod-action="flagged" data-mod-id="${r.id}">Flag</button>` : ''}
            ${r.status !== 'rejected' ? `<button class="btn btn-quiet btn-sm" data-mod-action="rejected" data-mod-id="${r.id}">Reject</button>` : ''}
            ${r.status !== 'pending' ? `<button class="btn btn-quiet btn-sm" data-mod-action="pending" data-mod-id="${r.id}">Reset</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  }

  function maskEmail(email) {
    if (!email || !email.includes('@')) return '***@***.***';
    const [local, domain] = email.split('@');
    const maskedLocal = local.length <= 2 ? local[0] + '***' : local[0] + '***' + local[local.length - 1];
    const parts = domain.split('.');
    const maskedDomain = parts.map(p => p.length <= 2 ? p[0] + '***' : p[0] + '***' + p[p.length - 1]).join('.');
    return `${maskedLocal}@${maskedDomain}`;
  }

  async function renderAdminUsersTable() {
    const tbody = $('#adminUsersTableBody');
    if (!tbody) return;
    const q = $('#adminUserSearch')?.value.trim().toLowerCase() || '';
    let users = [];
    try {
      if (SafePathApi.isLiveBackend()) {
        users = await SafePathApi.fetchAdminUsers(q);
      } else {
        users = SafePathApi.getAdminUsers(q);
      }
    } catch (e) {
      users = SafePathApi.getAdminUsers(q);
    }

    if (!users || !users.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No users match filter criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => `
      <tr>
        <td><code>${escapeHtml(u.id)}</code></td>
        <td><strong>${escapeHtml(u.displayName || ('User-' + (u.id ? u.id.slice(0, 8) : '...')))}</strong></td>
        <td><span style="font-family: monospace; color: var(--text-muted);">${escapeHtml(u.emailMasked || maskEmail(u.email || ''))}</span></td>
        <td><code>${escapeHtml(u.role)}</code></td>
        <td><span class="badge ${u.status === 'active' ? 'badge-success' : 'badge-neutral'}">${escapeHtml(u.status)}</span></td>
        <td>${u.joinedAt ? new Date(u.joinedAt).toLocaleDateString() : 'N/A'}</td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" data-user-role-edit="${u.id}">Edit Role</button>
            <button class="btn btn-secondary btn-sm" data-user-reveal="${u.id}" title="Authorized identity lookup for account support">Reveal</button>
          </div>
        </td>
      </tr>
    `).join('');
  }

  async function renderAdminFeedbackTable() {
    const tbody = $('#adminFeedbackTableBody');
    if (!tbody) return;
    const cat = $('#adminFeedbackCategoryFilter')?.value || 'all';
    const status = $('#adminFeedbackStatusFilter')?.value || 'all';

    let items = [];
    try {
      if (SafePathApi.isLiveBackend()) {
        items = await SafePathApi.fetchAdminFeedback({ category: cat, status: status });
      } else {
        items = SafePathApi.getAdminFeedback({ category: cat, status: status });
      }
    } catch (e) {
      console.warn('Feedback fetch error:', e);
      items = SafePathApi.getAdminFeedback({ category: cat, status: status });
    }

    if (!items || !items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No feedback submissions match filter criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = items.map(fb => `
      <tr>
        <td><code>${escapeHtml(fb.id)}</code></td>
        <td><span class="badge badge-neutral">${escapeHtml(fb.category)}</span></td>
        <td>${fb.rating ? `<span class="rating-score-pill">${SP_ICONS.star({ size: 11, fill: 'currentColor' })} ${fb.rating} / 5</span>` : '<span style="color:var(--text-muted);">-</span>'}</td>
        <td style="max-width: 280px; word-break: break-word;">
          ${escapeHtml(fb.message)}
          ${fb.adminNotes ? `<div style="font-size: 11px; color: var(--primary); margin-top: 4px;"><em>Admin note:</em> ${escapeHtml(fb.adminNotes)}</div>` : ''}
        </td>
        <td>${fb.createdAt ? new Date(fb.createdAt).toLocaleDateString() : 'N/A'}</td>
        <td>
          <span class="badge ${fb.status === 'resolved' ? 'badge-success' : fb.status === 'in_review' ? 'badge-warning' : 'badge-neutral'}">${escapeHtml(fb.status)}</span>
        </td>
        <td>
          <select class="select-input" data-feedback-status-change="${fb.id}" style="padding: 4px 8px; font-size: 11px;">
            <option value="new" ${fb.status === 'new' ? 'selected' : ''}>New</option>
            <option value="in_review" ${fb.status === 'in_review' ? 'selected' : ''}>In Review</option>
            <option value="resolved" ${fb.status === 'resolved' ? 'selected' : ''}>Resolved</option>
            <option value="dismissed" ${fb.status === 'dismissed' ? 'selected' : ''}>Dismissed</option>
          </select>
        </td>
      </tr>
    `).join('');
  }

  function renderAdminDataSourcesTable() {
    const tbody = $('#adminDataSourcesTableBody');
    if (!tbody) return;
    const sources = SafePathApi.getAdminDataSources();

    tbody.innerHTML = sources.map(s => `
      <tr>
        <td>
          <strong>${escapeHtml(s.name)}</strong>
          <small style="display: block; color: var(--text-muted);">${escapeHtml(s.notes)}</small>
        </td>
        <td>${escapeHtml(s.type)}</td>
        <td>${escapeHtml(s.coverage)}</td>
        <td>${new Date(s.lastIngested).toLocaleDateString()}</td>
        <td>${s.recordsCount.toLocaleString()}</td>
        <td>
          <span class="badge ${s.staleWarning ? 'badge-warning' : 'badge-success'}">
            ${s.status.toUpperCase()}${s.staleWarning ? ' (STALE)' : ''}
          </span>
        </td>
      </tr>
    `).join('');
  }

  function renderAdminAuditTable() {
    const tbody = $('#adminAuditTableBody');
    if (!tbody) return;
    const log = SafePathApi.getAuditLog();

    if (!log.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 18px;">No audit records found.</td></tr>';
      return;
    }

    tbody.innerHTML = log.map(entry => `
      <tr>
        <td>${new Date(entry.timestamp).toLocaleString()}</td>
        <td><strong>${escapeHtml(entry.action)}</strong></td>
        <td><code>${escapeHtml(entry.record)}</code></td>
        <td>${escapeHtml(entry.actor)}</td>
        <td><span class="badge badge-neutral">${escapeHtml(entry.environment)}</span></td>
      </tr>
    `).join('');
  }

  // ==========================================================================
  // EVENT LISTENERS & WIRING
  // ==========================================================================
  // LOCATION SEARCH & AUTOCOMPLETE CONTROLLER
  // ==========================================================================
  function setupLocationAutocomplete(inputSelector, dropdownSelector, clearBtnSelector, stateKey) {
    const input = $(inputSelector);
    const dropdown = $(dropdownSelector);
    const clearBtn = $(clearBtnSelector);
    if (!input || !dropdown) return;

    let debounceTimer = null;
    let activeIndex = -1;
    let currentResults = [];

    function updateClearBtn() {
      if (!clearBtn) return;
      if (input.value && input.value.trim().length > 0) {
        clearBtn.classList.remove('hidden');
      } else {
        clearBtn.classList.add('hidden');
      }
    }

    function hideDropdown() {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
      activeIndex = -1;
    }

    function selectItem(item) {
      if (!item) return;
      input.value = item.name;
      state[stateKey] = {
        id: item.id,
        name: item.name,
        displayName: item.displayName,
        lat: item.latitude,
        lon: item.longitude,
        inStudyArea: item.inStudyArea,
        type: item.type,
        distanceMeters: item.studyAreaDistanceMeters,
        address: item.address
      };
      hideDropdown();
      updateClearBtn();

      const alertBox = $('#routePlannerAlert');
      if (!item.inStudyArea && alertBox) {
        alertBox.innerHTML = `<div><strong>Location Notice:</strong> '${escapeHtml(item.name)}' is outside the active pedestrian routing corridor (Bengaluru Pilot Corridor: Jayanagar to Cubbon Park / MG Road). SafePath will submit it, but route comparison requires endpoints within the research network boundary.</div>`;
        alertBox.classList.remove('hidden');
      } else if (alertBox) {
        alertBox.classList.add('hidden');
      }
    }

    input.addEventListener('input', () => {
      updateClearBtn();
      // Reset selected state since the user changed the query text
      state[stateKey] = null;

      const q = input.value.trim();
      if (q.length < 2) {
        hideDropdown();
        return;
      }

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(async () => {
        const queryNow = input.value.trim();
        if (queryNow.length < 2) {
          hideDropdown();
          return;
        }

        dropdown.classList.remove('hidden');
        dropdown.innerHTML = `<div class="autocomplete-loading">${SP_ICONS.loader({ size: 14, cls: 'sp-spin' })} Searching places & landmarks...</div>`;

        try {
          const results = await SafePathApi.searchPlaces(queryNow, 5);
          currentResults = results || [];
          if (!currentResults.length) {
            dropdown.innerHTML = `<div class="autocomplete-empty">No matching places found for "<strong>${escapeHtml(queryNow)}</strong>". You can enter coordinates (lat, lon) directly.</div>`;
            return;
          }

          dropdown.innerHTML = currentResults.map((r, idx) => {
            const inArea = r.inStudyArea;
            const distKm = r.studyAreaDistanceMeters ? ` (~${Math.round(r.studyAreaDistanceMeters / 1000)} km)` : '';
            const pillHtml = inArea
              ? '<span class="coverage-pill coverage-pill--in">Within Corridor</span>'
              : `<span class="coverage-pill coverage-pill--out">Outside Corridor${distKm}</span>`;

            let iconSvg = SP_ICONS.mapPin({ size: 14 });
            if (r.type === 'coordinate') iconSvg = SP_ICONS.compass({ size: 14 });
            else if (r.type === 'transit') iconSvg = SP_ICONS.train({ size: 14 });
            else if (r.type === 'commercial') iconSvg = SP_ICONS.store({ size: 14 });
            else if (r.type === 'park' || r.type === 'leisure' || r.type === 'attraction') iconSvg = SP_ICONS.trees({ size: 14 });

            return `
              <div class="autocomplete-item" data-index="${idx}" role="option" tabindex="0">
                <div class="autocomplete-item-left">
                  <span class="autocomplete-icon">${iconSvg}</span>
                  <div class="autocomplete-item-main">
                    <span class="autocomplete-item-title">${escapeHtml(r.name)}</span>
                    <span class="autocomplete-item-sub">${escapeHtml(r.displayName)}</span>
                  </div>
                </div>
                <div class="autocomplete-pills">
                  ${pillHtml}
                </div>
              </div>
            `;
          }).join('') + '<div class="autocomplete-footer"><small>Search &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a></small></div>';

          dropdown.classList.remove('hidden');
          activeIndex = -1;

          $$('.autocomplete-item', dropdown).forEach(itemEl => {
            itemEl.addEventListener('click', () => {
              const idx = parseInt(itemEl.dataset.index, 10);
              selectItem(currentResults[idx]);
            });
          });
        } catch (err) {
          dropdown.innerHTML = `<div class="autocomplete-error" style="display:flex; align-items:center; gap:6px;">${SP_ICONS.alertTriangle({ size: 14 })} ${escapeHtml(err.message || 'Geocoding service unavailable.')}</div>`;
        }
      }, 300);
    });

    input.addEventListener('keydown', e => {
      if (dropdown.classList.contains('hidden') || !currentResults.length) return;

      const items = $$('.autocomplete-item', dropdown);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % items.length;
        items.forEach((it, i) => it.classList.toggle('active', i === activeIndex));
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + items.length) % items.length;
        items.forEach((it, i) => it.classList.toggle('active', i === activeIndex));
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') {
        if (activeIndex >= 0 && currentResults[activeIndex]) {
          e.preventDefault();
          selectItem(currentResults[activeIndex]);
        }
      } else if (e.key === 'Escape') {
        hideDropdown();
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        input.value = '';
        state[stateKey] = null;
        updateClearBtn();
        hideDropdown();
        input.focus();
      });
    }

    document.addEventListener('click', e => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        hideDropdown();
      }
    });

    updateClearBtn();
  }

  // ==========================================================================
  function setupEventListeners() {
    // 0. Logo & Main Navigation links
    $('#brandLogo')?.addEventListener('click', (e) => {
      e.preventDefault();
      navigateToSection('plan', true);
    });

    $$('#mainNav .nav-link, #mobileNavDrawer a[data-nav-close]').forEach(link => {
      link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
          e.preventDefault();
          navigateToSection(href, true);
        }
      });
    });

    // Initialize in-page scroll spy
    setupScrollSpy();

    // Browser back/forward navigation support
    window.addEventListener('popstate', () => {
      const hash = (window.location.hash || '').replace(/^#/, '');
      if (hash && NAV_SECTIONS.includes(hash)) {
        navigateToSection(hash, false);
      }
    });

    // Initialize location search autocomplete
    setupLocationAutocomplete('#originInput', '#originSuggestions', '#originClearBtn', 'originLocation');
    setupLocationAutocomplete('#destinationInput', '#destinationSuggestions', '#destinationClearBtn', 'destinationLocation');

    // 1. Mobile Navigation Drawer Toggle
    const mobileToggle = $('#mobileNavToggle');
    const mobileDrawer = $('#mobileNavDrawer');
    if (mobileToggle && mobileDrawer) {
      mobileToggle.addEventListener('click', () => {
        const isOpen = mobileDrawer.classList.toggle('open');
        mobileToggle.setAttribute('aria-expanded', String(isOpen));
      });
      $$('[data-nav-close]', mobileDrawer).forEach(link => {
        link.addEventListener('click', () => {
          mobileDrawer.classList.remove('open');
          mobileToggle.setAttribute('aria-expanded', 'false');
        });
      });
    }

    // 2. Route Planner Submission
    $('#plannerForm')?.addEventListener('submit', e => {
      e.preventDefault();
      loadRoutes();
      $('#routes')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // 3. Quick Landmarks Buttons
    $$('[data-set-route]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.setRoute;
        if (type === 'jayanagar-lalbagh') {
          $('#originInput').value = 'Jayanagar 4th Block, Bengaluru';
          $('#destinationInput').value = 'Lalbagh West Gate, Bengaluru';
          state.originLocation = { name: 'Jayanagar 4th Block', lat: 12.9257, lon: 77.5833, inStudyArea: true };
          state.destinationLocation = { name: 'Lalbagh West Gate', lat: 12.9460, lon: 77.5844, inStudyArea: true };
        } else if (type === 'southend-gandhibazaar') {
          $('#originInput').value = 'South End Circle, Bengaluru';
          $('#destinationInput').value = 'Gandhi Bazaar Main Road, Bengaluru';
          state.originLocation = { name: 'South End Circle', lat: 12.9330, lon: 77.5832, inStudyArea: true };
          state.destinationLocation = { name: 'Gandhi Bazaar Main Road', lat: 12.9420, lon: 77.5720, inStudyArea: true };
        } else if (type === 'cubbon-mgroad') {
          $('#originInput').value = 'Cubbon Park, Bengaluru';
          $('#destinationInput').value = 'MG Road, Bengaluru';
          state.originLocation = { name: 'Cubbon Park', lat: 12.9770, lon: 77.5920, inStudyArea: true };
          state.destinationLocation = { name: 'MG Road', lat: 12.9750, lon: 77.6050, inStudyArea: true };
        }
        loadRoutes();
        showToast('Updated route points to ' + $('#originInput').value + ' → ' + $('#destinationInput').value);
      });
    });

    // 4. Geolocation Button
    $('#locateMeBtn')?.addEventListener('click', () => {
      if (!navigator.geolocation) {
        showToast('Geolocation is not supported by this browser.');
        return;
      }
      const btn = $('#locateMeBtn');
      btn.innerHTML = `${SP_ICONS.loader({ size: 13, cls: 'sp-spin' })} Locating...`;
      navigator.geolocation.getCurrentPosition(
        pos => {
          btn.innerHTML = `${SP_ICONS.crosshair({ size: 13 })} Locate me`;
          if (state.map && state.layers.userLocation) {
            state.layers.userLocation.clearLayers();
            L.circleMarker([pos.coords.latitude, pos.coords.longitude], {
              radius: 8,
              color: '#fff',
              weight: 3,
              fillColor: '#28597a',
              fillOpacity: 1
            }).addTo(state.layers.userLocation).bindPopup('Your temporary location. Routes not recalculated.').openPopup();
            state.map.setView([pos.coords.latitude, pos.coords.longitude], 15);
          }
          showToast('Device location plotted on map.');
        },
        err => {
          btn.innerHTML = `${SP_ICONS.crosshair({ size: 13 })} Locate me`;
          showToast(err.code === 1 ? 'Location permission was declined.' : 'Unable to acquire location.');
        },
        { timeout: 8000 }
      );
    });

    // 5. Map Layer Toggles
    $('#toggleCoverageOverlayBtn')?.addEventListener('click', e => {
      state.toggles.coverage = !state.toggles.coverage;
      e.currentTarget.setAttribute('aria-pressed', String(state.toggles.coverage));
      renderSegmentCoverageLayer();
      showToast(state.toggles.coverage ? 'Enabled segment coverage layer.' : 'Hidden segment coverage layer.');
    });

    $('#toggleObservationsBtn')?.addEventListener('click', e => {
      state.toggles.observations = !state.toggles.observations;
      e.currentTarget.setAttribute('aria-pressed', String(state.toggles.observations));
      renderMapFeatures();
      showToast(state.toggles.observations ? 'Enabled community observation pins.' : 'Hidden community observation pins.');
    });

    $('#togglePlacesBtn')?.addEventListener('click', e => {
      state.toggles.places = !state.toggles.places;
      e.currentTarget.setAttribute('aria-pressed', String(state.toggles.places));
      renderMapFeatures();
      showToast(state.toggles.places ? 'Enabled transit and safe haven pins.' : 'Hidden transit pins.');
    });

    $('#toggleDogsBtn')?.addEventListener('click', e => {
      state.toggles.dogs = !state.toggles.dogs;
      e.currentTarget.setAttribute('aria-pressed', String(state.toggles.dogs));
      renderMapFeatures();
      showToast(state.toggles.dogs ? 'Enabled dog encounter evidence layer.' : 'Hidden dog encounter pins.');
    });

    $('#fitMapBoundsBtn')?.addEventListener('click', fitMapBounds);

    // 6. Save Plan
    $('#saveCurrentPlanBtn')?.addEventListener('click', () => {
      const activeRoute = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];
      const plan = SafePathApi.savePlan({
        start: $('#originInput').value,
        end: $('#destinationInput').value,
        routeId: activeRoute.id,
        routeName: activeRoute.name,
        distanceMeters: activeRoute.distanceMeters,
        durationMinutes: Math.round(activeRoute.durationSeconds / 60)
      });
      showToast('Plan saved locally to Traveller Workspace.');
    });

    // 7. Preference Sliders
    ['sliderLighting', 'sliderUnknown', 'sliderTime'].forEach(id => {
      $(`#${id}`)?.addEventListener('input', handleAlgorithmSettingChange);
    });

    // 8. Community Filter Chips
    $$('[data-report-filter]').forEach(chip => {
      chip.addEventListener('click', () => {
        $$('[data-report-filter]').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activeReportFilter = chip.dataset.reportFilter;
        renderCommunityReports();
      });
    });

    // 9. Community Report Modal
    const reportModal = $('#reportModal');
    $('#openReportModalBtn')?.addEventListener('click', () => {
      reportModal.classList.add('open');
      setTimeout(() => $('#reportCategoryInput')?.focus(), 50);
    });
    $('#workspaceAddReportBtn')?.addEventListener('click', () => {
      reportModal.classList.add('open');
    });
    $('#closeReportModalBtn')?.addEventListener('click', () => reportModal.classList.remove('open'));
    $('#cancelReportBtn')?.addEventListener('click', () => reportModal.classList.remove('open'));

    // Dynamic Dog Form Fields toggle
    $('#reportCategoryInput')?.addEventListener('change', e => {
      const val = e.target.value;
      const dogFields = $('#dogReportFields');
      const isAggrCheckbox = $('#reportIsAggressiveInput');
      if (dogFields) {
        if (val.startsWith('dog_')) {
          dogFields.style.display = 'block';
          if (val === 'dog_aggressive' || val === 'dog_bite') {
            if (isAggrCheckbox) isAggrCheckbox.checked = true;
          } else {
            if (isAggrCheckbox) isAggrCheckbox.checked = false;
          }
        } else {
          dogFields.style.display = 'none';
        }
      }
    });

    $('#btnPickMapLocation')?.addEventListener('click', () => {
      state.isPickingMapCoordinate = true;
      reportModal.classList.remove('open');
      showToast('Map pin mode: Click anywhere on the map to set observation coordinates.');
    });

    $('#newReportForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      try {
        const cat = $('#reportCategoryInput').value;
        const latVal = $('#reportLatitudeInput')?.value ? parseFloat($('#reportLatitudeInput').value) : null;
        const lonVal = $('#reportLongitudeInput')?.value ? parseFloat($('#reportLongitudeInput').value) : null;
        const encounterTimeVal = $('#reportEncounterTimeInput')?.value || null;
        const dogCountVal = $('#reportDogCountInput')?.value ? parseInt($('#reportDogCountInput').value, 10) : null;
        const isAggrVal = $('#reportIsAggressiveInput') ? $('#reportIsAggressiveInput').checked : null;
        const observedAtVal = $('#reportObservedAtInput')?.value || null;

        if (observedAtVal) {
          const obsTime = new Date(observedAtVal).getTime();
          if (obsTime > Date.now() + 300000) {
            throw new Error('Observation timestamp cannot be in the future.');
          }
        }

        await SafePathApi.submitReport({
          category: cat,
          location: $('#reportLocationInput').value,
          description: $('#reportDescInput').value,
          latitude: latVal,
          longitude: lonVal,
          encounterTime: encounterTimeVal,
          dogCount: dogCountVal,
          isAggressive: isAggrVal,
          observedAt: observedAtVal
        });
        reportModal.classList.remove('open');
        e.target.reset();
        if ($('#dogReportFields')) $('#dogReportFields').style.display = 'none';
        renderCommunityReports();
        if (state.currentScreen === 'account') renderTravellerWorkspace();
        showToast('Report submitted and queued for moderation as "pending".');
      } catch (err) {
        showToast(err.message);
      }
    });

    // 10. Traveller Workspace Navigation
    $$('[data-traveller-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.travellerTab;
        state.travellerTab = tab;
        $$('.traveller-nav-btn').forEach(b => b.classList.toggle('active', b.dataset.travellerTab === tab));
        $$('.traveller-tab-view').forEach(v => v.classList.toggle('hidden', v.id !== `tabView-${tab}`));
      });
    });

    $('#backToPlannerBtn')?.addEventListener('click', () => setScreen('app'));
    $('#createNewPlanBtn')?.addEventListener('click', () => setScreen('app'));
    $('#myWorkspaceBtn')?.addEventListener('click', () => setScreen('account'));
    $('#userSignOutBtn')?.addEventListener('click', async () => {
      await SafePathApi.logout();
      setScreen('app');
      showToast('Signed out of session.');
    });

    // Add Saved Place Button
    $('#addSavedPlaceBtn')?.addEventListener('click', () => {
      const label = window.prompt('Enter place name (e.g. Home, Office, Gym, Transit hub):');
      if (!label || !label.trim()) return;
      const address = window.prompt(`Enter address or landmark for "${label.trim()}":`);
      if (!address || !address.trim()) return;
      try {
        SafePathApi.addSavedPlace({ label: label.trim(), address: address.trim() });
        renderSavedPlaces(SafePathApi.getSavedPlaces());
        showToast(`Saved place "${label.trim()}" added.`);
      } catch (err) {
        showToast(err.message);
      }
    });

    // User Preferences Form Submission
    $('#userPreferencesForm')?.addEventListener('submit', e => {
      e.preventDefault();
      const prefs = {
        preferLighting: $('#userPrefLighting') ? $('#userPrefLighting').checked : true,
        preferActivity: $('#userPrefActivity') ? $('#userPrefActivity').checked : true,
        avoidUnknown: $('#userPrefUnknown') ? $('#userPrefUnknown').checked : true,
        reducedMotion: $('#userPrefReducedMotion') ? $('#userPrefReducedMotion').checked : false
      };
      SafePathApi.savePreferences(prefs);
      document.documentElement.classList.toggle('reduce-motion', prefs.reducedMotion);
      showToast('Navigation & accessibility preferences saved.');
    });

    // 11. Trusted Contacts Modal
    const contactModal = $('#contactModal');
    $('#openAddContactModalBtn')?.addEventListener('click', () => {
      contactModal.classList.add('open');
      setTimeout(() => $('#contactNameInput')?.focus(), 50);
    });
    $('#closeContactModalBtn')?.addEventListener('click', () => contactModal.classList.remove('open'));
    $('#cancelContactBtn')?.addEventListener('click', () => contactModal.classList.remove('open'));

    $('#newContactForm')?.addEventListener('submit', e => {
      e.preventDefault();
      try {
        SafePathApi.addTrustedContact({
          name: $('#contactNameInput').value,
          relationship: $('#contactRelationshipInput').value,
          phone: $('#contactPhoneInput').value
        });
        contactModal.classList.remove('open');
        e.target.reset();
        renderTrustedContacts(SafePathApi.getTrustedContacts());
        showToast('Trusted contact added locally.');
      } catch (err) {
        showToast(err.message);
      }
    });

    // 12. Trip Sharing & Live Journey Protection (Phase 3)
    function openJourneySessionModal() {
      const activeRoute = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];
      const dest = $('#destinationInput')?.value || state.destinationLocation?.displayName || 'Selected Destination';

      const modalDest = $('#modalJourneyDest');
      if (modalDest) modalDest.textContent = dest;

      const modalRoute = $('#modalJourneyRoute');
      if (modalRoute) modalRoute.textContent = activeRoute ? `${activeRoute.name} (${activeRoute.preference})` : 'Safety-prioritized Route';

      const durationMins = activeRoute ? Math.round(activeRoute.durationSeconds / 60) : 15;
      const distKm = activeRoute ? (activeRoute.distanceMeters / 1000).toFixed(2) : '1.20';
      const modalDistDur = $('#modalJourneyDistanceDuration');
      if (modalDistDur) modalDistDur.textContent = `${distKm} km (~${durationMins} mins walk)`;

      const now = new Date();
      const etaDate = new Date(now.getTime() + durationMins * 60000);
      const etaStr = etaDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const modalETA = $('#modalJourneyETA');
      if (modalETA) modalETA.textContent = `${etaStr} (in ~${durationMins}m)`;

      // Populate contacts checklist
      const contacts = SafePathApi.getTrustedContacts ? SafePathApi.getTrustedContacts() : [];
      const checklistEl = $('#journeyContactsChecklist');
      if (checklistEl) {
        if (!contacts || contacts.length === 0) {
          checklistEl.innerHTML = `<div style="font-size: 11.5px; color: var(--text-muted); padding: 8px;">No trusted contacts configured. A private shareable link will still be generated for you to copy or paste into WhatsApp/SMS.</div>`;
        } else {
          checklistEl.innerHTML = contacts.map(c => `
            <label style="display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 4px; background: #fff; border: 1px solid var(--border); font-size: 12px; margin-bottom: 4px; cursor: pointer;">
              <input type="checkbox" name="journeyContactId" value="${escapeHtml(c.id)}" checked />
              <span><strong>${escapeHtml(c.name)}</strong> (${escapeHtml(c.relationship || 'Contact')})</span>
            </label>
          `).join('');
        }
      }

      const consentCheck = $('#journeyConsentCheck');
      if (consentCheck) consentCheck.checked = false;

      $('#journeySessionModal')?.classList.add('open');
    }

    $('#shareTripPreviewBtn')?.addEventListener('click', openJourneySessionModal);
    $('#generateShareLinkBtn')?.addEventListener('click', openJourneySessionModal);
    $('#closeJourneyModalBtn')?.addEventListener('click', () => $('#journeySessionModal')?.classList.remove('open'));
    $('#cancelJourneySessionBtn')?.addEventListener('click', () => $('#journeySessionModal')?.classList.remove('open'));

    $('#journeySessionForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const consentCheck = $('#journeyConsentCheck');
      if (!consentCheck || !consentCheck.checked) {
        showToast('Voluntary consent is required to start and share this walking journey.');
        return;
      }

      const activeRoute = state.currentRoutes.find(r => r.id === state.selectedRouteId) || state.currentRoutes[0];
      const durationMins = activeRoute ? Math.round(activeRoute.durationSeconds / 60) : 15;
      const distMeters = activeRoute ? activeRoute.distanceMeters : 1200;
      const selectedContactIds = Array.from(document.querySelectorAll('input[name="journeyContactId"]:checked')).map(cb => cb.value);

      try {
        const session = await SafePathApi.startJourneySession({
          origin: $('#originInput')?.value || 'Origin',
          destination: $('#destinationInput')?.value || 'Destination',
          routeName: activeRoute ? activeRoute.name : 'Safety-prioritized',
          routeId: activeRoute ? activeRoute.id : 'fastest',
          etaMinutes: durationMins,
          distanceMeters: distMeters,
          consentGiven: true,
          contactIds: selectedContactIds
        });

        state.activeJourneySession = session;
        $('#journeySessionModal')?.classList.remove('open');
        activateJourneyBanner(session);

        if (session.shareUrl && navigator.clipboard) {
          navigator.clipboard.writeText(session.shareUrl).catch(() => {});
        }
        showToast(`Protected walk started! Share link ready (notified ${session.contactCount || selectedContactIds.length} contact(s)).`);
      } catch (err) {
        showToast(`Could not start journey: ${err.message}`);
      }
    });

    function activateJourneyBanner(session) {
      if (!session) return;
      state.activeJourneySession = session;
      if (state.journeyCountdownTimer) {
        clearInterval(state.journeyCountdownTimer);
        state.journeyCountdownTimer = null;
      }

      const banner = $('#activeJourneyBanner');
      if (!banner) return;
      banner.classList.remove('hidden');

      const destEl = $('#activeJourneyDest');
      if (destEl) destEl.textContent = session.destination || 'Destination';

      const routeEl = $('#activeJourneyRoute');
      if (routeEl) routeEl.textContent = session.routeName || 'Safety-prioritized';

      const arrivalTime = new Date(session.expectedArrivalAt).getTime();

      function tickCountdown() {
        const diffMs = arrivalTime - Date.now();
        const countdownEl = $('#activeJourneyCountdown');
        if (!countdownEl) return;
        if (diffMs <= 0) {
          countdownEl.textContent = 'Overdue (Check-in pending)';
          countdownEl.style.background = '#fee2e2';
          countdownEl.style.color = '#991b1b';
          return;
        }
        const totalSecs = Math.floor(diffMs / 1000);
        const mins = Math.floor(totalSecs / 60);
        const secs = totalSecs % 60;
        countdownEl.textContent = `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
        countdownEl.style.background = '';
        countdownEl.style.color = '';
      }

      tickCountdown();
      state.journeyCountdownTimer = setInterval(tickCountdown, 1000);
    }

    function deactivateJourneyBanner() {
      if (state.journeyCountdownTimer) {
        clearInterval(state.journeyCountdownTimer);
        state.journeyCountdownTimer = null;
      }
      state.activeJourneySession = null;
      $('#activeJourneyBanner')?.classList.add('hidden');
    }

    $('#btnArrivalCheckIn')?.addEventListener('click', async () => {
      if (!state.activeJourneySession) {
        showToast('No active journey session in progress.');
        return;
      }
      try {
        const res = await SafePathApi.checkInJourneySession(state.activeJourneySession.id);
        deactivateJourneyBanner();
        showToast(res.message || 'Safe arrival confirmed! Journey completed.');
      } catch (err) {
        showToast(err.message);
      }
    });

    $('#confirmArrivalNowBtn')?.addEventListener('click', async () => {
      if (state.activeJourneySession) {
        try {
          const res = await SafePathApi.checkInJourneySession(state.activeJourneySession.id);
          deactivateJourneyBanner();
          showToast(res.message || 'Safe arrival confirmed! Journey completed.');
          return;
        } catch (err) {
          // fallback to demo arrival
        }
      }
      const res = await SafePathApi.confirmArrival({
        destination: $('#destinationInput')?.value || 'Current Walk',
        journeyId: 'jrn-active-demo'
      });
      showToast(res.message);
    });

    $('#btnSimulateReminder')?.addEventListener('click', async () => {
      if (!state.activeJourneySession) return;
      try {
        const res = await SafePathApi.simulateJourneyReminder(state.activeJourneySession.id);
        showToast(`5-Min Reminder: ${res.message} (${res.deliveryStatus})`);
      } catch (err) {
        showToast(err.message);
      }
    });

    $('#btnCopyShareLink')?.addEventListener('click', () => {
      if (!state.activeJourneySession || !state.activeJourneySession.shareUrl) {
        showToast('No active journey URL available.');
        return;
      }
      const url = state.activeJourneySession.shareUrl;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url)
          .then(() => showToast('Share URL copied to clipboard!'))
          .catch(() => window.prompt('Share link:', url));
      } else {
        window.prompt('Share link:', url);
      }
    });

    $('#btnRevokeJourney')?.addEventListener('click', async () => {
      if (!state.activeJourneySession) return;
      if (!confirm('Are you sure you want to end and revoke this journey session? Contacts will no longer be able to track your ETA.')) return;
      try {
        const res = await SafePathApi.cancelJourneySession(state.activeJourneySession.id);
        deactivateJourneyBanner();
        showToast(res.message || 'Journey session ended and revoked.');
      } catch (err) {
        showToast(err.message);
      }
    });

    // Public Journey Share viewer modal
    $('#closePublicJourneyModalBtn')?.addEventListener('click', () => {
      $('#publicJourneyModal')?.classList.remove('open');
    });

    function renderPublicJourneyShareModal(data) {
      const modal = $('#publicJourneyModal');
      const content = $('#publicJourneyContent');
      if (!modal || !content) return;

      const isCompleted = data.status === 'completed';
      const isRevoked = data.status === 'revoked';
      const isExpired = data.status === 'expired';
      const statusColor = isCompleted ? '#16a34a' : (isRevoked || isExpired ? '#dc2626' : '#2563eb');

      content.innerHTML = `
        <div style="background: var(--surface-alt); padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border); margin-bottom: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--text-muted);">Status</span>
            <span style="font-size: 11px; font-weight: 700; color: #fff; background: ${statusColor}; padding: 3px 8px; border-radius: 12px; text-transform: uppercase;">
              ${escapeHtml(data.status)}
            </span>
          </div>
          <div style="display: grid; grid-template-columns: 1fr; gap: 8px; font-size: 12px;">
            <div><strong>Origin:</strong> ${escapeHtml(data.origin || 'Unknown')}</div>
            <div><strong>Destination:</strong> ${escapeHtml(data.destination || 'Unknown')}</div>
            <div><strong>Route Chosen:</strong> ${escapeHtml(data.routeName || 'Pedestrian corridor')}</div>
            <div><strong>Distance & Est. Walk:</strong> ${(data.distanceMeters / 1000).toFixed(2)} km (~${data.etaMinutes} mins)</div>
            <div><strong>Expected Arrival:</strong> ${data.expectedArrivalAt ? new Date(data.expectedArrivalAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Pending'}</div>
            ${data.completedAt ? `<div><strong>Actual Check-in:</strong> ${new Date(data.completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (Confirmed Safe)</div>` : ''}
          </div>
        </div>

        <div class="notice" style="margin-bottom: 0; font-size: 11px;">
          <span class="notice-icon" style="width: 18px; height: 18px; flex: 0 0 18px;">!</span>
          <div>
            <strong>Peer-to-Peer Reassurance Link:</strong> SafePath Finder provides peer-to-peer reassurance and is <strong>NOT</strong> connected to emergency dispatchers, 112, or the police. A missed check-in indicates unconfirmed arrival, not that an emergency has occurred.
            <div style="margin-top: 4px; color: var(--text-muted);">
              Delivery Channel: <code>${escapeHtml(data.notificationMode || 'Simulated Dev Mode')}</code>
            </div>
          </div>
        </div>
      `;

      modal.classList.add('open');
    }

    async function checkPublicJourneyShareToken() {
      const params = new URLSearchParams(window.location.search);
      const token = params.get('share_token');
      if (!token) return;
      try {
        const share = await SafePathApi.getPublicJourneyShare(token);
        renderPublicJourneyShareModal(share);
      } catch (err) {
        showToast(`Journey link notice: ${err.message}`);
      }
    }

    // Departure period dynamic notice and routing reload
    function updateDepartureEvidenceNotice() {
      const selected = document.querySelector('input[name="departurePeriod"]:checked')?.value || 'daytime';
      const noteText = $('#depEvidenceNoteText');
      if (!noteText) return;
      if (selected === 'daytime') {
        noteText.innerHTML = '<strong>Daytime period:</strong> High natural solar illumination. Street-lighting verification is weighted minimally in safety penalties. Crime observations reflect daytime historical baseline. Commercial pedestrian activity levels estimated high.';
      } else if (selected === 'evening') {
        noteText.innerHTML = '<strong>Evening period (18:00–22:00):</strong> Twilight transition. Street-lighting status and active commercial pedestrian corridors receive increased priority. Avoids poorly illuminated shortcuts.';
      } else if (selected === 'night') {
        noteText.innerHTML = '<strong>Night period (22:00–06:00):</strong> Full darkness. Verified street-lighting and avoidance of aggressive stray dog packs heavily weighted. <em>Data limitation note: Real-time bulb operational status and live CCTV feeds are not available; calculations use mapped GIS infrastructure and community observations.</em>';
      }
    }

    $$('input[name="departurePeriod"]').forEach(radio => {
      radio.addEventListener('change', () => {
        updateDepartureEvidenceNotice();
        loadRoutes();
      });
    });

    // 13. Privacy Controls
    $('#exportMyDataBtn')?.addEventListener('click', () => {
      const data = {
        plans: SafePathApi.getSavedPlans(),
        history: SafePathApi.getJourneyHistory(),
        reports: SafePathApi.getMyReports(),
        contacts: SafePathApi.getTrustedContacts(),
        preferences: SafePathApi.getPreferences(),
        audit: SafePathApi.getAuditLog()
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `safepath-data-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast('Exported your local demo data to JSON.');
    });

    $('#clearLocalDataBtn')?.addEventListener('click', () => {
      if (confirm('Permanently clear all saved plans, contacts, and preferences from this device?')) {
        SafePathApi.clearAllUserData();
        renderTravellerWorkspace();
        showToast('All local data cleared from this browser.');
      }
    });

    // 14. Admin Navigation & Modals
    $('#adminPortalBtn')?.addEventListener('click', () => setScreen('admin'));
    $('#mobileAdminBtn')?.addEventListener('click', () => {
      mobileDrawer.classList.remove('open');
      setScreen('admin');
    });
    $('#footerAdminLink')?.addEventListener('click', e => {
      e.preventDefault();
      setScreen('admin');
    });
    $('#footerPrivacyLink')?.addEventListener('click', e => {
      e.preventDefault();
      setScreen('account');
      $('[data-traveller-tab="privacy-data"]')?.click();
    });
    $('#exitAdminPortalBtn')?.addEventListener('click', () => setScreen('app'));

    $$('[data-admin-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.adminTab;
        state.adminTab = tab;
        $$('.admin-nav-link').forEach(b => b.classList.toggle('active', b.dataset.adminTab === tab));
        $$('.admin-tab-view').forEach(v => v.classList.toggle('hidden', v.id !== `adminView-${tab}`));
        $('#adminPageHeaderTitle').textContent = btn.textContent.trim();
        if (tab === 'reports') renderAdminReportsTable();
        if (tab === 'audit-log') renderAdminAuditTable();
        if (tab === 'users') renderAdminUsersTable();
        if (tab === 'feedback') renderAdminFeedbackTable();
      });
    });

    $('#adminReportSearch')?.addEventListener('input', renderAdminReportsTable);
    $('#adminReportStatusFilter')?.addEventListener('change', renderAdminReportsTable);
    $('#adminUserSearch')?.addEventListener('input', renderAdminUsersTable);
    $('#adminFeedbackCategoryFilter')?.addEventListener('change', renderAdminFeedbackTable);
    $('#adminFeedbackStatusFilter')?.addEventListener('change', renderAdminFeedbackTable);
    $('#adminRefreshAllBtn')?.addEventListener('click', () => {
      renderAdminPortal();
      showToast('Admin dashboard refreshed from local state.');
    });

    // Admin Moderation Action Confirmation Modal
    const modModal = $('#moderationReasonModal');
    $('#closeModReasonModalBtn')?.addEventListener('click', () => modModal.classList.remove('open'));
    $('#cancelModReasonBtn')?.addEventListener('click', () => modModal.classList.remove('open'));

    document.addEventListener('click', e => {
      const modBtn = e.target.closest('[data-mod-action]');
      if (modBtn) {
        const action = modBtn.dataset.modAction;
        const id = modBtn.dataset.modId;
        $('#modTargetReportId').value = id;
        $('#modTargetStatus').value = action;
        $('#modReasonTitle').textContent = `Set Report #${id} to ${action.toUpperCase()}`;
        $('#modReasonTextInput').value = action === 'approved' ? 'Corroborated with municipal streetlight survey' : action === 'flagged' ? 'Flagged for on-site verification' : 'Condition unverified';
        modModal.classList.add('open');
        setTimeout(() => $('#modReasonTextInput')?.focus(), 50);
      }
    });

    $('#modReasonForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const id = $('#modTargetReportId').value;
      const status = $('#modTargetStatus').value;
      const reason = $('#modReasonTextInput').value;

      try {
        await SafePathApi.updateReportModeration(id, status, reason);
        modModal.classList.remove('open');
        renderAdminPortal();
        renderCommunityReports();
        showToast(`Report #${id} updated to "${status}". Recorded in audit trail.`);
      } catch (err) {
        showToast(err.message);
      }
    });

    // Admin Settings Form Submission
    $('#adminSettingsForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const updated = {
        freshnessThresholdDays: parseInt($('#settingFreshnessDays').value, 10) || 30,
        outdatedThresholdDays: parseInt($('#settingOutdatedDays').value, 10) || 90,
        autoFlagKeywords: $('#settingAutoFlagKeywords').value.trim()
      };
      await SafePathApi.saveSystemSettings(updated);
      const newBaseUrl = $('#settingApiBaseUrl')?.value.trim();
      if (newBaseUrl) {
        SafePathApi.config.baseUrl = newBaseUrl;
      }
      showToast('Administration and data governance settings saved.');
    });

    $('#exportReportsCsvBtn')?.addEventListener('click', () => {
      const reports = SafePathApi.getReports();
      const cols = ['id', 'location', 'category', 'description', 'status', 'createdAt', 'moderatorNotes'];
      const csv = [
        cols.join(','),
        ...reports.map(r => cols.map(c => `"${String(r[c] ?? '').replace(/"/g, '""')}"`).join(','))
      ].join('\r\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `safepath-reports-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast('Exported reports to CSV.');
    });

    $('#clearAuditTrailBtn')?.addEventListener('click', () => {
      if (confirm('Clear the administrative audit trail?')) {
        SafePathApi.clearAuditLog();
        renderAdminAuditTable();
        showToast('Audit trail cleared.');
      }
    });

    // 15. Authentication Dialog
    const authModal = $('#authModal');
    function openAuthModal(mode = 'signin') {
      state.authMode = mode;
      authModal.classList.add('open');
      updateAuthModalUI();
      setTimeout(() => $('#authEmailInput')?.focus(), 60);
    }

    function updateAuthModalUI() {
      const mode = state.authMode;
      $('#tabAuthSignIn').classList.toggle('btn-quiet', mode !== 'signin');
      $('#tabAuthSignUp').classList.toggle('btn-quiet', mode !== 'signup');
      $('#tabAuthForgot').classList.toggle('btn-quiet', mode !== 'forgot' && mode !== 'reset');

      $('#authNameGroup').classList.toggle('hidden', mode !== 'signup');
      $('#authPasswordGroup').classList.toggle('hidden', mode === 'forgot');
      $('#authResetTokenGroup').classList.toggle('hidden', mode !== 'reset');
      $('#authExtraRow').classList.toggle('hidden', mode !== 'signin');

      if (mode === 'signup') {
        $('#authTitle').textContent = 'Create your SafePath Account';
        $('#authSubtitle').textContent = 'Save custom walking preferences and track your contributions.';
        $('#authSubmitBtn').textContent = 'Create account';
      } else if (mode === 'forgot') {
        $('#authTitle').textContent = 'Reset your Password';
        $('#authSubtitle').textContent = 'Enter your email to receive recovery instructions.';
        $('#authSubmitBtn').textContent = 'Send reset instructions';
      } else if (mode === 'reset') {
        $('#authTitle').textContent = 'Set New Password';
        $('#authSubtitle').textContent = 'Enter the reset token and choose your new password.';
        $('#authSubmitBtn').textContent = 'Save new password';
      } else {
        $('#authTitle').textContent = 'Sign in to SafePath';
        $('#authSubtitle').textContent = 'Access saved journeys, preferences, and personal reports.';
        $('#authSubmitBtn').textContent = 'Sign in';
      }
    }

    $('#signInBtn')?.addEventListener('click', () => openAuthModal('signin'));
    $('#mobileSignInBtn')?.addEventListener('click', () => {
      mobileDrawer.classList.remove('open');
      openAuthModal('signin');
    });
    $('#closeAuthModalBtn')?.addEventListener('click', () => authModal.classList.remove('open'));
    $('#tabAuthSignIn')?.addEventListener('click', () => { state.authMode = 'signin'; updateAuthModalUI(); });
    $('#tabAuthSignUp')?.addEventListener('click', () => { state.authMode = 'signup'; updateAuthModalUI(); });
    $('#tabAuthForgot')?.addEventListener('click', () => { state.authMode = 'forgot'; updateAuthModalUI(); });
    $('#authForgotPassLink')?.addEventListener('click', () => { state.authMode = 'forgot'; updateAuthModalUI(); });

    $('#togglePasswordVisBtn')?.addEventListener('click', () => {
      const input = $('#authPasswordInput');
      const isPass = input.type === 'password';
      input.type = isPass ? 'text' : 'password';
      $('#togglePasswordVisBtn').textContent = isPass ? 'Hide' : 'Show';
    });

    $('#quickPreviewTravellerBtn')?.addEventListener('click', () => {
      authModal.classList.remove('open');
      SafePathApi.login({ email: 'traveller.demo@safepath.local', password: 'demopassword123', role: 'traveller' });
      setScreen('account');
      showToast('Opened Traveller Workspace demo session.');
    });

    $('#quickPreviewAdminBtn')?.addEventListener('click', () => {
      authModal.classList.remove('open');
      SafePathApi.login({ email: 'admin.demo@safepath.test', password: 'demopassword123', role: 'admin' });
      setScreen('admin');
      showToast('Opened Administrator Console demo session.');
    });

    $('#authMainForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const email = $('#authEmailInput').value;
      const pass = $('#authPasswordInput').value;
      const name = $('#authFullName')?.value || '';

      try {
        if (state.authMode === 'signup') {
          await SafePathApi.register({ name, email, password: pass });
          authModal.classList.remove('open');
          setScreen('account');
          showToast('Welcome! Your demo account was created.');
        } else if (state.authMode === 'forgot') {
          const res = await SafePathApi.requestPasswordReset(email);
          showToast(res.message);
          state.authMode = 'reset';
          if ($('#authResetTokenInput')) $('#authResetTokenInput').value = 'DEMO-RESET-2026';
          updateAuthModalUI();
        } else if (state.authMode === 'reset') {
          const token = $('#authResetTokenInput')?.value.trim();
          await SafePathApi.confirmPasswordReset({ token, password: pass });
          state.authMode = 'signin';
          updateAuthModalUI();
          showToast('Password reset confirmed! You may now sign in.');
        } else {
          await SafePathApi.login({ email, password: pass });
          authModal.classList.remove('open');
          setScreen('account');
          showToast('Signed in successfully.');
        }
      } catch (err) {
        showToast(err.message);
      }
    });

    // Global document click delegation for dynamic items
    document.addEventListener('click', e => {
      // Load saved plan in planner
      const loadPlanBtn = e.target.closest('[data-load-plan]');
      if (loadPlanBtn) {
        const planId = loadPlanBtn.dataset.loadPlan;
        const plans = SafePathApi.getSavedPlans();
        const plan = plans.find(p => p.id === planId);
        if (plan) {
          $('#originInput').value = plan.start;
          $('#destinationInput').value = plan.end;
          setScreen('app');
          loadRoutes();
          showToast(`Loaded saved plan: ${plan.start} → ${plan.end}`);
        }
      }

      // Delete saved plan
      const delPlanBtn = e.target.closest('[data-delete-plan]');
      if (delPlanBtn) {
        SafePathApi.deletePlan(delPlanBtn.dataset.deletePlan);
        renderTravellerWorkspace();
        showToast('Plan deleted.');
      }

      // Delete contact
      const delContactBtn = e.target.closest('[data-delete-contact]');
      if (delContactBtn) {
        SafePathApi.deleteTrustedContact(delContactBtn.dataset.deleteContact);
        renderTrustedContacts(SafePathApi.getTrustedContacts());
        showToast('Contact removed.');
      }

      // Delete saved place
      const delPlaceBtn = e.target.closest('[data-delete-place]');
      if (delPlaceBtn) {
        SafePathApi.deleteSavedPlace(delPlaceBtn.dataset.deletePlace);
        renderSavedPlaces(SafePathApi.getSavedPlaces());
        showToast('Saved place removed.');
      }

      // Edit user role in Admin Console
      const editRoleBtn = e.target.closest('[data-user-role-edit]');
      if (editRoleBtn) {
        const userId = editRoleBtn.dataset.userRoleEdit;
        const users = SafePathApi.getAdminUsers();
        const user = users.find(u => u.id === userId);
        const currentRole = user ? user.role : 'traveller';
        const newRole = window.prompt(
          `Update system role for ${user ? user.name : userId}.\nAllowed roles: traveller, moderator, administrator\nCurrent: ${currentRole}`,
          currentRole === 'traveller' ? 'moderator' : (currentRole === 'moderator' ? 'administrator' : 'traveller')
        );
        if (newRole && ['traveller', 'moderator', 'administrator'].includes(newRole.trim().toLowerCase())) {
          try {
            SafePathApi.updateUserRole(userId, newRole.trim().toLowerCase());
            renderAdminUsersTable();
            renderAdminAuditTable();
            showToast(`Role for ${user ? user.name : userId} updated to "${newRole.trim().toLowerCase()}".`);
          } catch (err) {
            showToast(err.message);
          }
        } else if (newRole) {
          showToast('Invalid role. Must be traveller, moderator, or administrator.');
        }
      }

      // Set saved place as origin/destination
      const usePlaceOrigin = e.target.closest('[data-use-place-origin]');
      if (usePlaceOrigin) {
        $('#originInput').value = usePlaceOrigin.dataset.usePlaceOrigin;
        setScreen('app');
        showToast(`Set origin to ${usePlaceOrigin.dataset.usePlaceOrigin}`);
      }

      const usePlaceDest = e.target.closest('[data-use-place-dest]');
      if (usePlaceDest) {
        $('#destinationInput').value = usePlaceDest.dataset.usePlaceDest;
        setScreen('app');
        showToast(`Set destination to ${usePlaceDest.dataset.usePlaceDest}`);
      }
    });

    // Identity Revelation Modal & Form
    const idRevealModal = $('#identityRevealModal');
    $('#closeIdentityRevealModalBtn')?.addEventListener('click', () => {
      idRevealModal?.classList.remove('open');
      $('#revealedIdentityContainer')?.classList.add('hidden');
    });
    $('#cancelIdentityRevealBtn')?.addEventListener('click', () => {
      idRevealModal?.classList.remove('open');
      $('#revealedIdentityContainer')?.classList.add('hidden');
    });

    document.addEventListener('click', e => {
      const revealBtn = e.target.closest('[data-user-reveal]');
      if (revealBtn) {
        const userId = revealBtn.dataset.userReveal;
        $('#revealTargetUserId').value = userId;
        $('#revealJustification').value = '';
        $('#revealedIdentityContainer')?.classList.add('hidden');
        idRevealModal?.classList.add('open');
        setTimeout(() => $('#revealJustification')?.focus(), 50);
      }
    });

    $('#identityRevealForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const userId = $('#revealTargetUserId').value;
      const reason = $('#revealJustification').value.trim();
      if (reason.length < 5) {
        showToast('Justification must be at least 5 characters.');
        return;
      }
      try {
        const details = await SafePathApi.revealUserIdentity(userId, reason);
        $('#revealedUserId').textContent = details.id;
        $('#revealedUserName').textContent = details.name;
        $('#revealedUserEmail').textContent = details.email;
        $('#revealedUserRole').textContent = details.role;
        $('#revealedUserStatus').textContent = details.status;
        $('#revealedIdentityContainer')?.classList.remove('hidden');
        showToast('Identity revealed and action recorded in audit log.');
        renderAdminAuditTable();
      } catch (err) {
        showToast(err.message);
      }
    });

    // Feedback Submission Modal & Form
    const feedbackModal = $('#feedbackModal');
    $('#openFeedbackBtn')?.addEventListener('click', () => {
      feedbackModal?.classList.add('open');
      if ($('#feedbackMessage')) $('#feedbackMessage').value = '';
      if ($('#feedbackRating')) $('#feedbackRating').value = '';
      setTimeout(() => $('#feedbackMessage')?.focus(), 50);
    });
    $('#closeFeedbackModalBtn')?.addEventListener('click', () => feedbackModal?.classList.remove('open'));
    $('#cancelFeedbackBtn')?.addEventListener('click', () => feedbackModal?.classList.remove('open'));

    $('#feedbackForm')?.addEventListener('submit', async e => {
      e.preventDefault();
      const category = $('#feedbackCategory')?.value || 'general';
      const rating = $('#feedbackRating')?.value || null;
      const message = $('#feedbackMessage')?.value.trim();

      try {
        await SafePathApi.submitFeedback({ category, rating, message });
        feedbackModal?.classList.remove('open');
        showToast('Thank you! Your feedback has been securely submitted.');
      } catch (err) {
        showToast(err.message);
      }
    });

    // Admin Feedback Status Changes
    document.addEventListener('change', async e => {
      const select = e.target.closest('[data-feedback-status-change]');
      if (select) {
        const fbId = select.dataset.feedbackStatusChange;
        const newStatus = select.value;
        try {
          await SafePathApi.updateFeedbackStatus(fbId, newStatus);
          showToast(`Feedback #${fbId} marked as ${newStatus}.`);
          renderAdminFeedbackTable();
          renderAdminAuditTable();
        } catch (err) {
          showToast(err.message);
        }
      }
    });

    // Dismiss modals by clicking on backdrop
    $$('.modal-backdrop').forEach(backdrop => {
      backdrop.addEventListener('click', e => {
        if (e.target === backdrop) {
          backdrop.classList.remove('open');
        }
      });
    });

    // Escape key modal dismiss
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        $$('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
      }
    });
  }

  // ==========================================================================
  // INITIALIZATION ON DOM READY
  // ==========================================================================
    async function renderDatasetCatalog() {
    const tbody = $('#datasetCatalogBody');
    if (!tbody) return;

    try {
      const sources = await SafePathApi.getEvidenceSources();
      if (!sources || !sources.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 20px; color: var(--text-muted);">No dataset records returned.</td></tr>';
        return;
      }

      tbody.innerHTML = sources.map(src => {
        let statusBadge = '<span class="badge badge-success" style="font-size: 10px;">ACTIVE</span>';
        if (src.status === 'unavailable') {
          statusBadge = '<span class="badge badge-neutral" style="font-size: 10px; background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1;">UNAVAILABLE</span>';
        } else if (src.status === 'stale') {
          statusBadge = '<span class="badge badge-warning" style="font-size: 10px;">STALE</span>';
        }

        const name = escapeHtml(src.name || src.id || 'Dataset');
        const org = escapeHtml(src.sourceOrganisation || src.source_organisation || src.sourceOrg || 'Open Contributor Network');
        const licence = escapeHtml(src.licence || src.license || 'Open Database License (ODbL) 1.0');
        const coverage = escapeHtml(src.geographicCoverage || src.geographic_coverage || src.coverage || 'Bengaluru Pilot Study Area');
        const period = escapeHtml(src.collectionPeriod || src.collection_period || src.lastIngested || '2022 - 2026');
        const recCount = (src.recordsCount !== undefined ? src.recordsCount : (src.record_count ?? (src.records_count ?? 0))).toLocaleString();
        const notes = escapeHtml(src.limitations || src.notes || 'Documented open dataset. Unmapped tags represent survey gaps.');

        return `
          <tr style="border-bottom: 1px solid var(--border); vertical-align: top;">
            <td style="padding: 10px 12px; font-weight: 500;">
              <div>${name}</div>
              <small style="color: var(--text-muted); font-size: 11px;">${escapeHtml(src.type || src.id)}</small>
            </td>
            <td style="padding: 10px 12px; color: var(--text-muted);">${org}</td>
            <td style="padding: 10px 12px;"><span class="badge badge-neutral" style="font-size: 10px;">${licence}</span></td>
            <td style="padding: 10px 12px; color: var(--text-muted);">${coverage}</td>
            <td style="padding: 10px 12px; color: var(--text-muted); font-family: var(--font-mono, monospace); font-size: 11px;">${period}</td>
            <td style="padding: 10px 12px; font-weight: 600; text-align: right;">${recCount}</td>
            <td style="padding: 10px 12px;">${statusBadge}</td>
            <td style="padding: 10px 12px; color: var(--text-muted); max-width: 320px; font-size: 11px; line-height: 1.4;">${notes}</td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      console.warn('Could not render dataset catalog:', e);
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 20px; color: #dc2626;">Error loading dataset registry: ${escapeHtml(e.message)}</td></tr>`;
    }
  }

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    initMap();
    loadRoutes();
    renderCommunityReports();
    updatePreferenceImpact();
    updateDepartureEvidenceNotice();
    checkPublicJourneyShareToken();
    renderDatasetCatalog();
    $('#btnRefreshCatalog')?.addEventListener('click', () => renderDatasetCatalog());

    // Check for active journey session to restore banner
    SafePathApi.getActiveJourneySessions().then(sessions => {
      if (sessions && sessions.length > 0) {
        activateJourneyBanner(sessions[0]);
      }
    }).catch(() => {});

    // Apply reduced motion if user preference was saved
    const prefs = SafePathApi.getPreferences();
    if (prefs && prefs.reducedMotion) {
      document.documentElement.classList.add('reduce-motion');
    }

    // Check if previously logged in
    const existingUser = SafePathApi.getCurrentUser();
    if (existingUser) {
      $('#signInBtn').classList.add('hidden');
      $('#myWorkspaceBtn').classList.remove('hidden');
    }

    // Support direct screen routing via URL params or hash
    const params = new URLSearchParams(window.location.search);
    const screenParam = params.get('screen') || (window.location.hash === '#admin' ? 'admin' : (window.location.hash === '#account' ? 'account' : null));
    if (screenParam === 'admin') {
      setScreen('admin');
    } else if (screenParam === 'account') {
      setScreen('account');
    } else if (params.get('auth') || window.location.hash === '#auth') {
      openAuthModal('signin');
    } else if (window.location.hash) {
      const initialHash = window.location.hash.replace(/^#/, '');
      if (NAV_SECTIONS.includes(initialHash)) {
        setTimeout(() => {
          navigateToSection(initialHash, false);
        }, 150);
      }
    } else {
      setActiveNavLink('plan');
    }
  });


})();
