/* Shared by build.mjs and city.mjs: where a coordinate lands in the scene. */
export const KM = 5;                        // scene units per kilometre in the city view
export const CENTRE = { lat: 48.2083, lon: 16.3731 };   // Stephansplatz

export function project(lat, lon) {   // east = +x, south = +z, scene units
  return [(lon - CENTRE.lon) * 111.32 * Math.cos(CENTRE.lat * Math.PI / 180) * KM, -(lat - CENTRE.lat) * 111.32 * KM];
}

export function simplify(pts, tol) {   // Douglas-Peucker
  if (pts.length < 3) return pts;
  const keep = new Uint8Array(pts.length), last = pts.length - 1; keep[0] = keep[last] = 1;
  let stack = [[0, last]];
  if (pts[0][0] === pts[last][0] && pts[0][1] === pts[last][1]) {   // closed ring: split at the point farthest from the start
    let far = 0, at = 0;
    pts.forEach((q, i) => { const d = Math.hypot(q[0] - pts[0][0], q[1] - pts[0][1]); if (d > far) { far = d; at = i; } });
    keep[at] = 1; stack = [[0, at], [at, last]];
  }
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, az] = pts[a], [bx, bz] = pts[b], dx = bx - ax, dz = bz - az, len = Math.hypot(dx, dz) || 1e-9;
    let worst = 0, at = -1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs((pts[i][0] - ax) * dz - (pts[i][1] - az) * dx) / len;
      if (d > worst) { worst = d; at = i; }
    }
    if (worst > tol) { keep[at] = 1; stack.push([a, at], [at, b]); }
  }
  return pts.filter((_, i) => keep[i]);
}
