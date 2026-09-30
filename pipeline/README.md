# Data pipeline

Builds `machines.json` and `aliases.json` from MAME, the manual links in the April 2026 data, and the review decisions.

## Rebuild

From the repo root:

```
mkdir -p pipeline/cache && cd pipeline/cache
curl -LO https://github.com/mamedev/mame/releases/download/mame0289/mame0289lx.zip && unzip mame0289lx.zip && cd ../..
python3 pipeline/mame_summary.py pipeline/cache/mame0289.xml pipeline/cache/mame0289.summary.json
python3 pipeline/classify.py pipeline/cache/mame0289.summary.json pipeline/cache/categories.json
python3 pipeline/rematch.py
python3 pipeline/triage.py
python3 pipeline/build_data.py
node build.mjs
```

`build_data.py` stops with an error if any manual link has no decision, so new mismatches can't slip through.

## Files

- `scope.json`: what the site covers (arcade only, 1999 or earlier plus later games in pre-2000 series; no gambling, prize, pinball or mahjong machines).
- `classify.py`: sorts every MAME machine into arcade, gambling, prize, mahjong, pinball or other.
- `rematch.py`, `triage.py`: score every manual against MAME game families and flag the doubtful ones.
- `review/`: decisions on the flagged manuals and on post-1999 series continuations.
- `overrides.json`: hand corrections. These win over everything else; add new fixes here.
- `platforms.json`: canonical names for platform-level documents.
- `missing_files.json`: manual links whose PDF was never uploaded. Remove an entry once the file is in the bucket.
- `source/`: the April 2026 data the manual links and manual-extracted fields come from. Don't edit.
- `search_mame.py`: look up a title in MAME while reviewing.
