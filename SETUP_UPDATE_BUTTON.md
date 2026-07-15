# 「今すぐ最新化する」ボタンのセットアップ手順

サイト上部のボタンを押すだけで、その場で最新情報に更新できるようにする設定です。
所要 約15分・すべて無料。1回設定すれば以降ずっと使えます。

仕組み: ボタン →（Cloudflare Worker が認証を代行）→ GitHub Actions が収集を実行 → 2〜4分でサイト反映。
GitHubの認証キーは Cloudflare 側に隠して保存するので、公開サイトでも安全です。

---

## ステップ1: GitHubの認証キー（PAT）を作る

このボタン専用の、権限を絞った鍵を発行します。

1. ブラウザで https://github.com/settings/personal-access-tokens/new を開く（OJKBCでログイン）
2. 次のように設定:
   - **Token name**: `japonism-update-button`
   - **Expiration**: `Custom` で1年後など長めに（切れたら作り直し）
   - **Repository access**: 「Only select repositories」→ `japonism-hanro-dashboard` を選ぶ
   - **Permissions**: 「Repository permissions」の中の **Actions** を **Read and write** に設定
     （他は触らない）
3. 下の **Generate token** を押す
4. 表示された `github_pat_...` の文字列を**コピー**（この画面を離れると二度と表示されません）

---

## ステップ2: Cloudflare Worker を作る

1. https://dash.cloudflare.com/ にアクセスし、無料アカウントを作成/ログイン
2. 左メニュー **Compute (Workers)**（または Workers & Pages）→ **Create** → **Start with Hello World** → **Create Worker**
3. 名前を `japonism-update` などにして **Deploy**（いったんそのまま）
4. **Edit code**（コードを編集）を開き、表示されているコードを全部消して、
   このリポジトリの `worker/worker.js` の中身を丸ごと貼り付け → **Deploy**
5. Worker の画面上部に出る URL（例: `https://japonism-update.あなたの名前.workers.dev`）を**コピー**

### シークレット（鍵）を登録

6. その Worker の **Settings** → **Variables and Secrets**（変数とシークレット）を開く
7. **＋ Add** で2つ登録:
   - Type: **Secret** / Name: `GH_TOKEN` / Value: ステップ1でコピーしたPAT
   - Type: **Text**（またはPlaintext）/ Name: `ALLOW_ORIGIN` / Value: `https://ojkbc.github.io`
8. **Deploy / Save** で保存

---

### 毎朝6時の定時実行を設定（重要）

GitHub標準のスケジュールは時刻が数時間ずれるため、正確な毎朝6時はこのWorkerで回します。

9. その Worker の **Settings** → **Triggers**（トリガー）→ **Cron Triggers** →
   **＋ Add Cron Trigger**
10. スケジュール欄に **`0 21 * * *`** と入力して保存
    （21:00 UTC = 日本時間 午前6:00。worker.js の `scheduled` が毎朝これで動きます）

---

## ステップ3: サイトにWorkerのURLを教える

Worker の URL をサイトに設定すると、ボタンが表示されます。

- このURLを私（Claude）に伝えてください。`site/data/config.js` に設定して反映します。

または自分で設定する場合:
1. `site/data/config.js` を開く
2. `updateEndpoint: ""` の `""` の中に、ステップ2でコピーしたWorkerのURLを貼る
   例: `updateEndpoint: "https://japonism-update.xxxx.workers.dev"`
3. 保存して `git add -A && git commit -m "更新ボタンを有効化" && git push`

---

## 完成後の使い方

- サイト上部の **「今すぐ最新化する」** を押す → 「更新を開始しました」と表示
- 2〜4分待ってページを再読み込みすると、最新の内容になります
- 連打しても90秒間は二重に走らない安全装置つき

## うまくいかないとき

- ボタンが出ない → `config.js` のURL設定を確認（保存・pushしたか）
- 押すと「失敗しました」→ Workerの `GH_TOKEN`（PAT）が正しいか、PATの権限がActions=Read and writeか、有効期限切れでないかを確認
