/* ==========================================================================
   SafePath Finder — Professional SVG Icon System
   Consistent outline SVG icons replacing all emoji usage.
   Stroke-based, 16x16 default, 1.5px stroke width.
   ========================================================================== */

const SP_ICONS = (() => {
  const DEFAULT_SIZE = 16;
  const DEFAULT_STROKE = 1.5;

  function svg(paths, { size = DEFAULT_SIZE, stroke = DEFAULT_STROKE, cls = "", color = "currentColor", fill = "none", viewBox = "0 0 24 24", ariaLabel = "" } = {}) {
    const ariaAttr = ariaLabel ? `role="img" aria-label="${ariaLabel}"` : `aria-hidden="true"`;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${viewBox}" fill="${fill}" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" class="sp-icon ${cls}" ${ariaAttr}>${paths}</svg>`;
  }

  // — Navigation & Routes
  const route = (opts) => svg('<circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M12 19h4.5a3.5 3.5 0 0 0 0-7h-8a3.5 3.5 0 0 1 0-7H12"/>', opts);
  const navigation = (opts) => svg('<polygon points="3 11 22 2 13 21 11 13 3 11"/>', opts);
  const mapPin = (opts) => svg('<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>', opts);
  const compass = (opts) => svg('<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>', opts);

  // — Route Preference Icons
  const clock = (opts) => svg('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>', opts);
  const scale = (opts) => svg('<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>', opts);
  const shieldCheck = (opts) => svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>', opts);
  const gitFork = (opts) => svg('<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/>', opts);
  const sliders = (opts) => svg('<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/>', opts);

  // — Time of Day Selectors
  const sun = (opts) => svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>', opts);
  const sunset = (opts) => svg('<path d="M12 10V2"/><path d="m4.93 10.93 1.41 1.41"/><path d="M2 18h2"/><path d="M20 18h2"/><path d="m19.07 10.93-1.41 1.41"/><path d="M22 22H2"/><path d="m8 6 4-4 4 4"/><path d="M16 18a4 4 0 0 0-8 0"/>', opts);
  const moon = (opts) => svg('<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>', opts);

  // — Evidence & Safety
  const alertTriangle = (opts) => svg('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>', opts);
  const shieldAlert = (opts) => svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/>', opts);
  const shield = (opts) => svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>', opts);
  const info = (opts) => svg('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>', opts);
  const eye = (opts) => svg('<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>', opts);
  const search = (opts) => svg('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', opts);
  const checkCircle = (opts) => svg('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>', opts);
  const check = (opts) => svg('<polyline points="20 6 9 17 4 12"/>', opts);
  const x = (opts) => svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', opts);

  // — Street Infrastructure & Lighting
  const lightbulb = (opts) => svg('<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>', opts);
  const lamp = (opts) => svg('<path d="M8 2h8l4 10H4L8 2Z"/><path d="M12 12v6"/><path d="M8 22v-2c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v2H8Z"/>', opts);
  const footprints = (opts) => svg('<path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5 10 7.89 8.73 10 7.5 11.5l-1 1"/><path d="M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 2.39 1.27 4.11 2.5 5.5l1 1"/><path d="M7.5 16h3"/><path d="M13.5 20h3"/>', opts);
  const accessibility = (opts) => svg('<circle cx="16" cy="4" r="1"/><path d="m18 19 1-7-6 1"/><path d="m5 8 3-3 5.5 3-2.36 3.5"/><path d="M4.24 14.5a5 5 0 0 0 6.88 6"/><path d="M13.76 17.5a5 5 0 0 0-6.88-6"/>', opts);
  const construction = (opts) => svg('<rect x="2" y="6" width="20" height="8" rx="1"/><path d="M17 14v7"/><path d="M7 14v7"/><path d="M17 3v3"/><path d="M7 3v3"/><path d="M10 14 2.3 6.3"/><path d="M14 6l7.7 7.7"/><path d="M8 6l8 8"/>', opts);

  // — Dog & Animal Encounters
  const pawPrint = (opts) => svg('<circle cx="11" cy="4" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="20" cy="16" r="2"/><path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.045Q6.52 17.48 4.46 16.84A3.5 3.5 0 0 1 5.5 10Z"/>', { viewBox: "0 0 24 24", ...opts });
  const siren = (opts) => svg('<path d="M7 18v-6a5 5 0 1 1 10 0v6"/><path d="M5 21a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1H5Z"/><path d="M12 12v-2"/><path d="M12 4h.01"/>', opts);

  // — Facilities & Civic Points
  const hospital = (opts) => svg('<path d="M12 6v4"/><path d="M14 14h-4"/><path d="M14 18h-4"/><path d="M14 8h-4"/><path d="M18 12h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2"/><path d="M18 22V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v18"/>', opts);
  const building = (opts) => svg('<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>', opts);
  const train = (opts) => svg('<rect width="16" height="16" x="4" y="3" rx="2"/><path d="M4 11h16"/><path d="M12 3v8"/><path d="m8 19-2 3"/><path d="m18 22-2-3"/><path d="M8 15h0"/><path d="M16 15h0"/>', opts);
  const trees = (opts) => svg('<path d="M10 10v.2A3 3 0 0 1 8.9 16v0H5v0h0a3 3 0 0 1-1-5.8V10a3 3 0 0 1 6 0Z"/><path d="M7 16v6"/><path d="M13 19v3"/><path d="M18 22v-8.3a4 4 0 0 0-1.8-3.3L15 9.7V7a3 3 0 1 1 6 0v2.7l-1.2.7a4 4 0 0 0-1.8 3.3Z"/>', opts);
  const landmark = (opts) => svg('<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/><line x1="1" x2="23" y1="22" y2="22"/>', opts);
  const store = (opts) => svg('<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M22 7v3a2 2 0 0 1-2 2v0a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12v0a2 2 0 0 1-2-2V7"/>', opts);
  const graduationCap = (opts) => svg('<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 10 3 12 0v-5"/>', opts);
  const pill = (opts) => svg('<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>', opts);

  // — Community & People
  const messageSquare = (opts) => svg('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>', opts);
  const users = (opts) => svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', opts);
  const user = (opts) => svg('<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>', opts);
  const userCheck = (opts) => svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>', opts);
  const heart = (opts) => svg('<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>', opts);

  // — Actions & UI
  const share2 = (opts) => svg('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>', opts);
  const copy = (opts) => svg('<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>', opts);
  const plus = (opts) => svg('<path d="M5 12h14"/><path d="M12 5v14"/>', opts);
  const arrowUpRight = (opts) => svg('<path d="M7 7h10v10"/><path d="M7 17 17 7"/>', opts);
  const arrowLeft = (opts) => svg('<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>', opts);
  const arrowRight = (opts) => svg('<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>', opts);
  const download = (opts) => svg('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>', opts);
  const refresh = (opts) => svg('<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>', opts);
  const filter = (opts) => svg('<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>', opts);
  const settings = (opts) => svg('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>', opts);
  const grid = (opts) => svg('<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>', opts);
  const list = (opts) => svg('<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>', opts);
  const fileText = (opts) => svg('<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>', opts);
  const barChart = (opts) => svg('<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>', opts);
  const gauge = (opts) => svg('<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>', opts);
  const crosshair = (opts) => svg('<circle cx="12" cy="12" r="10"/><line x1="22" x2="18" y1="12" y2="12"/><line x1="6" x2="2" y1="12" y2="12"/><line x1="12" x2="12" y1="6" y2="2"/><line x1="12" x2="12" y1="22" y2="18"/>', opts);
  const locateFixed = (opts) => svg('<line x1="2" x2="5" y1="12" y2="12"/><line x1="19" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="5"/><line x1="12" x2="12" y1="19" y2="22"/><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3"/>', opts);
  const flag = (opts) => svg('<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>', opts);
  const edit = (opts) => svg('<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>', opts);
  const trash = (opts) => svg('<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>', opts);
  const bookmark = (opts) => svg('<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>', opts);
  const history = (opts) => svg('<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>', opts);
  const brain = (opts) => svg('<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>', opts);
  const menu = (opts) => svg('<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>', opts);
  const star = (opts) => svg('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>', opts);
  const calendar = (opts) => svg('<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>', opts);
  const loader = (opts) => svg('<line x1="12" x2="12" y1="2" y2="6"/><line x1="12" x2="12" y1="18" y2="22"/><line x1="4.93" x2="7.76" y1="4.93" y2="7.76"/><line x1="16.24" x2="19.07" y1="16.24" y2="19.07"/><line x1="2" x2="6" y1="12" y2="12"/><line x1="18" x2="22" y1="12" y2="12"/><line x1="4.93" x2="7.76" y1="19.07" y2="16.24"/><line x1="16.24" x2="19.07" y1="7.76" y2="4.93"/>', opts);
  const lock = (opts) => svg('<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>', opts);
  const key = (opts) => svg('<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>', opts);

  // Icon catalog map for dynamic lookup
  const icons = {
    route, navigation, mapPin, compass,
    clock, scale, shieldCheck, gitFork, sliders,
    sun, sunset, moon,
    alertTriangle, shieldAlert, shield, info, eye, search, checkCircle, check, x,
    lightbulb, lamp, footprints, accessibility, construction,
    pawPrint, siren,
    hospital, building, train, trees, landmark, store, graduationCap, pill,
    messageSquare, users, user, userCheck, heart,
    share2, copy, plus, arrowUpRight, arrowLeft, arrowRight, download, refresh, filter,
    settings, grid, list, fileText, barChart, gauge, crosshair, locateFixed,
    flag, edit, trash, bookmark, history, brain, menu, star, calendar, loader, lock, key
  };

  function render(name, opts = {}) {
    if (icons[name]) {
      return icons[name](opts);
    }
    return info(opts);
  }

  /**
   * Leaflet Map Marker HTML Generator
   * Generates clean, accessible SVG markers distinguishable by BOTH shape and outline icon.
   * Does NOT rely on color alone.
   */
  function createMarkerHtml(type, { label = "", size = 28, letter = "", dogCount = null } = {}) {
    let shapeClass = "sp-shape-circle";
    let innerSvg = "";
    let bgClass = "sp-bg-neutral";
    let tooltip = label || type;

    switch (type) {
      case "police":
        shapeClass = "sp-shape-shield";
        bgClass = "sp-bg-navy";
        innerSvg = shield({ size: 14, stroke: 2, color: "#ffffff" });
        break;

      case "hospital":
      case "clinic":
        shapeClass = "sp-shape-square";
        bgClass = "sp-bg-crimson";
        innerSvg = hospital({ size: 14, stroke: 2, color: "#ffffff" });
        break;

      case "pharmacy":
        shapeClass = "sp-shape-capsule";
        bgClass = "sp-bg-teal";
        innerSvg = pill({ size: 13, stroke: 2, color: "#ffffff" });
        break;

      case "transit":
        shapeClass = "sp-shape-square";
        bgClass = "sp-bg-sky";
        innerSvg = train({ size: 13, stroke: 1.8, color: "#ffffff" });
        break;

      case "park":
        shapeClass = "sp-shape-hexagon";
        bgClass = "sp-bg-emerald";
        innerSvg = trees({ size: 13, stroke: 1.8, color: "#ffffff" });
        break;

      case "landmark":
        shapeClass = "sp-shape-squircle";
        bgClass = "sp-bg-amber";
        innerSvg = landmark({ size: 13, stroke: 1.8, color: "#ffffff" });
        break;

      // Stray Dog Encounters Distinguishable By Severity
      case "dog_sighting":
        shapeClass = "sp-shape-circle";
        bgClass = "sp-bg-slate";
        innerSvg = pawPrint({ size: 13, stroke: 1.8, color: "#ffffff" });
        break;

      case "dog_group":
        shapeClass = "sp-shape-squircle sp-marker-pack";
        bgClass = "sp-bg-indigo";
        innerSvg = `<span class="sp-inner-wrap">${pawPrint({ size: 11, stroke: 1.8, color: "#ffffff" })}<span class="sp-pack-tag">${dogCount ? dogCount : "2+"}</span></span>`;
        break;

      case "dog_aggressive":
        shapeClass = "sp-shape-diamond";
        bgClass = "sp-bg-amber-dark";
        innerSvg = alertTriangle({ size: 13, stroke: 2, color: "#ffffff" });
        break;

      case "dog_bite":
        shapeClass = "sp-shape-octagon";
        bgClass = "sp-bg-dark-crimson";
        innerSvg = shieldAlert({ size: 14, stroke: 2.2, color: "#ffffff" });
        break;

      case "community":
      case "observation":
        shapeClass = "sp-shape-diamond";
        bgClass = "sp-bg-violet";
        innerSvg = messageSquare({ size: 12, stroke: 2, color: "#ffffff" });
        break;

      case "hazard":
      case "infrastructure_hazard":
        shapeClass = "sp-shape-triangle";
        bgClass = "sp-bg-amber-dark";
        innerSvg = construction({ size: 12, stroke: 2, color: "#ffffff" });
        break;

      case "origin":
        shapeClass = "sp-shape-circle sp-marker-endpoint sp-marker-origin";
        bgClass = "sp-bg-teal";
        innerSvg = `<span class="sp-marker-letter">${letter || "A"}</span>`;
        break;

      case "destination":
        shapeClass = "sp-shape-square sp-marker-endpoint sp-marker-dest";
        bgClass = "sp-bg-crimson";
        innerSvg = `<span class="sp-marker-letter">${letter || "B"}</span>`;
        break;

      default:
        shapeClass = "sp-shape-circle";
        bgClass = "sp-bg-neutral";
        innerSvg = mapPin({ size: 13, stroke: 2, color: "#ffffff" });
        break;
    }

    return `<div class="sp-marker ${shapeClass} ${bgClass}" style="width:${size}px; height:${size}px;" title="${escapeAttr(tooltip)}" role="img" aria-label="${escapeAttr(tooltip)}">${innerSvg}</div>`;
  }

  function escapeAttr(s) {
    if (!s) return "";
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  return {
    ...icons,
    render,
    createMarkerHtml
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = SP_ICONS;
}
