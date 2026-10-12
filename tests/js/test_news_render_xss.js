/* رگرسیون XSS برای رندر اخبار: فیلدهای فید نباید ساختار HTML تزریق کنند. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const uiPath = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'ui.js');
const O = {
  ico: () => '<svg></svg>',
  icoStr: (s) => s,
  faNum: (n) => String(n),
  countdown2: () => 'تازه',
  newsDirectionFa: () => '',
  CONFIG: {}
};
const ctx = { console, URL, Date, ODIN: O };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(uiPath, 'utf8'), ctx, { filename: 'ui.js' });

const hostileTitle = '"><img src=x onerror=alert(1)>';
const hostileLink = 'javascript:alert(1)" onmouseover="alert(2)';
const hostileSource = '<svg onload=alert(3)>';
const html = O.renderNews({
  state: {
    newsSnap: {
      ok: true, items: [{
        title: hostileTitle, link: hostileLink, source: hostileSource,
        score: 4, published: null, breaking: false, roundup: false,
        keywords: ['<script>alert(4)</script>'], direction: {}
      }],
      feedsOk: 1, feedsFailed: 0, staleFeeds: []
    }
  }
});

assert(html.includes('&lt;img src=x onerror=alert(1)&gt;'), 'headline HTML is escaped');
assert(!html.includes('<img src=x onerror=alert(1)>'), 'headline cannot inject img element');
assert(!html.includes(' onmouseover="alert(2)"'), 'link cannot inject a new event attribute');
assert(html.includes('javascript:alert(1)&quot; onmouseover=&quot;alert(2)'), 'hostile URL stays attribute-escaped');
assert(html.includes('&lt;svg onload=alert(3)&gt;'), 'source HTML is escaped');
assert(html.includes('&lt;script&gt;alert(4)&lt;/script&gt;'), 'keyword HTML is escaped');
console.log('news render XSS regression tests passed (6 assertions).');
