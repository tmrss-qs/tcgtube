// TCGTube index: client-side filters, search, pagination, URL state.
// All text goes through esc(); ids are validated. No innerHTML with raw data.
(function () {
  "use strict";
  var PAGE = 48;
  var ID_RE = /^[A-Za-z0-9_-]{11}$/;
  var GAME_LABEL = {"MTG": "Magic", "Pokemon": "Pokémon", "Yu-Gi-Oh": "Yu-Gi-Oh!", "FAB": "Flesh and Blood", "Lorcana": "Lorcana", "One Piece": "One Piece", "General": "Cross-game"};
  var LEN = [["any", "any"], ["s", "under 10m"], ["m", "10–30m"], ["l", "30–60m"], ["xl", "over an hour"]];
  var SORT = [["lasting", "lasting"], ["people", "most people"], ["recent", "still recommended"], ["new", "newly qualified"]];
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); };
  var fmtDur = function (d) { if (d == null) return ""; var h = Math.floor(d / 3600), m = Math.floor(d % 3600 / 60), s = d % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0"); };
  var lenOk = function (d, b) { if (b === "any") return true; if (d == null) return false; var m = d / 60; return b === "s" ? m < 10 : b === "m" ? m >= 10 && m < 30 : b === "l" ? m >= 30 && m < 60 : m >= 60; };

  var DATA = [], state = {};
  var el = function (id) { return document.getElementById(id); };

  function readState() {
    var p = new URLSearchParams(location.search);
    state = {g: p.get("g") || "", f: p.get("f") || "", k: p.get("k") || "", len: p.get("len") || "any",
             sort: p.get("sort") || "lasting", q: p.get("q") || "", dated: p.get("dated") === "1", p: Math.max(1, parseInt(p.get("p") || "1", 10) || 1)};
  }
  function writeState(push) {
    var p = new URLSearchParams();
    if (state.g) p.set("g", state.g); if (state.f) p.set("f", state.f); if (state.k) p.set("k", state.k);
    if (state.len !== "any") p.set("len", state.len); if (state.sort !== "lasting") p.set("sort", state.sort);
    if (state.q) p.set("q", state.q); if (state.dated) p.set("dated", "1"); if (state.p > 1) p.set("p", String(state.p));
    var url = location.pathname + (p.toString() ? "?" + p.toString() : "");
    (push ? history.pushState : history.replaceState).call(history, null, "", url);
  }
  function set(k, v) { state[k] = v; if (k !== "p") state.p = 1; if (k === "g") state.f = ""; writeState(k === "p"); render(); if (k === "p") window.scrollTo(0, 0); }

  function base(skip) {
    var toks = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    return DATA.filter(function (r) {
      if (skip !== "g" && state.g && r.g !== state.g) return false;
      if (skip !== "f" && state.f && r.f !== state.f) return false;
      if (skip !== "k" && state.k && r.k !== state.k) return false;
      if (!lenOk(r.d, state.len)) return false;
      if (!state.dated && r.s === "dated") return false;
      for (var i = 0; i < toks.length; i++) if (r._h.indexOf(toks[i]) < 0) return false;
      return true;
    });
  }
  function counts(rows, key) { var c = {}; rows.forEach(function (r) { if (r[key]) c[r[key]] = (c[r[key]] || 0) + 1; }); return c; }

  function opt(label, on, onclick, n) {
    var b = document.createElement("button");
    b.type = "button"; b.className = on ? "on" : ""; b.textContent = label;
    if (n != null) { var s = document.createElement("span"); s.className = "n"; s.textContent = n; b.appendChild(s); }
    b.addEventListener("click", onclick); return b;
  }
  function row(id, items) { var o = el(id); o.textContent = ""; items.forEach(function (x) { o.appendChild(x); }); }

  function renderControls() {
    var gc = counts(base("g"), "g");
    var games = Object.keys(gc).sort(function (a, b) { return gc[b] - gc[a]; });
    row("o-game", [opt("all", !state.g, function () { set("g", ""); })].concat(games.map(function (g) { return opt(GAME_LABEL[g] || g, state.g === g, function () { set("g", state.g === g ? "" : g); }, gc[g]); })));
    var fc = counts(base("f"), "f"), fmts = Object.keys(fc).sort(function (a, b) { return fc[b] - fc[a]; });
    el("c-format").style.display = fmts.length ? "" : "none";
    row("o-format", [opt("any", !state.f, function () { set("f", ""); })].concat(fmts.map(function (f) { return opt(f, state.f === f, function () { set("f", state.f === f ? "" : f); }, fc[f]); })));
    var kc = counts(base("k"), "k"), types = Object.keys(kc).sort(function (a, b) { return kc[b] - kc[a]; });
    row("o-type", [opt("any", !state.k, function () { set("k", ""); })].concat(types.map(function (k) { return opt(k, state.k === k, function () { set("k", state.k === k ? "" : k); }, kc[k]); })));
    row("o-len", LEN.map(function (x) { return opt(x[1], state.len === x[0], function () { set("len", x[0]); }); }));
    row("o-sort", SORT.map(function (x) { return opt(x[1], state.sort === x[0], function () { set("sort", x[0]); }); })
      .concat([opt(state.dated ? "including dated" : "hiding dated", state.dated, function () { set("dated", !state.dated); })]));
  }

  function card(r) {
    if (!ID_RE.test(r.i)) return "";
    var meta = "<b>" + esc(r.v) + " people</b>" + (r.m ? " · " + esc(r.m) + " months" : " · first pass") + " · " + esc(GAME_LABEL[r.g] || r.g) + (r.f ? " · " + esc(r.f) : "") + " · " + esc(r.k);
    return '<a class="card" href="/v/' + r.i + '/"><div class="thumb"><img loading="lazy" alt="" src="https://i.ytimg.com/vi/' + r.i + '/hq2.jpg" onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/' + r.i + '/mqdefault.jpg\'">' +
      (r.d != null ? '<span class="dur">' + esc(fmtDur(r.d)) + "</span>" : "") + '</div><div class="t">' + esc(r.t) + '</div><div class="ch">' + esc(r.c) +
      (r.y ? " · " + esc(r.y) : "") + "</div>" + (r.w ? '<div class="why">“' + esc(r.w) + '”</div>' : "") + '<div class="m">' + meta + "" + (r.s === "dated" ? ' <span class="flag">dated</span>' : "") + "</div></a>";
  }

  function render() {
    renderControls();
    var active = [state.g && (GAME_LABEL[state.g] || state.g), state.f, state.k, state.len !== "any" && state.len].filter(Boolean);
    if (el("fsum")) el("fsum").textContent = "Filters" + (active.length ? ": " + active.join(" · ") : "");
    var rows = base();
    var key = {lasting: function (r) { return -r.n; }, people: function (r) { return -r.v; },
               recent: function (r) { return r.z ? -parseInt(r.z.replace("-", ""), 10) : 0; }, "new": function (r) { return r.q ? -parseInt(r.q.replace(/-/g, ""), 10) : 0; }}[state.sort] || function (r) { return -r.n; };
    rows = rows.slice().sort(function (a, b) { return key(a) - key(b) || b.n - a.n; });
    var pages = Math.max(1, Math.ceil(rows.length / PAGE));
    if (state.p > pages) state.p = pages;
    var slice = rows.slice((state.p - 1) * PAGE, state.p * PAGE);
    el("count").textContent = rows.length.toLocaleString() + " of " + DATA.length.toLocaleString() + " videos" + (state.dated ? "" : " · dated deck techs, set reviews and prices hidden");
    el("grid").innerHTML = slice.length ? slice.map(card).join("") : '<p class="empty">Nothing matches. Try fewer filters.</p>';
    var pg = el("pager"); pg.textContent = "";
    if (pages > 1) {
      var prev = opt("← prev", false, function () { set("p", state.p - 1); }); if (state.p === 1) prev.disabled = true; pg.appendChild(prev);
      var nums = []; for (var i = 1; i <= pages; i++) if (i === 1 || i === pages || Math.abs(i - state.p) <= 2) nums.push(i);
      var last = 0; nums.forEach(function (n) { if (n - last > 1) { var s = document.createElement("span"); s.textContent = "…"; pg.appendChild(s); } pg.appendChild(opt(String(n), n === state.p, function () { set("p", n); })); last = n; });
      var next = opt("next →", false, function () { set("p", state.p + 1); }); if (state.p === pages) next.disabled = true; pg.appendChild(next);
    }
  }

  function init() {
    readState();
    var det = el("filters");
    if (det && window.matchMedia("(max-width:640px)").matches) det.open = !!(state.g || state.f || state.k || state.len !== "any" || state.sort !== "lasting");
    var q = el("q"); q.value = state.q;
    var t; q.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { set("q", q.value.trim()); }, 160); });
    document.addEventListener("keydown", function (e) { if (e.key === "/" && document.activeElement !== q) { e.preventDefault(); q.focus(); } });
    window.addEventListener("popstate", function () { readState(); q.value = state.q; render(); });
    fetch("/data/videos.json").then(function (r) { return r.json(); }).then(function (d) {
      DATA = d; DATA.forEach(function (r) { r._h = (r.t + " " + r.c + " " + (r.w || "") + " " + (r.f || "") + " " + r.k + " " + (GAME_LABEL[r.g] || r.g)).toLowerCase(); });
      render();
    });
  }
  init();
})();
