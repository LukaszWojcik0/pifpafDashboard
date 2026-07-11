import assert from 'node:assert/strict';
import test from 'node:test';
import {
  HTML_PREVIEW_IFRAME_SANDBOX,
  buildPreviewSrcDoc,
  sanitizePreviewHtml,
} from '../components/htmlPreviewSecurity.mjs';

const payloads = [
  ['onerror', '<img src=x onerror="alert(1)">', /onerror/i],
  ['onclick', '<a href="https://example.com" onclick="alert(1)">link</a>', /onclick/i],
  ['SVG with onload', '<svg onload="alert(1)"><circle /></svg>', /<svg|onload/i],
  ['script', '<script>alert(1)</script><p>safe</p>', /<script|alert\(1\)/i],
  ['iframe', '<iframe src="https://example.com"></iframe><p>safe</p>', /<iframe/i],
  ['javascript URL', '<a href="javascript:alert(1)">bad</a>', /javascript:/i],
];

for (const [name, payload, forbiddenPattern] of payloads) {
  test(`sanitizes ${name} payload`, () => {
    const output = sanitizePreviewHtml(payload);
    assert.doesNotMatch(output, forbiddenPattern);
  });
}

test('wraps preview in a CSP-protected iframe document', () => {
  const doc = buildPreviewSrcDoc('<p>Hello</p>');
  assert.match(doc, /Content-Security-Policy/);
  assert.match(doc, /script-src 'none'/);
  assert.match(doc, /<p>Hello<\/p>/);
  assert.equal(HTML_PREVIEW_IFRAME_SANDBOX, '');
});
