# Datasets

The data behind KalaVigyan's charts, tables, timelines and map layers: rivers, relief, minerals,
climate, soil and cover, and the places where each craft is practised. A dataset is a published
table, series or layer of values by place or by year. Every value a reader sees comes from one,
recorded with its version and citation, and nothing is drawn that the dataset does not state.

## Open sources and licences

- Use a dataset only when its licence allows redistribution: the public domain (a U.S. Government
  work included), CC0, PDDL, CC BY, CC BY-SA, ODC-By, ODbL, the Government Open Data License -
  India, or a publisher's own licence whose text says the data may be shared and on what terms.
- Never a non-commercial or no-derivatives licence, a licence the publisher does not state, "for
  reference only", or a download behind registration, a login or a key.
- A dataset whose licence cannot be confirmed may be read for internal analysis, and none of its
  values or geometry is shown or exported until it is confirmed.
- A licence that allows the data only inside a derived product (HydroSHEDS) shows it inside the
  site's own maps and never as a download or an export.
- The attribution the licence asks for is shown wherever the data is.

## Recording a dataset

Record each dataset once, before any value of it is used: a short code, the title, the publisher,
the edition or version, the period it covers, its native resolution, its coordinate reference
system, the licence with its address, the attribution to display, whether it may be redistributed,
the citation (with its DOI when there is one), the landing page, the day it was read, and the
SHA-256 of the file read. A dataset changes only as a new version with its own record.

## Provenance per value

- Every value keeps where it came from: the dataset's code and version, the variable, the period or
  depth, the statistic (a district mean, a normal, a share, a count), the unit, the method and the
  resolution it was read at.
- A value proposed as a fact is quoted from the dataset's published table or record, its locator
  naming the table and the row (the quote rules, `quotes.md`).
- A statistic over an area names the area: a district value is over the district's boundary, and a
  state value is an area-weighted mean or a sum over the districts that have the value, with how
  many did.

## Units and conversions

- A value keeps the unit its dataset states: millimetres of rain, degrees Celsius, metres of
  elevation, square kilometres, a fraction for a share.
- A conversion uses an exact definition only (NIST Special Publication 811, Appendix B: the inch is
  2.54 cm, the foot 0.3048 m, the yard 0.9144 m, the mile 1.609344 km) and keeps the original
  beside it. A local Indian unit (seer, maund, tola, gaj) is converted only by a value a cited source
  states for that region, never by a table.
- A delivered component states each value in the unit its fact quotes, and converts nothing.
- Precision stays the dataset's: never more decimals than it gives, and whole degrees Celsius on
  maps.

## Projection and the outline

- Coordinates are WGS 84 longitude and latitude (EPSG:4326) in decimal degrees. A dataset in another
  system (SoilGrids' Homolosine) is read at its native resolution and its values reprojected, never
  its pixels resampled into new values.
- India's maps are equirectangular: x is the longitude times the cosine of 21.919 degrees, the
  middle latitude of India's frame (6.756 to 37.082 degrees north, 68.206 to 97.394 east), and y is
  the latitude.
- India's external boundary is the Survey of India's depiction, captioned "External boundaries of
  India as depicted by Survey of India." Neighbouring land comes from Natural Earth 1:10m as India
  sees it, drawn under the outline, and every layer is clipped to the outline or the map frame.
- District boundaries are indicative, not official: a map that shows them says "District
  boundaries are indicative.", and their geometry is never a download or an export.
- No scale bar unless the map is drawn to a stated projection and scale.

## Simplification

Simplify a line or a shape no further than its layer needs, and never a point:

| Layer | Tolerance |
|---|---|
| rivers and their centre lines | 0.01 degree (about 1.1 km) |
| lakes | 0.006 degree, and a lake under 0.004 square degree is left out |
| country outlines, simplified together so neighbours still meet | 0.012 degree |
| relief bands | 0.018 degree |
| a river basin's reaches, each with its ends kept so junctions stay joined | 0.005 degree (about 550 m) |
| district shapes, on a 0.001-degree grid | 0.01 degree |

Coordinates are stored to 0.001 degree (about 110 m), and a point site to at most 0.0001 degree.
Shapes that share a border are simplified together, so they still meet.

## No invented values

- A value is what the dataset states for that place and period. Never interpolate, smooth, average
  in a neighbour or extend a series to fill a gap.
- A place with no reading is drawn as no reading (the cross-hatch, and the words in the table),
  never as zero. Zero is shown only where the dataset counts and found none, and then it says so
  ("none recorded in the Mineral Resources Data System", not "no deposits").
- A place is drawn where a source puts it: a district-level place at its district, a point at the
  coordinates of an open gazetteer record (Wikidata, CC0) of that village or town, read with
  `lookup`, never a guessed or estimated position. A craft's place is shown only with the source that names it.
- A trend is the dataset's series fitted by its stated method, with its period; never a line drawn
  by eye.

## From a dataset to a component

Over the MCP server, for a dataset about the craft itself (a census of artisans, production or
export tables, a registry's records, prices over the years):

- Write each value as a fact quoting its row, with the dataset's published table or record as the
  source, as `propose_facts` takes each.
- Build the component from those facts by the component guide (`components.md`): a series over
  years or places is a `general_chart`, rows of attributes a `general_table`, dated events a
  `general_timeline`, places with readings a `general_map_layer`. Each value is stated by its
  reading unit, which cites its fact.
- Put the facts and the component in one page bundle, see it with `preview_page`, then send it with
  `propose_page`: the facts are proposed with the component, never twice. A bundle holds at most
  20 facts; for a figure of more values, propose the facts first with `propose_facts`, follow them
  until they are shown, then deliver the component citing their ids.
- Environment values by district (rainfall, temperature, soil, forest and land cover, elevation,
  geology, rivers) are the site's own layers, built from its open datasets: never propose them as
  facts and never redraw them in a delivered component. The page shows them through its own maps
  and region panel.

In the repository:

- A per-district environment dataset enters `etl/geo`: a layer in `geo_etl/layers`, its record in
  `geo_etl/catalog.py` (the source of truth, mirrored by `docs/DATA_SOURCES.md`), run by the
  `geo-etl` workflow on GitHub Actions and loaded by `etl/geo/load.py`.
- A physical map layer (rivers, lakes, relief, minerals) enters `tools/maplayers`: its source as a
  `Source` in `maplayers/sources.py` (file, title, publisher, address, licence, citation), built by
  `tools/maplayers_build.py` into `frontend/public/layers` with the SHA-256 of every download it
  read. The base map's countries come from `tools/basemap_build.py`.
- Heavy downloads run on GitHub Actions, never on a laptop.

## How it is checked

- A delivered component passes the delivery checks of the component guide: every value stated by
  its unit and every number of a unit in its facts. The gates re-read every source and re-find every
  quote, and the preview shows the component drawn before it is sent.
- A layer in the repository has tests with expected values derived independently of the code;
  `load.py --dry-run` checks dataset codes, keys and values without writing; the river network is
  checked before anything is written; and the run's summary lists the districts without values and
  without cells, so a gap is visible rather than filled.
- A layer or value is shown publicly only when its dataset's record says it may be redistributed.
