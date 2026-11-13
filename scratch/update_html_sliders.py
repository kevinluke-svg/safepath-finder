with open('safepath_pro.html', 'r') as f:
    content = f.read()

target = '''        <div class="pref-comparison-grid">
          <div class="pref-slider-card">
            <label for="sliderLighting">
              <span>Lighting evidence weight</span>
              <strong id="valLighting">50%</strong>
            </label>
            <input type="range" id="sliderLighting" min="0" max="100" value="50" step="5" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Penalizes routes with uncorroborated dark stretches.</small>
          </div>

          <div class="pref-slider-card">
            <label for="sliderUnknown">
              <span>Aversion to missing data</span>
              <strong id="valUnknown">30%</strong>
            </label>
            <input type="range" id="sliderUnknown" min="0" max="100" value="30" step="5" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Demands high verification before recommending residential shortcuts.</small>
          </div>

          <div class="pref-slider-card">
            <label for="sliderTime">
              <span>Travel time priority</span>
              <strong id="valTime">20%</strong>
            </label>
            <input type="range" id="sliderTime" min="0" max="100" value="20" step="5" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Favours direct geometry and shortest walking distance.</small>
          </div>
        </div>

        <div class="pref-impact-note" id="preferenceImpactNote">
          <strong>Current Ranking Logic:</strong> Evidence-led Route ranks #1 because lighting evidence and uncertainty aversion outweigh the 5-minute time savings of the Shortest Route.
        </div>'''

repl = '''        <div class="pref-comparison-grid">
          <div class="pref-slider-card">
            <label for="sliderLighting">
              <span>Street Lighting Weight (w_lighting)</span>
              <strong id="valLighting">50%</strong>
            </label>
            <input type="range" id="sliderLighting" min="0" max="100" value="50" step="5" aria-label="Street lighting weight percentage" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Calibrates illumination priority in composite risk R_observed.</small>
          </div>

          <div class="pref-slider-card">
            <label for="sliderUnknown">
              <span>Aversion to Missing Data (R_unknown)</span>
              <strong id="valUnknown">30%</strong>
            </label>
            <input type="range" id="sliderUnknown" min="0" max="100" value="30" step="5" aria-label="Aversion to missing data prior percentage" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Sets neutral prior R_unknown in R_effective = Q·R_obs + (1-Q)·R_unknown.</small>
          </div>

          <div class="pref-slider-card">
            <label for="sliderTime">
              <span>Travel Time Priority (vs &lambda; Risk Penalty)</span>
              <strong id="valTime">20%</strong>
            </label>
            <input type="range" id="sliderTime" min="0" max="100" value="20" step="5" aria-label="Travel time priority percentage" />
            <small style="font-size: 10.5px; color: var(--text-muted);">Scales lambda in Cost(e) = T(e) &times; (1 + &lambda; &times; R_effective(e)).</small>
          </div>
        </div>

        <!-- 6 Implemented Model Dimensions Documentation -->
        <div style="margin: 12px 0 10px 0; padding: 10px 14px; background: #ffffff; border: 1px solid var(--border); border-radius: 6px; font-size: 11px; line-height: 1.5; color: var(--text-muted);">
          <strong style="color: var(--text-main); display: block; margin-bottom: 4px;">Implemented Risk Dimensions & Weight Normalization:</strong>
          The backend synthesizes 6 empirical dimensions:
          <strong>(1) Street Lighting</strong> (OSM tags & surveyed lamps),
          <strong>(2) Pedestrian Infrastructure</strong> (sidewalks, crossings, tactile paving),
          <strong>(3) Stray Dog Encounters</strong> (calm vs aggressive reports),
          <strong>(4) Historical Crime</strong> (public incident bulletins),
          <strong>(5) Community Feedback</strong> (corroborated reports), and
          <strong>(6) Emergency Access</strong> (police & hospital proximity).
          Weights are dynamically normalized so &sum; w<sub>i</sub> = 1.0, adjusted by temporal profiles (Daytime, Evening, Night).
        </div>

        <div class="pref-impact-note" id="preferenceImpactNote">
          <strong>Interactive Sensitivity Evaluation:</strong> Adjust sliders to dynamically update backend parameters, re-run multi-criteria routing, and observe route trade-offs in real time.
        </div>'''

assert target in content, 'target not found in safepath_pro.html'
content = content.replace(target, repl, 1)

with open('safepath_pro.html', 'w') as f:
    f.write(content)
print('safepath_pro.html sliders updated successfully!')
