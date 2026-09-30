"""Condense a MAME -listxml dump into one compact JSON record per machine.

Usage: python3 pipeline/mame_summary.py pipeline/cache/mame0289.xml pipeline/cache/mame0289.summary.json
"""
import json, sys
import xml.etree.ElementTree as ET

src, dst = sys.argv[1], sys.argv[2]
out = {}
for _, el in ET.iterparse(src, events=('end',)):
    if el.tag != 'machine':
        continue
    a = el.attrib
    inp = el.find('input')
    m = {
        'desc': el.findtext('description'),
        'year': el.findtext('year'),
        'mfr': el.findtext('manufacturer'),
        'src': a.get('sourcefile'),
        'clone': a.get('cloneof'),
        'romof': a.get('romof'),
        'bios': a.get('isbios') == 'yes',
        'device': a.get('isdevice') == 'yes',
        'mech': a.get('ismechanical') == 'yes',
        'runnable': a.get('runnable', 'yes') == 'yes',
        'coins': int(inp.get('coins', 0)) if inp is not None else 0,
        'swlist': [s.get('name') for s in el.findall('softwarelist')],
        'chips': [[c.get('type'), c.get('name'), c.get('tag'), int(c.get('clock') or 0)] for c in el.findall('chip')],
        'devs': sorted({d.get('name') for d in el.findall('device_ref')}),
        'roms': [r.get('name') for r in el.findall('rom') if not r.get('merge')],
        'mroms': [r.get('name') for r in el.findall('rom') if r.get('merge')],
        'screens': [d.get('type') for d in el.findall('display')],
        'ctrls': sorted({c.get('type') for c in inp.findall('control')}) if inp is not None else [],
    }
    drv = el.find('driver')
    if drv is not None:
        m['status'] = drv.get('status')
    out[a['name']] = m
    el.clear()
json.dump(out, open(dst, 'w'), separators=(',', ':'))
print(len(out), 'machines')
