// Build script for Cloudflare Pages.
// Copies the existing static site into dist/ unchanged and adds one
// crawlable HTML page per machine (/m/<id>), an A-Z index (/machines)
// and a full sitemap. The interactive homepage is not modified.
//
//   node build.mjs          -> writes ./dist
import { readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync, rmSync, statSync } from 'node:fs';
import { join } from 'node:path';

const SITE = 'https://arcadertfm.com';
const OUT = 'dist';
const SKIP = new Set(['build.mjs', 'aliases.json', 'package.json', 'package-lock.json', 'README.md', '.gitignore', '.DS_Store']);

rmSync(OUT, { recursive: true, force: true });
mkdirSync(join(OUT, 'm'), { recursive: true });

// 1. Copy the existing site through untouched.
for (const f of readdirSync('.')) {
  if (f.startsWith('.') || SKIP.has(f) || f === OUT) continue;
  if (statSync(f).isFile()) copyFileSync(f, join(OUT, f));
}

const DATA = JSON.parse(readFileSync('machines.json', 'utf8'));
// Alternate titles (regional names, licensed re-releases) derived from MAME clone families.
// Merged into the copy of machines.json that ships, so the homepage search finds them too.
let ALIASES = {};
try { ALIASES = JSON.parse(readFileSync('aliases.json', 'utf8')); } catch {}
for (const m of DATA) {
  const aka = m.id && ALIASES[m.id];
  if (aka && aka.length) { m.aka = aka; m.sb = (m.sb || '') + ' ' + aka.join(' '); }
}
writeFileSync(join(OUT, 'machines.json'), JSON.stringify(DATA));
const machines = DATA.filter(m => m.id && /^[a-z0-9_]+$/.test(m.id));
const lastmod = new Date().toISOString().slice(0, 10);

// ---------- helpers ported from index.html ----------
const esc = s => (s == null || s === '') ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const fmtClock = c => c.mhz ? c.mhz + ' MHz' : c.khz ? c.khz + ' kHz' : '';
const orientOf = d => (d.rot === 90 || d.rot === 270) ? 'Vertical' : (d.rot === 0 || d.rot === 180) ? 'Horizontal' : '';

function metaLine(item) {
  const meta = [];
  if (mfr(item)) meta.push(mfr(item));
  if (item.y) meta.push(item.y);
  if (item.disp && item.disp.length) meta.push([item.disp[0].type, orientOf(item.disp[0])].filter(Boolean).join(' '));
  if (item.inp) {
    if (item.inp.p) meta.push(item.inp.p + 'P');
    if (item.inp.ctrl) meta.push([...new Set(item.inp.ctrl.map(c => c.type === 'paddle' ? 'rotary' : c.type))].join('/'));
  }
  return meta;
}

function chipSummary(item) {
  const chips = [];
  if (item.cpu) {
    const seen = new Set();
    for (const c of item.cpu) {
      if (seen.has(c.n)) continue;
      const count = item.cpu.filter(x => x.n === c.n).length;
      chips.push((count > 1 ? count + 'x ' : '') + c.n);
      seen.add(c.n);
    }
  }
  if (item.aud) for (const a of item.aud) if (!chips.includes(a.n)) chips.push(a.n);
  return chips;
}

function renderBody(item) {
  let html = '<div class="spec-grid">';
  if (item.disp && item.disp.length) {
    html += '<section class="spec-section"><h2 class="spec-title">Display</h2>';
    for (const d of item.disp) {
      const o = orientOf(d);
      html += `<div class="spec-row"><span class="label">Type: </span><span class="val">${esc(d.type)}${o ? ' ' + o : ''}</span></div>`;
      if (d.w && d.h) html += `<div class="spec-row"><span class="label">Resolution: </span><span class="val">${d.w} x ${d.h}</span></div>`;
      if (d.hz) html += `<div class="spec-row"><span class="label">Refresh: </span><span class="val">${d.hz} Hz</span></div>`;
    }
    html += '</section>';
  }
  if (item.cpu && item.cpu.length) {
    html += '<section class="spec-section"><h2 class="spec-title">Processors</h2>';
    const seen = new Map();
    for (const c of item.cpu) {
      const key = c.n + '|' + (c.mhz || c.khz || '');
      seen.set(key, seen.has(key) ? { ...seen.get(key), count: seen.get(key).count + 1 } : { ...c, count: 1 });
    }
    for (const c of seen.values()) {
      const clk = fmtClock(c);
      html += `<div class="spec-row"><span class="val">${c.count > 1 ? c.count + 'x ' : ''}${esc(c.n)}</span>${clk ? ' <span class="label">@ ' + clk + '</span>' : ''}</div>`;
    }
    html += '</section>';
  }
  if (item.aud && item.aud.length) {
    html += '<section class="spec-section"><h2 class="spec-title">Audio</h2>';
    for (const a of item.aud) {
      const clk = fmtClock(a);
      html += `<div class="spec-row"><span class="val">${esc(a.n)}</span>${clk ? ' <span class="label">@ ' + clk + '</span>' : ''}</div>`;
    }
    if (item.ch) html += `<div class="spec-row"><span class="label">Channels: </span><span class="val">${item.ch}</span></div>`;
    html += '</section>';
  }
  if (item.inp) {
    html += '<section class="spec-section"><h2 class="spec-title">Controls</h2>';
    if (item.inp.p) html += `<div class="spec-row"><span class="label">Players: </span><span class="val">${item.inp.p}</span></div>`;
    if (item.inp.co) html += `<div class="spec-row"><span class="label">Coin slots: </span><span class="val">${item.inp.co}</span></div>`;
    if (item.inp.ctrl) for (const c of item.inp.ctrl) {
      const parts = [c.type === 'paddle' ? 'rotary' : c.type];
      if (c.ways) parts.push(c.ways + '-way');
      if (c.btn) parts.push(c.btn + ' button' + (c.btn > 1 ? 's' : ''));
      html += `<div class="spec-row"><span class="val">${esc(parts.join(', '))}</span></div>`;
    }
    html += '</section>';
  }
  if (item.ics && item.ics.length) {
    html += '<section class="spec-section"><h2 class="spec-title">Components (from manual)</h2>';
    for (const ic of item.ics) {
      if (typeof ic !== 'object') continue;
      const details = [ic.type, ic.location, ic.description].filter(Boolean).join(' · ');
      html += `<div class="spec-row"><span class="val">${esc(ic.part || '?')}</span>${details ? ' <span class="label">' + esc(details) + '</span>' : ''}</div>`;
    }
    html += '</section>';
  }
  if (item.pcbs && item.pcbs.length) {
    html += '<section class="spec-section"><h2 class="spec-title">PCBs (from manual)</h2>';
    for (const p of item.pcbs) {
      html += `<div class="spec-row"><span class="val">${esc(p.name || '?')}</span>${p.part_number ? ' <span class="label">' + esc(p.part_number) + '</span>' : ''}${p.description ? '<br><span class="label">' + esc(p.description) + '</span>' : ''}</div>`;
    }
    html += '</section>';
  }
  if (item.fuses && item.fuses.length) {
    html += '<section class="spec-section"><h2 class="spec-title">Fuses (from manual)</h2>';
    for (const f of item.fuses) {
      html += `<div class="spec-row"><span class="val">${esc(f.id || '?')}</span> <span class="label">${esc([f.rating, f.type].filter(Boolean).join(' · '))}</span></div>`;
    }
    html += '</section>';
  }
  if (item.dip && item.dip.length) {
    const hasAnyLoc = item.dip.some(d => d.loc);
    html += '<section class="spec-section dip-section"><h2 class="spec-title">DIP Switch Settings</h2>';
    html += '<p class="dip-note">Data from MAME. On later hardware, game settings are typically in the Test/Service Menu, not DIP switches. <a href="/dip-info">Learn more</a></p>';
    if (!hasAnyLoc) html += `<p class="dip-note">Physical switch positions not available for this machine in MAME.${item.docs ? ' Check the service manual below for DIP switch details.' : ''}</p>`;
    html += hasAnyLoc
      ? '<table class="dip-table"><thead><tr><th>Switch</th><th>Setting</th><th>Options</th><th>Default</th></tr></thead><tbody>'
      : '<table class="dip-table"><thead><tr><th>Setting</th><th>Options</th><th>Default</th></tr></thead><tbody>';
    for (const d of item.dip) {
      const rowClass = (d.name === 'Unknown' || d.name === 'Unused') ? ' class="dip-unknown"' : '';
      const opts = d.opts || [];
      const hasSw = opts.length > 0 && opts[0] && opts[0].sw;
      const locs = d.loc ? d.loc.split(', ') : [];
      let optsHtml = '';
      if (hasSw && locs.length > 1) optsHtml += `<span class="dip-sw-header"><span class="dip-sw">${locs.map(l => `<span class="sw-label">${esc(l)}</span>`).join(' ')}</span></span>`;
      for (const o of opts) {
        const isDefault = o.n === d.def;
        const swBits = (hasSw && o.sw) ? `<span class="dip-sw">${o.sw.split(' ').map(s => `<span class="sw-${s.toLowerCase()}">${s}</span>`).join(' ')}</span> ` : '';
        optsHtml += `<span class="dip-opt${isDefault ? ' dip-opt-def' : ''}">${swBits}${esc(o.n)}${isDefault ? ' ✱' : ''}</span>`;
      }
      html += hasAnyLoc
        ? `<tr${rowClass}><td class="dip-loc">${esc(d.loc || '')}</td><td class="dip-name">${esc(d.name)}</td><td class="dip-values">${optsHtml}</td><td class="dip-default">${esc(d.def || '')}</td></tr>`
        : `<tr${rowClass}><td class="dip-name">${esc(d.name)}</td><td class="dip-values">${optsHtml}</td><td class="dip-default">${esc(d.def || '')}</td></tr>`;
    }
    html += '</tbody></table></section>';
  }
  if (item.docs && item.docs.length) {
    html += '<section class="spec-section manual-links"><h2 class="spec-title">Available Manuals</h2>';
    for (const doc of item.docs) {
      html += `<a href="${esc(doc.l)}" target="_blank" rel="noopener" class="manual-link">${esc(doc.t || 'Document')} - ${esc(doc.f)}</a>`;
    }
    html += '</section>';
  }
  return html + '</div>';
}

function description(item) {
  const who = [mfr(item), item.y].filter(Boolean).join(', ');
  const aka = item.aka && item.aka.length ? ', also known as ' + item.aka[0] : '';
  const lead = `${item.name}${who ? ' (' + who + ')' : ''}${aka}: arcade machine specs`;
  const parts = [];
  const chips = chipSummary(item);
  if (chips.length) parts.push('Hardware: ' + chips.slice(0, 4).join(', '));
  if (item.dip && item.dip.length) parts.push(item.dip.length + ' DIP switch settings');
  if (item.docs && item.docs.length) parts.push(item.docs.length + ' service manual' + (item.docs.length > 1 ? 's' : ''));
  const tail = ' Free repair reference from ArcadeRTFM.';
  // Drop detail from the front (hardware first) until it fits a search snippet.
  while (parts.length && (lead + '. ' + parts.join('. ') + '.' + tail).length > 158) parts.shift();
  return parts.length ? `${lead}. ${parts.join('. ')}.${tail}` : `${lead}.${tail}`;
}
const mfr = item => (item.m && item.m !== '<unknown>') ? item.m : '';

const head = (title, desc, canonical) => `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${SITE}${canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ArcadeRTFM">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${SITE}${canonical}">
<meta property="og:image" content="${SITE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:description" content="${esc(desc)}">
<meta name="twitter:image" content="${SITE}/og-image.png">
<meta name="theme-color" content="#1a1a2e">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Share+Tech+Mono&display=swap">
<link rel="stylesheet" href="/m.css">
</head>
<body>
<div class="scanlines"></div>
<div class="screen-wrap">
<header class="header">
  <a class="home" href="/"><span class="site">ARCADE MANUAL ARCHIVE</span><span class="subtitle">Machine Specs, DIP Switches &amp; Service Manuals</span></a>
</header>
`;

const footer = `
<footer class="footer">
  <a href="/">Search the database</a> &middot; <a href="/machines">All machines A&ndash;Z</a> &middot; <a href="/dip-info">About DIP switch data</a><br>
  Technical data sourced from <a href="https://www.mamedev.org/" target="_blank" rel="noopener">MAME</a> and the manual archive<br>
  All manuals remain the property of their original copyright holders &middot; Hosted for preservation and repair reference purposes<br>
  Found an error? Have manuals to contribute? <a href="mailto:info@arcadertfm.com">info@arcadertfm.com</a>
</footer>
</div>
</body>
</html>
`;

// 2. One page per machine.
const urls = [{ loc: '/', pri: '1.0', freq: 'weekly' }, { loc: '/machines', pri: '0.6', freq: 'weekly' }, { loc: '/dip-info', pri: '0.4', freq: 'yearly' }];
for (const item of machines) {
  const meta = metaLine(item);
  const who = [mfr(item), item.y].filter(Boolean).join(', ');
  const akaT = item.aka && item.aka.length ? ' aka ' + item.aka[0] : '';
  const title = `${item.name}${akaT}${who ? ' (' + who + ')' : ''} - Specs, DIP Switches & Manuals | ArcadeRTFM`;
  const path = `/m/${item.id}`;
  const jsonld = {
    '@context': 'https://schema.org', '@type': 'WebPage', name: item.name, url: SITE + path, description: description(item),
    isPartOf: { '@type': 'WebSite', name: 'ArcadeRTFM', url: SITE + '/' },
    about: { '@type': 'Thing', name: item.name, ...(item.aka && item.aka.length ? { alternateName: item.aka } : {}), ...(mfr(item) ? { manufacturer: { '@type': 'Organization', name: mfr(item) } } : {}) },
    breadcrumb: { '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'ArcadeRTFM', item: SITE + '/' },
      { '@type': 'ListItem', position: 2, name: 'All machines', item: SITE + '/machines' },
      { '@type': 'ListItem', position: 3, name: item.name, item: SITE + path } ] }
  };
  const html = head(title, description(item), path).replace('</head>', `<script type="application/ld+json">${JSON.stringify(jsonld).replace(/</g, '\\u003c')}</script>\n</head>`) + `
<main class="machine-page">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">ArcadeRTFM</a> &rsaquo; <a href="/machines">All machines</a> &rsaquo; <span>${esc(item.name)}</span></nav>
  <h1>${esc(item.name)}</h1>
  ${meta.length ? '<p class="machine-meta">' + meta.map(esc).join(' &middot; ') + ' &middot; <span class="rom-name">' + esc(item.id) + '</span></p>' : ''}
  ${item.aka && item.aka.length ? '<p class="machine-aka">Also known as: ' + item.aka.map(esc).join(', ') + '</p>' : ''}
  <p class="open-app"><a class="btn" href="/#${esc(item.id)}">&#9654; Open in the searchable database</a></p>
  ${renderBody(item)}
</main>` + footer;
  writeFileSync(join(OUT, 'm', item.id + '.html'), html);
  urls.push({ loc: path, pri: item.docs ? '0.8' : '0.5', freq: 'monthly' });
}

// 3. A-Z index page.
const groups = new Map();
for (const m of [...machines].sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }))) {
  const first = m.name.replace(/^['"‘’“”(]+/, '').charAt(0).toUpperCase();
  const key = /[A-Z]/.test(first) ? first : '#';
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(m);
}
const letters = [...groups.keys()];
let idx = head('All Arcade Machines A-Z | ArcadeRTFM', `Alphabetical index of ${machines.length.toLocaleString('en')} arcade machines with hardware specs, DIP switch settings and service manuals.`, '/machines') + `
<main class="index-page">
  <h1>All machines A&ndash;Z</h1>
  <p class="machine-meta">${machines.length.toLocaleString('en')} machines. For search by chip, manufacturer or year use the <a href="/">searchable database</a>.</p>
  <nav class="letters" aria-label="Jump to letter">${letters.map(l => `<a href="#${l === '#' ? 'other' : l}">${l}</a>`).join(' ')}</nav>
`;
for (const [l, list] of groups) {
  idx += `<section><h2 id="${l === '#' ? 'other' : l}">${l === '#' ? '0-9 &amp; other' : l}</h2><ul class="machine-list">`;
  for (const m of list) idx += `<li><a href="/m/${m.id}">${esc(m.name)}</a>${m.aka && m.aka.length ? ' <span class="aka">aka ' + esc(m.aka[0]) + '</span>' : ''}${mfr(m) || m.y ? ' <span class="label">' + esc([mfr(m), m.y].filter(Boolean).join(', ')) + '</span>' : ''}${m.docs ? ' <span class="badge-manual">' + m.docs.length + ' manual' + (m.docs.length > 1 ? 's' : '') + '</span>' : ''}</li>`;
  idx += '</ul></section>';
}
idx += '</main>' + footer;
writeFileSync(join(OUT, 'machines.html'), idx); // served by Pages at /machines

// 4. Shared stylesheet (same palette and rules as index.html).
writeFileSync(join(OUT, 'm.css'), `*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root { --phosphor: #44ff77; --phosphor-dim: #33bb66; --phosphor-bright: #77ffbb; --amber: #ffaa00; --screen-bg: #0a0e0a; --cabinet: #1a1a2e; --coin-slot: #ffcc00; --border-glow: rgba(51,255,102,0.15); --cyan: #44dddd; --pink: #ff6699; }
html { font-size: 16px; }
body { background: var(--cabinet); color: var(--phosphor); font-family: 'Share Tech Mono', monospace; min-height: 100vh; overflow-x: hidden; line-height: 1.5; }
.scanlines { position: fixed; inset: 0; pointer-events: none; z-index: 1000; background: repeating-linear-gradient(0deg, rgba(0,0,0,0.12) 0px, rgba(0,0,0,0.12) 1px, transparent 1px, transparent 3px); }
.screen-wrap { max-width: 1100px; margin: 0 auto; padding: 0 16px 20px; }
.header { text-align: center; padding: 16px 0 10px; }
.header .home { text-decoration: none; display: inline-block; }
.header .site { display: block; font-family: 'Press Start 2P', cursive; font-size: 0.9rem; color: var(--coin-slot); text-shadow: 0 0 20px rgba(255,204,0,0.5), 0 0 40px rgba(255,204,0,0.2); letter-spacing: 2px; line-height: 1.8; }
.header .subtitle { display: block; font-size: 0.8rem; color: var(--phosphor-dim); margin-top: 6px; letter-spacing: 1px; }
.crumbs { font-size: 0.74rem; color: #7a997a; margin: 18px 0 10px; }
.crumbs a { color: var(--phosphor-dim); text-decoration: none; }
.crumbs a:hover { color: var(--phosphor); }
h1 { font-size: 1.25rem; color: var(--phosphor-bright); font-weight: bold; margin: 6px 0 4px; }
.machine-meta { font-size: 0.82rem; color: #99bb99; margin-bottom: 10px; }
.machine-meta a { color: var(--cyan); }
.rom-name { color: #667766; }
.machine-aka, .aka { font-size: 0.8rem; color: #7a997a; font-style: italic; }
.machine-aka { margin: -6px 0 10px; }
.open-app { margin: 10px 0 16px; }
.btn { display: inline-block; padding: 8px 14px; background: rgba(68,255,119,0.1); border: 1px solid var(--phosphor-dim); color: var(--phosphor); text-decoration: none; font-size: 0.82rem; border-radius: 2px; }
.btn:hover { background: rgba(68,255,119,0.2); border-color: var(--phosphor); color: var(--phosphor-bright); box-shadow: 0 0 10px var(--border-glow); }
.spec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
.spec-section { padding: 8px 10px; background: rgba(10,14,10,0.5); border-left: 2px solid #2a3a2a; }
.spec-title { font-size: 0.72rem; color: var(--amber); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; font-weight: normal; }
.spec-row { font-size: 0.78rem; color: var(--phosphor); padding: 1px 0; }
.spec-row .label, .label { color: #8aaa8a; }
.spec-row .val { color: var(--phosphor-bright); }
.dip-section, .manual-links { grid-column: 1 / -1; }
.dip-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; margin-top: 4px; }
.dip-table th { text-align: left; padding: 4px 8px; color: var(--cyan); border-bottom: 1px solid #2a3a2a; font-weight: normal; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; }
.dip-table td { padding: 4px 8px; border-bottom: 1px solid #141e14; color: var(--phosphor); vertical-align: top; }
.dip-table td.dip-name { color: var(--phosphor-bright); white-space: nowrap; }
.dip-table td.dip-loc { color: var(--cyan); white-space: nowrap; font-size: 0.72rem; }
.dip-table td.dip-values { color: #99bb99; }
.dip-table td.dip-default { color: var(--amber); font-size: 0.74rem; }
.dip-table tr.dip-unknown td { opacity: 0.5; }
.dip-table tr.dip-unknown td.dip-name { font-style: italic; }
.dip-note { font-size: 0.7rem; color: #8a998a; font-style: italic; margin-bottom: 6px; }
.dip-note a { color: #8a998a; }
.dip-sw { font-size: 0.68rem; margin-right: 4px; }
.sw-on, .sw-off { display: inline-block; width: 32px; text-align: center; padding: 2px 0; border-radius: 2px; font-size: 0.65rem; margin-right: 2px; font-family: system-ui, -apple-system, sans-serif; letter-spacing: 0.5px; }
.sw-on { color: #000; background: var(--phosphor); font-weight: 700; }
.sw-off { color: #556655; background: rgba(255,255,255,0.08); }
.dip-sw-header { display: block; margin-bottom: 2px; }
.sw-label { display: inline-block; width: 32px; text-align: center; font-size: 0.56rem; color: var(--cyan); margin-right: 2px; }
.dip-opt { line-height: 1.8; display: block; }
.dip-opt-def { color: var(--phosphor-bright); }
.manual-link { display: inline-block; margin: 2px 6px 2px 0; padding: 3px 8px; background: rgba(255,170,0,0.08); border: 1px solid rgba(255,170,0,0.2); color: var(--amber); text-decoration: none; font-size: 0.74rem; border-radius: 1px; }
.manual-link:hover { background: rgba(255,170,0,0.2); border-color: var(--amber); }
.badge-manual { font-size: 0.66rem; padding: 1px 6px; background: rgba(255,170,0,0.15); color: var(--amber); border: 1px solid rgba(255,170,0,0.3); border-radius: 1px; white-space: nowrap; }
.index-page h1 { margin-top: 18px; }
.letters { margin: 10px 0 18px; font-size: 0.9rem; line-height: 2.2; }
.letters a { color: var(--cyan); text-decoration: none; padding: 2px 6px; border: 1px solid #2a3a2a; margin-right: 2px; }
.letters a:hover { border-color: var(--phosphor-dim); color: var(--phosphor); }
.index-page h2 { font-family: 'Press Start 2P', cursive; font-size: 0.85rem; color: var(--coin-slot); margin: 22px 0 8px; scroll-margin-top: 12px; }
.machine-list { list-style: none; columns: 2; column-gap: 24px; font-size: 0.8rem; }
.machine-list li { padding: 2px 0; break-inside: avoid; }
.machine-list a { color: var(--phosphor-bright); text-decoration: none; }
.machine-list a:hover { color: var(--phosphor); text-decoration: underline; }
.footer { text-align: center; padding: 40px 0 30px; font-size: 0.75rem; color: #7a997a; line-height: 1.8; }
.footer a { color: var(--phosphor-dim); text-decoration: none; }
.footer a:hover { color: var(--phosphor); }
@media (max-width: 640px) { .machine-list { columns: 1; } .dip-table td.dip-name { white-space: normal; } }
`);

// 5. Sitemap covering every page.
writeFileSync(join(OUT, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
  urls.map(u => `  <url><loc>${SITE}${u.loc}</loc><lastmod>${lastmod}</lastmod><changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`).join('\n') + '\n</urlset>\n');

console.log(`Built ${machines.length} machine pages (+ index, sitemap) into ${OUT}/. ${DATA.length - machines.length} records without a MAME id were skipped.`);
