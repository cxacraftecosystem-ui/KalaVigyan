# 0075. Reader names, one normal per quantity and citation clusters

Catalogue text is written for readers, a district place is named for its district, each quantity has
one normal from the dataset of its trend, and numbers read in words. The map keeps one line in view,
and citations cluster by source.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

The 2026-11-18 production capture (plan task 1A-12 and the Region, Overview and Map audits) showed
internal names and admissions on reader screens: the boundary dataset was titled after the
Designer Portal with a Kaggle handle and a join date, the HydroRIVERS method said "Designer
Portal district centroid", and CHELSA's licence read "licence text not confirmed". The Region tab
titled a whole-district card "Ajrakhpur", showed two rainfall normals for one place (CHELSA
434 mm for 1981-2010 and CHIRPS 449 mm for 1981-2025), printed a p-value as "0" and raw codes
such as "Bdod" and "1981-2010-01". Citation chips repeated a number inside one sentence
("1 4 1 4 5 1"), and the Shared science tab numbered its sources from 1 again.

## Decision

1. **Catalogue text is written for readers.** `etl/geo/geo_etl/catalog.py` titles the boundary
   dataset "Indian district boundaries, matched to LGD codes", stores no licence URL or citation
   for it, and keeps its provenance only in `docs/DATA_SOURCES.md`. CHELSA's licence is not
   confirmed, so its licence slot names the paper CHELSA asks to be cited, "Karger et al. 2017",
   linked to doi:10.1038/sdata.2017.122, its attribution is "CHELSA V2.1" and the full citation
   follows, so the credit names the paper once in short and once in full. The HydroRIVERS method
   (`hydrorivers.METHOD`) says "distance from the district's centre" and the CHELSA method
   (`chelsa.METHOD`) "averaged over each district on the 1 km grid"; the engineering detail of
   both stays in `docs/DATA_SOURCES.md`. A test fails if any reader field of the catalogue, or any
   shared golden, names the Designer Portal or says "not confirmed".
2. **The map keeps one line in view.** `MapAttribution` shows the Survey of India caption with
   "© OpenStreetMap contributors" (linked to openstreetmap.org/copyright) on the same line, and
   puts DataMeet and the district-boundary dataset behind a native "Map credits" disclosure. The
   OpenStreetMap credit stays in view because the OSMF attribution guidelines let it collapse
   only after it has been shown and never require a reader to interact to see it (ODbL, for the
   OSM-derived outline).
3. **A district place is named for its district.** `geo/places` labels a district place with the
   district's name, since its values describe the whole district; the card lists the craft's
   making places inside the district from the craft page's places ("includes Ajrakhpur, Dhamadka
   and Khavda"). Point facts at village coordinates remain for plan task 2-03.
4. **One normal per quantity, from the dataset of its trend.** `geo/climate.TREND_DATASETS` is
   the one home: CHIRPS for rainfall, GHCN CAMS for annual mean temperature.
   `geo/region_view.one_normal_per_quantity`, applied in `region_facets` (craft Region tab and the
   map's district panel), keeps that dataset's annual and monthly normals and drops CHELSA's
   normal and its district percentiles only where the trend dataset has that normal for the
   place. The map's "Annual precipitation" and "Annual mean temperature" layers draw the same
   normals over the dataset's period (`geo/layers._trend_normal`), so a district's colour, its
   panel, its Region card and the answer's climate card state one value. CHELSA's 1 km grid is
   finer than GHCN CAMS's 0.5 degree, but a normal that matches the trend shown beside it and
   comes from a public-domain dataset outweighs the finer grid; CHELSA keeps the warmest- and
   coldest-month layers and the values no other dataset gives. Yearly values and trends always
   stay.
5. **Numbers read in words.** P-values use `measure.pText` ("p = 0.005", "p < 0.001"), the one
   home it moved to from `climateView`. Bulk density reads in g/cm³, slope in degrees, Strahler
   order bare, a monthly normal names its month in the label ("Mean temperature, January") and a
   period reads "1981–2010". A share is captioned by what it is a share of, from its unit: the
   district's area, its land, or the 2000 forest (`regionView.statLabel`), on the Region tab and
   under a map layer.
6. **Citations cluster by source.** `citations.citationsBySource` groups a sentence's citations
   by source in ascending number, one chip per source; the chip opens every distinct passage
   behind it (`OpenCitation.citations`). The Shared science tab continues the craft page's
   numbering (`listedSourceNumbers(sources, numbered)`), so a source has one number on every tab.
   Plan task 1A-05 redesigns the chip and dialog on top of this grouping.

## Consequences

Production rows change only when the Geo ETL workflow loads HydroRIVERS (the method) and CHELSA
(the method, licence and attribution) again; every load also rewrites the boundary dataset row.
The layer golden's version hash and the phase-B map block that cites it were recomputed for the
new boundary text, and the layer list golden now lists the GHCN CAMS temperature layer. The two
climate layers read rows production already holds (CHIRPS and GHCN CAMS normals, decision 0065),
so they change with the backend deploy alone.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
