"""手動フォールバック。誰でも1行追加できる表から案件を読み込む。

優先順位（SPEC_CHANGES.md §6）:
1. config.json の manual_sheet_csv_url（Googleスプレッドシート「ウェブに公開」CSV）
2. ローカルの manual/manual_items.csv

列: 種別 / 名称 / URL / 開催日 / 場所 / 申込締切 / 地域 / メモ
- 種別: 補助金・展示会・商談会 のいずれか
- 日付: 2026-09-01 または 2026/9/1。開催日は「2026/9/1～2026/9/3」の期間も可
"""
import csv
import hashlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors import common

SOURCE = "manual"
LOCAL_CSV = common.ROOT / "manual" / "manual_items.csv"

CATEGORY_MAP = {"補助金": "subsidy", "助成金": "subsidy",
                "商談会": "matching", "展示会": "exhibition"}
DATE_RE = re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})")


def _dates(text: str) -> list[str]:
    return [f"{y}-{int(m):02d}-{int(d):02d}"
            for y, m, d in DATE_RE.findall(text or "")]


def _read_csv_text() -> str | None:
    url = common.load_config().get("manual_sheet_csv_url", "").strip()
    if url:
        return common.http_get(url, interval=1.0).text
    if LOCAL_CSV.exists():
        raw = LOCAL_CSV.read_bytes()
        for enc in ("utf-8-sig", "cp932"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    return None


def run() -> int:
    text = _read_csv_text()
    if text is None:
        print("  [manual] 手動リストが未設定のためスキップします")
        common.save_raw(SOURCE, [])
        return 0

    items = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lstrip("﻿"): (v or "").strip()
               for k, v in row.items()}
        name = row.get("名称")
        if not name:
            continue
        period = _dates(row.get("開催日", ""))
        deadline = _dates(row.get("申込締切", ""))
        memo = row.get("メモ", "")
        items.append({
            "id": "manual:" + hashlib.md5(name.encode()).hexdigest()[:10],
            "category": CATEGORY_MAP.get(row.get("種別", ""), "exhibition"),
            "title": name,
            "organizer": None,
            "url": row.get("URL") or "#",
            "region": row.get("地域") or "全国",
            "start_date": period[0] if period else None,
            "end_date": period[1] if len(period) > 1 else None,
            "deadline": deadline[0] if deadline else None,
            "location": row.get("場所") or None,
            "amount": None,
            "tags": ["手動追加"],
            "summary": memo,
            "status": "unknown",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": " ".join([name, memo, row.get("場所", "")]),
        })

    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    print(run())
