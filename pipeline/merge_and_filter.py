"""全ソースの raw データを統合し、JAPON!SM条件でスコアリングして
site/data/data.json（＋ローカル閲覧用 data.js）を出力する。

スコアリング方針（仕様書 第5章＋会社資料の実態を反映。SPEC_CHANGES.md §7参照）:
- 完全一致で絞りすぎない。該当キーワードが多いほど match_score が上がり上位表示される。
- 除外は「締切超過」と「明らかな業種違い（タイトルで判定）」のみ。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors import common

SITE_DATA_DIR = common.ROOT / "site" / "data"

# 販路・チャネルに直結する語（+3）
STRONG_WORDS = [
    "販路開拓", "販路拡大", "展示会", "出展", "商談会", "マッチング",
    "インバウンド", "訪日", "海外展開", "海外販路", "越境EC", "輸出",
    "観光", "お土産", "土産", "免税", "ギフト", "見本市",
]
# 商材・既存販路との親和語（+2）
MEDIUM_WORDS = [
    "化粧品", "コスメ", "フレグランス", "香り", "石鹸", "ソープ",
    "ルームスプレー", "雑貨", "日用品", "インテリア", "ライフスタイル",
    "伝統工芸", "工芸", "クラフト", "デザイン", "ブランディング", "ブランド",
    "ミュージアム", "美術館", "博物館", "アート", "日本文化", "和雑貨",
    "百貨店", "ホテル", "空港", "駅ナカ", "文化",
]
# 対象事業者との親和語（+1）
WEAK_WORDS = [
    "中小企業", "小規模事業者", "製造業", "卸売", "小売", "EC",
    "新商品", "商品開発", "消費財",
]
# 明らかな業種違い（タイトルに含まれる場合のみ -4）
NEGATIVE_TITLE_WORDS = [
    "建設業", "土木", "建築物", "農業者", "漁業者", "林業者",
    "医療機器", "介護", "保育", "受託開発", "住宅",
]

# 展示会・商談会の業種違い除外（タイトル・タグで判定。石鹸・スプレー・雑貨と
# 無関係な専門イベントを掲載しない。手動追加とキュレーション分は対象外）
EVENT_OFF_WORDS_JA = [
    "食品", "農林水産", "農水産", "フード", "飲料", "焼酎", "日本酒", "ワイン",
    "酒類", "ハラル", "水産", "畜産", "青果",
    "自動車", "部品", "機械", "機器", "半導体", "エレクトロニクス",
    "エンジニアリング", "ものづくり", "工作機械", "建設", "建材", "住宅",
    "医療", "ライフサイエンス", "バイオ", "製薬", "康養", "高齢者", "老年",
    "養老", "シルバー産業", "銀髪", "介護",
    "繊維", "ICT", "ソフトウェア", "コンテンツ", "アニメ", "ゲーム",
    "航空", "宇宙", "エネルギー",
]
EVENT_OFF_WORDS_EN = [  # 英字タイトル用（小文字部分一致）
    "food", "halal", "anime", "steam", "biofach", "bio-europe", "bio europe",
    "medica", "electronica",
]
EVENT_OFF_EXEMPT_SOURCES = {"manual", "curated"}

# 地域限定の判定: 本社=東京都新宿区・製造元(OEM)=福岡のため、
# 「特定地域の企業限定」案件は東京・福岡関連のみ掲載する。
# 開催地が他県・海外でも、応募企業を限定しないものは掲載対象。
ALLOWED_COMPANY_REGIONS = ("全国", "東京", "福岡", "海外",
                           "関東・甲信越", "九州・沖縄")
RESTRICT_PATTERNS = [
    re.compile(r"([一-龥]{1,4}(?:県|府|都|道))産"),                       # ●●県産
    re.compile(r"([一-龥]{1,4}(?:県|府|都|市|区))内(?:の)?(?:会員)?(?:中小)?(?:企業|事業者)"),
    re.compile(r"【([^】]{2,14}(?:県|府|市|町|村))】"),                    # 【●●県】【●●市】
    re.compile(r"([一-龥]{1,6}(?:県|府|市|町|村|区))(?:の|内の?)(?:企業|事業者)(?:限定|のみ|対象)"),
]


def region_allowed(item: dict) -> bool:
    """東京・福岡以外の「企業限定」案件を除外する。"""
    if item.get("source") == "manual":
        return True
    if item.get("category") == "subsidy":
        # jGrantsは補助対象地域が構造化されている（複数は「 / 」区切り）
        region = item.get("region") or ""
        return any(a in region for a in ALLOWED_COMPANY_REGIONS)
    text = " ".join(filter(None, [item.get("title"), item.get("summary")]))
    for pat in RESTRICT_PATTERNS:
        for m in pat.finditer(text):
            seg = m.group(1)
            if not any(a in seg for a in ("東京", "新宿", "福岡", "全国", "47都道府県")):
                return False
    return True


def event_fits(item: dict) -> bool:
    """展示会・商談会がJAPON!SMの商材に合うかをタイトル・タグで判定する。"""
    if item.get("category") not in ("exhibition", "matching"):
        return True
    if item.get("source") in EVENT_OFF_EXEMPT_SOURCES:
        return True
    text = " ".join([item.get("title") or ""] + (item.get("tags") or []))
    # 「非食品」は食品の除外対象ではなくむしろ適合案件
    text = text.replace("非食品", "")
    if any(w in text for w in EVENT_OFF_WORDS_JA):
        return False
    lower = text.lower()
    return not any(w in lower for w in EVENT_OFF_WORDS_EN)


def score_item(item: dict) -> tuple[int, list[str]]:
    text = item.get("_match_text") or " ".join(filter(None, [
        item.get("title"), item.get("summary"), " ".join(item.get("tags") or []),
    ]))
    title = item.get("title") or ""
    score = 0
    reasons = []
    for words, weight in ((STRONG_WORDS, 3), (MEDIUM_WORDS, 2), (WEAK_WORDS, 1)):
        for w in words:
            if w in text:
                score += weight
                reasons.append(w)
    for w in NEGATIVE_TITLE_WORDS:
        if w in title:
            score -= 4
            reasons.append(f"-{w}")
    # 展示会・商談会はBtoB販路に直結するため底上げ（仕様書: BtoB優先）
    if item.get("category") in ("exhibition", "matching"):
        score += 2
    return score, reasons


def load_raw_items() -> list[dict]:
    items = []
    if not common.RAW_DIR.exists():
        return items
    for path in sorted(common.RAW_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            items.extend(payload.get("items", []))
        except Exception as e:
            print(f"  [merge] {path.name} の読み込みに失敗: {e}")
    return items


def run() -> dict:
    cfg = common.load_config()
    min_score = cfg.get("filter", {}).get("min_score", 1)
    today = common.now_jst().strftime("%Y-%m-%d")

    raw = load_raw_items()
    seen_ids = set()
    kept, dropped_past, dropped_score, dropped_offcat, dropped_region = [], 0, 0, 0, 0

    for item in raw:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])

        # 締切・会期が過ぎたものは除外
        deadline = item.get("deadline")
        end = item.get("end_date") or item.get("start_date")
        if (deadline and deadline < today) or \
           (not deadline and end and end < today):
            dropped_past += 1
            continue

        if not event_fits(item):
            dropped_offcat += 1
            continue

        if not region_allowed(item):
            dropped_region += 1
            continue

        score, reasons = score_item(item)
        if score < min_score:
            dropped_score += 1
            continue

        out = {k: v for k, v in item.items() if not k.startswith("_")}
        out["match_score"] = score
        out["match_reasons"] = reasons
        kept.append(out)

    # 締切が近い順（締切なしは最後）→ スコア降順
    kept.sort(key=lambda x: (x.get("deadline") or "9999-12-31",
                             -x["match_score"]))

    data = {
        "updated_at": common.now_jst().isoformat(timespec="seconds"),
        "count": len(kept),
        "items": kept,
    }
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SITE_DATA_DIR / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    # file:// で開いてもCORSに阻まれないよう、JS代入版も出力する
    with open(SITE_DATA_DIR / "data.js", "w", encoding="utf-8") as f:
        f.write("window.__DATA__ = ")
        json.dump(data, f, ensure_ascii=False)
        f.write(";\n")

    print(f"  [merge] 入力{len(raw)}件 → 掲載{len(kept)}件 "
          f"(締切超過 {dropped_past} / 業種違い {dropped_offcat} / "
          f"地域限定 {dropped_region} / スコア未満 {dropped_score})")
    return data


if __name__ == "__main__":
    run()
