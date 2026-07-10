from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


DATE_COLUMNS = {"date", "日期", "时间", "transaction date", "交易日期"}
ITEM_COLUMNS = {"item", "项目", "名称", "description", "说明", "商品"}
TYPE_COLUMNS = {"type", "类型", "transaction type", "交易类型"}
AMOUNT_COLUMNS = {"total", "amount", "金额", "总计", "price", "费用"}
AMOUNT_RE = re.compile(
    r"(?P<sign>[-+−])?\s*(?P<currency>[$¥￥€£楼]|[A-Z]{3})?\s*(?P<number>[0-9][0-9,]*(?:\.[0-9]+)?)"
)


@dataclass(frozen=True)
class Transaction:
    date: str
    item: str
    type: str
    currency: str
    amount: str


def normalize_column(name: str) -> str:
    return name.strip().lower()


def find_column(headers: list[str], candidates: set[str]) -> str | None:
    normalized = {normalize_column(header): header for header in headers}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for header in headers:
        lowered = normalize_column(header)
        if any(candidate in lowered for candidate in candidates if len(candidate) > 2):
            return header
    return None


def parse_date(value: str) -> str:
    text = value.strip()
    chinese_match = re.search(r"(20\d{2}|19\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if chinese_match:
        return date(int(chinese_match.group(1)), int(chinese_match.group(2)), int(chinese_match.group(3))).isoformat()

    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%b %d, %Y", "%B %d, %Y", "%d %b, %Y", "%d %B, %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(20\d{2}|19\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    raise ValueError(f"无法识别日期: {value!r}")


def parse_amount(value: str) -> tuple[str, Decimal]:
    text = value.strip().replace("−", "-")
    text = text.replace("–", "-").replace("￥", "¥")
    match = AMOUNT_RE.search(text)
    if not match:
        raise ValueError(f"无法识别金额: {value!r}")
    currency = match.group("currency") or "UNKNOWN"
    currency = {"￥": "¥", "楼": "¥"}.get(currency, currency)
    number = match.group("number").replace(",", "")
    try:
        amount = Decimal(number)
    except InvalidOperation as exc:
        raise ValueError(f"无法识别金额: {value!r}") from exc
    if match.group("sign") == "-":
        amount = -amount
    return currency.replace("￥", "¥"), amount


def detect_dialect(text: str) -> csv.Dialect:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        return csv.excel_tab if "\t" in sample else csv.excel


def parse_transactions(text: str) -> list[Transaction]:
    reader = csv.DictReader(io.StringIO(text), dialect=detect_dialect(text))
    if not reader.fieldnames:
        return []

    headers = reader.fieldnames
    date_col = find_column(headers, DATE_COLUMNS)
    item_col = find_column(headers, ITEM_COLUMNS)
    type_col = find_column(headers, TYPE_COLUMNS)
    amount_col = find_column(headers, AMOUNT_COLUMNS)
    missing = [
        label
        for label, column in [("date", date_col), ("item", item_col), ("type", type_col), ("amount", amount_col)]
        if column is None
    ]
    if missing:
        raise ValueError(f"缺少必要列: {', '.join(missing)}")

    transactions: list[Transaction] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        currency, amount = parse_amount(row[amount_col] or "")
        transactions.append(
            Transaction(
                date=parse_date(row[date_col] or ""),
                item=(row[item_col] or "").strip(),
                type=(row[type_col] or "").strip() or "Unknown",
                currency=currency,
                amount=str(amount),
            )
        )
    return transactions


def add_decimal(mapping: dict[str, Decimal], key: str, amount: Decimal) -> None:
    mapping[key] = mapping.get(key, Decimal("0")) + amount


def summarize(transactions: Iterable[Transaction]) -> dict:
    by_currency: dict[str, Decimal] = {}
    purchases: dict[str, Decimal] = {}
    refunds: dict[str, Decimal] = {}
    by_month: dict[str, dict[str, Decimal]] = {}
    by_type: dict[str, dict[str, Decimal]] = {}
    rows = list(transactions)

    for transaction in rows:
        amount = Decimal(transaction.amount)
        currency = transaction.currency
        add_decimal(by_currency, currency, amount)
        if amount >= 0:
            add_decimal(purchases, currency, amount)
        else:
            add_decimal(refunds, currency, amount)

        month = transaction.date[:7]
        by_month.setdefault(month, {})
        by_type.setdefault(transaction.type, {})
        add_decimal(by_month[month], currency, amount)
        add_decimal(by_type[transaction.type], currency, amount)

    def stringify_money_map(mapping: dict[str, Decimal]) -> dict[str, str]:
        return {key: str(value) for key, value in sorted(mapping.items())}

    return {
        "count": len(rows),
        "net": stringify_money_map(by_currency),
        "purchases": stringify_money_map(purchases),
        "refunds": stringify_money_map(refunds),
        "by_month": {month: stringify_money_map(values) for month, values in sorted(by_month.items())},
        "by_type": {kind: stringify_money_map(values) for kind, values in sorted(by_type.items())},
        "transactions": [asdict(transaction) for transaction in rows],
    }


def render_text(summary: dict) -> str:
    lines = ["# Steam Spend Ledger", "", f"Transactions: {summary['count']}", ""]
    for title, key in [("Net", "net"), ("Purchases", "purchases"), ("Refunds", "refunds")]:
        lines.append(f"## {title}")
        values = summary[key] or {"N/A": "0"}
        for currency, amount in values.items():
            lines.append(f"- {currency}: {amount}")
        lines.append("")

    lines.append("## By month")
    for month, values in summary["by_month"].items():
        rendered = ", ".join(f"{currency} {amount}" for currency, amount in values.items())
        lines.append(f"- {month}: {rendered}")
    lines.append("")

    lines.append("## By type")
    for kind, values in summary["by_type"].items():
        rendered = ", ".join(f"{currency} {amount}" for currency, amount in values.items())
        lines.append(f"- {kind}: {rendered}")
    return "\n".join(lines) + "\n"


def read_input(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8-sig")
    return sys.stdin.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Steam purchase history exports.")
    parser.add_argument("path", nargs="?", help="CSV/TSV file path. Reads stdin when omitted.")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    transactions = parse_transactions(read_input(args.path))
    summary = summarize(transactions)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_text(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
