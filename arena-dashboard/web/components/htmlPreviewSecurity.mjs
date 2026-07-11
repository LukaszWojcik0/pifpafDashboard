const BLOCKED_TAGS = new Set([
  'base',
  'button',
  'embed',
  'form',
  'frame',
  'frameset',
  'iframe',
  'input',
  'link',
  'math',
  'meta',
  'object',
  'option',
  'script',
  'select',
  'style',
  'svg',
  'textarea',
]);

const ALLOWED_TAGS = new Set([
  'a',
  'article',
  'aside',
  'b',
  'blockquote',
  'br',
  'caption',
  'code',
  'div',
  'em',
  'figcaption',
  'figure',
  'footer',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'header',
  'hr',
  'i',
  'img',
  'li',
  'main',
  'ol',
  'p',
  'pre',
  'section',
  'small',
  'span',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'time',
  'tr',
  'u',
  'ul',
]);

const GLOBAL_ATTRS = new Set(['aria-label', 'class', 'id', 'title']);
export const HTML_PREVIEW_IFRAME_SANDBOX = '';

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function removeBlockedTagBlocks(html) {
  let output = String(html);
  for (const tag of BLOCKED_TAGS) {
    const block = new RegExp(`<\\s*${tag}\\b[^>]*>[\\s\\S]*?<\\s*\\/\\s*${tag}\\s*>`, 'gi');
    const standalone = new RegExp(`<\\s*\\/?\\s*${tag}\\b[^>]*>`, 'gi');
    output = output.replace(block, '').replace(standalone, '');
  }
  return output;
}

function isSafeUrl(value, allowImageData = false) {
  const normalized = String(value).replace(/[\u0000-\u001F\u007F\s]+/g, '').toLowerCase();
  if (!normalized) return false;
  if (normalized.startsWith('#') || normalized.startsWith('/') || normalized.startsWith('./') || normalized.startsWith('../')) {
    return true;
  }
  if (allowImageData && /^data:image\/(?:gif|png|jpeg|jpg|webp);base64,[a-z0-9+/]+=*$/i.test(normalized)) {
    return true;
  }
  try {
    const parsed = new URL(normalized, 'https://example.invalid');
    return ['http:', 'https:', 'mailto:', 'tel:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

function sanitizeAttributes(tagName, rawAttributes) {
  const attrs = [];
  const attrPattern = /([^\s=/"'<>`]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let match;

  while ((match = attrPattern.exec(rawAttributes)) !== null) {
    const name = match[1].toLowerCase();
    const value = match[2] ?? match[3] ?? match[4] ?? '';

    if (name.startsWith('on')) continue;
    if (name === 'srcdoc') continue;

    if (GLOBAL_ATTRS.has(name) || name.startsWith('data-')) {
      attrs.push(`${name}="${escapeHtml(value)}"`);
      continue;
    }

    if (tagName === 'a' && name === 'href' && isSafeUrl(value)) {
      attrs.push(`href="${escapeHtml(value)}"`);
      attrs.push('rel="noreferrer noopener"');
      attrs.push('target="_blank"');
      continue;
    }

    if (tagName === 'img' && name === 'src' && isSafeUrl(value, true)) {
      attrs.push(`src="${escapeHtml(value)}"`);
      continue;
    }

    if (tagName === 'img' && name === 'alt') {
      attrs.push(`alt="${escapeHtml(value)}"`);
    }
  }

  return attrs.length > 0 ? ` ${attrs.join(' ')}` : '';
}

export function sanitizePreviewHtml(html) {
  const withoutBlockedTags = removeBlockedTagBlocks(html);
  const tagPattern = /<\/?([a-zA-Z][a-zA-Z0-9:-]*)([^<>]*)>/g;
  let output = '';
  let lastIndex = 0;
  let match;

  while ((match = tagPattern.exec(withoutBlockedTags)) !== null) {
    output += escapeHtml(withoutBlockedTags.slice(lastIndex, match.index));

    const rawTag = match[0];
    const tagName = match[1].toLowerCase();
    const rawAttributes = match[2] ?? '';
    const isClosing = /^<\s*\//.test(rawTag);
    const isSelfClosing = /\/\s*>$/.test(rawTag) || ['br', 'hr', 'img'].includes(tagName);

    if (ALLOWED_TAGS.has(tagName)) {
      if (isClosing) {
        if (!['br', 'hr', 'img'].includes(tagName)) output += `</${tagName}>`;
      } else {
        output += `<${tagName}${sanitizeAttributes(tagName, rawAttributes)}${isSelfClosing ? ' />' : '>'}`;
      }
    }

    lastIndex = tagPattern.lastIndex;
  }

  output += escapeHtml(withoutBlockedTags.slice(lastIndex));
  return output;
}

export function buildPreviewSrcDoc(html) {
  const sanitizedHtml = sanitizePreviewHtml(html);
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src http: https: data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-src 'none'; object-src 'none'; script-src 'none'">
<style>
  html { color-scheme: light; }
  body { margin: 0; padding: 12px; font: 14px/1.5 system-ui, sans-serif; color: #111827; background: #ffffff; }
  img { max-width: 100%; height: auto; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #d1d5db; padding: 4px 6px; }
</style>
</head>
<body>${sanitizedHtml}</body>
</html>`;
}
