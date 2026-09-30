"""Search MAME 0.289 game families by title words, for manual review.

Usage: python3 pipeline/search_mame.py "crazy climber" [--all]
Shows parents whose own or clone titles contain every word; --all includes non-arcade.
"""
import json, re, sys

S = json.load(open('pipeline/cache/mame0289.summary.json'))
C = json.load(open('pipeline/cache/categories.json'))
words = [w for w in re.sub(r'[^a-z0-9 ]', ' ', sys.argv[1].lower()).split()]
show_all = '--all' in sys.argv
fam = {}
for name, m in S.items():
    root = m['clone'] or name
    text = re.sub(r'[^a-z0-9 ]', ' ', f"{m['desc']} {name}".lower())
    squashed = text.replace(' ', '')
    if all(w in text or w in squashed for w in words):
        fam.setdefault(root, []).append(name)
for root, members in sorted(fam.items(), key=lambda kv: S[kv[0]]['year'] or ''):
    p = S[root]
    if not show_all and C.get(root) not in ('arcade', 'pinball'):
        continue
    clones = [f"{c} ({S[c]['desc']})" for c in members if c != root][:4]
    print(f"{root:12} {C.get(root):8} {p['year']} | {p['mfr']} | {p['desc']} | src={p['src']}" + (f" | clones: {'; '.join(clones)}" if clones else ''))
