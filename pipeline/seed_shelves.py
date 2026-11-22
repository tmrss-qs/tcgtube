#!/usr/bin/env python3
"""Seed config/shelves.yaml with DRAFT picks from the current rankings.

Never overwrites a file that already has shelves unless --force. Tom edits the
YAML by hand afterwards (reorder, swap picks, write notes, set draft: false).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT  # noqa: E402
import yaml  # noqa: E402

SHELVES = [
    ("learn-magic", "Learn Magic in six videos", "From never played to sitting down at a draft table.",
     lambda v: v["game"] == "MTG" and v["type"] == "learn-to-play", 6),
    ("commander-canon", "The Commander canon", "The deckbuilding and table-politics videos EDH players keep pointing each other to.",
     lambda v: v["game"] == "MTG" and v["format"] in ("Commander", "cEDH") and v["type"] != "coverage", 8),
    ("coverage-moments", "Coverage moments people still link", "Matches and plays that come up in threads years after they happened.",
     lambda v: v["type"] == "coverage", 8),
    ("fab-from-zero", "Flesh and Blood from zero", "Rules, classes and the value math, in a sensible order.",
     lambda v: v["game"] == "FAB", 6),
    ("pokemon-cards", "Pokémon cards: storing, grading, not getting scammed", "For collectors more than players.",
     lambda v: v["game"] == "Pokemon", 6),
    ("essays", "Long reads, but videos", "Essays, design talks and histories worth an evening.",
     lambda v: v["type"] in ("essay", "lore") and (v["duration_s"] or 0) >= 900, 8),
    ("newer-games", "Starting Lorcana, One Piece or Yu-Gi-Oh!", "The first videos people recommend for the other big games.",
     lambda v: v["game"] in ("Lorcana", "One Piece", "Yu-Gi-Oh") and v["type"] in ("learn-to-play", "strategy", "essay"), 6),
]


def main():
    path = os.path.join(ROOT, "config", "shelves.yaml")
    cur = yaml.safe_load(open(path)) if os.path.exists(path) else None
    if cur and cur.get("shelves") and "--force" not in sys.argv:
        print("shelves.yaml already has shelves; use --force to reseed")
        return
    videos = json.load(open(os.path.join(ROOT, "corpus", "videos.json")))
    out = []
    used = set()
    for slug, title, intro, pred, n in SHELVES:
        picks = [v for v in videos if pred(v) and v["shelf_life"] != "dated" and v["id"] not in used][:n]
        used |= {v["id"] for v in picks}
        if picks:
            out.append({"slug": slug, "title": title, "intro": intro, "draft": True,
                        "videos": [{"id": v["id"], "note": None, "_title": v["title"]} for v in picks]})
    header = ("# Curated shelves. DRAFT: auto-seeded from the rankings on build day for Tom to edit.\n"
              "# Edit freely: reorder, swap ids, add a one-line `note`, set `draft: false` when a shelf is yours.\n"
              "# `_title` is a reminder only (ignored by the build).\n")
    with open(path, "w") as fh:
        fh.write(header)
        yaml.safe_dump({"shelves": out}, fh, sort_keys=False, allow_unicode=True, width=120)
    print(f"seeded {len(out)} draft shelves -> {path}")


if __name__ == "__main__":
    main()
