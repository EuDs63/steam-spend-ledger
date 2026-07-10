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

### 从 Steam 账户历史页导出 CSV

Steam 的 `https://store.steampowered.com/account/history/` 页面本身没有直接的 CSV 下载按钮，但页面里的“加载更多”会调用：

```text
POST https://store.steampowered.com/account/AjaxLoadMoreHistory/
```

请求参数来自当前页面：

- `sessionid`
- `cursor`

所以最稳的方式是在已经登录 Steam 的浏览器页面里运行导出脚本，让脚本复用当前登录态，自动解析当前页表格并继续请求后续分页，最后下载 `steam-history-YYYY-MM-DD.csv`。

生成浏览器脚本：

```bash
python -m steam_history_exporter --print-js > steam-history-exporter.js
```

然后打开 `https://store.steampowered.com/account/history/`，按 F12 打开控制台，把 `steam-history-exporter.js` 的内容粘进去运行。脚本只访问 Steam 同源接口，不会上传到第三方。

如果你已经把页面另存为 HTML，也可以离线转 CSV：

```bash
python -m steam_history_exporter --html steam-history.html -o steam-history.csv
```

### 汇总 CSV

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
