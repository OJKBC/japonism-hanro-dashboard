"""sources/curated_exhibitions.json（人手検証済みの主要展示会リスト）を読み込む。

主催者サイトの個別スクレイパーは壊れやすいため、キュレーション方式を採用
（SPEC_CHANGES.md §5）。会期・URLは公式サイトで確認した値のみを記載する運用。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors import common

SOURCE = "curated"
SOURCE_FILE = common.ROOT / "sources" / "curated_exhibitions.json"


def run() -> int:
    with open(SOURCE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for row in data["items"]:
        items.append({
            "id": f"curated:{row['slug']}",
            "category": row.get("category", "exhibition"),
            "title": row["title"],
            "organizer": row.get("organizer"),
            "url": row["url"],
            "region": row.get("region", "全国"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "deadline": row.get("deadline"),
            "location": row.get("location"),
            "amount": None,
            "tags": row.get("tags", []),
            "summary": row.get("summary", ""),
            "status": "open",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": " ".join(filter(None, [
                row["title"], row.get("summary", ""), " ".join(row.get("tags", [])),
            ])),
        })

    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    print(run())
