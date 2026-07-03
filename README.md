# JAPON!SM 販路拡大ダッシュボード

補助金・展示会・商談会の情報を毎日自動で収集し、1つのサイトで一覧できるようにする仕組みです。

- **補助金**: jGrants（Jグランツ）公式APIから全自動取得
- **展示会・商談会**: JETROの公開ページ＋主要展示会キュレーションリスト＋手動追加分
- サイトは静的ファイルのみ（`site/`）。`site/data/data.json` を読んで表示するだけです。

仕様書からの変更点と理由は [SPEC_CHANGES.md](SPEC_CHANGES.md) を参照してください。

## フォルダ構成

```
collectors/   各ソースの収集スクリプト（1つ壊れても他は動く）
  fetch_subsidies.py   jGrants API（補助金・全自動）
  fetch_jetro.py       JETRO 展示会・商談会（スクレイピング）
  fetch_curated.py     主要展示会キュレーションリスト
  fetch_manual.py      手動追加分（Googleシート or ローカルCSV）
pipeline/     統合・スコアリング・data.json出力
sources/      curated_exhibitions.json（主要展示会リスト・年1回更新）
manual/       manual_items.csv（手動追加用・1行1案件）
data/raw/     各コレクターの中間出力（コミット対象）
data/cache/   jGrants詳細のキャッシュ（コミット対象・API負荷軽減）
site/         公開する静的サイト
run_all.py    全部まとめて実行するエントリポイント
```

## ローカルでの実行・確認

```powershell
py -3 run_all.py          # データ収集 → site/data/data.json 更新
```

サイトの確認はどちらでも:
- `site/index.html` をダブルクリック（`data.js` 経由で表示されます）
- または `py -3 -m http.server -d site 8000` → http://localhost:8000

## 自動更新と公開（GitHub Actions + GitHub Pages）

`.github/workflows/update.yml` が毎日 06:00 JST に `run_all.py` を実行し、
変更を自動コミットしたうえで GitHub Pages にデプロイします。
手動実行は GitHub の Actions タブ →「Run workflow」。

**セットアップ状況（2026-07-03 完了済み）:**
- リポジトリ: https://github.com/OJKBC/japonism-hanro-dashboard
- 公開サイト: https://ojkbc.github.io/japonism-hanro-dashboard/
- Workflow permissions（Read and write）・Pages（Source: Deploy from a branch / gh-pages）設定済み
- 公開の実体はワークフローが `site/` を gh-pages ブランチへ push する方式です

ローカルで変更したら `git push` するだけで自動デプロイされます。

※公開URLになるため、URLを知っていれば誰でも閲覧できます
（検索エンジンには載らないよう noindex 設定済み）。
閲覧制限が必要になったら Cloudflare Pages + Access への移行を検討してください。

## 手動で案件を追加する

`manual/manual_items.csv` に1行追加してプッシュするだけです（列: 種別/名称/URL/開催日/場所/申込締切/地域/メモ）。

Googleスプレッドシートで運用する場合:
1. 同じ列構成のシートを作成し「ファイル → 共有 → ウェブに公開」でCSV形式のURLを発行
2. `config.json` の `manual_sheet_csv_url` にそのURLを設定

## フィルタ条件の調整

- 検索キーワード（jGrants）: `config.json` の `jgrants.keywords`
- スコアリング語彙: `pipeline/merge_and_filter.py` の `STRONG_WORDS` など
- 掲載する最低スコア: `config.json` の `filter.min_score`
- 各案件の `match_reasons`（data.json内）でスコアの根拠を確認できます

## 注意事項

- 掲載情報は自動収集です。**申込・申請条件は必ず各公式ページで確認**してください。
- スクレイピングは対象サイトの改変で壊れることがあります。壊れたソースはスキップされ、
  実行ログ（Actionsのログ）に「失敗ソース」として表示されます。
