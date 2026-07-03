"""JETRO の公開ページから展示会・商談会を取得する（Phase 2）。

対象（2026-07-03 に実ページで構造確認済み。SPEC_CHANGES.md §3参照）:
1. 展示会・商談会一覧  https://www.jetro.go.jp/events/tradefair.html
   テーブル5列: 種別 / タイトル(リンク) / 会期 / 開催地 / 受付状況
2. ジェトロ出展支援展示会（年間予定） https://www.jetro.go.jp/services/tradefair/list.html
   テーブル8列: 大分野 / 産業 / 展示会名(リンク) / 開催地 / 会期 / 募集開始時期 / 備考 / 問い合わせ先
3. イベントRSS https://www.jetro.go.jp/rss/event.xml （新着の取りこぼし防止・補助）

ページ改変で壊れる可能性がある前提で、ソースごとに独立して try/except する。
robots.txt 確認済み（Disallowは特定クローラー向けのみ）。アクセス間隔は3秒。
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from collectors import common

SOURCE = "jetro"
BASE = "https://www.jetro.go.jp"
EVENTS_URL = f"{BASE}/events/tradefair.html"
LIST_URL = f"{BASE}/services/tradefair/list.html"
RSS_URL = f"{BASE}/rss/event.xml"

PREFS = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木",
    "群馬", "埼玉", "千葉", "東京", "神奈川", "新潟", "富山", "石川", "福井",
    "山梨", "長野", "岐阜", "静岡", "愛知", "三重", "滋賀", "京都", "大阪",
    "兵庫", "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口", "徳島",
    "香川", "愛媛", "高知", "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎",
    "鹿児島", "沖縄",
]

DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
SHORT_DATE_RE = re.compile(r"[～〜~]\s*(?:(\d{1,2})月)?(\d{1,2})日")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_period(text: str) -> tuple[str | None, str | None]:
    """「2026年11月05日 ～2026年11月10日」「2026年4月21日～23日」→ (start, end)"""
    dates = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in DATE_RE.findall(text)]
    start = dates[0] if dates else None
    end = dates[-1] if len(dates) > 1 else None
    if start and not end:
        m = SHORT_DATE_RE.search(text)
        if m:
            month = int(m.group(1)) if m.group(1) else int(start[5:7])
            end = f"{start[:4]}-{month:02d}-{int(m.group(2)):02d}"
    return start, end


def region_of(location: str) -> str:
    loc = location or ""
    if re.search(r"オンライン|ウェビナー|Web", loc, re.I):
        return "オンライン"
    for p in PREFS:
        if p in loc:
            return f"{p}都" if p == "東京" else (
                f"{p}府" if p in ("大阪", "京都") else (
                    p if p == "北海道" else f"{p}県"))
    return "海外" if loc else "全国"


def _category(title: str) -> str:
    return "matching" if re.search(r"商談会|商談・|マッチング", title) else "exhibition"


def fetch_tradefair_events(interval: float) -> list[dict]:
    res = common.http_get(EVENTS_URL, interval=interval)
    soup = BeautifulSoup(res.text, "html.parser")
    items = []
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r"^/events/"))
        if not link:
            continue
        cells = [_clean(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
        if len(cells) < 5:
            continue
        event_type, title_raw, period_text, location, accept = cells[:5]
        if "終了" in accept:  # 受付終了は掲載しない（仕様書: 締切超過は除外）
            continue
        title = re.sub(r"^\[[^\]]+\]\s*", "", title_raw)
        start, end = parse_period(period_text)
        url = BASE + link["href"]
        items.append({
            "id": "jetro:" + link["href"],
            "category": _category(title + event_type),
            "title": title,
            "organizer": "JETRO（日本貿易振興機構）",
            "url": url,
            "region": region_of(location),
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": location or None,
            "amount": None,
            "tags": [t for t in re.split(r"\s+", event_type) if t],
            "summary": f"受付状況: {accept}" if accept else "",
            "status": "open",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": " ".join([title, event_type, location, period_text]),
        })
    return items


def fetch_support_list(interval: float) -> list[dict]:
    res = common.http_get(LIST_URL, interval=interval)
    soup = BeautifulSoup(res.text, "html.parser")
    today = common.now_jst().strftime("%Y-%m-%d")
    items = []
    for tr in soup.find_all("tr"):
        cells_el = tr.find_all(["th", "td"])
        cells = [_clean(c.get_text(" ", strip=True)) for c in cells_el]
        if len(cells) < 6 or cells[0] == "大分野":
            continue
        field, industry, name, location, period_text, recruit = cells[:6]
        note = cells[6] if len(cells) > 6 else ""
        link = tr.find("a", href=True)
        url = link["href"] if link else LIST_URL
        if url.startswith("/"):
            url = BASE + url
        start, end = parse_period(period_text)
        if (end or start) and (end or start) < today:  # 会期が過ぎたものは除外
            continue
        summary = f"ジェトロ出展支援（ジャパンパビリオン等）。募集開始時期: {recruit}" \
            if recruit else "ジェトロ出展支援（ジャパンパビリオン等）"
        items.append({
            "id": "jetro:support:" + re.sub(r"\W+", "-", name)[:60],
            "category": "exhibition",
            "title": name,
            "organizer": "JETRO 出展支援",
            "url": url,
            "region": region_of(location),
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": location or None,
            "amount": None,
            "tags": [t for t in {field, "BtoB", "海外展開"} if t],
            "summary": summary,
            "status": "unknown",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": " ".join([name, field, industry, location, note,
                                     "海外 輸出 出展"]),
        })
    return items


def fetch_rss_extras(interval: float, seen_urls: set) -> list[dict]:
    res = common.http_get(RSS_URL, interval=interval)
    root = ET.fromstring(res.content)
    items = []
    for it in root.iter("item"):
        category = (it.findtext("category") or "").strip()
        if "展示会" not in category and "商談会" not in category:
            continue
        link = (it.findtext("link") or "").strip()
        title = _clean(it.findtext("title") or "")
        if not link or link in seen_urls:
            continue
        items.append({
            "id": "jetro:" + link.replace(BASE, ""),
            "category": _category(title),
            "title": title,
            "organizer": "JETRO（日本貿易振興機構）",
            "url": link,
            "region": "全国",
            "start_date": None,
            "end_date": None,
            "deadline": None,
            "location": None,
            "amount": None,
            "tags": [category],
            "summary": "新着イベント（詳細はリンク先で確認してください）",
            "status": "unknown",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            "_match_text": title + " " + category,
        })
    return items


def run() -> int:
    interval = common.load_config().get("jetro", {}).get("request_interval_sec", 3.0)
    items: list[dict] = []
    for name, fetcher in (("tradefair", fetch_tradefair_events),
                          ("support_list", fetch_support_list)):
        try:
            got = fetcher(interval)
            print(f"  [jetro] {name}: {len(got)}件")
            items.extend(got)
        except Exception as e:
            print(f"  [jetro] {name} の取得に失敗: {e}")
    try:
        extras = fetch_rss_extras(interval, {i["url"] for i in items})
        print(f"  [jetro] rss新着: {len(extras)}件")
        items.extend(extras)
    except Exception as e:
        print(f"  [jetro] rss の取得に失敗: {e}")

    if not items:
        raise RuntimeError("JETROの全ソースが0件でした（ページ構造変更の可能性）")
    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    print(run())
