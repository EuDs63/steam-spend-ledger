from __future__ import annotations

import argparse
import csv
import io
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import TextIO


CSV_COLUMNS = [
    "Date",
    "Item",
    "Type",
    "Base Price",
    "Tax",
    "Shipping",
    "Total",
    "Wallet Change",
    "Wallet Balance",
]

FIELD_CLASSES = {
    "Date": "wht_date",
    "Item": "wht_items",
    "Type": "wht_type",
    "Base Price": "wht_base_price",
    "Tax": "wht_tax",
    "Shipping": "wht_shipping",
    "Total": "wht_total",
    "Wallet Change": "wht_wallet_change",
    "Wallet Balance": "wht_wallet_balance",
}


BROWSER_EXPORTER_JS = r"""
(async () => {
  const columns = [
    "Date",
    "Item",
    "Type",
    "Base Price",
    "Tax",
    "Shipping",
    "Total",
    "Wallet Change",
    "Wallet Balance",
  ];

  const selectors = {
    "Date": ".wht_date",
    "Item": ".wht_items",
    "Type": ".wht_type",
    "Base Price": ".wht_base_price",
    "Tax": ".wht_tax",
    "Shipping": ".wht_shipping",
    "Total": ".wht_total",
    "Wallet Change": ".wht_wallet_change",
    "Wallet Balance": ".wht_wallet_balance",
  };

  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const textOf = (row, selector) => clean(row.querySelector(selector)?.textContent || "");

  const parseRows = (root) =>
    Array.from(root.querySelectorAll("tr.wallet_table_row"))
      .map((row) =>
        Object.fromEntries(columns.map((column) => [column, textOf(row, selectors[column])]))
      )
      .filter((row) => columns.some((column) => row[column]));

  const stringAssignment = (name) => {
    const source = document.documentElement.innerHTML;
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = source.match(new RegExp(`${escaped}\\s*=\\s*("([^"]*)"|'([^']*)'|null)`, "i"));
    if (!match || match[1] === "null") return null;
    return match[2] || match[3] || null;
  };

  const readGlobalString = (name) => {
    try {
      const value = globalThis[name];
      return typeof value === "string" && value ? value : null;
    } catch {
      return null;
    }
  };

  const sessionid = readGlobalString("g_sessionID") || stringAssignment("g_sessionID");
  let cursor = readGlobalString("g_historyCursor") || stringAssignment("g_historyCursor");

  let rows = parseRows(document);
  let extraPages = 0;
  const endpoint = new URL("/account/AjaxLoadMoreHistory/", location.origin).href;

  while (sessionid && cursor && extraPages < 200) {
    const response = await fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: new URLSearchParams({ cursor, sessionid }),
    });

    if (!response.ok) {
      throw new Error(`Steam history request failed: HTTP ${response.status}`);
    }

    const data = await response.json();
    if (data.html) {
      const table = document.createElement("table");
      const tbody = document.createElement("tbody");
      table.appendChild(tbody);
      tbody.innerHTML = data.html;
      rows = rows.concat(parseRows(tbody));
    }

    cursor = data.cursor || null;
    extraPages += 1;
  }

  const seen = new Set();
  rows = rows.filter((row) => {
    const key = columns.map((column) => row[column]).join("\u001f");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const csvEscape = (value) => `"${String(value || "").replace(/"/g, '""')}"`;
  const csvText = "\ufeff" + [
    columns.map(csvEscape).join(","),
    ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(",")),
  ].join("\r\n");

  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `steam-history-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);

  console.log(`Steam history CSV exported: ${rows.length} rows, ${extraPages} extra page(s).`);
})().catch((error) => {
  console.error(error);
  alert(`Steam history CSV export failed: ${error.message}`);
});
""".strip()


def clean_text(value: str) -> str:
    return " ".join(value.split())


def field_for_classes(class_value: str) -> str | None:
    classes = set(class_value.split())
    for field, class_name in FIELD_CLASSES.items():
        if class_name in classes:
            return field
    return None


class SteamHistoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._in_row = False
        self._row: dict[str, str] = {}
        self._current_field: str | None = None
        self._current_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        class_value = attrs_map.get("class", "")

        if tag.lower() == "tr" and "wallet_table_row" in class_value.split():
            self._in_row = True
            self._row = {}
            return

        if self._in_row and tag.lower() in {"td", "th"}:
            self._current_field = field_for_classes(class_value)
            self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_field:
            self._current_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._in_row and tag in {"td", "th"} and self._current_field:
            self._row[self._current_field] = clean_text("".join(self._current_parts))
            self._current_field = None
            self._current_parts = []
            return

        if tag == "tr" and self._in_row:
            if any(self._row.values()):
                self.rows.append({column: self._row.get(column, "") for column in CSV_COLUMNS})
            self._in_row = False
            self._row = {}
            self._current_field = None
            self._current_parts = []


def extract_rows_from_html(html: str) -> list[dict[str, str]]:
    parser = SteamHistoryParser()
    parser.feed(html)
    parser.close()
    return parser.rows


def rows_to_csv(rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_output(text: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8-sig")
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Steam account history page data to CSV.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--print-js", action="store_true", help="Print the browser-console exporter script.")
    source.add_argument("--html", help="Parse a saved Steam account history HTML file.")
    parser.add_argument("-o", "--output", help="Write CSV or JS to a file instead of stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.print_js:
        write_output(BROWSER_EXPORTER_JS + "\n", args.output)
        return 0

    html = Path(args.html).read_text(encoding="utf-8-sig")
    write_output(rows_to_csv(extract_rows_from_html(html)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
