// Cloudflare Worker: 2つの役割を持つ。
//  (1) fetch  … サイトの「今すぐ最新化する」ボタンから呼ばれ、収集ワークフローを起動
//  (2) scheduled … Cloudflare Cron Trigger により毎朝6時(JST)に定時起動
//      （GitHubの標準スケジュールは時刻がルーズで数時間遅れるため、こちらで正確に回す）
//
// 認証トークン（GitHub PAT）は Worker のシークレット GH_TOKEN に保存し、
// サイト側には一切出さない（公開サイトでも安全）。
//
// 設定するシークレット/変数（Cloudflareダッシュボード → Settings → Variables）:
//   GH_TOKEN     … GitHubのFine-grained PAT（対象リポジトリのActions: Read and write）
//   ALLOW_ORIGIN … 許可するサイトのURL（例: https://ojkbc.github.io）
//
// 定時実行の時刻は Cloudflare の Cron Triggers で設定する（UTCで指定）:
//   0 21 * * *  = 毎日 21:00 UTC = 06:00 JST

const REPO = "OJKBC/japonism-hanro-dashboard";
const WORKFLOW = "update.yml";
const BRANCH = "master";
const COOLDOWN_SEC = 90; // 連打対策: この秒数以内の再起動は無視する

async function triggerWorkflow(env) {
  return fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "japonism-update-button",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: BRANCH }),
    }
  );
}

export default {
  // 毎朝6時(JST)の定時実行。Cloudflare Cron Trigger から呼ばれる。
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerWorkflow(env));
  },

  // 「今すぐ最新化する」ボタンからのリクエスト。
  async fetch(request, env) {
    const allowOrigin = env.ALLOW_ORIGIN || "*";
    const cors = {
      "Access-Control-Allow-Origin": allowOrigin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }
    if (request.method !== "POST") {
      return json({ ok: false, error: "Method Not Allowed" }, 405, cors);
    }

    // クールダウン（Cache API を簡易ロックに利用）
    const cache = caches.default;
    const lockUrl = "https://cooldown.local/last-run";
    const last = await cache.match(lockUrl);
    if (last) {
      return json({ ok: true, skipped: true,
        message: "直前に更新を実行済みです。数分お待ちください。" }, 200, cors);
    }

    const res = await triggerWorkflow(env);

    if (res.status === 204) {
      await cache.put(lockUrl, new Response("1", {
        headers: { "Cache-Control": `max-age=${COOLDOWN_SEC}` },
      }));
      return json({ ok: true, message: "更新を開始しました。" }, 200, cors);
    }

    const detail = await res.text();
    return json({ ok: false, status: res.status, detail }, 502, cors);
  },
};

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
