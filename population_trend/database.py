from __future__ import annotations

import sqlite3
from typing import Iterable

from flask import g

from .config import DATA_DIR, DB_PATH, DOMESTIC_POPULATION_RECORDS, GLOBAL_POPULATION_RECORDS
from .security import hash_password


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db


def close_db(_error: object | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def query_all(sql: str, params: Iterable[object] = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable[object] = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, tuple(params)).fetchone()


def execute(sql: str, params: Iterable[object] = ()) -> None:
    get_db().execute(sql, tuple(params))
    get_db().commit()


def init_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'viewer')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL DEFAULT '省级行政区',
                admin_code TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS population_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                year INTEGER NOT NULL,
                total_population INTEGER NOT NULL CHECK(total_population >= 0),
                male_population INTEGER NOT NULL CHECK(male_population >= 0),
                female_population INTEGER NOT NULL CHECK(female_population >= 0),
                birth_rate REAL NOT NULL CHECK(birth_rate >= 0),
                death_rate REAL NOT NULL CHECK(death_rate >= 0),
                natural_growth_rate REAL NOT NULL,
                aging_rate REAL NOT NULL CHECK(aging_rate >= 0),
                urbanization_rate REAL NOT NULL CHECK(urbanization_rate >= 0),
                source TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(region, year)
            );

            CREATE TABLE IF NOT EXISTS global_population_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country TEXT NOT NULL,
                continent TEXT NOT NULL,
                year INTEGER NOT NULL,
                total_population INTEGER NOT NULL CHECK(total_population >= 0),
                male_population INTEGER NOT NULL CHECK(male_population >= 0),
                female_population INTEGER NOT NULL CHECK(female_population >= 0),
                birth_rate REAL NOT NULL CHECK(birth_rate >= 0),
                death_rate REAL NOT NULL CHECK(death_rate >= 0),
                natural_growth_rate REAL NOT NULL,
                aging_rate REAL NOT NULL CHECK(aging_rate >= 0),
                urbanization_rate REAL NOT NULL CHECK(urbanization_rate >= 0),
                source TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(country, year)
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [
                ("admin", hash_password("admin123"), "admin"),
                ("viewer", hash_password("viewer123"), "viewer"),
            ],
        )
        connection.executemany(
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
            DOMESTIC_POPULATION_RECORDS,
        )
        for region, *_ in DOMESTIC_POPULATION_RECORDS:
            connection.execute(
                """
                INSERT INTO regions (name, description) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description
                """,
                (region, "系统内置地区档案，可在地区管理中维护。"),
            )
        connection.executemany(
            """
            INSERT INTO global_population_records (
                country, continent, year, total_population, male_population, female_population,
                birth_rate, death_rate, natural_growth_rate, aging_rate,
                urbanization_rate, source, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(country, year) DO UPDATE SET
                continent = excluded.continent,
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
            GLOBAL_POPULATION_RECORDS,
        )
        connection.commit()
