import DOMPurify from 'dompurify';

/**
 * 清洗后端返回的 SVG，再交给 dangerouslySetInnerHTML。
 *
 * 后端图表文本里可能包含用户上传的变量名，必须按 SVG profile 过滤
 * <script>、事件处理器（onload 等）和 javascript: URL。
 */
export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
  });
}
