#!/usr/bin/env python
"""Everyday chores, judged the same way as the coding suite.

The coding matrix answers "can this model drive a repo". Most people do not want
that; they want the inbox sorted, the spreadsheet cleaned, the receipt turned
into JSON, the meeting turned into action items, and the weekly numbers added up
correctly. Those are the tasks here, and every prompt is in Chinese because that
is how they would actually be asked.

Eight tasks, one file or one small folder each, all verifiable from the
filesystem:

* 整理笔记  sort five notes into date-prefixed file names
* 清洗表格  trim, dedupe, title-case and sort a messy CSV
* 票据转 JSON  pull vendor, date, total and tax out of a Chinese receipt
* 会议纪要  turn a transcript into action items with owners
* 笔记索引  build a date-sorted index table from four notes
* 邮件回复  answer a customer's three questions from a policy sheet
* 周报汇总  add up three daily sales files into one report
* 预算表    sum a receipt list into an xlsx with category totals

Usage:
  python bench/daily_matrix.py --selftest
  python bench/daily_matrix.py --model spark-1.7b-q4 --task all --timeout 120
"""

from __future__ import annotations

import json
import pathlib
import re

import suite
from suite import Task

# --------------------------------------------------------------------------
# seeds
# --------------------------------------------------------------------------

NOTES = {
    "note-a.md": ("季度预算复盘", "2026-03-02", "财务,复盘"),
    "note-b.md": ("客户访谈要点", "2026-01-15", "销售,访谈"),
    "note-c.md": ("上线检查清单", "2026-03-09", "工程,发布"),
    "note-d.md": ("差旅报销说明", "2025-12-28", "行政"),
    "note-e.md": ("周会待办", "2026-02-11", "会议,待办"),
}

RAW_CSV = """date,name,city,amount
2026-03-01,  Alice , beijing ,100
2026-03-02,Bob,Shanghai,200
2026-03-01,Alice,Beijing,100
2026-03-03,  Carol,beijing,150
2026-03-02, Bob ,shanghai,200
"""

RECEIPT = """城市咖啡（建国路店）
日期：2026年3月5日 14:32
拿铁 x2        38.00
芝士蛋糕 x1    22.00
合计           60.00 元
税率           6%
付款方式：微信
"""

MEETING = """项目周会 2026-03-10
主持人：赵敏
张三：后端接口这周能联调完，我周三前把接口文档发到群里。
李四：前端页面还差两个，我周四前补完，然后开始回归测试。
王五：上线时间我周五再跟运维确认一次，确认完贴到群里。
赵敏：好，那就这样，其他事项下周再议。
"""

EMAIL = """主题：关于订单 20831 的咨询

你好，
我有三个问题：
1. 可以开发票吗？
2. 下单后多久发货？
3. 收到货后能退货吗？
谢谢！
客户 王先生
"""

POLICY = """# 售后政策速查

- 发票：默认开电子发票，当天开出，发到下单邮箱。
- 发货：现货 48 小时内发出。
- 退货：签收后 7 天内无理由退货，运费由买家承担。
"""

SALES = {
    "sales-mon.csv": "product,qty,price\nA,2,10\nB,1,5\n",
    "sales-tue.csv": "product,qty,price\nA,1,10\nC,3,2\n",
    "sales-wed.csv": "product,qty,price\nB,2,5\n",
}

BUDGET_CSV = """category,item,amount
餐饮,午餐,30
交通,地铁,20
餐饮,晚餐,90
交通,打车,25
"""


def seed_tidy_notes(d: pathlib.Path) -> None:
    for name, (title, date, tags) in NOTES.items():
        (d / "inbox").mkdir(exist_ok=True)
        (d / "inbox" / name).write_text(
            f"---\nTitle: {title}\nDate: {date}\nTags: {tags}\n---\n\n今天的记录。\n",
            encoding="utf-8",
        )


def seed_clean_csv(d: pathlib.Path) -> None:
    (d / "raw.csv").write_text(RAW_CSV, encoding="utf-8")


def seed_receipt(d: pathlib.Path) -> None:
    (d / "receipt.txt").write_text(RECEIPT, encoding="utf-8")


def seed_meeting(d: pathlib.Path) -> None:
    (d / "meeting.txt").write_text(MEETING, encoding="utf-8")


def seed_index(d: pathlib.Path) -> None:
    notes = d / "notes"
    notes.mkdir()
    for name, (title, date, tags) in NOTES.items():
        (notes / name).write_text(
            f"---\nTitle: {title}\nDate: {date}\nTags: {tags}\n---\n\n正文。\n", encoding="utf-8"
        )


def seed_email(d: pathlib.Path) -> None:
    (d / "email.txt").write_text(EMAIL, encoding="utf-8")
    (d / "policy.md").write_text(POLICY, encoding="utf-8")


def seed_weekly(d: pathlib.Path) -> None:
    for name, body in SALES.items():
        (d / name).write_text(body, encoding="utf-8")


def seed_budget(d: pathlib.Path) -> None:
    (d / "receipts.csv").write_text(BUDGET_CSV, encoding="utf-8")


# --------------------------------------------------------------------------
# verifiers
# --------------------------------------------------------------------------

EXPECTED_NAME = {
    "季度预算复盘": "quarterly-budget-review",
    "客户访谈要点": "customer-interview-notes",
    "上线检查清单": "release-checklist",
    "差旅报销说明": "travel-expense-notes",
    "周会待办": "weekly-meeting-todos",
}
EXPECTED_SLUG = {
    "季度预算复盘": "季度预算复盘",
    "客户访谈要点": "客户访谈要点",
    "上线检查清单": "上线检查清单",
    "差旅报销说明": "差旅报销说明",
    "周会待办": "周会待办",
}


def v_tidy_notes(d: pathlib.Path, task: Task) -> suite.Verdict:
    found = sorted(p.name for p in (d / "sorted").glob("*") if p.is_file()) if (d / "sorted").is_dir() else []
    expected = [f"{date}-{title}.md" for title, date, _tags in NOTES.values()]
    if not found:
        return False, False, ""
    ok = sorted(found) == sorted(expected)
    return ok, True, f"found={found[:5]}"


def v_clean_csv(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "clean.csv"
    if not target.exists():
        return False, False, ""
    rows = [line.rstrip("\n") for line in target.read_text(errors="replace").splitlines() if line.strip()]
    expected = [
        "date,name,city,amount",
        "2026-03-01,Alice,Beijing,100",
        "2026-03-02,Bob,Shanghai,200",
        "2026-03-03,Carol,Beijing,150",
    ]
    got = [",".join(part.strip() for part in row.split(",")) for row in rows]
    return got == expected, True, f"rows={got[1:4]}"


def v_receipt(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "receipt.json"
    if not target.exists():
        return False, False, ""
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, True, f"invalid json: {exc}"
    if not isinstance(data, dict):
        return False, True, "json is not an object"
    flat = {str(k).lower(): v for k, v in data.items()}

    def pick(*names: str):
        for name in names:
            if name in flat:
                return flat[name]
        return None

    vendor = str(pick("vendor", "商家", "shop") or "")
    date = str(pick("date", "日期") or "")
    total = pick("total", "amount", "合计", "总额")
    tax = pick("tax_rate", "tax", "税率")
    try:
        total_f = float(str(total).replace("元", "").strip())
    except (TypeError, ValueError):
        total_f = None
    try:
        tax_f = float(str(tax).replace("%", "").strip())
        tax_f = tax_f / 100 if tax_f > 1 else tax_f
    except (TypeError, ValueError):
        tax_f = None
    ok = (
        "城市咖啡" in vendor
        and date.replace("/", "-").replace("年", "-").replace("月", "-").replace("日", "").startswith("2026-03-05")
        and total_f == 60.0
        and tax_f is not None
        and abs(tax_f - 0.06) < 1e-6
    )
    return ok, True, f"vendor={vendor!r} date={date!r} total={total!r} tax={tax!r}"


def v_meeting(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "actions.md"
    if not target.exists():
        return False, False, ""
    text = target.read_text(errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(("-", "*"))]
    owners = {"张三": "接口文档", "李四": "测试", "王五": "上线"}
    hits = {}
    for owner, keyword in owners.items():
        line = next((row for row in lines if owner in row), None)
        hits[owner] = bool(line and (keyword in line or "文档" in line))
    ok = all(hits.values()) and len(lines) >= 3
    return ok, True, f"lines={len(lines)} hits={hits}"


def v_index(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "index.md"
    if not target.exists():
        return False, False, ""
    text = target.read_text(errors="replace")
    rows = [line for line in text.splitlines() if line.strip().startswith("|") and "---" not in line]
    order = []
    for line in rows:
        for title, date, _tags in NOTES.values():
            if title in line:
                order.append(date)
    expected = ["2026-03-09", "2026-03-02", "2026-02-11", "2026-01-15", "2025-12-28"]
    ok = order == expected
    return ok, True, f"order={order}"


def v_email(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "reply.md"
    if not target.exists():
        return False, False, ""
    text = target.read_text(errors="replace")
    checks = {
        "电子发票": "电子发票" in text or ("发票" in text and "当天" in text),
        "48": "48" in text,
        "7 天": ("7 天" in text) or ("七天" in text) or ("7天" in text),
        "称呼": ("王先生" in text) or ("您好" in text) or ("你好" in text),
    }
    ok = all(checks.values())
    return ok, True, f"checks={checks}"


def v_weekly(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "report.md"
    if not target.exists():
        return False, False, ""
    text = target.read_text(errors="replace")
    numbers = set(int(n) for n in re.findall(r"\b\d+\b", text))
    ok = {30, 15, 6, 51} <= numbers
    return ok, True, f"numbers={sorted(numbers)[:8]}"


def v_budget(d: pathlib.Path, task: Task) -> suite.Verdict:
    target = d / "budget.xlsx"
    if not target.exists():
        return False, False, ""
    try:
        import openpyxl

        book = openpyxl.load_workbook(str(target))
    except Exception as exc:  # noqa: BLE001
        return False, True, f"cannot open xlsx: {exc}"
    values: dict[str, float] = {}
    flat: list[str] = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            flat.append(" ".join(cells))
            if len(cells) >= 2:
                try:
                    number = float(cells[1])
                except ValueError:
                    continue
                values[cells[0].strip()] = number
    joined = " ".join(flat)
    ok = (
        abs(values.get("餐饮", -1) - 120.0) < 0.01
        and abs(values.get("交通", -1) - 45.0) < 0.01
        and ("165" in joined)
    )
    return ok, True, f"values={values} has_total={'165' in joined}"


VERIFIERS = {
    "tidy_notes": v_tidy_notes,
    "clean_csv": v_clean_csv,
    "receipt": v_receipt,
    "meeting": v_meeting,
    "index": v_index,
    "email": v_email,
    "weekly": v_weekly,
    "budget": v_budget,
}


# --------------------------------------------------------------------------
# reference solutions
# --------------------------------------------------------------------------


def ref_tidy_notes(d: pathlib.Path) -> None:
    out = d / "sorted"
    out.mkdir(exist_ok=True)
    for name, (title, date, _tags) in NOTES.items():
        (out / f"{date}-{title}.md").write_text((d / "inbox" / name).read_text(encoding="utf-8"), encoding="utf-8")


def ref_clean_csv(d: pathlib.Path) -> None:
    rows = [line.split(",") for line in RAW_CSV.strip().splitlines()]
    header, body = rows[0], rows[1:]
    cleaned = set()
    for date, name, city, amount in body:
        cleaned.add((date.strip(), name.strip(), city.strip().title(), amount.strip()))
    ordered = sorted(cleaned, key=lambda row: (row[0], row[1]))
    text = ",".join(header) + "\n" + "\n".join(",".join(row) for row in ordered) + "\n"
    (d / "clean.csv").write_text(text, encoding="utf-8")


def ref_receipt(d: pathlib.Path) -> None:
    payload = {"vendor": "城市咖啡（建国路店）", "date": "2026-03-05", "total": 60.0, "tax_rate": 0.06}
    (d / "receipt.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ref_meeting(d: pathlib.Path) -> None:
    text = (
        "# 待办\n\n"
        "- [ ] 张三：周三前发出接口文档\n"
        "- [ ] 李四：周四前补完页面并开始回归测试\n"
        "- [ ] 王五：周五确认上线时间并贴到群里\n"
    )
    (d / "actions.md").write_text(text, encoding="utf-8")


def ref_index(d: pathlib.Path) -> None:
    ordered = sorted(NOTES.values(), key=lambda item: item[1], reverse=True)
    lines = ["| 日期 | 标题 | 标签 |", "|---|---|---|"]
    lines += [f"| {date} | {title} | {tags} |" for title, date, tags in ordered]
    (d / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ref_email(d: pathlib.Path) -> None:
    text = (
        "王先生您好，\n\n"
        "逐条回复您的问题：\n\n"
        "1. 可以开发票：默认开电子发票，当天开出，发到下单邮箱。\n"
        "2. 发货：现货 48 小时内发出。\n"
        "3. 退货：签收后 7 天内可无理由退货，运费由买家承担。\n\n"
        "祝好，\n客服\n"
    )
    (d / "reply.md").write_text(text, encoding="utf-8")


def ref_weekly(d: pathlib.Path) -> None:
    totals: dict[str, int] = {}
    for body in SALES.values():
        for line in body.strip().splitlines()[1:]:
            product, qty, price = line.split(",")
            totals[product] = totals.get(product, 0) + int(qty) * int(price)
    grand = sum(totals.values())
    lines = ["# 本周销售\n", "| 商品 | 金额 |", "|---|---|"]
    lines += [f"| {p} | {v} |" for p, v in sorted(totals.items())]
    lines += ["", f"总计 {grand}"]
    (d / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ref_budget(d: pathlib.Path) -> None:
    import openpyxl

    totals: dict[str, float] = {}
    for line in BUDGET_CSV.strip().splitlines()[1:]:
        category, _item, amount = line.split(",")
        totals[category] = totals.get(category, 0) + float(amount)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "预算"
    sheet.append(["类别", "金额"])
    for category, amount in totals.items():
        sheet.append([category, amount])
    sheet.append(["总计", sum(totals.values())])
    book.save(str(d / "budget.xlsx"))


# --------------------------------------------------------------------------
# task table
# --------------------------------------------------------------------------

TASKS = {
    "tidy_notes": Task(
        key="tidy_notes",
        label="整理笔记",
        prompt=(
            "inbox/ 里有五个笔记，每个开头都有 `Title:` 和 `Date: YYYY-MM-DD`。请把它们移动到 "
            "`sorted/` 目录下，文件名改成 `日期-标题.md`（例如 `2026-03-02-季度预算复盘.md`），"
            "内容保持不变。"
        ),
        verifier="tidy_notes",
        seed=seed_tidy_notes,
        reference=ref_tidy_notes,
    ),
    "clean_csv": Task(
        key="clean_csv",
        label="清洗表格",
        prompt=(
            "raw.csv 很脏：字段前后有空格、城市大小写不一致、有重复行。请生成 clean.csv："
            "去掉每格首尾空格、城市改成首字母大写、去掉完全重复的行，按 date 再按 name 升序排序，"
            "表头保持 `date,name,city,amount`。"
        ),
        verifier="clean_csv",
        seed=seed_clean_csv,
        reference=ref_clean_csv,
    ),
    "receipt": Task(
        key="receipt",
        label="票据转 JSON",
        prompt=(
            "读 receipt.txt，生成 receipt.json，字段为 vendor（商家名）、date（`YYYY-MM-DD`）、"
            "total（数字，单位元）、tax_rate（小数，例如 0.06）。先自己读一遍确认数字对得上。"
        ),
        verifier="receipt",
        seed=seed_receipt,
        reference=ref_receipt,
    ),
    "meeting": Task(
        key="meeting",
        label="会议纪要",
        prompt=(
            "读 meeting.txt，把每个人承诺的事情整理成 actions.md，每条一行，格式 "
            "`- [ ] 负责人：事项`。只写真正的待办，不要复述寒暄。"
        ),
        verifier="meeting",
        seed=seed_meeting,
        reference=ref_meeting,
    ),
    "index": Task(
        key="index",
        label="笔记索引",
        prompt=(
            "notes/ 里每个文件开头有 Title / Date / Tags。请生成 index.md，做成 Markdown 表格，"
            "表头 `| 日期 | 标题 | 标签 |`，按日期从新到旧排列，五行都要有。"
        ),
        verifier="index",
        seed=seed_index,
        reference=ref_index,
    ),
    "email": Task(
        key="email",
        label="邮件回复",
        prompt=(
            "读 email.txt 里客户提的三个问题，再读 policy.md 里的政策，写 reply.md 回复客户："
            "称呼客户本人，三个问题逐条回答，用政策里的具体数字。不要编造政策里没有的内容。"
        ),
        verifier="email",
        seed=seed_email,
        reference=ref_email,
    ),
    "weekly": Task(
        key="weekly",
        label="周报汇总",
        prompt=(
            "sales-mon.csv、sales-tue.csv、sales-wed.csv 是三天销量（product,qty,price）。"
            "请生成 report.md：一个表格列出每个商品的金额，最后一行写 `总计 <数字>`。"
        ),
        verifier="weekly",
        seed=seed_weekly,
        reference=ref_weekly,
    ),
    "budget": Task(
        key="budget",
        label="预算表",
        prompt=(
            "receipts.csv 是逐笔支出（category,item,amount）。请用 openpyxl 生成 budget.xlsx："
            "第一列类别、第二列该类合计金额，最后一行是 `总计` 和总金额。"
        ),
        verifier="budget",
        seed=seed_budget,
        reference=ref_budget,
    ),
}


if __name__ == "__main__":
    raise SystemExit(
        suite.run_cli(
            None,
            TASKS,
            VERIFIERS,
            "Everyday-chore suite for local models: eight file-and-data tasks, judged by the filesystem.",
        )
    )
