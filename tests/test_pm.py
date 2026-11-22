import build_site


CFG = {"name": "TCGTube", "base_url": "https://example.test", "tagline": "t"}


def test_pm_curated_pages_escaped_and_dead_skipped():
    doc = {"shelves": [{"slug": "ai-product", "title": "AI <b>product</b>", "intro": "i", "draft": True, "videos": [
        {"id": "LCEmiRjPEtQ", "title": "<script>x()</script>", "channel": "YC", "duration_s": 2372, "note": "<img onerror=1>"},
        {"id": "zjkBMFhNj_g", "title": "Intro", "channel": "AK", "duration_s": 3588, "dead": True},
        {"id": "../../bad", "title": "bad", "channel": "x"}]}]}
    pages = build_site.build_pm(CFG, doc)
    assert set(pages) == {"pm/index.html", "pm/v/LCEmiRjPEtQ/index.html"}
    for html in pages.values():
        assert "<script>x()" not in html and "<img onerror" not in html and "<b>product" not in html
    idx = pages["pm/index.html"]
    assert "DRAFT STARTER PICKS" in idx and "hand-picked" in idx
    assert "youtube-nocookie.com/embed/" in pages["pm/v/LCEmiRjPEtQ/index.html"]


def test_pm_nav_present():
    assert 'href="/pm/"' in build_site.page(CFG, "x", "", desc="d")
