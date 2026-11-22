import json
import os

import build_site


EVIL = '<script>alert(1)</script><img src=x onerror=alert(2)>'


def corpus(tmp_path, monkeypatch):
    root = tmp_path
    (root / "corpus").mkdir()
    (root / "config").mkdir()
    v = {"id": "AAAAAAAAAAA", "title": EVIL, "channel": EVIL, "duration_s": 754, "published": "2020-01-01", "game": "MTG",
         "format": "Commander", "type": "strategy", "level": "all", "shelf_life": "evergreen", "vouchers": 5, "months": 4,
         "first": "2020-01", "last": "2024-03", "qualified": "2026-11-18", "subs": ["EDH"], "score": 40.5, "legacy": False,
         "meta_src": "test", "norm": 1.0, "also": ["BAD\"ID<x>"],
         "quotes": [{"q": EVIL, "url": "javascript:alert(3)", "sub": "EDH", "ym": "2021-02"},
                    {"q": "fine", "url": "https://www.reddit.com/r/EDH/comments/a/_/b/", "sub": "EDH", "ym": "2021-03"}]}
    bad = dict(v, id="../../etc/x")
    (root / "corpus" / "videos.json").write_text(json.dumps([v, bad]))
    (root / "corpus" / "stats.json").write_text(json.dumps({"built": "2026-11-22", "videos": 1, "by_game": {"MTG": 1}, "rule": "r", "drops": {}}))
    (root / "corpus" / "coverage.json").write_text(json.dumps([{"subreddit": "EDH", "game": "MTG", "start": "2010-01", "windows_done": 1,
                                                                 "windows_expected": 2, "windows_failed": 0, "complete": False,
                                                                 "links": 3, "by_year": {"2020": 3}}]))
    (root / "config" / "shelves.yaml").write_text("shelves:\n  - {slug: s, title: S, draft: true, intro: i, videos: [AAAAAAAAAAA, ZZZZZZZZZZZ]}\n")
    cfgp = root / "config" / "tcg.yaml"
    cfgp.write_text("name: TCGTube\nbase_url: https://example.test\ntagline: t\nranking: {min_vouchers: 3, min_months: 3}\nshelf_file: config/shelves.yaml\n")
    monkeypatch.setenv("TCGTUBE_CONFIG", str(cfgp))
    monkeypatch.setattr(build_site, "ROOT", str(root))
    monkeypatch.setattr(build_site, "OUT", str(root / "site"))
    return root


def test_everything_escaped(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    build_site.main()
    site = root / "site"
    for rel in ("index.html", "v/AAAAAAAAAAA/index.html", "shelves/index.html", "rss.xml"):
        s = (site / rel).read_text()
        assert "<script>alert" not in s and "<img src=x" not in s, rel
    vp = (site / "v/AAAAAAAAAAA/index.html").read_text()
    assert "javascript:alert" not in vp                       # unsafe permalink dropped
    assert "https://www.reddit.com/r/EDH/comments/a/_/b/" in vp
    assert "youtube-nocookie.com/embed/" in vp and "<iframe" not in vp  # click-to-load only
    assert 'property="og:title"' in vp and 'og:image' in vp
    assert not os.path.exists(site / "etc")                   # invalid id never becomes a path
    assert "BAD" not in vp


def test_client_data_and_rss(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    build_site.main()
    d = json.loads((root / "site" / "data" / "videos.json").read_text())
    assert [r["i"] for r in d] == ["AAAAAAAAAAA"]
    rss = (root / "site" / "rss.xml").read_text()
    assert "New this week" in rss and "tcgtube-week-2026-W47" in rss and "Fri, 22 Nov" not in rss
    assert "Sun, 22 Nov 2026" in rss  # week ending at build date, real date


def test_app_js_escapes():
    js = open(os.path.join(os.path.dirname(__file__), "..", "web", "app.js")).read()
    assert "function (s) { return String(s == null" in js and "esc(r.t)" in js and "esc(r.c)" in js and "esc(r.w)" in js
