"""コレクター共通ユーティリティ。

- HTTP取得（User-Agent明示・リトライ・アクセス間隔の強制）
- data/raw/ への中間データ保存
- JST日時ヘルパー
"""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = ROOT / "data" / "cache"

JST = timezone(timedelta(hours=9), "JST")

USER_AGENT = "JAPONISM-HanroDashboard/1.0 (daily batch; low frequency)"

_session = None
_last_request_at = 0.0


def load_config() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def now_jst() -> datetime:
    return datetime.now(JST)


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    return _session


def http_get(url: str, *, interval: float = 1.0, timeout: float = 30.0,
             retries: int = 2, **kwargs) -> requests.Response:
    """アクセス間隔を強制しつつGETする。5xx/接続エラーは軽くリトライ。"""
    global _last_request_at
    sess = _get_session()
    last_err = None
    for attempt in range(retries + 1):
        wait = interval - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        try:
            res = sess.get(url, timeout=timeout, **kwargs)
            if res.status_code >= 500:
                last_err = RuntimeError(f"HTTP {res.status_code}: {url}")
                time.sleep(2 * (attempt + 1))
                continue
            res.raise_for_status()
            return res
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def save_raw(source_name: str, items: list) -> None:
    """コレクターの出力を data/raw/<source>.json に保存する。"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source_name,
        "fetched_at": now_jst().isoformat(timespec="seconds"),
        "items": items,
    }
    with open(RAW_DIR / f"{source_name}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def load_cache(name: str) -> dict:
    path = CACHE_DIR / f"{name}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(name: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_DIR / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def to_jst_date(iso_datetime: str | None) -> str | None:
    """'2026-07-15T08:00:00.000Z' → JSTの 'YYYY-MM-DD'。"""
    if not iso_datetime:
        return None
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%Y-%m-%d")
    except ValueError:
        return None
