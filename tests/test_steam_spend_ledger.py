import io
import json
import unittest
from contextlib import redirect_stdout

from steam_history_exporter import BROWSER_EXPORTER_JS, extract_rows_from_html, rows_to_csv
from steam_spend_ledger import main, parse_transactions, summarize


SAMPLE = """Date,Item,Type,Total
2025-01-02,Game A,Purchase,¥ 68.00
2025-01-05,Game A,Refund,-¥ 68.00
2025-02-10,Game B,Purchase,¥ 128.00
"""

STEAM_HISTORY_HTML = """
<table class="wallet_history_table">
  <tr class="wallet_table_row wallet_table_row_amt_change">
    <td class="wht_date">2026 年 6 月 11 日</td>
    <td class="wht_items">Steam Community Market</td>
    <td class="wht_type"><span class="wth_payment">Wallet</span> Market Transaction</td>
    <td class="wht_base_price">¥ 3.17</td>
    <td class="wht_tax"></td>
    <td class="wht_shipping"></td>
    <td class="wht_total">¥ 3.17</td>
    <td class="wht_wallet_change">-¥ 3.17</td>
    <td class="wht_wallet_balance">¥ 25.09</td>
  </tr>
</table>
"""


class SteamSpendLedgerTest(unittest.TestCase):
    def test_parse_transactions(self):
        transactions = parse_transactions(SAMPLE)

        self.assertEqual(len(transactions), 3)
        self.assertEqual(transactions[0].currency, "¥")
        self.assertEqual(transactions[1].amount, "-68.00")

    def test_summarize(self):
        summary = summarize(parse_transactions(SAMPLE))

        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["net"]["¥"], "128.00")
        self.assertEqual(summary["purchases"]["¥"], "196.00")
        self.assertEqual(summary["refunds"]["¥"], "-68.00")
        self.assertEqual(summary["by_month"]["2025-01"]["¥"], "0.00")

    def test_cli_json_from_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "steam.csv"
            path.write_text(SAMPLE, encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([str(path), "--json"])

        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["net"]["¥"], "128.00")

    def test_extract_rows_from_steam_history_html(self):
        rows = extract_rows_from_html(STEAM_HISTORY_HTML)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Date"], "2026 年 6 月 11 日")
        self.assertEqual(rows[0]["Item"], "Steam Community Market")
        self.assertEqual(rows[0]["Total"], "¥ 3.17")

    def test_exported_csv_can_feed_summarizer(self):
        transactions = parse_transactions(rows_to_csv(extract_rows_from_html(STEAM_HISTORY_HTML)))

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].date, "2026-06-11")
        self.assertEqual(transactions[0].amount, "3.17")

    def test_browser_exporter_uses_steam_history_endpoint(self):
        self.assertIn("/account/AjaxLoadMoreHistory/", BROWSER_EXPORTER_JS)
        self.assertIn("g_historyCursor", BROWSER_EXPORTER_JS)
        self.assertIn("g_sessionID", BROWSER_EXPORTER_JS)


if __name__ == "__main__":
    unittest.main()
