#!/usr/bin/env python3
"""Download the building prisms (Baukörpermodell, part of the City of Vienna's 3D city model,
CC BY 4.0) around every research site. The city is cut into tiles; a tile is fetched once and
kept in build/cache/bkm/. Only tiles within RADIUS of a site are needed."""
import json, math, pathlib, subprocess, urllib.parse

HERE = pathlib.Path(__file__).parent
CACHE = HERE / "cache" / "bkm"
RADIUS = 300          # metres around a site, a little more than build.mjs draws
DLON, DLAT = 0.006, 0.004   # tile size, about 445 m square
WFS = ("https://data.wien.gv.at/daten/geo?service=WFS&version=1.1.0&request=GetFeature&srsName=EPSG:4326&outputFormat=json"
       "&typeName=ogdwien:FMZKBKMOGD&propertyName=FMZK_ID,F_KLASSE,O_KOTE,U_KOTE,HOEHE_DGM,BW_GEB_ID,BEZUG,SHAPE&bbox=")

coords = json.loads((HERE / "site-coords.json").read_text())
tiles = set()
for c in coords.values():
    if not (48.11 < c["lat"] < 48.33 and 16.18 < c["lon"] < 16.58):   # the model ends at the city limits
        continue
    dlat, dlon = RADIUS / 111_320, RADIUS / (111_320 * math.cos(math.radians(c["lat"])))
    for ix in range(math.floor((c["lon"] - dlon) / DLON), math.floor((c["lon"] + dlon) / DLON) + 1):
        for iy in range(math.floor((c["lat"] - dlat) / DLAT), math.floor((c["lat"] + dlat) / DLAT) + 1):
            tiles.add((ix, iy))

CACHE.mkdir(parents=True, exist_ok=True)
(HERE / "cache" / "bkm-tiles.json").write_text(json.dumps(sorted(tiles)))   # build.mjs reads only these
new = 0
for n, (ix, iy) in enumerate(sorted(tiles)):
    out = CACHE / f"{ix}_{iy}.json"
    if out.exists():
        continue
    bbox = f"{ix * DLON:.6f},{iy * DLAT:.6f},{(ix + 1) * DLON:.6f},{(iy + 1) * DLAT:.6f},EPSG:4326"
    text = subprocess.run(["curl", "-fsS", "--connect-timeout", "6", "--retry", "5", "--retry-delay", "1", WFS + urllib.parse.quote(bbox)], capture_output=True, text=True, check=True).stdout
    count = len(json.loads(text)["features"])   # fails loudly on an error page
    out.write_text(text)
    new += 1
    print(f"{n + 1}/{len(tiles)} tile {ix}_{iy}: {count} buildings", flush=True)
print(f"{len(tiles)} tiles needed, {new} downloaded")
