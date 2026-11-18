#!/usr/bin/env node
/* Builds data/city.json: the buildings around every research site, as prisms.

   Source: the Baukörpermodell of the City of Vienna (layer FMZKBKMOGD, CC BY 4.0), the part of
   the city's 3D model that describes each building by its outline and the height of its top.
   Run build/fetch-buildings.py first; it downloads the tiles this script reads.
   Sites outside Vienna get their buildings from the BEV's block model of Austria (CC BY 4.0).

   The whole city would be several hundred thousand prisms, too many for a phone. So the model
   is drawn only within RADIUS of a research site and fades out towards the edge. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { KM, project, simplify } from './geo.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const read = name => JSON.parse(fs.readFileSync(path.join(HERE, name), 'utf8'));
const M = KM / 1000;                 // scene units per metre
const RADIUS = 260 * M;              // drawn around a site
const SOLID = 0.6;                   // inside this share of the radius a building has its full colour
const KINDS = new Set([11, 12, 14]); // building, building over a passage, glasshouse; no kiosks or shelters
const MIN_AREA = 25 * M * M, MIN_HEIGHT = 2.5;
const Q = 2000;                      // integers per scene unit: 10 cm
const NEAR = 35 * M;                 // an address point may lie this far outside its building

const sites = [];   // every located site, once per address
const coords = read('site-coords.json');
for (const inst of Object.values(read('sites.json'))) for (const s of inst.sites) {
  const c = coords[s.addr];
  if (c && !sites.some(x => x.addr === s.addr)) sites.push({ addr: s.addr, p: project(c.lat, c.lon), house: s.house !== false, grounds: c.grounds?.map(([lon, lat]) => project(lat, lon)) });   // house: false marks a site whose point is not its building
}

/* Read the tiles. A building on a tile border comes twice; FMZK_ID tells. */
const seen = new Set(), raw = [];
let absent = 0;
for (const [ix, iy] of read('cache/bkm-tiles.json')) {
  if (!fs.existsSync(path.join(HERE, `cache/bkm/${ix}_${iy}.json`))) { absent++; continue; }
  for (const f of read(`cache/bkm/${ix}_${iy}.json`).features) {
    const a = f.properties;
    if (seen.has(a.FMZK_ID) || !KINDS.has(a.F_KLASSE) || a.O_KOTE == null || a.HOEHE_DGM == null) continue;
    seen.add(a.FMZK_ID);
    const height = a.O_KOTE - a.HOEHE_DGM, base = a.F_KLASSE === 12 && a.U_KOTE != null ? Math.max(0, a.U_KOTE - a.HOEHE_DGM) : 0;
    if (height < MIN_HEIGHT || height - base < 1) continue;
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const rings of polys) raw.push({ rings: rings.map(r => r.map(([lon, lat]) => project(lat, lon))), height, base, geb: a.BW_GEB_ID, bezug: a.BEZUG });
  }
}

/* Outside Vienna the city's model ends. There the prisms come from the federal block model
   (fetch-buildings-bev.py): one outline per building and the median height of its roof. */
const federal = fs.existsSync(path.join(HERE, 'cache/bev-buildings.json')) ? read('cache/bev-buildings.json').buildings : [];
for (const b of federal) {
  if (b.height == null || b.height < MIN_HEIGHT) continue;
  for (const rings of b.polygons) raw.push({ rings: rings.map(r => r.map(([lon, lat]) => project(lat, lon))), height: b.height, base: 0, geb: 'bev' + b.id, bezug: null });
}

const area = ring => { let s = 0; for (let i = 0; i < ring.length - 1; i++) s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]; return Math.abs(s) / 2; };
const centre = ring => { let x = 0, z = 0; for (const p of ring) { x += p[0]; z += p[1]; } return [x / ring.length, z / ring.length]; };
const inside = ([x, z], ring) => {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, zi] = ring[i], [xj, zj] = ring[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) hit = !hit;
  }
  return hit;
};
const toRing = ([x, z], ring) => {   // distance from a point to the outline
  let best = Infinity;
  for (let i = 0; i < ring.length - 1; i++) {
    const [ax, az] = ring[i], [bx, bz] = ring[i + 1], dx = bx - ax, dz = bz - az;
    const u = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1e-12)));
    best = Math.min(best, Math.hypot(x - ax - u * dx, z - az - u * dz));
  }
  return best;
};

/* Keep what stands within RADIUS of a site, and note how close. */
const kept = [];
for (const b of raw) {
  if (area(b.rings[0]) < MIN_AREA) continue;
  const c = centre(b.rings[0]);
  let d = Infinity;
  for (const s of sites) d = Math.min(d, s.grounds && inside(c, s.grounds) ? 0 : Math.hypot(c[0] - s.p[0], c[1] - s.p[1]));   // a campus is drawn whole
  if (d > RADIUS) continue;
  b.c = c;
  b.fade = Math.max(1, Math.round(9 * Math.min(1, (1 - d / RADIUS) / (1 - SOLID))));   // 9 = full colour … 1 = almost ground
  kept.push(b);
}

/* Which buildings belong to a site: the one its address point stands in (or next to), and every
   other part the city files under the same building number or the same address code. Where
   OpenStreetMap maps a site outside Vienna as grounds, every building on them belongs to it. */
const own = {};
let unmatched = 0;
for (const s of sites) {
  if (!s.house) continue;
  let hit = kept.find(b => inside(s.p, b.rings[0]));
  if (!hit) {
    let best = NEAR;
    for (const b of kept) { if (Math.hypot(b.c[0] - s.p[0], b.c[1] - s.p[1]) > 1) continue; const d = toRing(s.p, b.rings[0]); if (d < best) { best = d; hit = b; } }
  }
  if (!hit && !s.grounds) { unmatched++; continue; }
  own[s.addr] = kept.map((b, k) => ((s.grounds && inside(b.c, s.grounds)) || (hit && (b === hit || (hit.geb != null && b.geb === hit.geb) || (hit.bezug && b.bezug === hit.bezug)))) ? k : -1).filter(k => k >= 0);
}

/* The map ends at the city limits. A site beyond them gets a soft patch of ground of its own,
   as wide as what is drawn around it: [x, z, reach]. */
const ground = sites.filter(s => !/,\s*1\d{3}\s+Wien/.test(s.addr)).map(s => {
  const reach = Math.max(0, ...kept.filter(b => Math.hypot(b.c[0] - s.p[0], b.c[1] - s.p[1]) <= RADIUS || (s.grounds && inside(b.c, s.grounds))).map(b => Math.hypot(b.c[0] - s.p[0], b.c[1] - s.p[1])));
  return [...s.p, reach].map(v => Math.round(v * 1000) / 1000);
}).filter(g => g[2] > 0);

const pack = ring => {   // outline as integers: first point, then steps; the closing point is dropped
  const pts = simplify(ring, 0.4 * M).slice(0, -1).map(p => p.map(v => Math.round(v * Q)));
  const out = [];
  pts.forEach((p, i) => { if (i && p[0] === pts[i - 1][0] && p[1] === pts[i - 1][1]) return; out.push(i ? p[0] - pts[i - 1][0] : p[0], i ? p[1] - pts[i - 1][1] : p[1]); });
  return out;
};
const buildings = kept.map(b => {
  const rings = b.rings.map(pack).filter((r, i) => r.length >= 6 || i === 0);
  return [Math.round(b.height * 10), Math.round(b.base * 10), b.fade, ...rings];   // heights in decimetres
});
const bad = buildings.filter(b => b[3].length < 6).length;
if (bad) throw new Error(`${bad} outlines collapsed while simplifying`);

const file = path.join(path.dirname(HERE), 'data', 'city.json');
fs.writeFileSync(file, JSON.stringify({ q: Q, m: M, b: buildings, own, ground }));
const sizes = Object.values(own).map(l => l.length).sort((a, b) => b - a);
console.log(`${federal.length} of the outlines read come from the federal model (outside Vienna)`);
console.log(`${buildings.length} buildings around ${sites.length} sites, ${(fs.statSync(file).size / 1e6).toFixed(2)} MB`);
console.log(`${Object.keys(own).length} sites stand in a building of the model, ${unmatched} do not (outside Vienna or open ground); largest group ${sizes[0]} parts, median ${sizes[sizes.length >> 1]}`);
if (absent) console.warn(`INCOMPLETE: ${absent} tiles are not downloaded yet. Rerun build/fetch-buildings.py, then this script.`);
