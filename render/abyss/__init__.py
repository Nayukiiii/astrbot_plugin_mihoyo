"""Compatibility exports for legacy render.abyss imports."""

from ..genshin.abyss import render_spiral_abyss
from ..starrail.endgame import (
    render_apocalyptic_shadow,
    render_challenge_peak,
    render_forgotten_hall,
    render_pure_fiction,
)

__all__ = [
    "render_apocalyptic_shadow",
    "render_challenge_peak",
    "render_forgotten_hall",
    "render_pure_fiction",
    "render_spiral_abyss",
]
