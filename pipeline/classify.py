"""Assign each MAME machine a category: arcade, gambling, pinball or other.

Rules, in order:
  - devices, BIOS sets and unrunnable machines are 'other'
  - handheld/TV-game drivers and anything with a software list (consoles, computers) are 'other'
  - cranes and prize merchandisers are 'prize'; mahjong/hanafuda panels are 'mahjong' unless scope.json keeps them
  - fruit/slot/AWP manufacturers, and anything with gambling controls, are 'gambling';
    the pinball folder is 'pinball'
  - machines with neither a screen nor controls (broadcast gear, synth modules) are 'other'
  - a machine with a coin slot is 'arcade'
  - a coinless machine counts as 'arcade' only if its source folder is mostly coin-op
    (MAME omits coin inputs on some discrete and I/O-board games, e.g. Death Race, Tekken 4),
    or if it predates 1980 and sits in a partly coin-op folder such as 'misc' (discrete-logic games)
"""
import collections, json, os

SCOPE = json.load(open(os.path.join(os.path.dirname(__file__), 'scope.json')))

NON_ARCADE_FOLDERS = {'handheld', 'tvgames', 'skeleton', 'homebrew', 'chess', 'trainer'}
# Coinless pre-1980 machines in partly coin-op folders that are not arcade games.
NOT_ARCADE = {'mcm70'}
# Amusement games that MAME gives gambling-style controls (bar-top trivia etc).
# Also electro-mechanical games MAME lists without a screen.
ARCADE_EXCEPTIONS = {'phrcraze', 'icecold', 'qncrash', 'schexx', 'mdntmrdr',
                     'magictg', 'rcorsair', 'su2000', 'savquest', 'skeetsht', 'popshot', 'intrscti'}
# Japanese arcade mahjong makers: their bet buttons don't make them gambling machines.
# Only used when scope.json has mahjong switched on.
MAHJONG_ARCADE_FOLDERS = set() if not SCOPE['mahjong'] else {'dynax', 'nichibutsu', 'seibu', 'seta', 'toaplan', 'jaleco', 'sega', 'taito',
                          'vsystem', 'nmk', 'sanritsu', 'alba', 'dooyong'}
# Cranes, UFO catchers and prize merchandisers: category 'prize'.
PRIZE_SOURCES = {'sega/segaufo.cpp', 'taito/capr1.cpp', 'taito/caprcyc.cpp', 'namco/sweetland.cpp', 'pc/przone.cpp'}
PRIZE_IDS = {'gocowboy', 'clubkprz', 'clubkpzb', 'shootpl', 'shootplm'}
# Fruit machine drivers filed outside the gambling manufacturers' folders.
GAMBLING_SOURCES = {'misc/ecoinf2.cpp', 'misc/ecoinf3.cpp', 'misc/aces1.cpp', 'misc/interflip8035.cpp',
                    'misc/sumt8035.cpp', 'acorn/aristmk5.cpp'}
GAMBLING_FOLDERS = {'bfm', 'barcrest', 'jpm', 'maygay', 'igt', 'aristocrat', 'ausnz', 'adp',
                    'cirsa', 'newcrest', 'sealy', 'amcoe', 'astrocorp', 'subsino', 'funworld'}


def folder(m):
    return (m.get('src') or '').split('/')[0]


def coinop_share(summary):
    tally = collections.defaultdict(lambda: [0, 0])
    for m in summary.values():
        if m['clone'] or m['device'] or not m['runnable']:
            continue
        t = tally[folder(m)]
        t[0] += 1
        t[1] += m['coins'] > 0
    return {f: c / n for f, (n, c) in tally.items()}


def categorise(summary):
    share = coinop_share(summary)
    cats = {}
    for name, m in summary.items():
        f = folder(m)
        if m['device'] or m['bios'] or not m['runnable'] or name in NOT_ARCADE:
            cat = 'other'
        elif name in ARCADE_EXCEPTIONS:
            cat = 'arcade'
        elif m['src'] in PRIZE_SOURCES or name in PRIZE_IDS or (m['clone'] in PRIZE_IDS):
            cat = 'prize'
        elif not SCOPE['mahjong'] and {'mahjong', 'hanafuda'} & set(m.get('ctrls', ())):
            cat = 'mahjong'
        elif f in NON_ARCADE_FOLDERS or m['swlist']:
            cat = 'other'
        elif f in GAMBLING_FOLDERS or m['src'] in GAMBLING_SOURCES or (
                'gambling' in m.get('ctrls', ()) and not (
                    'mahjong' in m.get('ctrls', ()) and f in MAHJONG_ARCADE_FOLDERS)):
            cat = 'gambling'
        elif not m['screens'] and not m.get('ctrls') and f != 'pinball':
            cat = 'other'                  # video switchers, VCRs, synth modules
        elif f == 'pinball':
            cat = 'pinball'
        elif m['coins'] > 0 or share.get(f, 0) >= 0.6:
            cat = 'arcade'
        elif share.get(f, 0) >= 0.3 and (m['year'] or '9')[:4] < '1980':
            cat = 'arcade'
        else:
            cat = 'other'
        cats[name] = cat
    return cats


if __name__ == '__main__':
    import json, sys
    summary = json.load(open(sys.argv[1]))
    cats = categorise(summary)
    json.dump(cats, open(sys.argv[2], 'w'), separators=(',', ':'))
    print(collections.Counter(c for n, c in cats.items() if not summary[n]['clone']))


# The site covers machines up to and including 1999. Uncertain years such as "199?" and
# "19??" count as in range; "200?" does not.
LAST_YEAR = SCOPE['last_year']


def in_year_range(year):
    if not year:
        return None                      # unknown: decide from other evidence
    y = year[:4].replace('?', '0')
    return y.isdigit() and int(y) <= LAST_YEAR


def in_scope(summary, cats, name):
    m = summary.get(name)
    if not m:
        return False
    root = m['clone'] or name
    return cats.get(root) == 'arcade' and bool(in_year_range(summary[root]['year']))
