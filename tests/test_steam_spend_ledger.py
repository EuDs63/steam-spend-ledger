import io
import json
import unittest
from contextlib import redirect_stdout

from steam_spend_ledger import main, parse_transactions, summarize


SAMPLE = """Date,Item,Type,Total
2025-01-02,Game A,Purchase,¥ 68.00
2025-01-05,Game A,Refund,-¥ 68.00
2025-02-10,Game B,Purchase,¥ 128.00
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


if __name__ == "__main__":
    unittest.main()

