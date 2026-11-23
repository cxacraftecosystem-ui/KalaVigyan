import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "backend" / "app" / "data" / "curation"
SCHEMA = REPO / "shared" / "curation.dossier.schema.json"
FIELD_CLAIMS = 3
CURATED_FIELDS = 12
BAR = {"pictures": 8, "placedShare": 1.0, "chaptersWithPictures": 4, "afterShare": 0.5, "whyShare": 0.66, "nativeNames": 1}


def dossiers(args):
    if args:
        return [Path(a) for a in args]
    files = sorted(ROOT.glob("*.json")) + sorted((ROOT / "categories").glob("*.json"))
    return [f for f in files if not f.name.endswith(".check.json") and f.name != "index.json"]


def fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema["$defs"]["Claim"]["properties"]["discipline"]["enum"]


def structure_claims(d):
    society = {c for g in d.get("communities") or [] for c in g.get("claimIds") or []}
    policy = set(((d.get("market") or {}).get("gi") or {}).get("claimIds") or [])
    return {"SOCIETY": society, "POLICY": policy}


def field_counts(d):
    counts = {field: 0 for field in fields()}
    for claim in d.get("claims") or []:
        counts[claim.get("discipline")] = counts.get(claim.get("discipline"), 0) + 1
    for field, ids in structure_claims(d).items():
        counts[field] += len(ids)
    return counts


def field_gaps(counts):
    missing = [f for f, n in counts.items() if n == 0]
    thin = [f"{f} {n}" for f, n in counts.items() if 0 < n < FIELD_CLAIMS]
    covered = len(counts) - len(missing)
    gaps = []
    if covered < CURATED_FIELDS:
        gaps.append(f"fields covered {covered}/{len(counts)} (bar {CURATED_FIELDS}+)")
    if missing:
        gaps.append(f"fields with no claim (search them): {', '.join(missing)}")
    if thin:
        gaps.append(f"fields under {FIELD_CLAIMS} claims: {', '.join(thin)}")
    return gaps


def share(part, whole):
    return part / whole if whole else 0.0


def picture_gaps(pictures, placed):
    roles = [p["placement"].get("role") for p in placed]
    chapters = {p["placement"].get("chapter") for p in placed}
    gaps = []
    if len(pictures) < BAR["pictures"]:
        gaps.append(f"pictures {len(pictures)}/{BAR['pictures']}+")
    if share(len(placed), len(pictures)) < BAR["placedShare"]:
        gaps.append(f"unplaced pictures {len(pictures) - len(placed)}")
    if "MASTHEAD" not in roles:
        gaps.append("no MASTHEAD")
    if len(chapters) < BAR["chaptersWithPictures"]:
        gaps.append(f"chapters with pictures {len(chapters)}/{BAR['chaptersWithPictures']}+")
    return gaps


def stage_gaps(stages):
    after = sum(1 for s in stages if s.get("after"))
    why = sum(1 for s in stages if s.get("whyClaimId"))
    gaps = []
    if share(after, len(stages)) < BAR["afterShare"]:
        gaps.append(f"stage after {after}/{len(stages)}")
    if share(why, len(stages)) < BAR["whyShare"]:
        gaps.append(f"stage why {why}/{len(stages)}")
    return gaps


def craft_gaps(d, stages):
    gaps = stage_gaps(stages) if stages else []
    if len(d.get("nativeNames") or []) < BAR["nativeNames"]:
        gaps.append("no native name")
    if d.get("scope", "CRAFT") == "CRAFT" and not (d.get("market") or {}).get("gi"):
        gaps.append("no GI record (only if GI-registered)")
    return gaps


def material_gaps(materials):
    maybe_plants = [m for m in materials if m.get("kind") in {"DYE", "FIBRE", "WOOD", "RESIN", "MORDANT"}]
    unnamed = [m["id"] for m in maybe_plants if not m.get("botanicalName")]
    return [f"check for plants without botanicalName: {', '.join(unnamed)}"] if unnamed else []


def report(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    pictures = d.get("pictures") or []
    placed = [p for p in pictures if p.get("placement")]
    stages = d.get("stages") or []
    sources = d.get("sources") or []
    gaps = picture_gaps(pictures, placed)
    if path.parent.name != "categories":
        gaps.extend(craft_gaps(d, stages))
    gaps.extend(material_gaps(d.get("materials") or []))
    counts = field_counts(d)
    gaps.extend(field_gaps(counts))
    ab = sum(1 for s in sources if s.get("reliability") in {"A", "B"})
    return {
        "dossier": path.stem,
        "claims": len(d.get("claims") or []),
        "fields": counts,
        "sourcesAB": f"{ab}/{len(sources)}",
        "pictures": len(pictures),
        "placed": len(placed),
        "stages": len(stages),
        "reactions": len(d.get("reactions") or []),
        "nativeNames": len(d.get("nativeNames") or []),
        "gaps": gaps,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = [report(p) for p in dossiers([a for a in sys.argv[1:] if not a.startswith("--")])]
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        covered = sum(1 for n in r["fields"].values() if n)
        head = f"{r['dossier'][:34]:34} claims {r['claims']:3} fields {covered:2}/{len(r['fields'])} AB {r['sourcesAB']:>6} pics {r['pictures']:2}/{r['placed']:2} stages {r['stages']:2} rx {r['reactions']} names {r['nativeNames']}"
        print(head)
        print("    " + ("; ".join(r["gaps"]) if r["gaps"] else "meets the bar"))


if __name__ == "__main__":
    main()
