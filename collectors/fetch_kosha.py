"""東京都中小企業振興公社のお知らせ一覧から商談会・マッチング系を取得する。

対象（2026-07-04 に実ページで構造確認済み）:
https://www.tokyo-kosha.or.jp/topics/index.html
- <li> 行が「YYYY.MM.DD タイトル（リンク）」形式（約150行）
- 商談会・マッチング・展示会・販路系のタイトルのみ採用
- 開催日はタイトル中の「令和N年M月D日開催」「YYYY年M月D日」から抽出

本社が東京都新宿区のため、公社の販路開拓支援・商談会は応募資格面で適合しやすい。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from collectors import common

SOURCE = "tokyo_kosha"
BASE = "https://www.tokyo-kosha.or.jp"
LIST_URL = f"{BASE}/topics/index.html"

KEEP_RE = re.compile(r"商談|マッチング|展示会|フェア|バイヤー|販路|見本市|受注企業")
DATE_WAREKI_RE = re.compile(r"令和(\d+)年度?\s*(\d{1,2})月(\d{1,2})日")
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
LISTED_RE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})")


def _event_date(title: str) -> str | None:
    m = DATE_RE.search(title)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = DATE_WAREKI_RE.search(title)
    if m:
        return f"{2018 + int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def run() -> int:
    interval = common.load_config().get("jetro", {}).get("request_interval_sec", 3.0)
    res = common.http_get(LIST_URL, interval=interval)
    # サーバーがcharsetヘッダを返さないため、bytesを渡してmetaタグから自動判定させる
    soup = BeautifulSoup(res.content, "html.parser")
    today = common.now_jst().strftime("%Y-%m-%d")

    items = []
    for li in soup.find_all("li"):
        link = li.find("a", href=True)
        if not link:
            continue
        text = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
        if not LISTED_RE.match(text) or not KEEP_RE.search(text):
            continue
        title = LISTED_RE.sub("", text).strip()
        start = _event_date(title)
        if start and start < today:
            continue
        href = link["href"]
        url = href if href.startswith("http") else BASE + href
        items.append({
            "id": "tokyo_kosha:" + re.sub(r"\W+", "-", href)[-60:],
            "category": "subsidy" if re.search(r"助成|補助金", title)
                        else ("exhibition" if re.search(r"展示会|見本市|フェア", title)
                              else "matching"),
            "title": title,
            "organizer": "東京都中小企業振興公社",
            "url": url,
            "region": "東京都",
            "start_date": start,
            "end_date": None,
            "deadline": None,
            "location": None,
            "amount": None,
            "tags": ["東京", "販路開拓"],
            "summary": "東京都中小企業振興公社の販路開拓・マッチング支援です。対象条件はリンク先で確認してください。",
            "status": "open",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": title + " 商談 販路開拓 東京",
        })

    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    print(run())
