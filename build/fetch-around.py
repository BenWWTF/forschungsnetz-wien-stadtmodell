#!/usr/bin/env python3
"""Outlines of the municipalities around Vienna that carry a research site, and of those between
them and the city, so that the map does not end in mid-air at the city limits.
From OpenStreetMap via Nominatim (ODbL). Writes build/umland.geojson, which build.mjs reads."""
import json, pathlib, subprocess, time, urllib.parse

HERE = pathlib.Path(__file__).parent
UA = "forschungsnetz-wien-build/1.0 (exhibition prototype)"
PLACES = ["Klosterneuburg", "Groß-Enzersdorf",                                  # north and east: they border Vienna
          "Perchtoldsdorf", "Brunn am Gebirge", "Maria Enzersdorf", "Mödling",  # south: Mödling and Laxenburg, and what lies between
          "Vösendorf", "Wiener Neudorf", "Biedermannsdorf", "Laxenburg"]

features = []
for name in PLACES:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"city": name, "state": "Niederösterreich", "country": "Österreich", "format": "json", "limit": 5, "polygon_geojson": 1, "polygon_threshold": 0.0002})
    hits = json.loads(subprocess.run(["curl", "-fsS", "-A", UA, url], capture_output=True, text=True, check=True).stdout)
    time.sleep(1.1)
    hit = next(h for h in hits if h["class"] == "boundary" and h["type"] == "administrative" and h["geojson"]["type"] in ("Polygon", "MultiPolygon"))   # fails loudly if a place is not found as a municipality
    features.append({"type": "Feature", "properties": {"name": name, "osm": f'{hit["osm_type"]}/{hit["osm_id"]}', "found": hit["display_name"]}, "geometry": hit["geojson"]})
    print(f'{name:20s} {hit["osm_type"]}/{hit["osm_id"]}  {hit["geojson"]["type"]}  {hit["display_name"][:70]}')
(HERE / "umland.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False))
