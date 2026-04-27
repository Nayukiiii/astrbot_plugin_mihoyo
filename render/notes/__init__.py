"""Compatibility exports for legacy render.notes imports."""

from ..genshin.notes import render_genshin_notes
from ..starrail.notes import render_starrail_notes

__all__ = ["render_genshin_notes", "render_starrail_notes"]
