# Steam Spend Ledger

离线 Steam 消费记录统计工具。

对应创意「Steam消费统计」：先不追求把杉果、小黑盒、充值卡等所有渠道都吞掉，先把 Steam 自己的账户消费历史整理清楚。你可以从 Steam 账户消费历史页面复制表格，或整理成 CSV/TSV，然后用这个工具汇总。

## 功能

- 读取 CSV、TSV，或浏览器复制出来的制表符文本。
- 自动识别常见列名：日期、项目、类型、金额。
- 解析金额中的币种和正负号。
- 输出：
  - 总消费/退款/净额
  - 按月份汇总
  - 按交易类型汇总
  - JSON 结果
- 完全离线，不上传消费记录。

## 使用

```bash
python -m steam_spend_ledger steam-history.csv
```

输出 JSON：

```bash
python -m steam_spend_ledger steam-history.tsv --json
```

从 stdin 读取：

```bash
Get-Content steam-history.tsv | python -m steam_spend_ledger
```

## 支持的输入示例

```csv
Date,Item,Type,Total
2025-01-02,Game A,Purchase,¥ 68.00
2025-01-05,Game A,Refund,-¥ 68.00
2025-02-10,Game B,Purchase,¥ 128.00
```

## 说明

这个工具不会替你判断“余额来源”，只按 Steam 账单里出现的交易记录做汇总。后续如果要扩展到杉果、小黑盒等外部渠道，可以把它们也转换成同样的四列结构后再统一统计。

