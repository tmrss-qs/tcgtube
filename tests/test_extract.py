from common import extract_ids


def test_forms():
    t = ("see https://www.youtube.com/watch?v=dQw4w9WgXcQ and youtu.be/AGXG5rNe_tI?t=30 "
         "https://m.youtube.com/watch?feature=share&v=wif9ppH5JpI https://youtube.com/shorts/HyUf987gJhI "
         "[x](https://www.youtube.com/watch?v=AsFrGTQlWck&amp;feature=player_detailpage#t=1179)")
    assert extract_ids(t) == ["dQw4w9WgXcQ", "AGXG5rNe_tI", "wif9ppH5JpI", "HyUf987gJhI", "AsFrGTQlWck"]


def test_dedupe_and_no_playlists():
    assert extract_ids("https://youtu.be/AGXG5rNe_tI https://youtu.be/AGXG5rNe_tI") == ["AGXG5rNe_tI"]
    assert extract_ids("https://www.youtube.com/playlist?list=PLBaWAg4scIN5mbh9gz1rzDA6r66H2TPOB") == []


def test_rejects_overlong_ids():
    assert extract_ids("https://youtu.be/AGXG5rNe_tIXYZ") == []
