# -*- coding: utf-8 -*-
"""报告服务 v2：模板式 Word 报告 + 网页预览 HTML。

结构对齐"临床模型工作流模板"（桌面\临床模型工作流模板\src\make_report.py）：
封面元信息 → 数据说明 → 方法与评价协议（固定方法学段落）→ 编号章节（01、02…）→ 结论与局限性。
图表：SVG 经 cairosvg 转 PNG 嵌入 Word；预览 HTML 中 SVG 原样内联、PNG 走 data URI。
"""
import base64
import html
import io
import os
import re
import secrets
from datetime import datetime

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.settings import DATA_DIR

# 报告文件名：report_<yyyymmddHHMMSS>_<token_urlsafe(12) 的 16 字符>.<docx|pdf>
REPORT_FILENAME_RE = re.compile(r"^report_[0-9]{14}_[A-Za-z0-9_-]{16}\.(docx|pdf)$")


def get_user_reports_dir(user_id: str) -> str:
    return os.path.join(DATA_DIR, "users", user_id, "reports")


def _new_report_path(user_id: str, ext: str) -> str:
    reports_dir = get_user_reports_dir(user_id)
    os.makedirs(reports_dir, exist_ok=True)
    filename = (
        f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        f"_{secrets.token_urlsafe(12)}.{ext}"
    )
    return os.path.join(reports_dir, filename)


METHOD_TEXT = (
    "本分析遵循临床预测模型标准工作流："
    "（1）预处理（中位数填补、哑变量展开、标准化）封装在 Pipeline 内，仅在训练折上拟合，杜绝信息泄漏；"
    "（2）模型比较采用重复分层 K 折交叉验证，若指定分组变量（如患者 ID）则采用分组交叉验证，"
    "同一分组不会同时出现在训练与验证两侧，以 OOF（out-of-fold）概率汇总评估；"
    "（3）内部验证采用乐观度校正 Bootstrap：每次重抽样后重新训练模型，报告表观、校正与 OOB 性能；"
    "（4）四维评估——区分度（AUC、PR-AUC、灵敏度、特异度、F1）、校准度（Brier 分数、校准曲线、"
    "Hosmer-Lemeshow 检验）、临床效用（决策曲线 DCA 净获益）、稳定性（训练-外检乐观度）；"
    "（5）组成型数据（峰占比等）经 ALR/CLR 对数比变换后建模。"
)

LIMITATIONS_TEXT = (
    "局限性：本报告基于单中心、有限样本数据，模型性能为内部验证结果，"
    "建议获得独立外部数据验证后再用于临床决策。"
)

# E7a 过渡措施（不需方案确认）：方法学说明章节固定警示语
E7A_WARNING_TEXT = (
    "变量筛选在全部数据上完成，内部验证结果偏乐观；"
    "内部验证不等于外部验证，结果不能直接用于临床决策。"
)


def _chart_png_bytes(chart: dict):
    """图表 dict → PNG 字节（Word 用）；失败返回 None。"""
    img_data = chart.get("data", "")
    if not img_data:
        return None
    try:
        if chart.get("type", "svg") == "svg":
            import cairosvg
            return cairosvg.svg2png(bytestring=img_data.encode("utf-8"))
        return base64.b64decode(img_data)
    except Exception:
        return None


def _chart_html(chart: dict) -> str:
    """图表 dict → <img> HTML（网页预览用）。"""
    img_data = chart.get("data", "")
    if not img_data:
        return ""
    title = html.escape(chart.get("title", "图表"))
    if chart.get("type", "svg") == "svg":
        b64 = base64.b64encode(img_data.encode("utf-8")).decode("ascii")
        return (f'<figure><img alt="{title}" style="max-width:100%" '
                f'src="data:image/svg+xml;base64,{b64}"/></figure>')
    return (f'<figure><img alt="{title}" style="max-width:100%" '
            f'src="data:image/png;base64,{img_data}"/></figure>')


def _numbered_sections(report_data: dict):
    """用户勾选的章节按顺序编号：01 xxx、02 xxx …"""
    sections = report_data.get("sections", [])
    return [(f"{i + 1:02d} {sec.get('title', '分析结果')}", sec) for i, sec in enumerate(sections)]


def _meta_lines(report_data: dict):
    lines = [f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    if report_data.get("dataset_name"):
        lines.append(f"数据集: {report_data['dataset_name']}")
    if report_data.get("y_variable"):
        lines.append(f"结局变量: {report_data['y_variable']}")
    if report_data.get("group_variable"):
        lines.append(f"分组变量: {report_data['group_variable']}（交叉验证按组划分，同一组不跨训练/验证）")
    if report_data.get("model_type"):
        lines.append(f"最佳模型: {report_data['model_type']}")
    return lines


def generate_word_report(report_data: dict, user_id: str) -> str:
    doc = Document()

    title = doc.add_heading("临床预测模型分析报告", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.runs[0]
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(0x2F, 0x85, 0x5A)

    for line in _meta_lines(report_data):
        doc.add_paragraph(line)
    doc.add_paragraph()

    doc.add_heading("方法与评价协议", level=1)
    doc.add_paragraph(METHOD_TEXT)
    warn_para = doc.add_paragraph()
    warn_run = warn_para.add_run(f"注意：{E7A_WARNING_TEXT}")
    warn_run.bold = True

    for num_title, sec in _numbered_sections(report_data):
        doc.add_heading(num_title, level=1)
        if sec.get("summary"):
            p = doc.add_paragraph()
            p.add_run("摘要: ").bold = True
            p.add_run(str(sec["summary"]))

        for tbl in sec.get("tables", []):
            doc.add_heading(tbl.get("title", "表格"), level=2)
            table = doc.add_table(rows=1, cols=len(tbl["headers"]))
            table.style = "Light Grid Accent 1"
            hdr_cells = table.rows[0].cells
            for i, h in enumerate(tbl["headers"]):
                hdr_cells[i].text = str(h)
                if hdr_cells[i].paragraphs[0].runs:
                    hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            for row in tbl.get("rows", []):
                row_cells = table.add_row().cells
                for i, cell in enumerate(row):
                    row_cells[i].text = "" if cell is None else str(cell)
            doc.add_paragraph()

        for chart in sec.get("charts", []):
            doc.add_heading(chart.get("title", "图表"), level=2)
            png = _chart_png_bytes(chart)
            if png:
                try:
                    doc.add_picture(io.BytesIO(png), width=Inches(5.5))
                except Exception:
                    doc.add_paragraph("[图表嵌入失败]")
            else:
                doc.add_paragraph("[图表请在网页预览中查看]")
            doc.add_paragraph()

    doc.add_heading("结论与局限性", level=1)
    conclusion = report_data.get("conclusion")
    if conclusion:
        doc.add_paragraph(conclusion)
    elif report_data.get("model_type"):
        doc.add_paragraph(f"综合各评估维度，{report_data['model_type']} 为当前最优模型。")
    doc.add_paragraph(LIMITATIONS_TEXT)

    output_path = _new_report_path(user_id, "docx")
    doc.save(output_path)
    return output_path


def generate_preview_html(report_data: dict) -> str:
    """与 Word 报告同结构的 HTML，供前端 iframe 预览。"""
    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"/>',
        '<style>body{font-family:"Microsoft YaHei",sans-serif;max-width:900px;margin:24px auto;'
        'color:#171717;line-height:1.7}h1{color:#171717;border-bottom:2px solid #dfdfdf;padding-bottom:4px}'
        'h2{color:#171717;margin-top:28px}h3{color:#171717;margin-bottom:6px}'
        'table{border-collapse:collapse;width:100%;margin:8px 0 16px;font-size:13px}'
        'th,td{border:1px solid #dfdfdf;padding:5px 8px;text-align:center}'
        'th{background:#171717;color:#ffffff}tr:nth-child(even){background:#fafafa}'
        '.meta{color:#707070}figure{margin:8px 0 20px}</style></head><body>',
        "<h1>临床预测模型分析报告</h1>",
    ]
    for line in _meta_lines(report_data):
        parts.append(f'<p class="meta">{html.escape(line)}</p>')

    parts.append("<h2>方法与评价协议</h2>")
    parts.append(f"<p>{html.escape(METHOD_TEXT)}</p>")
    parts.append(f"<p><b>注意：</b>{html.escape(E7A_WARNING_TEXT)}</p>")

    for num_title, sec in _numbered_sections(report_data):
        parts.append(f"<h2>{html.escape(num_title)}</h2>")
        if sec.get("summary"):
            parts.append(f"<p><b>摘要:</b> {html.escape(str(sec['summary']))}</p>")
        for tbl in sec.get("tables", []):
            parts.append(f"<h3>{html.escape(str(tbl.get('title', '表格')))}</h3>")
            parts.append("<table><thead><tr>")
            for h in tbl.get("headers", []):
                parts.append(f"<th>{html.escape(str(h))}</th>")
            parts.append("</tr></thead><tbody>")
            for row in tbl.get("rows", []):
                parts.append("<tr>" + "".join(
                    f"<td>{html.escape('' if c is None else str(c))}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
        for chart in sec.get("charts", []):
            parts.append(f"<h3>{html.escape(str(chart.get('title', '图表')))}</h3>")
            parts.append(_chart_html(chart))

    parts.append("<h2>结论与局限性</h2>")
    conclusion = report_data.get("conclusion")
    if conclusion:
        parts.append(f"<p>{html.escape(str(conclusion))}</p>")
    elif report_data.get("model_type"):
        parts.append(f"<p>综合各评估维度，{html.escape(str(report_data['model_type']))} 为当前最优模型。</p>")
    parts.append(f"<p>{html.escape(LIMITATIONS_TEXT)}</p>")
    parts.append("</body></html>")
    return "".join(parts)


def generate_pdf_report(report_data: dict, user_id: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "Helvetica"
    for cand in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
                 "C:/Windows/Fonts/simsun.ttc"):
        try:
            pdfmetrics.registerFont(TTFont("CJK", cand))
            font_name = "CJK"
            break
        except Exception:
            continue

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Heading1"], fontName=font_name,
        fontSize=20, textColor="#171717", alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"], fontName=font_name,
        fontSize=14, spaceAfter=10, spaceBefore=12)
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["BodyText"], fontName=font_name,
        fontSize=10, alignment=TA_LEFT, spaceAfter=8)

    output_path = _new_report_path(user_id, "pdf")
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = [Paragraph("临床预测模型分析报告", title_style), Spacer(1, 0.3*cm)]
    for line in _meta_lines(report_data):
        story.append(Paragraph(line, body_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("方法与评价协议", heading_style))
    story.append(Paragraph(METHOD_TEXT, body_style))
    story.append(Paragraph(f"<b>注意：</b>{E7A_WARNING_TEXT}", body_style))

    for num_title, sec in _numbered_sections(report_data):
        story.append(Paragraph(num_title, heading_style))
        if sec.get("summary"):
            story.append(Paragraph(f"<b>摘要:</b> {sec['summary']}", body_style))

        for tbl in sec.get("tables", []):
            story.append(Paragraph(tbl.get("title", "表格"), styles["Heading3"]))
            headers = [str(h) for h in tbl.get("headers", [])]
            rows = [["" if c is None else str(c) for c in row] for row in tbl.get("rows", [])]
            t = RLTable([headers] + rows, colWidths=[None]*len(headers))
            t.setStyle([
                ("BACKGROUND", (0, 0), (-1, 0), "#171717"),
                ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), "#fafafa"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#dfdfdf"),
            ])
            story.append(t)
            story.append(Spacer(1, 0.3*cm))

        for chart in sec.get("charts", []):
            story.append(Paragraph(chart.get("title", "图表"), styles["Heading3"]))
            png = _chart_png_bytes(chart)
            if png:
                try:
                    story.append(RLImage(io.BytesIO(png), width=14*cm, height=10*cm))
                except Exception:
                    story.append(Paragraph("[图表嵌入失败]", body_style))
            else:
                story.append(Paragraph("[图表请在网页预览中查看]", body_style))
            story.append(Spacer(1, 0.3*cm))
        story.append(PageBreak())

    story.append(Paragraph("结论与局限性", heading_style))
    conclusion = report_data.get("conclusion")
    if conclusion:
        story.append(Paragraph(str(conclusion), body_style))
    elif report_data.get("model_type"):
        story.append(Paragraph(f"综合各评估维度，{report_data['model_type']} 为当前最优模型。", body_style))
    story.append(Paragraph(LIMITATIONS_TEXT, body_style))

    doc.build(story)
    return output_path
