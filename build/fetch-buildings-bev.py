#!/usr/bin/env python3
"""Buildings around the research sites outside Vienna, where the city's own model ends.

Source: Digitales Landschaftsmodell, Bauwerke (BEV, CC BY 4.0), a block model of every building
in Austria: outline plus height above ground. Download the GeoPackage (2.6 GB) once into
build/cache/bev/ from https://data.bev.gv.at/download/DLM/ and run this script with a Python
that has pyproj (the data come in MGI / Austria GK Central, EPSG:31255):

    python3 -m venv build/cache/venv && build/cache/venv/bin/pip install pyproj
    build/cache/venv/bin/python build/fetch-buildings-bev.py

It writes build/cache/bev-buildings.json, which build/city.mjs reads if it is there."""
import glob, json, pathlib, re, sqlite3, struct
from pyproj import Transformer

HERE = pathlib.Path(__file__).parent
RADIUS = 300   # metres around a site, as in fetch-buildings.py
MAP_KM, CENTRE = 22, (16.3731, 48.2083)   # as in build.mjs and geo.mjs: sites further out are not drawn
gpkg = sorted(glob.glob(str(HERE / "cache" / "bev" / "DLM_8000_BAUWERK_*.gpkg")))[-1]   # the newest release
to_gk = Transformer.from_crs(4326, 31255, always_xy=True)
to_wgs = Transformer.from_crs(31255, 4326, always_xy=True)


def polygons(blob):
    """GeoPackage geometry (header + WKB MultiPolygon or Polygon) to [[ring, ...], ...] in lon/lat."""
    flags = blob[3]
    at = 8 + [0, 32, 48, 48, 64][(flags >> 1) & 7]   # skip the envelope
    def read(fmt):
        nonlocal at
        out = struct.unpack_from(fmt, blob, at); at += struct.calcsize(fmt)
        return out
    def polygon(dims):
        rings = []
        for _ in range(read("<I")[0]):
            pts = [read("<" + "d" * dims)[:2] for _ in range(read("<I")[0])]
            xs, ys = to_wgs.transform([p[0] for p in pts], [p[1] for p in pts])
            rings.append([[round(x, 7), round(y, 7)] for x, y in zip(xs, ys)])
        return rings
    def geometry():
        order, kind = read("<BI")
        assert order == 1, "big-endian WKB"
        dims = 2 + (kind // 1000 in (1, 2)) + (kind // 1000 == 3) * 2
        if kind % 1000 == 3:
            return [polygon(dims)]
        assert kind % 1000 == 6, kind
        return [p for _ in range(read("<I")[0]) for p in geometry()]
    return geometry()


coords = json.loads((HERE / "site-coords.json").read_text())
sites = {s["addr"] for inst in json.loads((HERE / "sites.json").read_text()).values() for s in inst["sites"]}
db = sqlite3.connect(gpkg)
centre = to_gk.transform(*CENTRE)
seen, out = set(), []
for addr in sorted(sites):
    c = coords.get(addr)
    if not c or re.search(r",\s*1\d{3}\s+Wien", addr):   # Vienna has its own, finer model
        continue
    x, y = to_gk.transform(c["lon"], c["lat"])
    if ((x - centre[0]) ** 2 + (y - centre[1]) ** 2) ** 0.5 > MAP_KM * 1000:
        continue
    xs, ys = to_gk.transform(*zip(*c.get("grounds", [[c["lon"], c["lat"]]])))   # a campus: its whole grounds
    xs, ys = list(xs) + [x], list(ys) + [y]
    rows = db.execute("""select b.id, b.geom, b.HOEHE_OBJEKT_MEDIAN, b.HOEHE_OBJEKT_MAX, b.ERFASS_ART_HOEHE_OBJEKT_MEDIAN, b.AGWR_OBJEKTNUMMER, b.DEL_FLAG
        from BWK_8100_BAUWERK_F b join rtree_BWK_8100_BAUWERK_F_geom r on r.id = b.id
        where r.maxx >= ? and r.minx <= ? and r.maxy >= ? and r.miny <= ?""", (min(xs) - RADIUS, max(xs) + RADIUS, min(ys) - RADIUS, max(ys) + RADIUS)).fetchall()
    kept = 0
    for fid, geom, median, top, how, agwr, gone in rows:
        if fid in seen or (gone or "").startswith("Ja"):   # "Ja": no longer standing
            continue
        seen.add(fid); kept += 1
        out.append({"id": fid, "height": median, "max": top, "measured": how != "Default", "agwr": agwr, "polygons": polygons(geom)})
    print(f"{addr:48s} {kept} buildings")
(HERE / "cache" / "bev-buildings.json").write_text(json.dumps({"release": pathlib.Path(gpkg).stem, "buildings": out}))
print(f"{len(out)} buildings from {pathlib.Path(gpkg).name}; heights by default value: {sum(not b['measured'] for b in out)}")
