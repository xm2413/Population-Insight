from __future__ import annotations

from dataclasses import dataclass

from .config import METRIC_LABELS
from .database import query_all, query_one
from .record_service import get_regions


def latest_records() -> list:
    row = query_one("SELECT MAX(year) AS year FROM population_records")
    if not row or row["year"] is None:
        return []
    return query_all(
        "SELECT * FROM population_records WHERE year = ? ORDER BY total_population DESC",
        (row["year"],),
    )


def overall_trend() -> list[dict]:
    rows = query_all("SELECT year, total_population FROM population_records ORDER BY year")
    totals: dict[int, int] = {}
    for row in rows:
        totals[row["year"]] = totals.get(row["year"], 0) + row["total_population"]
    return [{"label": str(year), "value": value} for year, value in sorted(totals.items())]


def dashboard_summary() -> dict:
    latest = latest_records()
    total_population = sum(row["total_population"] for row in latest)
    avg_growth = sum(row["natural_growth_rate"] for row in latest) / len(latest) if latest else 0
    avg_aging = sum(row["aging_rate"] for row in latest) / len(latest) if latest else 0
    return {
        "latest_year": latest[0]["year"] if latest else None,
        "region_count": len(latest),
        "record_count": query_one("SELECT COUNT(*) AS total FROM population_records")["total"],
        "total_population": total_population,
        "avg_growth": round(avg_growth, 2),
        "avg_aging": round(avg_aging, 2),
        "high_risk_count": len(get_alerts()),
        "latest": latest,
        "trend_points": overall_trend(),
    }


def build_line_points(points: list[dict], width: int = 720, height: int = 240) -> dict:
    if not points:
        return {"polyline": "", "labels": [], "min": 0, "max": 0}
    values = [float(item["value"]) for item in points]
    min_value = min(values)
    max_value = max(values)
    spread = max(max_value - min_value, 1)
    x_padding = 34
    plot_width = width - x_padding * 2
    step = plot_width / max(len(points) - 1, 1)
    coords = []
    labels = []
    for index, item in enumerate(points):
        x = round(x_padding + index * step, 2)
        y = round(height - ((float(item["value"]) - min_value) / spread * (height - 32)) - 16, 2)
        coords.append(f"{x},{y}")
        labels.append({"x": x, "label": item["label"]})
    return {"polyline": " ".join(coords), "labels": labels, "min": round(min_value, 2), "max": round(max_value, 2)}


def build_bars(rows: list, metric: str = "total_population", label_field: str = "region") -> list[dict]:
    if not rows:
        return []
    max_value = max(float(row[metric]) for row in rows) or 1
    return [
        {"label": row[label_field], "value": row[metric], "width": round(float(row[metric]) / max_value * 100, 1)}
        for row in rows
    ]


def region_statistics() -> list[dict]:
    rows = query_all("SELECT * FROM population_records ORDER BY region, year")
    result = []
    for region in get_regions():
        history = [row for row in rows if row["region"] == region]
        if not history:
            continue
        first, last = history[0], history[-1]
        change = last["total_population"] - first["total_population"]
        percent = change / first["total_population"] * 100 if first["total_population"] else 0
        result.append(
            {
                "region": region,
                "first_year": first["year"],
                "last_year": last["year"],
                "change": change,
                "percent": round(percent, 2),
                "aging_rate": last["aging_rate"],
                "urbanization_rate": last["urbanization_rate"],
            }
        )
    return result


@dataclass
class ForecastResult:
    region: str
    metric: str
    metric_label: str
    history: list[dict]
    future: list[dict]
    slope: float
    intercept: float


def linear_forecast(region: str, metric: str, years_ahead: int) -> ForecastResult | None:
    rows = query_all(
        f"SELECT year, {metric} AS value FROM population_records WHERE region = ? ORDER BY year",
        (region,),
    )
    if len(rows) < 2:
        return None
    xs = [row["year"] for row in rows]
    ys = [float(row["value"]) for row in rows]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    future = []
    for year in range(max(xs) + 1, max(xs) + years_ahead + 1):
        future.append({"label": str(year), "value": round(max(0, slope * year + intercept), 2)})
    history = [{"label": str(row["year"]), "value": row["value"]} for row in rows]
    return ForecastResult(region, metric, METRIC_LABELS[metric], history, future, slope, intercept)


def get_alerts() -> list[dict]:
    alerts = []
    for row in latest_records():
        reasons = []
        level = "关注"
        if row["aging_rate"] >= 20:
            reasons.append(f"老龄化率 {row['aging_rate']}% 已达到深度老龄化关注线")
            level = "较高"
        if row["natural_growth_rate"] < 0:
            reasons.append(f"自然增长率 {row['natural_growth_rate']}% 为负")
            level = "较高"
        if row["birth_rate"] < 7:
            reasons.append(f"出生率 {row['birth_rate']}% 偏低")
        if reasons:
            alerts.append(
                {
                    "region": row["region"],
                    "year": row["year"],
                    "level": level,
                    "reasons": reasons,
                    "suggestion": "建议结合产业、教育、养老和公共服务承载能力进行专题分析。",
                }
            )
    return alerts


def get_global_countries() -> list[str]:
    rows = query_all("SELECT DISTINCT country FROM global_population_records ORDER BY country")
    return [row["country"] for row in rows]


def get_global_continents() -> list[str]:
    rows = query_all("SELECT DISTINCT continent FROM global_population_records ORDER BY continent")
    return [row["continent"] for row in rows]


def latest_global_records(continent: str = "") -> list:
    row = query_one("SELECT MAX(year) AS year FROM global_population_records")
    if not row or row["year"] is None:
        return []
    params: list[object] = [row["year"]]
    condition = "WHERE year = ?"
    if continent:
        condition += " AND continent = ?"
        params.append(continent)
    return query_all(
        f"SELECT * FROM global_population_records {condition} ORDER BY total_population DESC",
        params,
    )


def global_population_trend(continent: str = "") -> list[dict]:
    params: list[object] = []
    condition = ""
    if continent:
        condition = "WHERE continent = ?"
        params.append(continent)
    rows = query_all(
        f"SELECT year, SUM(total_population) AS total FROM global_population_records {condition} GROUP BY year ORDER BY year",
        params,
    )
    return [{"label": str(row["year"]), "value": row["total"]} for row in rows]


def global_continent_summary() -> list[dict]:
    row = query_one("SELECT MAX(year) AS year FROM global_population_records")
    if not row or row["year"] is None:
        return []
    rows = query_all(
        """
        SELECT
            continent,
            COUNT(*) AS country_count,
            SUM(total_population) AS total_population,
            AVG(natural_growth_rate) AS avg_growth,
            AVG(aging_rate) AS avg_aging,
            AVG(urbanization_rate) AS avg_urbanization
        FROM global_population_records
        WHERE year = ?
        GROUP BY continent
        ORDER BY total_population DESC
        """,
        (row["year"],),
    )
    return [
        {
            "continent": item["continent"],
            "country_count": item["country_count"],
            "total_population": item["total_population"],
            "avg_growth": round(item["avg_growth"], 2),
            "avg_aging": round(item["avg_aging"], 2),
            "avg_urbanization": round(item["avg_urbanization"], 2),
        }
        for item in rows
    ]


def global_population_summary(continent: str = "") -> dict:
    latest = latest_global_records(continent)
    trend = global_population_trend(continent)
    total_population = sum(row["total_population"] for row in latest)
    avg_growth = sum(row["natural_growth_rate"] for row in latest) / len(latest) if latest else 0
    avg_aging = sum(row["aging_rate"] for row in latest) / len(latest) if latest else 0
    return {
        "latest_year": latest[0]["year"] if latest else None,
        "country_count": len(latest),
        "total_population": total_population,
        "avg_growth": round(avg_growth, 2),
        "avg_aging": round(avg_aging, 2),
        "top_country": latest[0]["country"] if latest else "-",
        "latest": latest,
        "trend_points": trend,
        "continent_summary": global_continent_summary(),
    }
