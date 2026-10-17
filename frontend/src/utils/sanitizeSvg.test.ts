import { describe, expect, it } from 'vitest';
import { sanitizeSvg } from './sanitizeSvg';

describe('sanitizeSvg', () => {
  it('removes <script> and event handlers from SVG', () => {
    const dirty = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40" onload="alert(1)">',
      '<script>alert("xss")</script>',
      '<text x="5" y="20" onclick="alert(2)">变量A</text>',
      '</svg>',
    ].join('');

    const clean = sanitizeSvg(dirty);

    expect(clean).not.toContain('<script');
    expect(clean.toLowerCase()).not.toContain('onload');
    expect(clean.toLowerCase()).not.toContain('onclick');
    expect(clean).not.toContain('alert(');
    expect(clean).toContain('变量A');
  });

  it('keeps normal SVG chart markup', () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="10" height="10" fill="#3498db"/><text>OK</text></svg>';

    const clean = sanitizeSvg(svg);

    expect(clean).toContain('<rect');
    expect(clean).toContain('<text');
    expect(clean).toContain('OK');
  });
});
