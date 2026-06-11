from __future__ import annotations

from .config import CHART_DIR
from .database import query_all
from .analysis_service import global_population_trend, latest_records, overall_trend


def _prepare_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def generate_charts() -> dict[str, str]:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    trend_path = CHART_DIR / "overall_trend.png"
    ranking_path = CHART_DIR / "population_ranking.png"
    gender_path = CHART_DIR / "gender_pie.png"
    global_path = CHART_DIR / "global_population_trend.png"

    plt = _prepare_matplotlib()
    trend = overall_trend()
    plt.figure(figsize=(8, 3.6), dpi=150)
    plt.plot([item["label"] for item in trend], [item["value"] for item in trend], marker="o", color="#2563eb", linewidth=2.5)
    plt.title("总体人口变化趋势")
    plt.xlabel("年份")
    plt.ylabel("人口总量（万人）")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(trend_path)
    plt.close()

    latest = latest_records()
    plt.figure(figsize=(8, 3.8), dpi=150)
    plt.bar([row["region"] for row in latest], [row["total_population"] for row in latest], color="#14b8a6")
    plt.title("最新年份地区人口排名")
    plt.xlabel("地区")
    plt.ylabel("总人口（万人）")
    plt.tight_layout()
    plt.savefig(ranking_path)
    plt.close()

    rows = query_all("SELECT SUM(male_population) AS male, SUM(female_population) AS female FROM population_records WHERE year = (SELECT MAX(year) FROM population_records)")
    male = rows[0]["male"] or 0
    female = rows[0]["female"] or 0
    plt.figure(figsize=(4.4, 4.4), dpi=150)
    plt.pie([male, female], labels=["男性", "女性"], autopct="%1.1f%%", colors=["#2563eb", "#f97316"], startangle=90)
    plt.title("最新年份性别结构")
    plt.tight_layout()
    plt.savefig(gender_path)
    plt.close()

    global_trend = global_population_trend()
    plt.figure(figsize=(8, 3.6), dpi=150)
    plt.plot(
        [item["label"] for item in global_trend],
        [item["value"] for item in global_trend],
        marker="o",
        color="#7c3aed",
        linewidth=2.5,
    )
    plt.title("全球国家人口变化趋势")
    plt.xlabel("年份")
    plt.ylabel("总人口（万人）")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(global_path)
    plt.close()

    return {
        "trend": "charts/overall_trend.png",
        "ranking": "charts/population_ranking.png",
        "gender": "charts/gender_pie.png",
        "global": "charts/global_population_trend.png",
    }
