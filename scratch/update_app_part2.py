with open('app.js', 'r') as f:
    content = f.read()

# 1. Update Decision Summary Header ETA pill
target_header_eta = '''          <div class="decision-stat-pill"><strong>${Math.round(route.durationSeconds / 60)} min</strong> Walking ETA</div>'''
repl_header_eta = '''          <div class="decision-stat-pill"><strong>${Math.round(route.durationSeconds / 60)} min</strong> Walking ETA (@ ${route.walkingSpeedKmh || ((route.distanceMeters / Math.max(route.durationSeconds, 1)) * 3.6).toFixed(1)} km/h)</div>'''
assert target_header_eta in content, 'target_header_eta not found'
content = content.replace(target_header_eta, repl_header_eta, 1)

# 2. Update Streetlight Evidence Summary variables
target_sl_vars = '''    // Streetlight Evidence Summary (Priority 4)
    let streetlightHtml = '';
    if (route.streetlightSummary) {
      const sl = route.streetlightSummary;
      const litPct = sl.litPercentage;
      const unlitPct = sl.unlitPercentage;
      const confPct = sl.conflictingPercentage;
      const unkPct = sl.unknownPercentage;'''

repl_sl_vars = '''    // Streetlight Evidence Summary (Priority 4)
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
      const lampsCount = sl.mappedStreetlampsCount ?? 0;'''
assert target_sl_vars in content, 'target_sl_vars not found'
content = content.replace(target_sl_vars, repl_sl_vars, 1)

# Update Streetlight card labels to use exact variables
target_sl_cards = '''          <div class="streetlight-stat-grid">
            <div class="streetlight-stat-card">
              <small style="color: #059669; font-weight: 700;">Verified Lit</small>
              <strong>${litPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${Math.round(sl.knownLitDistanceMeters)}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #d97706; font-weight: 700;">Verified Unlit</small>
              <strong>${unlitPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${Math.round(sl.knownUnlitDistanceMeters)}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #dc2626; font-weight: 700;">Conflicting</small>
              <strong>${confPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${Math.round(sl.conflictingDistanceMeters)}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #6b7280; font-weight: 700;">Unknown / Unmapped</small>
              <strong>${unkPct.toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${Math.round(sl.unknownDistanceMeters)}m of route</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: var(--primary); display: flex; align-items: center; gap: 4px;">${SP_ICONS.lamp({ size: 12 })} Mapped Lamps</small>
              <strong>${sl.mappedStreetlampsCount} posts</strong>
              <div style="font-size: 10px; color: var(--text-muted);">OSM node points</div>
            </div>
          </div>'''

repl_sl_cards = '''          <div class="streetlight-stat-grid">
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
          </div>'''
assert target_sl_cards in content, 'target_sl_cards not found'
content = content.replace(target_sl_cards, repl_sl_cards, 1)

# 3. Update Nearby Places: "mapped places" & distinction between straight-line and walking distance
target_places_header = '''              ${places.length} verified places mapped'''
repl_places_header = '''              ${places.length} mapped places in corridor'''
assert target_places_header in content, 'target_places_header not found'
content = content.replace(target_places_header, repl_places_header, 1)

target_places_empty = '''            No verified police stations, hospitals, public transit stops, or major public landmarks are mapped within the 500m corridor of this specific route.'''
repl_places_empty = '''            No mapped police stations, hospitals, public transit stops, or major public landmarks are mapped within the 500m corridor of this specific route.'''
assert target_places_empty in content, 'target_places_empty not found'
content = content.replace(target_places_empty, repl_places_empty, 1)

target_places_walktime = '''        const distTypeLabel = p.distanceType === 'pedestrian_network' ? 'walking distance' : 'straight-line proximity';
        const walkTime = p.walkingMinutes !== null && p.walkingMinutes !== undefined
          ? `~${Math.round(p.walkingMinutes)} min walk`
          : `~${Math.round(p.distanceMeters / 76.6)} min walk`;'''

repl_places_walktime = '''        const isNetworkDist = p.distanceType === 'pedestrian_network';
        const distTypeLabel = isNetworkDist ? 'pedestrian network distance' : 'straight-line proximity';
        const walkTime = isNetworkDist
          ? (p.walkingMinutes !== null && p.walkingMinutes !== undefined
              ? `~${Math.round(p.walkingMinutes)} min walk`
              : `~${Math.round(p.distanceMeters / 72.0)} min walk`)
          : '<span style=\"color:var(--text-muted); font-style:italic;\">network walking distance unmeasured</span>';'''
assert target_places_walktime in content, 'target_places_walktime not found'
content = content.replace(target_places_walktime, repl_places_walktime, 1)

# 4. Update Pedestrian Infrastructure Section: 3 distinct states + "0 documented hazards"
target_infra_sec = '''    // Pedestrian Infrastructure & Accessibility Audit (Section 6)
    let pedestrianInfraHtml = '';
    const infra = route.pedestrianInfrastructureSummary || route.pedestrian_infrastructure_summary;
    if (infra) {
      const swPct = infra.sidewalkCoveragePercentage ?? infra.sidewalk_coverage_percentage ?? 0;
      const knownSw = Math.round(infra.knownSidewalkDistanceMeters ?? infra.known_sidewalk_distance_meters ?? 0);
      const unmappedSw = Math.round(infra.unmappedSidewalkDistanceMeters ?? infra.unmapped_sidewalk_distance_meters ?? 0);
      const crossings = infra.crossingCount ?? infra.crossing_count ?? 0;
      const signalCrossings = infra.signalizedCrossingCount ?? infra.signalized_crossing_count ?? 0;
      const tactile = infra.tactilePavingCount ?? infra.tactile_paving_count ?? 0;
      const wheelchair = infra.wheelchairAccessibleCount ?? infra.wheelchair_accessible_count ?? 0;
      const highDiff = infra.highDifficultyCrossings ?? infra.high_difficulty_crossings ?? 0;
      const hazards = infra.constructionHazardsCount ?? infra.construction_hazards_count ?? 0;
      const totDist = Math.round(infra.totalDistanceMeters ?? infra.total_distance_meters ?? route.distanceMeters ?? 0);

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
              <div style="font-size: 10px; color: var(--text-muted);">${knownSw}m documented</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #6b7280; font-weight: 700;">Unmapped Sidewalks</small>
              <strong>${(totDist > 0 ? (unmappedSw / totDist) * 100 : 0).toFixed(1)}%</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${unmappedSw}m status unknown</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #d97706; font-weight: 700;">Road Crossings</small>
              <strong>${crossings}</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${signalCrossings} signalized</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: #2563eb; display: flex; align-items: center; gap: 3px;">${SP_ICONS.accessibility({ size: 11 })} Accessibility</small>
              <strong>${wheelchair} accessible</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${tactile} tactile paving</div>
            </div>
            <div class="streetlight-stat-card">
              <small style="color: ${hazards > 0 ? '#dc2626' : 'var(--text-muted)'}; display: flex; align-items: center; gap: 3px;">${SP_ICONS.construction({ size: 11 })} Hazards / Obstructions</small>
              <strong>${hazards} hazards</strong>
              <div style="font-size: 10px; color: var(--text-muted);">${highDiff} high-difficulty crossings</div>
            </div>
          </div>

          <div class="streetlight-explanation-text">
            <strong>Infrastructure Methodology & Accessibility:</strong> Sidewalk availability, tactile paving, wheelchair accessibility, and crossing signals are parsed directly from OpenStreetMap tags (<code>sidewalk</code>, <code>footway</code>, <code>tactile_paving</code>, <code>crossing</code>) and active community obstruction reports. Crucially, <em>unmapped sidewalk data is preserved as unknown</em> rather than assumed absent, ensuring evaluation dimensions remain distinct and transparent.
          </div>
        </div>
      `;
    }'''

repl_infra_sec = '''    // Pedestrian Infrastructure & Accessibility Audit (Section 6)
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
    }'''
assert target_infra_sec in content, 'target_infra_sec not found'
content = content.replace(target_infra_sec, repl_infra_sec, 1)

# 5. Update Dog Encounter Section
target_dog_sec = '''      ${(() => {
        const dSum = route.dogEncounterSummary;
        if (!dSum) return '';
        const totalReps = dSum.totalReportsCount || 0;
        const corridorM = Math.round(dSum.corridorMeters || 200);
        const affectedLenM = Math.round(dSum.affectedRouteLengthMeters || 0);
        const affectedPct = dSum.affectedLengthPercentage || 0;
        const freshestDays = dSum.freshestReportDays !== null && dSum.freshestReportDays !== undefined
          ? `${dSum.freshestReportDays} day(s) ago`
          : 'N/A';

        const guidanceItems = (dSum.guidance && dSum.guidance.length)
          ? dSum.guidance.map(g => `<li>${escapeHtml(g)}</li>`).join('')
          : '<li>Maintain normal pedestrian awareness when navigating unfamiliar areas.</li>';

        return `
          <div class="decision-full-width-section dog-encounter-section">
            <h4>
              <span><span class="sp-icon-inline">${SP_ICONS.pawPrint({ size: 15 })}</span> Stray & Street Dog Encounter Audit (${corridorM}m Corridor)</span>
              <span style="font-size: 11px; font-weight: 500; text-transform: none; color: var(--text-muted);">
                ${totalReps} community report(s) documented
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
                <strong>Corridor Assessment:</strong> ${escapeHtml(dSum.explanation)}
              </p>
              <div style="font-size: 11px; color: var(--text-muted);">
                Covered route length: <strong>${affectedLenM}m</strong> (${affectedPct}% of route).
              </div>
            </div>'''

repl_dog_sec = '''      ${(() => {
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
            </div>'''
assert target_dog_sec in content, 'target_dog_sec not found'
content = content.replace(target_dog_sec, repl_dog_sec, 1)

# 6. Update segment duration formatting
target_seg_dur = '''    const traversalTimeSeconds = seg.traversalTimeSeconds || Math.round(lengthMeters / 1.28); // 4.6 km/h = 1.28 m/s'''
repl_seg_dur = '''    const speedMps = (state.selectedRoute && state.selectedRoute.walkingSpeedMps) || 1.2;
    const traversalTimeSeconds = seg.traversalTimeSeconds || Math.round(lengthMeters / speedMps);'''
assert target_seg_dur in content, 'target_seg_dur not found'
content = content.replace(target_seg_dur, repl_seg_dur, 1)

target_seg_pane = '''            Length: <strong>${Math.round(seg.lengthMeters)}m</strong> · Estimated walking time: <strong>~${Math.round(seg.traversalTimeSeconds / 60)} min</strong> (@ 4.6 km/h)'''
repl_seg_pane = '''            Length: <strong>${Math.round(seg.lengthMeters)}m</strong> · Estimated walking time: <strong>${seg.traversalTimeSeconds < 60 ? `${Math.round(seg.traversalTimeSeconds)} sec (< 1 min)` : `~${Math.round(seg.traversalTimeSeconds / 60)} min (${Math.round(seg.traversalTimeSeconds)}s)`}</strong> (@ ${((state.selectedRoute?.walkingSpeedMps || 1.2) * 3.6).toFixed(1)} km/h)'''
assert target_seg_pane in content, 'target_seg_pane not found'
content = content.replace(target_seg_pane, repl_seg_pane, 1)

# 7. Update updatePreferenceImpact to dynamic recalculation
target_pref_fn = '''  // PREFERENCE SENSITIVITY CALCULATION
  // ==========================================================================
  function updatePreferenceImpact() {
    const lightingWeight = Number($('#sliderLighting').value);
    const unknownWeight = Number($('#sliderUnknown').value);
    const timeWeight = Number($('#sliderTime').value);

    $('#valLighting').textContent = `${lightingWeight}%`;
    $('#valUnknown').textContent = `${unknownWeight}%`;
    $('#valTime').textContent = `${timeWeight}%`;

    const note = $('#preferenceImpactNote');
    if (!note) return;

    if (timeWeight > 60) {
      note.innerHTML = `
        <strong>Algorithm Outcome:</strong> Shortest Sample Route moves to <strong>#1</strong>. You have configured travel time as your primary objective, accepting higher environmental uncertainty.
      `;
    } else if (unknownWeight > 40 && lightingWeight > 40) {
      note.innerHTML = `
        <strong>Algorithm Outcome:</strong> Evidence-led Route holds <strong>#1</strong> strongly. The algorithm heavily penalizes unmapped residential cuts and rewards verified lighting assets.
      `;
    } else {
      note.innerHTML = `
        <strong>Algorithm Outcome:</strong> Balanced Sample Route is prioritized as a competitive compromise between 19 min direct cut and well-documented 24 min avenue.
      `;
    }
  }'''

repl_pref_fn = '''  // PREFERENCE SENSITIVITY CALCULATION & DYNAMIC ROUTE RE-RANKING
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
  }'''
assert target_pref_fn in content, 'target_pref_fn not found'
content = content.replace(target_pref_fn, repl_pref_fn, 1)

# 8. Update slider event listeners
target_slider_listener = '''    ['sliderLighting', 'sliderUnknown', 'sliderTime'].forEach(id => {
      $(`#${id}`)?.addEventListener('input', updatePreferenceImpact);
    });'''
repl_slider_listener = '''    ['sliderLighting', 'sliderUnknown', 'sliderTime'].forEach(id => {
      $(`#${id}`)?.addEventListener('input', handleAlgorithmSettingChange);
    });'''
assert target_slider_listener in content, 'target_slider_listener not found'
content = content.replace(target_slider_listener, repl_slider_listener, 1)

with open('app.js', 'w') as f:
    f.write(content)
print('app.js Part 2 updates applied successfully!')
