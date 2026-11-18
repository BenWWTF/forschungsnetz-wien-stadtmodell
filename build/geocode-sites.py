#!/usr/bin/env python3
"""Geocode every address in build/sites.json. Vienna addresses go to the City of Vienna's own
address service, everything else to Nominatim. Results are kept in build/site-coords.json, keyed
by address, so a rerun only looks up what is new. Where OpenStreetMap maps an address outside
Vienna as grounds (a campus) and not as a single building, the outline is kept as well. Addresses that fail or land in another
postcode are listed at the end and must be fixed by hand in sites.json."""
import json, pathlib, re, subprocess, time, urllib.parse

HERE = pathlib.Path(__file__).parent
OUT = HERE / "site-coords.json"
UA = "forschungsnetz-wien-build/1.0 (exhibition prototype)"


def get(url):   # curl: this server's HTTP/2 responses trip other clients; it also refuses a connection now and then
    return json.loads(subprocess.run(["curl", "-fsS", "--connect-timeout", "6", "--retry", "5", "--retry-connrefused", "--retry-delay", "1", "-A", UA, url], capture_output=True, text=True, check=True).stdout)


def vienna(addr):
    street, plz = re.match(r"(.+?),\s*(1\d{3})\s+Wien", addr).groups()
    hits = get("https://data.wien.gv.at/daten/OGDAddressService.svc/GetAddressInfo?crs=EPSG:4326&Address=" + urllib.parse.quote(street))["features"]
    hits = [h for h in hits if h["properties"].get("PostalCode") == plz and h["properties"].get("Kategorie") == "Adresse"] 
    if not hits:
        return None
    lon, lat = hits[0]["geometry"]["coordinates"]
    return {"lat": lat, "lon": lon, "by": "wien", "found": hits[0]["properties"]["Adresse"]}


def nominatim(addr):
    hits = get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": addr, "format": "json", "limit": 1, "countrycodes": "at", "polygon_geojson": 1}))
    time.sleep(1.1)
    if not hits:
        return None
    hit = {"lat": float(hits[0]["lat"]), "lon": float(hits[0]["lon"]), "by": "nominatim", "found": hits[0]["display_name"]}
    shape = hits[0].get("geojson", {})
    if hits[0].get("class") != "building" and shape.get("type") == "Polygon":   # mapped as grounds, e.g. a campus: every house on them belongs to the site
        hit["grounds"] = [[round(x, 6), round(y, 6)] for x, y in shape["coordinates"][0]]
        hit["osm"] = f'{hits[0]["osm_type"]}/{hits[0]["osm_id"]} ({hits[0]["class"]}={hits[0]["type"]})'
    return hit


coords = json.loads(OUT.read_text()) if OUT.exists() else {}
missing = []
for key, inst in json.loads((HERE / "sites.json").read_text()).items():
    for site in inst["sites"]:
        addr = site["addr"]
        if addr in coords:
            continue
        try:
            hit = (vienna(addr) if re.search(r",\s*1\d{3}\s+Wien", addr) else None) or nominatim(addr)
        except Exception as err:   # one failed lookup must not lose the others
            hit = None
            print("error", addr, err)
        if hit:
            coords[addr] = hit
            OUT.write_text(json.dumps(coords, ensure_ascii=False, indent=1))   # the service drops connections now and then: keep what we have
        else:
            missing.append(f"{key}: {addr}")
        print(f"{key:36s} {addr:48s} {hit['by'] if hit else 'MISSING'}", flush=True)
OUT.write_text(json.dumps(coords, ensure_ascii=False, indent=1))
print(f"\n{len(coords)} addresses located, {len(missing)} missing")
print("\n".join(missing))
