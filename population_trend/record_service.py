from __future__ import annotations

import csv
import io
import sqlite3

from flask import request

from .database import execute, get_db, query_all, query_one
from .validators import to_float, to_int


def get_regions() -> list[str]:
    rows = query_all("SELECT DISTINCT region FROM population_records ORDER BY region")
    return [row["region"] for row in rows]


def get_years() -> list[int]:
    rows = query_all("SELECT DISTINCT year FROM population_records ORDER BY year DESC")
    return [row["year"] for row in rows]


def parse_record_form(form) -> dict:
    total = to_int(form.get("total_population", ""), "总人口")
    male = to_int(form.get("male_population", ""), "男性人口")
    female = to_int(form.get("female_population", ""), "女性人口")
    if male + female != total:
        raise ValueError("男性人口与女性人口之和应等于总人口。")
    region = form.get("region", "").strip()
    if not region:
        raise ValueError("地区不能为空。")
    return {
        "region": region,
        "year": to_int(form.get("year", ""), "年份"),
        "total_population": total,
        "male_population": male,
        "female_population": female,
        "birth_rate": to_float(form.get("birth_rate", ""), "出生率"),
        "death_rate": to_float(form.get("death_rate", ""), "死亡率"),
        "natural_growth_rate": to_float(form.get("natural_growth_rate", ""), "自然增长率", allow_negative=True),
        "aging_rate": to_float(form.get("aging_rate", ""), "老龄化率"),
        "urbanization_rate": to_float(form.get("urbanization_rate", ""), "城镇化率"),
        "source": form.get("source", "").strip(),
        "note": form.get("note", "").strip(),
    }


def list_records(region: str = "", year: str = "", keyword: str = ""):
    conditions = []
    params: list[object] = []
    if region:
        conditions.append("region = ?")
        params.append(region)
    if year:
        conditions.append("year = ?")
        params.append(year)
    if keyword:
        conditions.append("(region LIKE ? OR source LIKE ? OR note LIKE ?)")
        params.extend([f"%{keyword}%"] * 3)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return query_all(f"SELECT * FROM population_records {where} ORDER BY year DESC, region", params)


def get_record(record_id: int):
    return query_one("SELECT * FROM population_records WHERE id = ?", (record_id,))


def create_record(data: dict) -> None:
    execute(
        """
        INSERT INTO population_records (
            region, year, total_population, male_population, female_population,
            birth_rate, death_rate, natural_growth_rate, aging_rate,
            urbanization_rate, source, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(data.values()),
    )
    execute("INSERT OR IGNORE INTO regions (name) VALUES (?)", (data["region"],))


def update_record(record_id: int, data: dict) -> None:
    execute(
        """
        UPDATE population_records SET
            region = ?, year = ?, total_population = ?, male_population = ?,
            female_population = ?, birth_rate = ?, death_rate = ?,
            natural_growth_rate = ?, aging_rate = ?, urbanization_rate = ?,
            source = ?, note = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (*data.values(), record_id),
    )
    execute("INSERT OR IGNORE INTO regions (name) VALUES (?)", (data["region"],))


def delete_record_by_id(record_id: int):
    record = get_record(record_id)
    execute("DELETE FROM population_records WHERE id = ?", (record_id,))
    return record


def import_csv_text(raw_csv: str) -> int:
    reader = csv.DictReader(io.StringIO(raw_csv.strip()))
    required = {
        "region",
        "year",
        "total_population",
        "male_population",
        "female_population",
        "birth_rate",
        "death_rate",
        "natural_growth_rate",
        "aging_rate",
        "urbanization_rate",
    }
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("CSV 表头不完整，请包含 region、year 和全部指标字段。")

    imported = 0
    for item in reader:
        values = (
            item["region"].strip(),
            to_int(item["year"], "年份"),
            to_int(item["total_population"], "总人口"),
            to_int(item["male_population"], "男性人口"),
            to_int(item["female_population"], "女性人口"),
            to_float(item["birth_rate"], "出生率"),
            to_float(item["death_rate"], "死亡率"),
            to_float(item["natural_growth_rate"], "自然增长率", allow_negative=True),
            to_float(item["aging_rate"], "老龄化率"),
            to_float(item["urbanization_rate"], "城镇化率"),
            item.get("source", "CSV导入"),
            item.get("note", ""),
        )
        get_db().execute(
            """
            INSERT INTO population_records (
                region, year, total_population, male_population, female_population,
                birth_rate, death_rate, natural_growth_rate, aging_rate,
                urbanization_rate, source, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(region, year) DO UPDATE SET
                total_population = excluded.total_population,
                male_population = excluded.male_population,
                female_population = excluded.female_population,
                birth_rate = excluded.birth_rate,
                death_rate = excluded.death_rate,
                natural_growth_rate = excluded.natural_growth_rate,
                aging_rate = excluded.aging_rate,
                urbanization_rate = excluded.urbanization_rate,
                source = excluded.source,
                note = excluded.note,
                updated_at = CURRENT_TIMESTAMP
            """,
            values,
        )
        imported += 1
    get_db().commit()
    return imported


def records_to_csv(rows) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "region",
        "year",
        "total_population",
        "male_population",
        "female_population",
        "birth_rate",
        "death_rate",
        "natural_growth_rate",
        "aging_rate",
        "urbanization_rate",
        "source",
        "note",
    ])
    for row in rows:
        writer.writerow([
            row["region"],
            row["year"],
            row["total_population"],
            row["male_population"],
            row["female_population"],
            row["birth_rate"],
            row["death_rate"],
            row["natural_growth_rate"],
            row["aging_rate"],
            row["urbanization_rate"],
            row["source"],
            row["note"],
        ])
    return output.getvalue()


def add_region(form) -> None:
    name = form.get("name", "").strip()
    if not name:
        raise ValueError("地区名称不能为空。")
    try:
        execute(
            "INSERT INTO regions (name, category, admin_code, description) VALUES (?, ?, ?, ?)",
            (
                name,
                form.get("category", "省级行政区").strip(),
                form.get("admin_code", "").strip(),
                form.get("description", "").strip(),
            ),
        )
    except sqlite3.IntegrityError:
        raise ValueError("该地区已存在。") from None
