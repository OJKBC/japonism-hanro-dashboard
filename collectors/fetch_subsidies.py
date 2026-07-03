"""jGrants 公式APIから補助金を取得する（Phase 1・全自動）。

API仕様（OpenAPI jgrants-api.yaml で確認済み・2026-07）:
- 一覧: GET /exp/v1/public/subsidies
  必須クエリ: keyword(2文字以上) / sort / order / acceptance
  → 「全件取得」は不可のため、config.json のキーワード群でスイープしIDで重複排除する。
- 詳細: GET /exp/v2/public/subsidies/id/{id}
  → URL(front_subsidy_detail_page_url)・概要(detail)・利用目的(use_purpose)は詳細にのみ含まれる。
  募集終了日時が変わらない限りキャッシュを使い、再取得しない。
"""
import html
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors import common

API_BASE = "https://api.jgrants-portal.go.jp/exp"
SOURCE = "jgrants"

TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _format_amount(limit) -> str | None:
    if not limit:
        return None
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if n >= 100_000_000:
        oku = n / 100_000_000
        return f"上限{oku:g}億円"
    if n >= 10_000:
        man = n / 10_000
        return f"上限{man:g}万円"
    return f"上限{n:,}円"


def _search_ids(cfg: dict) -> dict:
    """キーワードスイープで募集中の補助金を集める。id → 一覧レスポンス行。"""
    interval = cfg.get("request_interval_sec", 1.0)
    found: dict[str, dict] = {}
    for kw in cfg["keywords"]:
        params = urllib.parse.urlencode({
            "keyword": kw,
            "sort": "acceptance_end_datetime",
            "order": "ASC",
            "acceptance": "1",
        })
        try:
            res = common.http_get(f"{API_BASE}/v1/public/subsidies?{params}",
                                  interval=interval)
            rows = res.json().get("result", [])
        except Exception as e:
            print(f"  [jgrants] キーワード「{kw}」の検索に失敗: {e}")
            continue
        for row in rows:
            found.setdefault(row["id"], row)
        print(f"  [jgrants] 「{kw}」: {len(rows)}件")
    return found


def _fetch_details(ids: dict, cfg: dict) -> dict:
    """詳細APIをキャッシュ付きで取得する。募集終了日時が変わったら再取得。"""
    interval = cfg.get("request_interval_sec", 1.0)
    cache = common.load_cache("jgrants_details")
    details: dict[str, dict] = {}
    fetched = 0
    for sid, row in ids.items():
        end_dt = row.get("acceptance_end_datetime") or ""
        cached = cache.get(sid)
        if cached and cached.get("_acceptance_end") == end_dt:
            details[sid] = cached
            continue
        try:
            res = common.http_get(f"{API_BASE}/v2/public/subsidies/id/{sid}",
                                  interval=interval)
            result = res.json().get("result", [])
            if not result:
                continue
            d = result[0]
            # 添付ファイル(Base64)はサイズが大きいだけなので保持しない
            slim = {k: v for k, v in d.items()
                    if k not in ("application_guidelines", "outline_of_grant",
                                 "application_form")}
            slim["_acceptance_end"] = end_dt
            details[sid] = slim
            cache[sid] = slim
            fetched += 1
        except Exception as e:
            print(f"  [jgrants] 詳細取得に失敗 ({sid}): {e}")
    common.save_cache("jgrants_details", cache)
    print(f"  [jgrants] 詳細API呼び出し: {fetched}件（キャッシュ利用: {len(details) - fetched}件）")
    return details


def run() -> int:
    cfg = common.load_config()["jgrants"]
    ids = _search_ids(cfg)
    details = _fetch_details(ids, cfg)

    items = []
    for sid, row in ids.items():
        d = details.get(sid, {})
        detail_text = _strip_html(d.get("detail"))
        catch = (d.get("subsidy_catch_phrase") or "").strip()
        summary = catch or detail_text[:180]
        url = d.get("front_subsidy_detail_page_url") or \
            f"https://www.jgrants-portal.go.jp/subsidy/{sid}"
        tags = [t.strip() for t in (d.get("use_purpose") or "").split("/") if t.strip()]
        items.append({
            "id": f"jgrants:{sid}",
            "category": "subsidy",
            "title": row.get("title") or d.get("title") or "",
            "organizer": row.get("institution_name") or d.get("institution_name")
                         or "Jグランツ掲載",
            "url": url,
            "region": row.get("target_area_search") or "全国",
            "start_date": common.to_jst_date(row.get("acceptance_start_datetime")),
            "end_date": None,
            "deadline": common.to_jst_date(row.get("acceptance_end_datetime")),
            "location": None,
            "amount": _format_amount(row.get("subsidy_max_limit")),
            "tags": tags,
            "summary": summary,
            "status": "open",
            "source": SOURCE,
            "fetched_at": common.now_jst().isoformat(timespec="seconds"),
            # スコアリング用の全文（data.json出力前にパイプラインで除去される）
            "_match_text": " ".join(filter(None, [
                row.get("title"), catch,
                d.get("use_purpose"), d.get("industry"),
                detail_text[:2000],
            ])),
        })

    common.save_raw(SOURCE, items)
    return len(items)


if __name__ == "__main__":
    n = run()
    print(f"[jgrants] {n}件を保存しました")
