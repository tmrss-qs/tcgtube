import datetime as dt
import json
import os

import pytest

import aggregate


def ts(y, m, d=5):
    return int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())


def test_video_stats_three_people_three_months():
    vs = [{"author": "a", "created_utc": ts(2020, 1)}, {"author": "b", "created_utc": ts(2020, 1, 20)},
          {"author": "c", "created_utc": ts(2020, 2)}]
    s = aggregate.video_stats(vs, 3, 3)
    assert s["vouchers"] == 3 and s["months"] == 2 and s["qualified_ts"] is None
    vs.append({"author": "a", "created_utc": ts(2021, 6)})
    s = aggregate.video_stats(vs, 3, 3)
    assert s["months"] == 3 and s["qualified_ts"] == ts(2021, 6)  # qualifies the moment both bars are met
    assert s["first"] == "2020-01" and s["last"] == "2021-06"


def test_same_person_many_months_does_not_qualify():
    vs = [{"author": "a", "created_utc": ts(2020, m)} for m in range(1, 13)]
    assert aggregate.video_stats(vs, 3, 3)["qualified_ts"] is None


def test_p90_floor():
    assert aggregate.p90([]) == 1.0
    assert aggregate.p90([0.2]) == 1.0
    assert aggregate.p90(list(range(1, 11))) == 9


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Run aggregate.main end-to-end on synthetic vouches, offline."""
    data = tmp_path / "data"
    (data / "vouches_arctic").mkdir(parents=True)
    corpus = tmp_path / "corpus"
    cfg = tmp_path / "tcg.yaml"
    cfg.write_text("""
name: T
base_url: https://example.test
tagline: t
subreddits:
  - {name: magicTCG, game: MTG, start: 2020-01}
  - {name: FleshandBloodTCG, game: FAB, start: 2020-01}
ranking: {min_vouchers: 3, min_months: 3, count_stances: [recommend, cite], dated_after_years: 2}
exclude_channels: {handles: ["@tmrss"], names: ["tmrss"]}
deny_video_ids: [dQw4w9WgXcQ]
bot_authors: [AutoModerator]
""")
    monkeypatch.setenv("TCGTUBE_CONFIG", str(cfg))
    monkeypatch.setenv("TCGTUBE_OFFLINE", "1")
    monkeypatch.delenv("TCGTUBE_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(aggregate, "DATA", str(data))
    monkeypatch.setattr(aggregate, "CORPUS", str(corpus))
    import classify
    import enrich
    monkeypatch.setattr(classify, "DATA", str(data))
    monkeypatch.setattr(enrich, "DATA", str(data))
    rows = []

    def add(vid, author, y, m, sub="magicTCG", body="Great video, highly recommend it"):
        rows.append({"video_id": vid, "kind": "comment", "author": author, "created_utc": ts(y, m), "score": 3,
                     "id": f"{vid}{author}{y}{m}", "link_id": "t3_p", "subreddit": sub, "body": body})
    good, mtg2, fab, bot, selfv, music, mine, deny = ("A" * 11, "B" * 11, "C" * 11, "D" * 11, "E" * 11, "F" * 11, "G" * 11, "dQw4w9WgXcQ")
    for i, a in enumerate("pqrstu"):
        add(good, a, 2020, 1 + i)
    for i, a in enumerate("pqr"):
        add(mtg2, a, 2021, 1 + i)
    for i, a in enumerate("pqr"):
        add(fab, a, 2022, 1 + i, sub="FleshandBloodTCG")
    for i in range(5):
        add(bot, "AutoModerator", 2020, 1 + i)
    add(selfv, "ChannelGuy", 2020, 1); add(selfv, "ChannelGuy", 2020, 2); add(selfv, "x", 2020, 3); add(selfv, "y", 2020, 4)
    for i, a in enumerate("pqr"):
        add(music, a, 2020, 1 + i)
        add(mine, a, 2020, 1 + i)
        add(deny, a, 2020, 1 + i)
    with open(data / "vouches_arctic" / "magicTCG.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    meta = {good: {"title": "How to draft in Magic", "channel": "LSV"}, mtg2: {"title": "Modern burn primer MTG", "channel": "X"},
            fab: {"title": "Which class should you play?", "channel": "MajiinBae"}, bot: {"title": "Bot pick MTG", "channel": "Z"},
            selfv: {"title": "My Commander deck MTG", "channel": "Channel Guy"},
            music: {"title": "Noisestorm - Crab Rave [Monstercat Release]", "channel": "Monstercat"},
            mine: {"title": "Pauper league MTG", "channel": "tmrss"}}
    for v in meta.values():
        v.update({"status": "ok", "duration_s": 600, "published": "2020-01-01", "src": "test"})
    (data / "meta_cache.json").write_text(json.dumps(meta))
    aggregate.main()
    return {v["id"]: v for v in json.load(open(corpus / "videos.json"))}, json.load(open(corpus / "stats.json")), locals()


def test_end_to_end_filters_and_order(sandbox):
    vids, stats, L = sandbox
    assert L["good"] in vids and L["mtg2"] in vids and L["fab"] in vids
    for k in ("bot", "selfv", "music", "mine", "deny"):
        assert L[k] not in vids, k
    assert stats["drops"].get("coi_excluded_channel") == 1
    assert stats["drops"].get("music_meme") == 1
    g = vids[L["good"]]
    assert g["months"] == 6 and g["vouchers"] == 6
    # per-game normalisation: the only FAB video tops its game, so norm is comparable to MTG's best
    assert vids[L["fab"]]["game"] == "FAB" and vids[L["fab"]]["norm"] >= vids[L["mtg2"]]["norm"]


def test_public_output_has_no_usernames(sandbox):
    vids, _, _ = sandbox
    blob = json.dumps(vids)
    for name in ("ChannelGuy", "AutoModerator", '"author"'):
        assert name not in blob
    for v in vids.values():
        for q in v["quotes"]:
            assert len(q["q"]) <= 201 and q["url"].startswith("https://www.reddit.com/r/")
