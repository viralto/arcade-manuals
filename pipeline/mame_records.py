"""Build site machine records (the machines.json schema) straight from a MAME -listxml dump.

Fields: id, name, y, m, cpu, aud, disp, inp, ch, dip — the MAME-derived part of a record.
DIP switch positions follow MAME's convention: a set bit means the switch is OFF.

Usage (from the repo root):
  python3 pipeline/mame_records.py pipeline/cache/mame0289.xml ids.json out.json
"""
import json, sys
import xml.etree.ElementTree as ET


def clock(hz):
    hz = int(hz or 0)
    if not hz:
        return {}
    if hz >= 1_000_000:
        return {'mhz': round(hz / 1_000_000, 3)}
    return {'khz': round(hz / 1_000, 1)}


def dip_record(ds):
    locs = ds.findall('diplocation')
    mask = int(ds.get('mask') or 0)
    bits = [b for b in range(32) if mask >> b & 1]
    rec = {'name': ds.get('name')}
    if locs:
        rec['loc'] = ', '.join(f"{l.get('name')}:{l.get('number')}" for l in locs)
    opts, default = [], None
    for v in ds.findall('dipvalue'):
        val = int(v.get('value') or 0)
        o = {'n': v.get('name')}
        if locs and len(bits) == len(locs):
            # diplocation order follows mask bit order, lowest bit first
            o['sw'] = ' '.join('OFF' if val >> b & 1 else 'ON' for b in bits)
        opts.append(o)
        if v.get('default') == 'yes':
            default = v.get('name')
    rec['opts'] = opts
    if default is not None:
        rec['def'] = default
    return rec


def machine_record(el):
    r = {'id': el.get('name'), 'name': el.findtext('description')}
    if el.findtext('year'):
        r['y'] = el.findtext('year')
    if el.findtext('manufacturer'):
        r['m'] = el.findtext('manufacturer')
    cpu = [dict({'n': c.get('name')}, **clock(c.get('clock'))) for c in el.findall('chip') if c.get('type') == 'cpu']
    aud = [dict({'n': c.get('name')}, **clock(c.get('clock'))) for c in el.findall('chip')
           if c.get('type') == 'audio' and c.get('name') != 'Speaker']
    if cpu:
        r['cpu'] = cpu
    if aud:
        r['aud'] = aud
    disp = []
    for d in el.findall('display'):
        x = {'type': d.get('type'), 'rot': int(d.get('rotate') or 0)}
        if d.get('width'):
            x['w'], x['h'] = int(d.get('width')), int(d.get('height'))
        if d.get('refresh'):
            x['hz'] = round(float(d.get('refresh')), 2)
        disp.append(x)
    if disp:
        r['disp'] = disp
    inp = el.find('input')
    if inp is not None:
        i = {'p': int(inp.get('players') or 0)}
        if inp.get('coins'):
            i['co'] = int(inp.get('coins'))
        ctrl = []
        for c in inp.findall('control'):
            x = {'type': c.get('type')}
            if c.get('buttons'):
                x['btn'] = int(c.get('buttons'))
            if c.get('ways'):
                x['ways'] = c.get('ways')
            ctrl.append(x)
        if ctrl:
            i['ctrl'] = ctrl
        r['inp'] = i
    snd = el.find('sound')
    if snd is not None and int(snd.get('channels') or 0):
        r['ch'] = int(snd.get('channels'))
    dips = [dip_record(ds) for ds in el.findall('dipswitch')]
    if dips:
        r['dip'] = dips
    return r


def build(xml_path, wanted):
    out = {}
    for _, el in ET.iterparse(xml_path, events=('end',)):
        if el.tag == 'machine':
            if el.get('name') in wanted:
                out[el.get('name')] = machine_record(el)
            el.clear()
    return out


if __name__ == '__main__':
    wanted = set(json.load(open(sys.argv[2])))
    recs = build(sys.argv[1], wanted)
    json.dump(recs, open(sys.argv[3], 'w'), separators=(',', ':'))
    print(len(recs), 'records')
