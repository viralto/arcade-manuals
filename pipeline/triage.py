"""Sort rematch results into ok / drop-post1999 / review, and write review batches.

Usage: python3 pipeline/triage.py [n_batches]   (run from the repo root, after rematch.py)
"""
import collections, json, os, sys

sys.path.insert(0, 'pipeline')
from classify import in_scope, in_year_range

S = json.load(open('pipeline/cache/mame0289.summary.json'))
C = json.load(open('pipeline/cache/categories.json'))
R = json.load(open('pipeline/cache/rematch.json'))


def bucket(r):
    top = r['top'][0] if r['top'] else None
    cur = r['current_family']
    if r['record_id']:
        cur_ok = cur and in_scope(S, C, cur)
        if cur_ok and (not top or top[1] == cur or r['current_score'] >= top[0] - 0.05):
            return 'ok'
        if cur and C.get(cur) == 'arcade' and in_year_range(S[cur]['year']) is False:
            if not top or top[0] < 0.85 or in_year_range(S[top[1]]['year']) is False:
                return 'drop-post1999'
        return 'review'
    if top and top[0] >= 0.85 and in_year_range(S[top[1]]['year']) is False:
        return 'drop-post1999'
    if r['record_year'] and in_year_range(r['record_year']) is False:
        return 'drop-post1999'
    return 'review'


for r in R:
    r['bucket'] = bucket(r)
json.dump(R, open('pipeline/cache/rematch.json', 'w'), indent=1)
print(collections.Counter(r['bucket'] for r in R))

review = [r for r in R if r['bucket'] == 'review']
n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
os.makedirs('pipeline/cache/review', exist_ok=True)
for i in range(n):
    items = []
    for j, r in enumerate(review[i::n]):
        cur = r['current_family']
        items.append({
            'key': f"{r['record_id'] or r['record_name']}|{r['file']}",
            'file': r['file'], 'doc_type': r['type'],
            'record': {'id': r['record_id'], 'name': r['record_name'], 'mfr': r['record_mfr'], 'year': r['record_year']},
            'current_family': cur and {'id': cur, 'desc': S[cur]['desc'], 'mfr': S[cur]['mfr'], 'year': S[cur]['year'], 'cat': C.get(cur)},
            'candidates': [{'id': t[1], 'desc': t[2], 'mfr': t[3], 'year': t[4], 'cat': t[5], 'score': t[0]} for t in r['top']],
        })
    json.dump(items, open(f'pipeline/cache/review/batch_{i + 1}.json', 'w'), indent=1)
    print(f'batch_{i + 1}.json', len(items))
