"""東京商工会議所のイベント一覧から商談会・交流会・展示会系を取得する。

対象（2026-07-04 に実ページで構造確認済み）:
https://myevent.tokyo-cci.or.jp/tile.php （受付中で絞り込んだ一覧・サーバレンダリング）
- 各イベントは div.posts__item。h3.posts__ttl がタイトル、
  .attribute__item が「イベント番号/開催日/会場/料金」のペア、
  .meta__label が種類（セミナー・講習会/交流会など）とリアル/オンライン区分
- 詳細URLは detail.php?event_kanri_id=<イベント番号>

セミナー等のノイズが多いため、商談・マッチング・交流会・展示・フェア系のみ採用する。
本社が東京のため、東商のイベントは応募資格の面でも適合しやすい。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from collectors import common

SOURCE = "tokyo_cci"
LIST_URL = ("https://myevent.tokyo-cci.or.jp/tile.php"
            "?searching_name=&kaisai_day_s=&kaisai_day_e=&entry_status2=2"
            "&canmati_flg=1&field=kaisai_day_s&sort=asc"
            "&search_syurui=000000000000000"
            "&search_category_genre=000000000000000000000000000000&recommend=")
DETAIL_URL = "https://myevent.tokyo-cci.or.jp/detail.php?event_kanri_id={}"

KEEP_RE = re.compile(r"商談|マッチング|交流会|展示会|フェア|バイヤー|見本市")
# 販路につながらない交流イベント・社内向けイベントのノイズを除外
SKIP_RE = re.compile(r"ゴルフ|就職|採用|人材確保|職場体験|面談会|視察会|女性活躍"
                     r"|懇親会|ピッチ|カクテル|戦略会議")
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _category(text: str) -> str:
    return "exhibition" if re.search(r"展示会|フェア|見本市", text) else "matching"


def run() -> int:
    interval = common.load_config().get("jetro", {}).get("request_interval_sec", 3.0)
    res = common.http_get(LIST_URL, interval=interval)
    soup = BeautifulSoup(res.content, "html.parser")
    today = common.now_jst().strftime("%Y-%m-%d")

    items = []
    for tile in soup.select(".posts__item"):
        ttl = tile.select_one(".posts__ttl")
        if not ttl:
            continue
        title = re.sub(r"\s+", " ", ttl.get_text(" ", strip=True))

        attrs = {}
        for a in tile.select(".attribute__item"):
            spans = [s.get_text(" ", strip=True) for s in a.find_all("span")]
            if len(spans) >= 2:
                attrs[spans[0]] = spans[1]
        labels = " ".join(li.get_text(" ", strip=True)
                          for li in tile.select(".meta__label li"))
        tags = [t.get_text(" ", strip=True) for t in tile.select(".tags__item")]

        if not KEEP_RE.search(title + " " + labels):
            continue
        if SKIP_RE.search(title):
            continue
        # 「展示会活用セミナー」のような講習会は商談の場ではないため除外
        if "セミナー・講習会" in labels:
            continue

        event_no = attrs.get("イベント番号")
        if not event_no:
            continue
        m = DATE_RE.search(attrs.get("開催日", ""))
        start = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
        if start and start < today:
            continue

        online = "オンライン" in labels
        items.append({
            "id": f"tokyo_cci:{event_no}",
            "category": _category(title + labels),
            "title": title,
            "organizer": "東京商工会議所",
            "url": DETAIL_URL.format(event_no),
            "region": "東京都",
            "start_date": start,
            "end_date": None,
            "deadline": None,
            "location": "オンライン" if online else (attrs.get("会場") or None),
            "amount": None,
            "tags": [t for t in tags if t][:5],
            "summary": " / ".join(filter(None, [
                labels, attrs.get("料金"),
            ])),
            "status": "open",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": " ".join([title, labels] + tags),
        })

    if not items:
        raise RuntimeError("東商イベントが0件でした（ページ構造変更の可能性）")
    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    print(run())
