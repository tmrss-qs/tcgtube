import taxonomy as t


def test_game_earliest_mention_and_subreddit_fallback():
    assert t.detect_game("Everyday Products for Magic: The Gathering, Pokemon, and other TCG Players", "Tolarian", []) == "MTG"
    assert t.detect_game("The CORRECT Way To Store Pokemon Cards in a Binder", "Deep Pocket Monster", []) == "Pokemon"
    assert t.detect_game("Which class should you play?", "MajiinBae", ["FAB", "FAB", "MTG"]) == "FAB"
    assert t.detect_game("Random", "Someone", []) == "General"


def test_format_type_level():
    c = t.classify("How To Build Your First Commander Deck | Magic: The Gathering", "Tolarian Community College", [])
    assert c["game"] == "MTG" and c["format"] == "Commander" and c["level"] == "beginner"
    assert t.detect_type("Noisestorm - Crab Rave [Monstercat Release]") == "music"
    assert t.detect_type("Bobby Roode - Glorious Domination (Entrance Theme)", "WWE Music") == "music"
    assert t.detect_type("Darude - Sandstorm", "Darude - Topic") == "music"
    assert t.detect_type("SCGLA - Legacy - Round 3 - Gregory Hatch vs Chris Kapica") == "coverage"
    assert t.detect_type("Shaking Graded Pokemon Cards Causes DAMAGE?!") == "collecting"


def test_shelf_life_rotation_aware():
    assert t.shelf_life("deck-tech", "Standard", 2019, 2019, 2026) == "dated"
    assert t.shelf_life("deck-tech", "Standard", 2019, 2026, 2026) == "aging"  # still being recommended
    assert t.shelf_life("learn-to-play", None, 2012, 2013, 2026) == "evergreen"
    assert t.shelf_life("coverage", "Legacy", 2006, 2010, 2026) == "evergreen"
    assert t.shelf_life("strategy", "Pioneer", 2018, 2018, 2026) == "dated"
