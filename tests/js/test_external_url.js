/* آزمون URLهای خارجی: schemeهای خطرناک، URL نسبی و user-info باید رد شوند. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const uiPath = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'ui.js');
const ctx = { console, URL };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(uiPath, 'utf8'), ctx, { filename: 'ui.js' });

const safe = ctx.ODIN.safeExternalUrl;
assert.strictEqual(typeof safe, 'function', 'safeExternalUrl is exported');
assert.strictEqual(safe('https://example.com/path?q=1'), 'https://example.com/path?q=1');
assert.strictEqual(safe('http://example.com'), 'http://example.com/');
assert.strictEqual(safe(' javascript:alert(1) '), '');
assert.strictEqual(safe('file:///etc/passwd'), '');
assert.strictEqual(safe('intent://scan/#Intent;scheme=zxing;end'), '');
assert.strictEqual(safe('data:text/html,<script>alert(1)</script>'), '');
assert.strictEqual(safe('//example.com/path'), '', 'relative/protocol-relative URL rejected');
assert.strictEqual(safe('/relative/path'), '', 'relative URL rejected');
assert.strictEqual(safe('https://user:pass@example.com/'), '', 'credentials/user-info rejected');
assert.strictEqual(safe('https://@example.com/'), '', 'empty user-info syntax rejected');
assert.strictEqual(safe('not a URL'), '');
assert.strictEqual(safe(null), '');
console.log('safeExternalUrl tests passed (12 assertions).');
