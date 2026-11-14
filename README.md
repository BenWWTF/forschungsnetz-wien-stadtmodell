# Wer forscht mit wem in Wien? Stadtmodell

A 3D model of the collaboration map from the [Vienna Research Radar](https://research.wwtf.at/collaboration.html) (WWTF),
built as a prototype for an exhibition on science literacy aimed at children and adolescents.

This is a fork of [forschungsnetz-wien](https://github.com/BenWWTF/forschungsnetz-wien). It differs in the city map:
the map shows the buildings of the City of Vienna's 3D city model around every research site, and an institution
is no longer one point but all of its sites.

- **Network view**: every sphere is a research institution in Vienna, every line stands for jointly authored publications.
- **City map view**, in three levels with one job each:
  1. *Vienna*: every sphere floats above its main site, small dots mark all sites of all institutions, lines show who publishes with whom.
  2. *One place*: after a tap on a sphere or dot the map belongs to that institution. Other spheres, dots and all lines step aside; its houses light up and its sites become pins. Pins that would overlap merge into a bubble with their number, which splits when tapped.
  3. *One site*: a tap on a pin or on a row of the site list flies down to roof level. Arrows walk from site to site.
  A breadcrumb (Wien › place › site) shows the level and leads back up.
- **Tour**: six steps that teach how to read the graphic, ending with what it leaves out.
- German and English, touch first, resets itself after 90 seconds without input (`?idle=30` changes the seconds).

No build step for the site itself: plain HTML, CSS and ES modules, three.js vendored in `vendor/`.

## Design

The look follows the Q. brand. `design/tokens.css` holds the brand values as CSS variables; `style.css` assigns
them to roles and `app.js` reads its colours from there.

Typefaces: Clash Display and Clash Grotesk come from Fontshare; local copies in `fonts/` (gitignored, their
licence does not allow public hosting) take precedence when present, so the page also works offline.
PP Radio Grotesk in `fonts/` is a licensed Pangram Pangram typeface, used here with the Q.'s consent.
It is not free to reuse.

## Hidden things

Easter eggs sit next to their spheres and appear when a visitor opens that place (`EGGS` in `texts.js`: icon,
place, story, search words, stage). Four are there from the start; a fifth appears once those are found, and a last
one then opens at the Q. on the city map.

## Updating the data

The numbers come from the Radar's API, `https://research.wwtf.at/api/v1/collaboration.json`, which the Radar
rewrites every Tuesday morning with the same code as its collaboration page. A GitHub Action
(`.github/workflows/update-data.yml`) runs the build every day at 07:43 UTC and commits `data/graph.json` when
the numbers changed, which redeploys the page. By hand:

```sh
node build/build.mjs            # fetches the current numbers from the API
node build/build.mjs --cached   # rebuilds from build/cache/
```

The script adds names, addresses and both layouts and writes `data/graph.json`; `data/wien.json` (district
outlines, waters) is rewritten only when the map layers are present in `build/`.

A new institution in the dataset stops the build (the Action fails and GitHub sends a mail) until it has an entry in `build/institutions.json` (full name, type, address), then
`python3 build/geocode.py` to refresh `build/coords.json`. The map layers come from the City of Vienna's WFS; `sh build/fetch-map.sh` downloads them into `build/` (they are not committed, and only change when the city redraws a district).

## Sites and the city model

`build/sites.json` lists the sites of every institution: name, address, the page it was read from and whether that
page was the institution's own (`verified`). The list was researched in November 2026; `notes` records what was
left out and why. Rules: sites where research or teaching happens, no dormitories or pure offices; sites more than
22 km from Stephansplatz are named in the list of a place but not drawn. Two networks without a building of their
own (VCQ, Austrian Cluster for Tissue Regeneration) are shown at their coordinating sites only as far as their own
pages name them.

```sh
python3 build/geocode-sites.py     # addresses to coordinates, kept in build/site-coords.json
python3 build/fetch-buildings.py   # building tiles around the sites, into build/cache/bkm/ (about 90 MB, not committed)
node build/city.mjs                # writes data/city.json
node build/build.mjs --cached      # writes the sites into data/graph.json
```

The buildings are the Baukörpermodell (layer `FMZKBKMOGD`), the part of the 3D city model that gives every
building its outline and the height of its top above ground. `city.mjs` keeps what stands within 260 m of a site,
simplifies the outlines to 0.4 m and assigns to each site the building its address point stands in, plus all
parts the city files under the same building number or address code. No roof shapes, no terrain.

After changing `sites.json`, run all four steps. The daily Action only needs the committed `sites.json` and
`site-coords.json`.

## Sources

Research data: Vienna Research Radar (WWTF), OpenAlex. Buildings (Baukörpermodell of the 3D city model), district borders, waters and Vienna addresses: Stadt Wien,
data.wien.gv.at (CC BY 4.0). Addresses outside Vienna geocoded with Nominatim, © OpenStreetMap contributors. three.js is MIT licensed.
