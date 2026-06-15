// AI Career Assistant — interactive 3D frontend
// Talks to the existing FastAPI backend: /api/scrape, /api/scrape/cancel,
// /api/verify, /api/logs/stream (SSE).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

/* =========================================================
   1) Interactive 3D globe
   ========================================================= */
const Globe = (() => {
  const wrap = document.getElementById('globe-wrap');
  const canvas = document.getElementById('globe-canvas');
  const fallback = document.getElementById('globe-fallback');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const RADIUS = 2;

  // Platform "hubs" on the globe (lat/lng chosen for visual spread).
  const HUBS = {
    indeed:   { lat: 38,  lng: -97,  color: 0x2557a7 },
    linkedin: { lat: 37,  lng: -122, color: 0x38bdf8 },
  };

  let scene, camera, renderer, controls, clock, globeGroup, arcsGroup, pinsGroup;
  const arcs = [];
  const pins = [];
  const headVec = new THREE.Vector3();
  let activeBoost = 0;
  let ok = false;

  function latLngToVec3(lat, lng, r = RADIUS) {
    const phi = (90 - lat) * Math.PI / 180;
    const theta = (lng + 180) * Math.PI / 180;
    return new THREE.Vector3(
      -r * Math.sin(phi) * Math.cos(theta),
       r * Math.cos(phi),
       r * Math.sin(phi) * Math.sin(theta)
    );
  }

  function buildGraticule() {
    const group = new THREE.Group();
    const mat = new THREE.LineBasicMaterial({ color: 0x1f6feb, transparent: true, opacity: 0.22 });
    for (let lat = -75; lat <= 75; lat += 15) {
      const pts = [];
      for (let lng = -180; lng <= 180; lng += 4) pts.push(latLngToVec3(lat, lng, RADIUS * 1.002));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    for (let lng = -180; lng < 180; lng += 15) {
      const pts = [];
      for (let lat = -90; lat <= 90; lat += 4) pts.push(latLngToVec3(lat, lng, RADIUS * 1.002));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    return group;
  }

  function buildSurfacePoints(n) {
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const v = latLngToVec3(Math.random() * 180 - 90, Math.random() * 360 - 180, RADIUS * 1.004);
      pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({
      color: 0x38bdf8, size: 0.018, transparent: true, opacity: 0.45,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
  }

  function buildAtmosphere() {
    return new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 1.2, 64, 64),
      new THREE.ShaderMaterial({
        transparent: true, side: THREE.BackSide,
        blending: THREE.AdditiveBlending, depthWrite: false,
        uniforms: { glowColor: { value: new THREE.Color(0x2f81f7) } },
        vertexShader: 'varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
        fragmentShader: 'varying vec3 vN; uniform vec3 glowColor; void main(){ float i = pow(0.75 - dot(vN, vec3(0.0,0.0,1.0)), 2.2); gl_FragColor = vec4(glowColor, 1.0) * i; }',
      })
    );
  }

  function buildStars(n) {
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 22 + Math.random() * 28;
      const th = 2 * Math.PI * Math.random();
      const ph = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
      pos[i * 3 + 1] = r * Math.cos(ph);
      pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color: 0x9fb6d6, size: 0.08, transparent: true, opacity: 0.7 }));
  }

  function addHubMarker(hub) {
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(0.05, 16, 16),
      new THREE.MeshBasicMaterial({ color: hub.color, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    m.position.copy(latLngToVec3(hub.lat, hub.lng));
    globeGroup.add(m);
  }

  function init() {
    try {
      const w = wrap.clientWidth, h = wrap.clientHeight;
      scene = new THREE.Scene();
      clock = new THREE.Clock();

      camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
      camera.position.set(0, 1.4, 6);

      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
      renderer.setSize(w, h, false);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.rotateSpeed = 0.5;
      controls.enablePan = false;
      controls.minDistance = 3.2;
      controls.maxDistance = 11;
      controls.autoRotate = !reduceMotion;
      controls.autoRotateSpeed = 0.45;

      globeGroup = new THREE.Group();
      scene.add(globeGroup);

      globeGroup.add(new THREE.Mesh(
        new THREE.SphereGeometry(RADIUS, 64, 64),
        new THREE.MeshPhongMaterial({ color: 0x0a1730, emissive: 0x06142c, shininess: 14, transparent: true, opacity: 0.95 })
      ));
      globeGroup.add(buildGraticule());
      globeGroup.add(buildSurfacePoints(650));

      arcsGroup = new THREE.Group(); globeGroup.add(arcsGroup);
      pinsGroup = new THREE.Group(); globeGroup.add(pinsGroup);
      Object.values(HUBS).forEach(addHubMarker);

      scene.add(buildAtmosphere());
      scene.add(buildStars(1100));
      scene.add(new THREE.AmbientLight(0x335577, 1.1));
      const d1 = new THREE.DirectionalLight(0x9ccbff, 1.4); d1.position.set(5, 3, 5); scene.add(d1);
      const d2 = new THREE.DirectionalLight(0x2233ff, 0.5); d2.position.set(-5, -2, -3); scene.add(d2);

      window.addEventListener('resize', onResize);
      ok = true;
      animate();
    } catch (err) {
      console.error('Globe init failed:', err);
      if (fallback) fallback.classList.remove('hidden');
    }
  }

  function onResize() {
    if (!ok) return;
    const w = wrap.clientWidth, h = wrap.clientHeight;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }

  function spawnArc(fromLat, fromLng, color) {
    if (!ok) return;
    const start = latLngToVec3(fromLat, fromLng);
    const dest = latLngToVec3(Math.random() * 140 - 60, Math.random() * 360 - 180);
    const mid = start.clone().add(dest).multiplyScalar(0.5);
    mid.normalize().multiplyScalar(RADIUS + start.distanceTo(dest) * 0.45);
    const curve = new THREE.QuadraticBezierCurve3(start, mid, dest);
    const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(50));
    const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    const line = new THREE.Line(geo, mat);
    arcsGroup.add(line);
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(0.03, 10, 10),
      new THREE.MeshBasicMaterial({ color, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    arcsGroup.add(head);
    arcs.push({ line, head, curve, t: 0 });

    const pin = new THREE.Mesh(
      new THREE.SphereGeometry(0.028, 10, 10),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    pin.position.copy(dest);
    pinsGroup.add(pin);
    pins.push(pin);
    if (pins.length > 80) { const old = pins.shift(); pinsGroup.remove(old); old.geometry.dispose(); old.material.dispose(); }
    activeBoost = 1.2;
  }

  function animate() {
    if (!ok) return;
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    controls.autoRotateSpeed = 0.45 + activeBoost * 1.6;
    activeBoost = Math.max(0, activeBoost - dt * 0.6);
    controls.update();

    for (let i = arcs.length - 1; i >= 0; i--) {
      const a = arcs[i];
      a.t += dt * 0.7;
      const p = Math.min(a.t, 1);
      a.curve.getPoint(p, headVec);
      a.head.position.copy(headVec);
      a.head.visible = a.t < 1;
      a.line.material.opacity = a.t < 1 ? Math.min(a.t * 2, 0.85) : Math.max(0.85 - (a.t - 1), 0);
      if (a.t > 2) {
        arcsGroup.remove(a.line); arcsGroup.remove(a.head);
        a.line.geometry.dispose(); a.line.material.dispose();
        a.head.geometry.dispose(); a.head.material.dispose();
        arcs.splice(i, 1);
      }
    }
    // gently pulse pins
    const s = 1 + Math.sin(clock.elapsedTime * 3) * 0.15;
    for (const pin of pins) pin.scale.setScalar(s);

    renderer.render(scene, camera);
  }

  return {
    init,
    addJob(platform) {
      const hub = HUBS[(platform || '').toLowerCase()] || HUBS.indeed;
      spawnArc(hub.lat, hub.lng, hub.color);
    },
    pulse() { activeBoost = Math.min(activeBoost + 0.4, 1.5); },
  };
})();

/* =========================================================
   2) App logic — scrape / verify / render
   ========================================================= */
let currentJobs = [];

const $ = (id) => document.getElementById(id);

function escapeHTML(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'\"]/g, t => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;' }[t]));
}

$('scrape-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const keyword = $('keyword').value.trim();
  const location = $('location').value.trim();
  const job_type = $('job-type').value;
  const experience_level = $('experience-level').value;
  const max_pages = parseInt($('max-pages').value, 10) || 1;
  const platforms = [];
  if ($('plat-indeed').checked) platforms.push('indeed');
  if ($('plat-linkedin').checked) platforms.push('linkedin');
  if (platforms.length === 0) { alert('Please select at least one platform.'); return; }

  setLoading(true, 'Scraping from ' + platforms.join(', ') + '…');
  setEngine('Scraping…', true);
  try {
    const res = await fetch('/api/scrape', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, location, job_type, experience_level, platforms, max_pages }),
    });
    if (!res.ok) throw new Error('Failed to scrape jobs.');
    const data = await res.json();
    if (data.status === 'cancelled') alert('Scrape was cancelled.');
    currentJobs = data.jobs || [];
    renderJobs(true);
    $('btn-verify').disabled = currentJobs.length === 0;
  } catch (err) {
    alert(err.message);
  } finally {
    setLoading(false);
    setEngine('Engine idle', false);
  }
});

$('btn-cancel-scrape').addEventListener('click', async () => {
  try {
    const res = await fetch('/api/scrape/cancel', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to cancel scrape.');
    setLoading(true, 'Cancelling…');
  } catch (err) { alert(err.message); }
});

$('btn-verify').addEventListener('click', async () => {
  if (currentJobs.length === 0) return;
  setLoading(true, 'Verifying ' + currentJobs.length + ' jobs…');
  setEngine('Verifying…', true);
  $('btn-verify').disabled = true;
  try {
    const res = await fetch('/api/verify', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jobs: currentJobs }),
    });
    if (!res.ok) throw new Error('Failed to verify jobs.');
    const data = await res.json();
    currentJobs = data.jobs || [];
    renderJobs(false);
  } catch (err) {
    alert(err.message);
    $('btn-verify').disabled = false;
  } finally {
    setLoading(false);
    setEngine('Engine idle', false);
  }
});

function setEngine(text, busy) {
  const chip = $('engine-chip');
  chip.textContent = text;
  chip.style.color = busy ? 'var(--accent)' : 'var(--text-dim)';
}

function setLoading(isLoading, text = 'Processing…') {
  const loadingEl = $('loading');
  const container = $('jobs-container');
  const btnScrape = $('btn-scrape');
  const btnCancel = $('btn-cancel-scrape');
  if (isLoading) {
    $('loading-text').innerText = text;
    loadingEl.classList.remove('hidden');
    container.classList.add('hidden');
    btnScrape.disabled = true;
    btnCancel.style.display = (text.includes('Scraping') || text.includes('Cancelling')) ? 'inline-block' : 'none';
  } else {
    loadingEl.classList.add('hidden');
    container.classList.remove('hidden');
    btnScrape.disabled = false;
    btnCancel.style.display = 'none';
  }
}

function updateStats() {
  $('stat-total').innerText = currentJobs.length;
  $('stat-verified').innerText = currentJobs.filter(j => (j.verified_status || 'none') === 'verified').length;
  $('stat-sources').innerText = new Set(currentJobs.map(j => j.platform).filter(Boolean)).size;
  $('job-count').innerText = currentJobs.length;
}

function renderJobs(animateGlobe) {
  const container = $('jobs-container');
  updateStats();
  if (currentJobs.length === 0) {
    container.innerHTML = '<div class="empty-state">No jobs found. Try different keywords.</div>';
    return;
  }
  container.innerHTML = currentJobs.map(job => {
    const status = (job.verified_status || 'none');
    const statusClass = 'status-' + status.replace(/_/g, '-');
    const statusText = status === 'none' ? 'UNVERIFIED' : status.replace(/_/g, ' ');
    return (
      '<div class="job-card">' +
        '<div class="job-platform">' + escapeHTML(job.platform || '—') + '</div>' +
        '<div class="job-title">' + escapeHTML(job.title) + '</div>' +
        '<div class="job-company">' + escapeHTML(job.company) + '</div>' +
        '<div class="job-meta">' +
          '<div>\uD83D\uDCCD ' + escapeHTML(job.location || 'N/A') + '</div>' +
          '<div>\uD83D\uDCBC ' + escapeHTML(job.job_type || 'N/A') + '</div>' +
          '<div>\uD83D\uDCB0 ' + escapeHTML(job.salary || 'N/A') + '</div>' +
        '</div>' +
        '<div class="job-footer">' +
          '<span class="status-badge ' + statusClass + '">' + escapeHTML(statusText) + '</span>' +
          '<a href="' + escapeHTML(job.apply_link || '#') + '" target="_blank" rel="noopener">View Job \u2192</a>' +
        '</div>' +
      '</div>'
    );
  }).join('');

  attachTilt();

  if (animateGlobe) {
    currentJobs.forEach((job, i) => setTimeout(() => Globe.addJob(job.platform), i * 120));
  }
}

// 3D tilt-on-hover for job cards
function attachTilt() {
  document.querySelectorAll('.job-card').forEach(card => {
    card.addEventListener('pointermove', (e) => {
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = 'perspective(700px) rotateY(' + (px * 9) + 'deg) rotateX(' + (-py * 9) + 'deg) translateZ(6px)';
    });
    card.addEventListener('pointerleave', () => { card.style.transform = ''; });
  });
}

/* =========================================================
   3) Live log viewer (SSE)
   ========================================================= */
const API_BASE = '';
const logOut = $('log-output');
const logStatus = $('log-status');
const connDot = $('conn-dot');
const logAutoscroll = $('log-autoscroll');
const logFilter = $('log-level-filter');
const LEVEL_RANK = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50 };

function logPasses(level) {
  const sel = logFilter.value;
  return sel === 'ALL' || (LEVEL_RANK[level] || 0) >= (LEVEL_RANK[sel] || 0);
}

function appendLogEntry(entry) {
  const line = document.createElement('span');
  const level = entry.level || 'INFO';
  line.className = 'log-line log-' + level.toLowerCase();
  line.dataset.level = level;
  line.innerHTML = '<span class="log-meta">[' + escapeHTML(entry.time) + '] ' +
    escapeHTML((level).padEnd(8)) + escapeHTML(entry.logger || '') + '</span>   ' + escapeHTML(entry.message);
  if (!logPasses(level)) line.style.display = 'none';
  logOut.appendChild(line);
  if (logAutoscroll.checked) logOut.scrollTop = logOut.scrollHeight;
  // visual feedback on the globe while scraping
  if (/page|search|scrap/i.test(entry.message || '')) Globe.pulse();
}

let logSource;
function connectLogs() {
  logSource = new EventSource(API_BASE + '/api/logs/stream');
  logSource.onopen = () => { logStatus.style.color = 'var(--green)'; logStatus.title = 'connected'; connDot.className = 'dot live'; };
  logSource.onmessage = (e) => { try { appendLogEntry(JSON.parse(e.data)); } catch (_) {} };
  logSource.onerror = () => { logStatus.style.color = 'var(--red)'; logStatus.title = 'reconnecting…'; connDot.className = 'dot off'; };
}

logFilter.addEventListener('change', () => {
  document.querySelectorAll('#log-output .log-line').forEach(l => {
    l.style.display = logPasses(l.dataset.level) ? '' : 'none';
  });
});
$('log-clear').addEventListener('click', () => { logOut.innerHTML = ''; });

/* =========================================================
   4) Boot
   ========================================================= */
Globe.init();
connectLogs();
