"""Download the public FAR-Trans release and audit raw values (Python stdlib only).

Run from any directory: python scripts/inspect_far_trans.py
Outputs: data/raw/ (originals), data/processed/far_trans_audit.json.
No split, candidate universe or evaluation population is selected here.
"""

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "FAR-Trans.zip": "https://researchdata.gla.ac.uk/1658/1/FAR-Trans.zip",
    "README.txt": "https://researchdata.gla.ac.uk/1658/2/README.txt",
    "repository.html": "https://researchdata.gla.ac.uk/1658/",
    "paper_2407.08692v1.html": "https://arxiv.org/html/2407.08692v1",
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(raw, refresh):
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = raw / "download_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest = {}
    for name, url in SOURCES.items():
        path = raw / name
        if refresh or not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "FAR-Trans-course-audit/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
                path.write_bytes(payload)
                meta = {"url": url, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "http_last_modified": response.headers.get("Last-Modified")}
        else:
            meta = old.get(name, {"url": url, "retrieved_utc": None})
            if "sha256" in meta and sha256(path) != meta["sha256"]:
                raise ValueError(f"Cached original changed: {path}; use --refresh to redownload")
        manifest[name] = dict(meta, bytes=path.stat().st_size, sha256=sha256(path))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    target = raw / "FAR-Trans"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(raw / "FAR-Trans.zip") as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failure: {bad}")
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise ValueError(f"Unsafe ZIP entry: {member.filename}")
        archive.extractall(target)
        members = [{"name": x.filename, "bytes": x.file_size, "crc32": f"{x.CRC:08x}"}
                   for x in archive.infolist()]
    return manifest, members, target


MISSING = {"", "-", "Not_Available", "NA", "N/A", "NULL", "null", "NaN", "nan", "None"}
IDENTIFIERS = {"customerID", "ISIN", "transactionID", "marketID", "exchangeID"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$")
NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$")


def value_type(value):
    if value in MISSING:
        return "missing_marker"
    if DATE.match(value):
        try:
            dt.datetime.fromisoformat(value)
            return "date" if len(value) == 10 else "datetime"
        except ValueError:
            return "invalid_date_like"
    if NUMBER.match(value):
        return "integer" if re.fullmatch(r"[+-]?\d+", value) else "decimal"
    return "string"


def profile(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        counts = {key: collections.Counter() for key in fields}
        rows = []
        malformed = []
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                malformed.append(line)
            for key in fields:
                counts[key][row[key]] += 1
            rows.append(row)
    columns = {}
    for key, values in counts.items():
        types = collections.Counter()
        for value, count in values.items():
            types["identifier_string" if key in IDENTIFIERS else value_type(value)] += count
        dates = [v for v in values if value_type(v) in {"date", "datetime"}]
        numbers = [float(v) for v in values if key not in IDENTIFIERS
                   and value_type(v) in {"integer", "decimal"} and math.isfinite(float(v))]
        columns[key] = {
            "types": dict(types), "unique": len(values),
            "missing": {v: n for v, n in values.items() if v in MISSING},
            "predicted_count": sum(n for v, n in values.items() if v.startswith("Predicted_")),
            "values_or_top20": dict(values if len(values) <= 60 else values.most_common(20)),
            "date_min": min(dates) if dates else None, "date_max": max(dates) if dates else None,
            "numeric_min": min(numbers) if numbers else None, "numeric_max": max(numbers) if numbers else None,
        }
    return rows, {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
                  "rows": len(rows), "fields": fields, "malformed_lines": malformed,
                  "exact_duplicate_rows": len(rows) - len({tuple(r[k] for k in fields) for r in rows}),
                  "columns": columns, "first_row": rows[0] if rows else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download again instead of using cached originals")
    args = parser.parse_args()
    manifest, members, target = download(ROOT / "data" / "raw", args.refresh)
    report = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "python": platform.python_version(), "sources": manifest, "zip_crc_ok": True,
              "zip_members": members, "files": {}}
    tables = {}
    for path in sorted(target.rglob("*")):
        if not path.is_file() or "__MACOSX" in path.parts or path.name.startswith("."):
            continue
        print(f"Inspecting {path.relative_to(target)}", flush=True)
        # questionnaires is prose despite its .csv suffix.
        if path.suffix.lower() == ".csv" and path.stem != "questionnaires":
            tables[path.stem], report["files"][path.name] = profile(path)
        else:
            text = path.read_text(encoding="utf-8-sig")
            report["files"][path.name] = {"path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path), "lines": len(text.splitlines()), "format": "text", "text": text}
    audit_relations(tables, report)
    output = ROOT / "data" / "processed" / "far_trans_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_profile(report)
    print(f"Audit written to {output}")
    for name, info in report["files"].items():
        print(name, info.get("rows", "text"), info.get("fields", ""))


def audit_relations(tables, report):
    tx = tables["transactions"]
    customers = tables["customer_information"]
    assets = tables["asset_information"]
    prices = tables["close_prices"]
    limits = tables["limit_prices"]
    markets = {r["marketID"] for r in tables["markets"]}
    ids = lambda rows, field: {r[field] for r in rows}
    customer_ids, asset_ids, price_ids = ids(customers, "customerID"), ids(assets, "ISIN"), ids(prices, "ISIN")
    price_map = {(r["ISIN"], r["timestamp"]): float(r["closePrice"]) for r in prices}
    by_asset = collections.defaultdict(list)
    for r in prices:
        by_asset[r["ISIN"]].append(r)
    limits_map = {r["ISIN"]: r for r in limits}
    checks = report["checks"] = {
        "transactions_unknown_customer": sorted(ids(tx, "customerID") - customer_ids),
        "transactions_unknown_asset": sorted(ids(tx, "ISIN") - asset_ids),
        "prices_without_asset_metadata": sorted(price_ids - asset_ids),
        "assets_without_prices": sorted(asset_ids - price_ids),
        "transaction_unknown_market": sorted(ids(tx, "marketID") - markets),
        "asset_unknown_market": sorted(ids(assets, "marketID") - markets),
        "customer_questionnaire_after_timestamp": sum(r["lastQuestionnaireDate"] > r["timestamp"] for r in customers),
        "customer_questionnaire_sentinel_2000": sum(r["lastQuestionnaireDate"] == "2000-01-01" for r in customers),
        "customer_timestamp_sentinel_2000": sum(r["timestamp"] == "2000-01-01" for r in customers),
        "customer_questionnaire_after_timestamp_example": next(r for r in customers if r["lastQuestionnaireDate"] > r["timestamp"]),
    }
    for name, rows, keys in [("customer_date", customers, ("customerID", "timestamp")),
                              ("asset_date", assets, ("ISIN", "timestamp")),
                              ("asset_market_date", assets, ("ISIN", "marketID", "timestamp")),
                              ("price_date", prices, ("ISIN", "timestamp")),
                              ("transaction_id", tx, ("transactionID",))]:
        freq = collections.Counter(tuple(r[k] for k in keys) for r in rows)
        checks[name + "_duplicate_key_groups"] = sum(n > 1 for n in freq.values())
        checks[name + "_excess_rows"] = sum(n - 1 for n in freq.values())
    negative = [r for r in tx if int(r["transactionID"]) < 0]
    checks["negative_transaction_ids"] = {
        "rows": len(negative), "types": dict(collections.Counter(r["transactionType"] for r in negative)),
        "date_min": min(r["timestamp"] for r in negative), "date_max": max(r["timestamp"] for r in negative),
        "at_asset_min_date": sum(r["timestamp"] == limits_map[r["ISIN"]]["minDate"] for r in negative),
        "at_asset_max_date": sum(r["timestamp"] == limits_map[r["ISIN"]]["maxDate"] for r in negative),
        "first_row": negative[0],
        "interpretation": "Synthetic-row indicator inferred from IDs and endpoints; not an explicit provenance flag in README.",
    }
    missing_price, different_value = [], []
    for i, r in enumerate(tx, 2):
        price = price_map.get((r["ISIN"], r["timestamp"]))
        if price is None:
            missing_price.append({"csv_record_line": i, **r})
        elif not math.isclose(float(r["totalValue"]), float(r["units"]) * price, rel_tol=1e-8, abs_tol=1e-6):
            different_value.append({"csv_record_line": i, **r})
    checks["transactions_without_same_day_price"] = {"count": len(missing_price), "examples": missing_price[:5]}
    checks["transactions_without_same_day_price"]["dates"] = dict(collections.Counter(r["timestamp"] for r in missing_price))
    checks["transactions_without_same_day_price"]["types"] = dict(collections.Counter(r["transactionType"] for r in missing_price))
    checks["totalValue_not_units_times_close"] = {"count": len(different_value), "examples": different_value[:5],
        "relative_tolerance": 1e-8, "absolute_tolerance": 1e-6}
    checks["nonpositive_numeric_values"] = {field: sum(float(r[field]) <= 0 for r in rows)
        for field, rows in [("units", tx), ("totalValue", tx), ("closePrice", prices)]}
    checks["transactions_month_type"] = dict(sorted(collections.Counter(r["timestamp"][:7] + "/" + r["transactionType"] for r in tx).items()))
    checks["transaction_assets"] = len(ids(tx, "ISIN"))
    checks["price_assets_without_transactions"] = len(price_ids - ids(tx, "ISIN"))
    checks["customers_with_at_most_3_release_rows"] = sum(n <= 3 for n in collections.Counter(r["customerID"] for r in tx).values())
    checks["top12_asset_transaction_share"] = sum(n for _, n in collections.Counter(r["ISIN"] for r in tx).most_common(12)) / len(tx)
    checks["unique_user_asset_type"] = len({(r["customerID"], r["ISIN"], r["transactionType"]) for r in tx})
    checks["unique_asset_categories"] = {category: len({r["ISIN"] for r in assets if r["assetCategory"] == category})
        for category in sorted(ids(assets, "assetCategory"))}
    checks["customer_rows_per_user"] = dict(sorted(collections.Counter(collections.Counter(r["customerID"] for r in customers).values()).items()))
    asset_keys = collections.Counter((r["ISIN"], r["timestamp"]) for r in assets)
    checks["asset_conflicting_same_date_rows"] = [r for r in assets if asset_keys[(r["ISIN"], r["timestamp"])] > 1]
    checks["questionnaire_sentinel_by_risk"] = dict(collections.Counter(r["riskLevel"] for r in customers if r["lastQuestionnaireDate"] == "2000-01-01"))
    gap_summary, endpoint_errors = [], []
    for isin, rows in sorted(by_asset.items()):
        ordered = sorted(rows, key=lambda r: r["timestamp"])
        dates = [dt.date.fromisoformat(r["timestamp"]) for r in ordered]
        # Weekdays are a diagnostic grid only: not an exchange holiday calendar.
        span = (dates[-1] - dates[0]).days
        expected = sum((dates[0] + dt.timedelta(days=i)).weekday() < 5 for i in range(span + 1))
        weekdays_present = sum(d.weekday() < 5 for d in dates)
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        gap_summary.append({"ISIN": isin, "first": str(dates[0]), "last": str(dates[-1]),
            "rows": len(rows), "absent_weekdays_inside_span": expected - weekdays_present,
            "max_calendar_gap_days": max(gaps, default=0)})
        lim = limits_map[isin]
        if (lim["minDate"] != str(dates[0]) or lim["maxDate"] != str(dates[-1])
            or not math.isclose(float(lim["priceMinDate"]), float(ordered[0]["closePrice"]))
            or not math.isclose(float(lim["priceMaxDate"]), float(ordered[-1]["closePrice"]))
            or not math.isclose(float(lim["profitability"]), float(ordered[-1]["closePrice"]) / float(ordered[0]["closePrice"]) - 1, abs_tol=1e-10)):
            endpoint_errors.append(isin)
    checks["price_coverage_per_asset"] = gap_summary
    checks["limit_price_endpoint_or_roi_mismatches"] = endpoint_errors
    checks["price_coverage_summary"] = {
        "assets_with_absent_weekdays_inside_span": sum(r["absent_weekdays_inside_span"] > 0 for r in gap_summary),
        "absent_weekday_asset_date_pairs": sum(r["absent_weekdays_inside_span"] for r in gap_summary),
        "max_calendar_gap_days": max(r["max_calendar_gap_days"] for r in gap_summary),
        "first_date_range": [min(r["first"] for r in gap_summary), max(r["first"] for r in gap_summary)],
        "last_date_range": [min(r["last"] for r in gap_summary), max(r["last"] for r in gap_summary)],
    }
    # Stable, real record selected by explicit transaction ID plus all its context.
    sample = next(r for r in tx if r["transactionID"] == "7590224")
    checks["report_example"] = {
        "transaction": sample, "csv_record_line": tx.index(sample) + 2,
        "all_rows_with_transaction_id": sum(r["transactionID"] == sample["transactionID"] for r in tx),
        "customer_history": [dict(csv_record_line=i, **r) for i, r in enumerate(customers, 2) if r["customerID"] == sample["customerID"]],
        "asset_history": [dict(csv_record_line=i, **r) for i, r in enumerate(assets, 2) if r["ISIN"] == sample["ISIN"]],
        "same_day_price": [dict(csv_record_line=i, **r) for i, r in enumerate(prices, 2) if r["ISIN"] == sample["ISIN"] and r["timestamp"] == sample["timestamp"]],
    }


def write_profile(report):
    """Human-readable field dictionary generated from every row, with exact values."""
    lines = ["# FAR-Trans: автоматически сформированный профиль", "",
        "Команда: `python scripts/inspect_far_trans.py`. Источник: https://researchdata.gla.ac.uk/1658/.",
        "Все количества относятся к строкам релиза, не к независимым пользователям/сделкам.",
        "Идентификаторы сохраняются строками. Типы остальных значений — лексические, не SQL-схема.",
        "Пропуски: пустая строка, `Not_Available`, `-` и стандартные NA-маркеры; дата `2000-01-01` проверяется отдельно.", ""]
    for name, info in report["files"].items():
        lines += [f"## {name}", "", f"Путь: `{info['path']}`; SHA-256: `{info['sha256']}`.", ""]
        if "rows" not in info:
            lines += [f"Текст, {info['lines']} строк. Не таблица наблюдений.", ""]
            continue
        lines += [f"Строк: **{info['rows']:,}**; полных дубликатов: {info['exact_duplicate_rows']}; некорректных CSV-записей: {len(info['malformed_lines'])}.", "",
                  "| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |",
                  "|---|---|---:|---|---:|---|"]
        for field, col in info["columns"].items():
            bounds = f"{col['date_min']} … {col['date_max']}" if col["date_min"] else (
                f"{col['numeric_min']} … {col['numeric_max']}" if col["numeric_min"] is not None else "—")
            lines.append(f"| {field} | {json.dumps(col['types'])} | {col['unique']} | `{json.dumps(col['missing'])}` | {col['predicted_count']} | {bounds} |")
        lines += ["", "### Значения: все при ≤60 уникальных, иначе 20 самых частых", ""]
        for field, col in info["columns"].items():
            lines += [f"**{field}**", "", "```json", json.dumps(col["values_or_top20"], ensure_ascii=False, indent=2), "```", ""]
    lines += ["## Межфайловые проверки и точный пример", "", "```json",
        json.dumps({k: v for k, v in report["checks"].items() if k != "price_coverage_per_asset"}, ensure_ascii=False, indent=2), "```", "",
        "Полное покрытие по каждому активу: `data/processed/far_trans_audit.json` → `checks.price_coverage_per_asset`."]
    path = ROOT / "notes" / "far_trans_profile.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
