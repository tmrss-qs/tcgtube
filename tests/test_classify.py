import classify as c


def test_stances():
    assert c.heuristic_stance("I am a bot, beep boop", "x") == "bot"
    assert c.heuristic_stance("anything", "AutoModerator", ["AutoModerator"]) == "bot"
    assert c.heuristic_stance("anything", "MTGCardFetcherBot") == "bot"
    assert c.heuristic_stance("I just uploaded my new video on Modern burn, please subscribe!") == "self_promo"
    assert c.heuristic_stance("Pure clickbait, don't watch it") == "criticize"
    assert c.heuristic_stance("Highly recommend this, it explains the stack really well") == "recommend"
    assert c.heuristic_stance("obligatory lol") == "joke"
    assert c.heuristic_stance("Here's the clip: https://youtu.be/AGXG5rNe_tI") == "cite"


def test_quote_hygiene_no_usernames_no_urls_short():
    body = ("Thanks /u/SomeUser and u/other_guy! @handle123 This video by [LSV](https://youtube.com/watch?v=AGXG5rNe_tI) "
            "is the best explanation of drafting I've ever seen, honestly start here if you want to learn. " * 3)
    q = c.clean_quote(body)
    assert q and len(q) <= 201
    for bad in ("SomeUser", "other_guy", "handle123", "http", "youtube.com", "youtu.be"):
        assert bad not in q


def test_quote_drops_deleted_and_tiny():
    assert c.clean_quote("[deleted]") == ""
    assert c.clean_quote("[removed]") == ""
    assert c.clean_quote("https://youtu.be/AGXG5rNe_tI") == ""


def test_permalink():
    assert c.permalink("EDH", "t3_abc12", "def34") == "https://www.reddit.com/r/EDH/comments/abc12/_/def34/"
    assert c.permalink("EDH", "", "def34") is None


def test_pick_quotes_distinct_authors_prefers_recommend():
    vs = [
        {"author": "a", "body": "Neutral link to the match coverage from that weekend, round three", "stance": "cite", "score": 50,
         "subreddit": "magicTCG", "link_id": "t3_x", "id": "1", "created_utc": 1},
        {"author": "b", "body": "Honestly the best video on mulligans ever made, watch it twice", "stance": "recommend", "score": 2,
         "subreddit": "magicTCG", "link_id": "t3_y", "id": "2", "created_utc": 2},
        {"author": "b", "body": "Again, the best video on mulligans ever made, really helpful", "stance": "recommend", "score": 1,
         "subreddit": "magicTCG", "link_id": "t3_z", "id": "3", "created_utc": 3},
    ]
    qs = c.pick_quotes(vs, "AGXG5rNe_tI", 3)
    assert len(qs) == 2 and "mulligans" in qs[0]["q"]
    assert all("author" not in q for q in qs)


def test_llm_provider_off_without_key(monkeypatch):
    monkeypatch.delenv("TCGTUBE_LLM_PROVIDER", raising=False)
    assert not c.provider_available()
    monkeypatch.setenv("TCGTUBE_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not c.provider_available()


def test_llm_path_uses_cache_and_batches(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "DATA", str(tmp_path))
    monkeypatch.setenv("TCGTUBE_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    calls = []

    def fake(items):
        calls.append(items)
        return {k: "joke" for k, _ in items}
    monkeypatch.setattr(c, "_llm_batch", fake)
    vs = [{"id": "c1", "video_id": "AGXG5rNe_tI", "author": "a", "body": "great video"}]
    c.label_vouches(vs, log=lambda *a: None)
    assert vs[0]["stance"] == "joke" and vs[0]["stance_src"] == "llm" and len(calls) == 1
    vs2 = [{"id": "c1", "video_id": "AGXG5rNe_tI", "author": "a", "body": "great video"}]
    c.label_vouches(vs2, log=lambda *a: None)
    assert vs2[0]["stance"] == "joke" and len(calls) == 1  # served from cache
