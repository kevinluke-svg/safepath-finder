with open('app.js', 'r') as f:
    content = f.read()

# 1. Update route cards infraHtml
target_infra_card = '''      // Infrastructure summary
      let infraHtml = '';
      if (route.infrastructureSummary) {
        const inf = route.infrastructureSummary;
        infraHtml = `
          <div style="font-size: 11px; margin-top: 5px; color: #047857; display: flex; align-items: center; justify-content: space-between; background: #ecfdf5; padding: 4px 8px; border-radius: 4px; border: 1px solid #a7f3d0;">
            <span><span class="sp-icon-inline">${SP_ICONS.footprints({ size: 12 })}</span> <strong>Pedestrian Footpaths:</strong></span>
            <span>${Math.round(inf.sidewalkCoveragePercentage || 85)}% sidewalk (${inf.designatedCrossingsCount || 2} crossings)</span>
          </div>
        `;
      }'''

repl_infra_card = '''      // Infrastructure summary
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
      }'''
assert target_infra_card in content, 'target_infra_card not found'
content = content.replace(target_infra_card, repl_infra_card, 1)

# 2. Update crime evidence in route cards
target_crime_card = '''      // Crime evidence summary
      let crimeHtml = '';
      const crimeCount = route.crimeCount !== undefined ? route.crimeCount : (route.evidenceSummary?.crimeIncidentsCount || 0);
      crimeHtml = `
        <div style="font-size: 11px; margin-top: 5px; color: #475569; display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 4px 8px; border-radius: 4px; border: 1px solid #e2e8f0;">
          <span><span class="sp-icon-inline">${SP_ICONS.shieldAlert({ size: 12 })}</span> <strong>Historical Crime Evidence:</strong></span>
          <span>${crimeCount === 0 ? '0 recorded incidents' : `${crimeCount} historical incident(s)`}</span>
        </div>
      `;'''

repl_crime_card = '''      // Crime evidence summary
      let crimeHtml = '';
      const crimeCount = route.crimeCount !== undefined ? route.crimeCount : (route.evidenceSummary?.crimeIncidentsCount || route.evidenceSummary?.crimeCount || 0);
      crimeHtml = `
        <div style="font-size: 11px; margin-top: 5px; color: #475569; display: flex; align-items: center; justify-content: space-between; background: #f8fafc; padding: 4px 8px; border-radius: 4px; border: 1px solid #e2e8f0;">
          <span><span class="sp-icon-inline">${SP_ICONS.shieldAlert({ size: 12 })}</span> <strong>Crime Dataset Evidence:</strong></span>
          <span>${crimeCount === 0 ? 'No incidents recorded in available dataset' : `${crimeCount} historical incident(s)`}</span>
        </div>
      `;'''
assert target_crime_card in content, 'target_crime_card not found'
content = content.replace(target_crime_card, repl_crime_card, 1)

# 3. Update walking speed & distance in route cards
target_speed_card = '''          <div class="route-metric-box">
            <div class="route-duration">
              ${Math.round(route.durationSeconds / 60)} <span>min walk</span>
              ${timeDiffHtml}
            </div>
            <div class="route-distance">${(route.distanceMeters / 1000).toFixed(2)} km · walking speed 4.6 km/h</div>
          </div>'''

repl_speed_card = '''          <div class="route-metric-box">
            <div class="route-duration">
              ${Math.round(route.durationSeconds / 60)} <span>min walk</span>
              ${timeDiffHtml}
            </div>
            <div class="route-distance">${(route.distanceMeters / 1000).toFixed(2)} km · walking speed ${route.walkingSpeedKmh || ((route.distanceMeters / Math.max(route.durationSeconds, 1)) * 3.6).toFixed(1)} km/h</div>
          </div>'''
assert target_speed_card in content, 'target_speed_card not found'
content = content.replace(target_speed_card, repl_speed_card, 1)

# 4. Update Model Risk label on route cards
target_risk_card = '''            <div class="route-env-metric-item">
              <small>Model Risk (Eff / Obs)</small>'''
repl_risk_card = '''            <div class="route-env-metric-item">
              <small title="Relative multi-attribute risk indicator [0.0 - 1.0], not probability of victimization">Model Risk Indicator (Eff / Obs)</small>'''
assert target_risk_card in content, 'target_risk_card not found'
content = content.replace(target_risk_card, repl_risk_card, 1)

with open('app.js', 'w') as f:
    f.write(content)
print('app.js Part 1 updates applied successfully!')
