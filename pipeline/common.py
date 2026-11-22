"""Shared helpers: paths, config, YouTube id extraction."""
import os
import re

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA = os.path.join(ROOT, "data")

# YouTube link patterns -> 11-char video id. Playlists/channels are ignored.
YT_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:[^\s\]\)>]*?&(?:amp;)?)?v=|live/|embed/|shorts/|v/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
)


def extract_ids(text):
    """Unique video ids in order of appearance."""
    if not text or "yout" not in text:
        return []
    seen, out = set(), []
    for m in YT_RE.finditer(text):
        v = m.group(1)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def load_config(path=None):
    path = path or os.environ.get("TCGTUBE_CONFIG") or os.path.join(ROOT, "config", "tcg.yaml")
    with open(path) as fh:
        return yaml.safe_load(fh)
