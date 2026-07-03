/* JAPON!SM 販路拡大ダッシュボード
   data.js（ローカル閲覧用）→ data.json（ホスティング用）の順で読み込む。
   状態はメモリ内のみで保持する。 */
(function () {
  "use strict";

  var CATEGORY_LABEL = {
    subsidy: "補助金",
    exhibition: "展示会",
    matching: "商談会"
  };

  var AREA_PREFS = {
    "北海道・東北": ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "東北"],
    "関東・甲信越": ["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川", "新潟", "山梨", "長野", "関東", "甲信越"],
    "東海・北陸": ["富山", "石川", "福井", "岐阜", "静岡", "愛知", "三重", "東海", "北陸"],
    "近畿": ["滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山", "近畿", "関西"],
    "中国・四国": ["鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知", "中国地方", "四国"],
    "九州・沖縄": ["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄", "九州"]
  };

  var state = { category: "all", query: "", area: "", deadlineOnly: false, items: [] };

  function matchesArea(item, area) {
    if (!area) return true;
    var text = [item.region, item.location].filter(Boolean).join(" ");
    if (area === "全国") return text.indexOf("全国") !== -1;
    if (area === "海外") {
      return text.indexOf("海外") !== -1 ||
        (item.location && !/日本|オンライン/.test(item.location) &&
         /[ア-ヴ]{2,}|米国|中国|台湾|韓国|香港|タイ|ドイツ|フランス|イタリア|スペイン|英国/.test(item.location));
    }
    if (area === "オンライン") return /オンライン|ウェブ|Web|web/.test(text);
    var prefs = AREA_PREFS[area] || [];
    return prefs.some(function (p) { return text.indexOf(p) !== -1; });
  }

  function daysUntil(dateStr) {
    if (!dateStr) return null;
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var d = new Date(dateStr + "T00:00:00");
    return Math.round((d - today) / 86400000);
  }

  function deadlineHtml(item) {
    if (!item.deadline) {
      if (item.status === "closed") return '<span>募集終了</span>';
      return '<span>締切情報なし</span>';
    }
    var days = daysUntil(item.deadline);
    var label = "締切 " + item.deadline.replace(/-/g, "/");
    if (days === null) return "<span>" + label + "</span>";
    if (days < 0) return "<span>" + label + "（終了）</span>";
    var count = days === 0 ? "本日締切" : "あと" + days + "日";
    if (days <= 7) return "<span>" + label + " <span class=\"soon\">" + count + "</span></span>";
    return "<span>" + label + "（" + count + "）</span>";
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function stars(score) {
    var n = Math.max(1, Math.min(5, Math.ceil(score / 4)));
    return "●".repeat(n) + "○".repeat(5 - n);
  }

  function render() {
    var list = document.getElementById("list");
    var q = state.query.trim().toLowerCase();

    var filtered = state.items.filter(function (item) {
      if (state.category !== "all" && item.category !== state.category) return false;
      if (state.deadlineOnly && !item.deadline) return false;
      if (!matchesArea(item, state.area)) return false;
      if (q) {
        var hay = [item.title, item.summary, item.organizer, item.region,
                   item.location, (item.tags || []).join(" ")].join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });

    document.getElementById("result-count").textContent =
      filtered.length + "件を表示しています";
    document.getElementById("empty").hidden = filtered.length > 0;

    list.innerHTML = filtered.map(function (item) {
      var cat = "cat-" + item.category;
      var metas = [];
      if (item.region) metas.push("<div><dt>地域</dt><dd>" + esc(item.region) + "</dd></div>");
      if (item.location) metas.push("<div><dt>開催地</dt><dd>" + esc(item.location) + "</dd></div>");
      if (item.start_date) {
        var period = item.start_date.replace(/-/g, "/") +
          (item.end_date ? "〜" + item.end_date.replace(/-/g, "/") : "〜");
        metas.push("<div><dt>期間</dt><dd>" + esc(period) + "</dd></div>");
      }
      if (item.amount) metas.push("<div><dt>補助額</dt><dd>" + esc(item.amount) + "</dd></div>");
      if (item.organizer) metas.push("<div><dt>実施</dt><dd>" + esc(item.organizer) + "</dd></div>");
      metas.push("<div><dt>適合度</dt><dd><span class=\"score\">" + stars(item.match_score) + "</span></dd></div>");

      return '<article class="card ' + cat + '">' +
        '<div class="card-top">' +
          '<span class="badge ' + cat + '">' + (CATEGORY_LABEL[item.category] || "その他") + "</span>" +
          '<span class="deadline">' + deadlineHtml(item) + "</span>" +
        "</div>" +
        "<h2><a href=\"" + esc(item.url) + '" target="_blank" rel="noopener">' +
          esc(item.title) + "</a></h2>" +
        (item.summary ? '<p class="summary">' + esc(item.summary) + "</p>" : "") +
        '<dl class="meta">' + metas.join("") + "</dl>" +
      "</article>";
    }).join("");
  }

  function init(data) {
    state.items = data.items || [];
    var d = new Date(data.updated_at);
    document.getElementById("updated-at").textContent = isNaN(d) ? data.updated_at :
      d.getFullYear() + "/" + (d.getMonth() + 1) + "/" + d.getDate() +
      " " + ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);

    document.getElementById("tabs").addEventListener("click", function (e) {
      var btn = e.target.closest(".tab");
      if (!btn) return;
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      btn.classList.add("active");
      state.category = btn.dataset.category;
      render();
    });
    document.getElementById("search").addEventListener("input", function (e) {
      state.query = e.target.value;
      render();
    });
    document.getElementById("region").addEventListener("change", function (e) {
      state.area = e.target.value;
      render();
    });
    document.getElementById("deadline-only").addEventListener("change", function (e) {
      state.deadlineOnly = e.target.checked;
      render();
    });
    render();
  }

  if (window.__DATA__) {
    init(window.__DATA__);
  } else {
    fetch("data/data.json")
      .then(function (r) { return r.json(); })
      .then(init)
      .catch(function () {
        document.getElementById("updated-at").textContent = "データを読み込めませんでした";
      });
  }
})();
