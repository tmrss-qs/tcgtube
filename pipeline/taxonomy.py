"""Rules-based TCG taxonomy: game > format > type > level > shelf life.

Inputs are public metadata only (title, channel, subreddits the vouches came
from, publish year). The LLM pass in classify.py can override any field; these
rules are the fallback that works with no key.
"""
import re

GAMES = ["MTG", "Pokemon", "Yu-Gi-Oh", "Lorcana", "FAB", "One Piece", "General"]

GAME_RX = [  # explicit mentions in title/channel win over subreddit
    ("Pokemon", r"pok[eé]mon|pikachu|charizard|tcg pocket|\bptcg|\bpkmn"),
    ("Yu-Gi-Oh", r"yu-?gi-?oh|duel monsters|\bygo\b|master duel|duel links"),
    ("Lorcana", r"lorcana|illumineer"),
    ("FAB", r"flesh (?:and|&) blood|\bfab\b|\bfabtcg\b|legend story"),
    ("One Piece", r"one piece (?:tcg|card)|\bop\d\d\b|optcg"),
    ("MTG", r"\bmtg\b|magic:? the gathering|\bedh\b|commander|planeswalker|mtgo|mtg ?arena|\bcedh\b|tolarian|command zone|star ?city"),
]
GAME_RX = [(g, re.compile(rx, re.I)) for g, rx in GAME_RX]

FORMAT_RX = {
    "MTG": [
        ("cEDH", r"\bcedh\b|competitive (?:edh|commander)"),
        ("Commander", r"commander|\bedh\b|precon"),
        ("Limited", r"draft|sealed|limited|\bcube\b|prerelease|\blsv\b set review|\blrcast"),
        ("Standard", r"\bstandard\b"),
        ("Pioneer", r"pioneer"),
        ("Modern", r"\bmodern\b"),
        ("Legacy", r"\blegacy\b"),
        ("Vintage", r"vintage|power ?9|black lotus"),
        ("Pauper", r"pauper"),
        ("Arena", r"\barena\b|\bmtga\b|historic|alchemy|timeless"),
    ],
    "Pokemon": [("Pocket", r"tcg pocket|pok[eé]mon pocket"), ("Expanded", r"expanded"),
                ("GLC", r"\bglc\b|gym leader challenge"), ("Standard", r"standard|regionals|worlds|\bnaic\b|\beuic\b")],
    "FAB": [("Blitz", r"blitz"), ("Classic Constructed", r"classic constructed|\bcc\b"),
            ("Limited", r"draft|sealed|limited"), ("Living Legend", r"living legend")],
    "Yu-Gi-Oh": [("Master Duel", r"master duel"), ("Duel Links", r"duel links"), ("Goat", r"\bgoat\b"),
                 ("Edison", r"edison"), ("Advanced", r"\bycs\b|regional|wcq|meta|tier \d")],
    "Lorcana": [("Core", r"core|set championship|\bstandard\b"), ("Infinity", r"infinity")],
    "One Piece": [],
    "General": [],
}
FORMAT_RX = {g: [(f, re.compile(rx, re.I)) for f, rx in v] for g, v in FORMAT_RX.items()}

# Order matters: first match wins.
TYPE_RX = [
    ("music", r"official (?:music )?video|\blyrics?\b|\bremix\b|monstercat|\bost\b|soundtrack|theme song|\bamv\b|extended mix|\bnightcore\b|music video|\bsong\b|entrance theme|full album"),
    ("learn-to-play", r"how to play|learn to play|beginner|new player|getting started|how to start|your first|rules|tutorial|explained|basics|101\b|introduction|guide to|primer|for dummies"),
    ("coverage", r"\bvs\.?\b|versus|round \d|quarterfinal|semifinal|finals?\b|top 8|feature match|grand prix|\bgp\b|pro tour|\bscg\w*|regionals|nationals|worlds|invitational|championship|\bycs\b|\bwcq\b|calling|\bpt\b"),
    ("deck-tech", r"deck ?tech|decklist|deck list|deck guide|deck profile|budget deck|upgrad|primer|brew|\bdeck\b"),
    ("set-review", r"set review|spoilers?|preview|first look|limited review|card review|every card|\btier list\b"),
    ("finance", r"financ|price|\bspec\b|investment|investing|market|value|worth|buyout|reprint"),
    ("collecting", r"grad(?:ed|ing)|\bpsa\b|\bcgc\b|binder|sleev|storage|store your|opening|unboxing|booster box|\bpack\b|packs|collection|rare|fake|counterfeit|proxy|proxies|alter"),
    ("lore", r"\blore\b|story of|storyline|vorthos|history of .*(?:plane|world|character)"),
    ("essay", r"history|documentary|the story|essay|analysis|retrospective|why .* (?:is|are|was)|\bdesign\b|lessons|philosophy|theory|\bgdc\b|\btalk\b|keynote|interview|podcast"),
    ("strategy", r"strategy|tips|mistakes|how to (?:win|build|mulligan|improve|get better)|mulligan|sideboard|play better|theory|\bmath\b|probability|mana base|manabase|card advantage|tempo|archetype"),
    ("comedy", r"funny|parody|sketch|\blol\b|meme|when you|comedy|\bskit\b|animated|animation"),
]
TYPE_RX = [(t, re.compile(rx, re.I)) for t, rx in TYPE_RX]
TYPES = [t for t, _ in TYPE_RX] + ["other"]

ADV_RX = re.compile(r"advanced|competitive|\bcedh\b|pro tour|optimal|theory|deep dive|frank karsten|\bmath\b|probability|frame data|\bev\b", re.I)
BEG_RX = re.compile(r"beginner|new player|how to play|learn to play|getting started|basics|101\b|first deck|your first|for dummies|introduction", re.I)

# Content that goes stale as sets rotate and prices move.
DATED_TYPES = {"deck-tech", "set-review", "finance"}
DATED_FORMATS = {"Standard", "Pioneer", "Arena", "Pocket", "Core", "Master Duel", "Duel Links", "Advanced"}
EVERGREEN_TYPES = {"learn-to-play", "essay", "lore", "comedy", "collecting"}


def detect_game(title, channel, sub_games):
    # earliest explicit mention in the title wins ("Magic: The Gathering, Pokemon and other TCGs" -> MTG),
    # then the channel name, then the subreddits the vouches came from
    for text in (title or "", channel or ""):
        hits = [(m.start(), g) for g, rx in GAME_RX for m in [rx.search(text)] if m]
        if hits:
            return min(hits)[1]
    if sub_games:
        # majority game among the subreddits the vouches came from
        counts = {}
        for g in sub_games:
            counts[g] = counts.get(g, 0) + 1
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        return best
    return "General"


def detect_format(game, title):
    for f, rx in FORMAT_RX.get(game, []):
        if rx.search(title):
            return f
    return None


MUSIC_CHANNEL = re.compile(r"(?:vevo| - topic|\bmusic|\brecords)$", re.I)


def detect_type(title, channel=""):
    if MUSIC_CHANNEL.search((channel or "").strip()):
        return "music"
    text = f"{title} {channel}"
    for t, rx in TYPE_RX:
        if rx.search(text):
            return t
    return "other"


def detect_level(title, ctype):
    if BEG_RX.search(title) or ctype == "learn-to-play":
        return "beginner"
    if ADV_RX.search(title):
        return "advanced"
    return "all"


def shelf_life(ctype, fmt, published_year, last_vouch_year, now_year, dated_after_years=2):
    """evergreen | aging | dated. Uses the *last vouch* as a freshness signal:
    if people still recommend it, it isn't dead yet."""
    if ctype in EVERGREEN_TYPES:
        return "evergreen"
    ref = max(filter(None, [published_year, last_vouch_year]), default=None)
    rotating = ctype in DATED_TYPES or fmt in DATED_FORMATS
    if not rotating:
        return "evergreen"  # coverage, strategy, essays age well enough
    if ref is None:
        return "aging"
    age = now_year - ref
    if age <= 1:
        return "aging"
    return "dated" if age >= dated_after_years else "aging"


def classify(title, channel, sub_games, published_year=None, last_vouch_year=None, now_year=2026, dated_after_years=2):
    game = detect_game(title, channel, sub_games)
    fmt = detect_format(game, title)
    ctype = detect_type(title, channel)
    return {
        "game": game,
        "format": fmt,
        "type": ctype,
        "level": detect_level(title, ctype),
        "shelf_life": shelf_life(ctype, fmt, published_year, last_vouch_year, now_year, dated_after_years),
    }
