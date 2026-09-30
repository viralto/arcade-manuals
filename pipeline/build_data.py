"""Build machines.json and aliases.json from MAME, the review decisions and the previous data.

Inputs (all under pipeline/):
  cache/mame0289.xml, cache/mame0289.summary.json, cache/categories.json   MAME data
  cache/rematch.json                                                      every manual link, bucketed
  review/decisions_*.json, post1999_decisions.json                  manual placement decisions
  review/series_decisions.json                                      post-1999 series continuations
  overrides.json                                                          hand corrections (win over everything)
  platforms.json                                                          canonical platform names
The previous machines.json supplies the manual links and the fields extracted from manuals.

Outputs: machines.json, aliases.json and pipeline/cache/changes.json (for the review page).
Run from the repo root: python3 pipeline/build_data.py
"""
import collections, glob, json, os, re, sys

sys.path.insert(0, 'pipeline')
from classify import in_year_range
from mame_records import build as build_mame_records

S = json.load(open('pipeline/cache/mame0289.summary.json'))
C = json.load(open('pipeline/cache/categories.json'))
OLD = json.load(open('pipeline/source/machines-2026-04.json'))
REMATCH = json.load(open('pipeline/cache/rematch.json'))
PLATFORMS = {k: v for k, v in json.load(open('pipeline/platforms.json')).items() if not k.startswith('_')}
OVERRIDES = json.load(open('pipeline/overrides.json')) if os.path.exists('pipeline/overrides.json') else {}
MISSING = set(json.load(open('pipeline/missing_files.json'))['files'])

EXTRACTED = ['ics', 'pcbs', 'power', 'monitor', 'audio', 'cabinet_type', 'coin_mechanism',
             'edge_connector', 'fuses', 'physical']


def root(mid):
    m = S.get(mid)
    return (m['clone'] or mid) if m else None


def key_of(record_id, record_name, fname):
    return f"{record_id or record_name}|{fname}"


# ---------------------------------------------------------------- decisions
decisions = {}
for f in sorted(glob.glob('pipeline/review/decisions_*.json')) + ['pipeline/review/post1999_decisions.json']:
    for d in json.load(open(f)):
        decisions[d['key']] = d
for k, d in OVERRIDES.get('docs', {}).items():
    decisions[k] = dict(d, key=k, confidence='override')

series = {d['id']: d for d in json.load(open('pipeline/review/series_decisions.json'))}
series_ids = {i for i, d in series.items() if d['include']}
for i in OVERRIDES.get('include', []):
    series_ids.add(i)
excluded = set(OVERRIDES.get('exclude', []))

# ---------------------------------------------------------------- scope
in_scope = set()
for name, m in S.items():
    if m['clone'] or C.get(name) != 'arcade':
        continue
    if in_year_range(m['year']) or name in series_ids:
        in_scope.add(name)
in_scope -= excluded

# ---------------------------------------------------------------- place every manual link
old_by_key = {}
for rec in OLD:
    for doc in rec.get('docs', []):
        old_by_key[key_of(rec.get('id'), rec['name'], doc['f'])] = (rec, doc)

placed = collections.defaultdict(list)       # destination -> [(doc, source record, decision)]
dropped_out_of_scope = []                    # reviewed targets that the scope settings exclude
changes = []
for r in REMATCH:
    k = key_of(r['record_id'], r['record_name'], r['file'])
    rec, doc = old_by_key[k]
    cur = root(r['record_id']) if r['record_id'] else None
    d = decisions.get(k)
    if d is None:
        if r['bucket'] != 'ok':
            raise SystemExit(f'no decision for {k}')
        d = {'decision': 'keep', 'target': cur, 'confidence': 'auto', 'note': 'filename matches its machine'}
    kind, target = d['decision'], d.get('target')
    if kind == 'keep':
        target = target or cur
        dest = ('game', target) if target else ('title', rec['name'])
    elif kind in ('move', 'merge'):
        dest = ('game', target)
    elif kind == 'platform':
        name = PLATFORMS.get((d.get('platform') or '').lower())
        if name is None:
            raise SystemExit(f"unmapped platform {d.get('platform')!r} for {k}")
        dest = ('game', name[5:]) if name.startswith('game:') else ('platform', name)
    elif kind == 'standalone':
        dest = ('title', d.get('title') or rec['name'])
    elif kind == 'drop':
        dest = None
    elif kind == 'multi':
        dest = ('multi', tuple(d['targets']))
    else:
        raise SystemExit(f'unknown decision {kind} for {k}')
    games = [dest[1]] if dest and dest[0] == 'game' else list(dest[1]) if dest and dest[0] == 'multi' else []
    for g in games:
        if g not in S or S[g]['clone']:
            raise SystemExit(f'bad target {g} for {k}')
        if C.get(g) == 'arcade':
            in_scope.add(g)                  # a reviewed manual pulls its arcade game into scope
        elif g not in in_scope:
            dropped_out_of_scope.append((k, g, C.get(g)))
    if dest and doc['f'] not in MISSING:
        for g in games or [None]:
            placed[('game', g) if g else dest].append((doc, rec, d))
    moved = dest != (('game', cur) if cur else ('title', rec['name']))
    if dest and dest[0] == 'multi':
        dest = ('game', ', '.join(dest[1]))
    if moved or d.get('confidence') in ('low', 'medium'):
        changes.append({
            'file': doc['f'], 'url': doc['l'], 'doc_type': doc['t'],
            'from': {'id': rec.get('id') or '', 'name': rec['name'], 'family': cur,
                     'family_name': S[cur]['desc'] if cur else None, 'category': C.get(cur) if cur else None},
            'decision': kind, 'dest_kind': dest[0] if dest else None, 'dest': dest[1] if dest else None,
            'dest_name': (S[dest[1]]['desc'] if dest and dest[0] == 'game' and dest[1] in S else (dest[1] if dest else None)),
            'confidence': d.get('confidence'), 'note': d.get('note'),
        })

# ---------------------------------------------------------------- MAME records
ids = sorted(in_scope)
mame = build_mame_records('pipeline/cache/mame0289.xml', set(ids))

old_by_id = {r['id']: r for r in OLD if r.get('id')}


def title_base(s):
    return re.sub(r'[^a-z0-9]', '', re.split(r'\s*\(', s.lower())[0])


def aliases_for(fam):
    """Alternate titles: clone titles by the same maker, plus titles of merged manual-only records."""
    parent = S[fam]
    seen = {title_base(parent['desc'])}
    out = []
    for name, m in S.items():
        if m['clone'] != fam:
            continue
        t = re.split(r'\s*\(', m['desc'])[0].strip()
        if (m['mfr'] or '').split(' ')[0] != (parent['mfr'] or '').split(' ')[0]:
            continue
        if title_base(t) and title_base(t) not in seen:
            seen.add(title_base(t))
            out.append(t)
    for doc, rec, d in placed.get(('game', fam), []):
        if not rec.get('id') and title_base(rec['name']) not in seen:
            seen.add(title_base(rec['name']))
            out.append(rec['name'])
    return out


records, aliases = [], {}
for fam in ids:
    r = mame[fam]
    docs = placed.get(('game', fam), [])
    r['docs'] = [doc for doc, _, _ in docs]
    # Manual-extracted fields: keep the old record's own only if some of its manuals stayed with it,
    # otherwise take them from a merged manual-only record.
    old = old_by_id.get(fam)
    sources = []
    if old and any(src is old for _, src, _ in docs):
        sources.append(old)
    sources += [src for _, src, _ in docs if not src.get('id') and src not in sources]
    for f in EXTRACTED:
        for src in sources:
            if src.get(f):
                r[f] = src[f]
                break
    al = aliases_for(fam)
    if al:
        aliases[fam] = al
    records.append(r)

# Manual-only records: games MAME lacks, and platforms.
by_title = collections.defaultdict(list)
display = {}
for (kind, name), docs in placed.items():
    if kind in ('title', 'platform'):
        k = (kind, title_base(name))
        by_title[k] += docs
        display.setdefault(k, name)
for (kind, base), docs in by_title.items():
    name = display[(kind, base)]
    src = next((s for _, s, _ in docs if not s.get('id')), docs[0][1])
    r = {'id': '', 'name': name}
    if kind == 'platform':
        r['kind'] = 'platform'
    years = [d.get('year') for _, _, d in docs if d.get('year')]
    y = years[0] if years else (src.get('y') if not src.get('id') else None)
    if y:
        r['y'] = str(y)
    if src.get('m') and not src.get('id'):
        r['m'] = src['m']
    r['docs'] = [doc for doc, _, _ in docs]
    for f in EXTRACTED:
        if src.get(f) and not src.get('id'):
            r[f] = src[f]
    records.append(r)

# ---------------------------------------------------------------- search blob and ordering
def search_blob(r):
    parts = [r['name'], r.get('m') or '', r.get('y') or '', r.get('id') or '']
    parts += [c['n'] for c in r.get('cpu', []) + r.get('aud', [])]
    parts += [d['type'] for d in r.get('disp', [])]
    parts += [c['type'] for c in (r.get('inp') or {}).get('ctrl', [])]
    parts += [d['name'] for d in r.get('dip', [])]
    for ic in r.get('ics') or []:
        if isinstance(ic, dict):
            parts += [ic.get('part') or '', ic.get('description') or '']
    for p in r.get('pcbs') or []:
        if isinstance(p, dict):
            parts += [p.get('name') or '', p.get('part_number') or '']
    if r.get('cabinet_type'):
        parts.append(str(r['cabinet_type']))
    return ' '.join(p for p in parts if p)


for r in records:
    r['sb'] = search_blob(r)
records.sort(key=lambda r: (r['name'].lower(), r.get('id') or ''))

KEY_ORDER = ['id', 'name', 'kind', 'y', 'm', 'cpu', 'aud', 'disp', 'inp', 'ch', 'dip', 'docs'] + EXTRACTED + ['sb']
records = [{k: r[k] for k in KEY_ORDER if k in r} for r in records]

json.dump(records, open('machines.json', 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(dict(sorted(aliases.items())), open('aliases.json', 'w'), indent=0, ensure_ascii=False)
json.dump(changes, open('pipeline/cache/changes.json', 'w'), indent=1)

for k, g, cat in dropped_out_of_scope:
    print(f'  out of scope ({cat}): {g} <- {k}')
n_docs = sum(len(r.get('docs', [])) for r in records)
print(f"{len(records)} records ({sum(1 for r in records if r.get('id'))} MAME, "
      f"{sum(1 for r in records if r.get('kind') == 'platform')} platforms, "
      f"{sum(1 for r in records if not r.get('id') and r.get('kind') != 'platform')} other manual-only); "
      f"{n_docs} manual links; {len(aliases)} alias entries; {len(changes)} changes for review")
