/* smoke_ui_polish.js — قراردادهای پایهٔ پولیش UI اندروید */
'use strict';

const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..', '..');
const css = fs.readFileSync(path.join(root, 'android/app/src/main/assets/www/style.css'), 'utf8');

const checks = [
  ['دکمه‌ها ارتفاع لمسی مناسب دارند', /\.btn\s*\{[^}]*min-height:\s*44px/s.test(css)],
  ['ردیف عملیات در عرض کم بازچینی می‌شود', /\.action-row\s*\{[^}]*flex-wrap:\s*wrap/s.test(css)],
  ['نمایشگر باریک چیدمان دکمه‌ها را ستونی می‌کند', /@media\s*\(max-width:\s*360px\)[\s\S]*?\.action-row\s*\{\s*flex-direction:\s*column/s.test(css)],
  ['کلیدهای چندحالته هدف لمسی دارند', /\.segmented button\s*\{[^}]*min-width:\s*44px/s.test(css)],
  ['تب‌های پایین ارتفاع قابل لمس دارند', /\.tab\s*\{[^}]*min-height:\s*44px/s.test(css)],
  ['فوکوس صفحه‌کلید قابل مشاهده است', /button:focus-visible[\s\S]*?outline:\s*2px solid var\(--brand\)/s.test(css)],
  ['وضعیت غیرفعال دکمه‌ها مشخص است', /button:disabled[\s\S]*?cursor:\s*not-allowed/s.test(css)],
  ['کاهش حرکت سیستم رعایت می‌شود', /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?transition-duration:\s*\.01ms/s.test(css)],
  ['توکن‌های تم در بلوک root حفظ شده‌اند', /--radius-card:\s*22px/.test(css) && /--brand:\s*#5B4BE8/i.test(css)]
];

let failures = 0;
for (const [label, pass] of checks) {
  console.log((pass ? '✓ ' : '✗ ') + label);
  if (!pass) failures++;
}
console.log('\nUI polish smoke: ' + (checks.length - failures) + '/' + checks.length + ' checks passed');
if (failures) process.exit(1);
