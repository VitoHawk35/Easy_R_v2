"""E6：matplotlib 统一风格加载与降级行为。"""
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.services.ml import utils


def test_plot_style_applied_on_import():
    """模块加载时应用 backend/app/assets/supabase-med.mplstyle。"""
    assert utils.PLOT_STYLE_PATH.exists()
    assert plt.rcParams["figure.dpi"] == 150.0
    assert plt.rcParams["savefig.dpi"] == 300.0
    assert plt.rcParams["axes.grid"] is True
    assert plt.rcParams["axes.grid.axis"] == "y"
    assert plt.rcParams["axes.spines.top"] is False
    assert plt.rcParams["axes.spines.right"] is False
    assert plt.rcParams["axes.unicode_minus"] is False


def test_plot_style_missing_degrades_to_default(tmp_path, caplog):
    """样式文件缺失：warning + 默认样式，不抛异常。"""
    missing = tmp_path / "not-there.mplstyle"

    with caplog.at_level(logging.WARNING, logger="app.services.ml.utils"):
        applied = utils.apply_plot_style(missing)

    assert applied is False
    assert any("回退默认样式" in record.getMessage() for record in caplog.records)
    assert plt.rcParams["figure.dpi"] == 100.0

    # 恢复统一主题，避免影响其他测试
    assert utils.apply_plot_style() is True
    assert plt.rcParams["figure.dpi"] == 150.0


def test_plot_style_invalid_degrades_to_default(tmp_path, caplog):
    """样式文件语法/取值错误：同样降级，不崩溃。"""
    bad = tmp_path / "bad.mplstyle"
    bad.write_text("axes.edgecolor: definitely-not-a-color\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="app.services.ml.utils"):
        applied = utils.apply_plot_style(bad)

    assert applied is False
    assert any("回退默认样式" in record.getMessage() for record in caplog.records)
    assert utils.apply_plot_style() is True


def test_plot_with_theme_renders_cjk_title():
    """统一风格下渲染中文标题并输出 SVG 不抛异常。"""
    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot([0, 1], [0, 1])
    ax.set_title("测试标题")
    ax.set_xlabel("阈值")
    ax.set_ylabel("净获益")
    svg = utils.fig_to_svg(fig)
    assert "<svg" in svg
