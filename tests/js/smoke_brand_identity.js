'use strict';
// هویت بصری ۱.۳: نشانِ «پالسِ منفی» — یک منبع هندسه، همهٔ سطوح.
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const root = path.resolve(__dirname, '..', '..');
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8');

const source = read('assets/brand_mark.py');
const getConst = (name) => {
  const m = source.match(new RegExp(name + '\\s*=\\s*"([^"]+)"'));
  assert(m, 'const ' + name + ' must exist in assets/brand_mark.py');
  return m[1];
};
const SQUIRCLE = getConst('SQUIRCLE');
const HOLE = getConst('PULSE_HOLE');
const LINE = getConst('PULSE_LINE');

assert(SQUIRCLE.startsWith('M39.0 16.0H69.0A23 23'), 'squircle geometry changed unexpectedly');
assert(HOLE.length > 200 && HOLE.startsWith('M39.0 65.5') && /Z$/.test(HOLE), 'pulse hole must be a closed stroke outline');
assert(LINE.startsWith('M24.0 60.0 L39.0 60.0 L45.0 39.0 L54.0 75.0'), 'pulse line geometry changed');

const svg = read('docs/odin-launcher-icon.svg');
const launcher = read('android/app/src/main/res/drawable/odin_launcher_icon.xml');
const foreground = read('android/app/src/main/res/drawable/odin_launcher_foreground.xml');
const status = read('android/app/src/main/res/drawable/ic_stat_odin.xml');
const html = read('android/app/src/main/assets/www/index.html');
const about = read('android/app/src/main/assets/www/js/ui.js');
const pyIcons = read('src/ui/icons.py');
const pyTheme = read('src/ui/theme.py');
const css = read('android/app/src/main/assets/www/style.css');
const manifest = read('android/app/src/main/AndroidManifest.xml');
const adaptive = read('android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml');
const generator = read('assets/make_icon.py');
const brandDoc = read('docs/brand-identity.md');

// ── همهٔ سطوح باید همان مسیرهای منبع را داشته باشند
assert(svg.includes(SQUIRCLE) && svg.includes(HOLE), 'canonical SVG must use the source mark paths');
assert(svg.includes('fill-rule="evenodd"'), 'canonical SVG must cut the pulse with evenodd');
assert(launcher.includes(SQUIRCLE) && launcher.includes(HOLE), 'Android launcher must reuse the source paths');
assert(launcher.includes('android:fillType="evenOdd"'), 'launcher must cut the pulse with evenOdd');
assert(foreground.includes(SQUIRCLE) && foreground.includes(HOLE), 'adaptive foreground must reuse the mark');
assert(foreground.includes('android:scaleX="0.868"'), 'foreground must be scaled into the 66dp safe zone');
assert(status.includes(HOLE) && !status.includes(SQUIRCLE), 'status icon must be the mono pulse only');
assert(html.includes(HOLE) && html.includes('scale(0.4444)'), 'Android splash must draw the mark');
assert(about.includes(HOLE) && about.includes('scale(0.4444)'), 'About page must draw the mark');
assert(pyIcons.includes(HOLE) && pyIcons.includes('scale(0.2222)'), 'desktop logo icon must use the mono pulse');
assert(/"logo":\s*\('\<g transform="scale\(0\.2222\)"/.test(pyIcons), 'desktop logo icon must stay filled, not stroked');
assert(generator.includes('brand_mark') && generator.includes('mipmap-'), 'icon generator must build from brand_mark and refresh mipmaps');
assert(brandDoc.includes('پالسِ منفی') && brandDoc.includes('brand_mark.py'), 'brand doc must describe the new mark and its source');

// ── توکن‌های برند و parity تم دست‌نخورده
assert(pyTheme.includes('brand: str = "#101013"') && pyTheme.includes('brand_tint: str = "#EDEDF0"'), 'Python brand tokens must stay monochrome');
assert(css.includes('--brand: #101013;') && css.includes('--brand-tint: #EDEDF0;'), 'Android CSS brand tokens must match Python');
assert(manifest.includes('android:icon="@mipmap/ic_launcher"'), 'manifest must use the adaptive launcher resource');
assert(adaptive.includes('<adaptive-icon') && adaptive.includes('odin_launcher_foreground'), 'adaptive icon must use the marked foreground');

// ── نشان قدیمی (Ø) نباید در هیچ سطح برند باقی بماند
const legacy = ['a25,25', 'M25,83 L83,25', 'M25 83 83 25', 'M11 37 37 11', 'r="5.55"',
                'M24,13 a11,11', 'extent = ring_r + 152'];
for (const needle of legacy) {
  for (const [name, text] of [['svg', svg], ['launcher', launcher], ['status', status],
                              ['splash', html], ['about', about], ['icons', pyIcons]]) {
    assert(!text.includes(needle), 'legacy Ø artwork must be gone from ' + name + ' (' + needle + ')');
  }
}

// ── فایل‌های رستری
const png = fs.readFileSync(path.join(root, 'assets/icon.png'));
assert(png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'desktop PNG signature invalid');
assert(png.readUInt32BE(16) === 512 && png.readUInt32BE(20) === 512, 'desktop PNG must be 512x512');
const ico = fs.readFileSync(path.join(root, 'assets/icon.ico'));
assert(ico.readUInt16LE(0) === 0 && ico.readUInt16LE(2) === 1 && ico.readUInt16LE(4) >= 1, 'desktop ICO container invalid');
const mipmaps = { mdpi: 48, hdpi: 72, xhdpi: 96, xxhdpi: 144, xxxhdpi: 192 };
for (const [name, px] of Object.entries(mipmaps)) {
  const buf = fs.readFileSync(path.join(root, 'android/app/src/main/res/mipmap-' + name + '/ic_launcher.png'));
  assert(buf.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'mipmap ' + name + ' is not a PNG');
  assert(buf.readUInt32BE(16) === px && buf.readUInt32BE(20) === px, 'mipmap ' + name + ' must be ' + px + 'px');
}

console.log('SMOKE BRAND IDENTITY OK — پالسِ منفی: یک منبع هندسه، ۸ سطح برند، PNG/ICO/mipmapها');
