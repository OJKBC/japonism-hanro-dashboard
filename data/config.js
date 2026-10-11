// サイトの設定。updateEndpoint に Cloudflare Worker のURLを設定すると
// ヘッダーに「今すぐ最新化する」ボタンが表示されるようになります。
// 空のままだとボタンは非表示です（セットアップ手順は SETUP_UPDATE_BUTTON.md 参照）。
window.__CONFIG__ = {
  updateEndpoint: ""
};
