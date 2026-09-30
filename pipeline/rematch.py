"""Check every manual's machine assignment against MAME game families.

A family is a parent set plus its clones. For each manual we derive a title from the
filename, score it against every arcade/pinball/gambling family, and compare the best
family with the one the manual is currently attached to.

Usage: python3 pipeline/rematch.py   (run from the repo root)
Writes pipeline/cache/rematch.json
"""
import collections, json, re, urllib.parse

from classify import categorise

S = json.load(open('pipeline/cache/mame0289.summary.json'))
CATS = json.load(open('pipeline/cache/categories.json'))
ALIASES = json.load(open('pipeline/source/aliases-2026-09.json'))
DATA = json.load(open('pipeline/source/machines-2026-04.json'))

DOC_WORDS = set('''manual manuals schematics schematic schem service instructions instruction kit parts
operating operation operators operator owners owner technical tech drawing drawings package pdf
wiring diagram diagrams catalog sheet sheets bulletin note notes supplement addendum addenda
change order amendment printing 1st 2nd 3rd 4th first second third general spare list lists
set rev revision complete partial conversion field install installation update updated
backdoor errata troubleshooting guide sb upright cocktail cabaret sitdown deluxe dlx std
standard mini version english japanese japan usa us world logic board pcb pwb sound sheet
dedicated universal cabinet cab and of the for with to in a'''.split())

MAKERS = set('''atari midway bally williams sega konami capcom namco taito nintendo cinematronics gottlieb
exidy dataeast deco irem centuri stern universal nichibutsu jaleco tecmo technos snk kaneko
toaplan seibu cave psikyo gaelco igs mylstar venture rockola meadows ramtek kee'''.split())

PARTNO = re.compile(r'^(tm|co|st|sp|ipc|dp|m\d+|a\d+|\d+[a-z]?)$')


def norm_tokens(s):
    s = s.lower().replace('&', ' and ').replace("'", '')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return s.split()


def title_tokens(s):
    """Tokens of a machine title, without region/version parentheticals."""
    s = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', s)
    return [t for t in norm_tokens(s) if t not in ('the', 'a', 'of', 'and')]


def file_tokens(fname):
    s = urllib.parse.unquote(fname)
    s = re.sub(r'\.pdf$', '', s, flags=re.I)
    s = re.sub(r'\([^)]*\)', ' ', s)          # part numbers and dates in brackets
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)  # CamelCase: "PitFighter" -> "Pit Fighter"
    out = []
    for t in norm_tokens(s):
        if t in DOC_WORDS or t in MAKERS:
            continue
        if PARTNO.match(t) and not re.fullmatch(r'19[4-9]\d|20[0-2]\d|\d{1,3}', t):
            continue                            # TM-357, 16-3030 etc, but keep 1942 / 720 / 005
        out.append(t)
    return out


# Build families: parent -> set of title token strings (parent, clones, aliases)
families = collections.defaultdict(set)
family_cat = {}
for name, m in S.items():
    root = m['clone'] or name
    cat = CATS.get(root)
    if cat not in ('arcade', 'pinball', 'gambling'):
        continue
    family_cat[root] = cat
    families[root].add(' '.join(title_tokens(m['desc'])))
    # "Title: Subtitle" and "Title / Other Title" also match on their first part
    for part in re.split(r'\s*[:/]\s*| - ', re.sub(r'\([^)]*\)', '', m['desc'])):
        if part.strip():
            families[root].add(' '.join(title_tokens(part)))
for root, names in ALIASES.items():
    if root in families:
        for n in names:
            families[root].add(' '.join(title_tokens(n)))

# Inverted index: token -> families
tok_index = collections.defaultdict(set)
for root, titles in families.items():
    for t in titles:
        for tok in t.split():
            tok_index[tok].add(root)
df = {tok: len(f) for tok, f in tok_index.items()}
joined_index = collections.defaultdict(set)
for root, titles in families.items():
    for t in titles:
        joined_index[t.replace(' ', '')].add(root)
NFAM = len(families)


def idf(tok):
    import math
    return math.log(NFAM / (1 + df.get(tok, 0)))


def score(ftoks, title):
    """Weighted overlap of filename tokens with one title, penalising unmatched title tokens."""
    tt = title.split()
    if not tt or not ftoks:
        return 0.0
    fs, ts = set(ftoks), set(tt)
    common = fs & ts
    joined_f, joined_t = ''.join(ftoks), ''.join(tt)
    if joined_f == joined_t:                  # "Burgertime" vs "burger time"
        return 1.0
    if not common:
        if joined_t and joined_t in joined_f and len(joined_t) >= 5:   # "Pitfighter" vs "pit fighter"
            return 0.9
        return 0.0
    w = lambda s: sum(idf(t) for t in s) or 1e-9
    recall_title = w(common) / w(ts)      # how much of the title the file mentions
    precision = w(common) / w(fs)         # how much of the file is explained by the title
    return 2 * recall_title * precision / (recall_title + precision)


# Ports and re-releases that share a title with the arcade original rank below it.
PORT_PREFIXES = ('pc_', 'nss_', 'mt_', 'ar_', 'mp_')
CAT_RANK = {'arcade': 2, 'pinball': 1, 'gambling': 0}


def rank_key(item):
    s, root = item
    return (round(s, 3), CAT_RANK[family_cat[root]], not root.startswith(PORT_PREFIXES), -len(root))


def best_families(ftoks, n=5):
    cands = set()
    for t in ftoks:
        cands |= tok_index.get(t, set())
    joined = ''.join(ftoks)
    cands |= joined_index.get(joined, set())
    scored = []
    for root in cands:
        s = max(score(ftoks, t) for t in families[root])
        scored.append((s, root))
    scored.sort(key=rank_key, reverse=True)
    return scored[:n]


def family_of(mid):
    m = S.get(mid)
    return (m['clone'] or mid) if m else None


results = []
for rec in DATA:
    for doc in rec.get('docs', []):
        ftoks = file_tokens(doc['f'])
        cur = family_of(rec.get('id')) if rec.get('id') else None
        cur_score = max((score(ftoks, t) for t in families.get(cur, ())), default=0.0)
        top = best_families(ftoks)
        results.append({
            'file': doc['f'], 'type': doc['t'], 'tokens': ftoks,
            'record_id': rec.get('id') or '', 'record_name': rec['name'],
            'record_mfr': rec.get('m'), 'record_year': rec.get('y'),
            'current_family': cur, 'current_cat': CATS.get(cur) if cur else None,
            'current_score': round(cur_score, 3),
            'top': [(round(s, 3), r, S[r]['desc'], S[r]['mfr'], S[r]['year'], family_cat[r]) for s, r in top],
        })
json.dump(results, open('pipeline/cache/rematch.json', 'w'), indent=1)
print(len(results), 'manual links scored')
