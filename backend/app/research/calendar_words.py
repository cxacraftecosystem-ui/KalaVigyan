from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

__all__ = [
    "CONTEXT_FREE_SEASON_WORDS",
    "EXCLUDING_BIGRAMS",
    "NEGATING_WORDS",
    "POINT_WORDS",
    "REGIONAL_MONTHS",
    "SEASONS",
    "SEASON_LABELS",
    "SEASON_WORDS",
    "SPAN_WORDS_AFTER",
    "SPAN_WORDS_BEFORE",
    "SPRING_WORDS_AFTER_REFUSED",
    "SPRING_WORDS_BEFORE",
]

SEASONS = ("MONSOON", "WINTER", "SUMMER", "SPRING", "AUTUMN", "PRE_MONSOON", "POST_MONSOON")
SEASON_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "MONSOON": "Monsoon",
        "WINTER": "Winter",
        "SUMMER": "Summer",
        "SPRING": "Spring",
        "AUTUMN": "Autumn",
        "PRE_MONSOON": "Pre-monsoon",
        "POST_MONSOON": "Post-monsoon",
    }
)
SEASON_WORDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "MONSOON": ("monsoon", "monsoons", "rainy season", "rainy months", "rains"),
        "WINTER": ("winter", "winters", "cold season"),
        "SUMMER": ("summer", "summers", "hot season"),
        "SPRING": ("spring", "springtime"),
        "AUTUMN": ("autumn",),
        "PRE_MONSOON": ("pre-monsoon", "pre monsoon"),
        "POST_MONSOON": ("post-monsoon", "post monsoon", "retreating monsoon"),
    }
)
CONTEXT_FREE_SEASON_WORDS = frozenset(word for words in SEASON_WORDS.values() for word in words) - {"spring"}
SPRING_WORDS_BEFORE = frozenset(
    {
        "in",
        "during",
        "the",
        "this",
        "each",
        "every",
        "early",
        "late",
        "mid",
        "and",
        "or",
        "of",
        "before",
        "after",
        "through",
        "until",
        "till",
        "by",
        "next",
        "last",
    }
)
SPRING_WORDS_AFTER_REFUSED = frozenset({"up", "back", "from", "into", "out", "water", "waters"})
REGIONAL_MONTHS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "chaitra": ("Chaitra", "Chait", "Chaita"),
        "vaishakha": ("Vaishakha", "Vaisakha", "Vaishakh", "Vaisakh", "Baisakh", "Baisakha", "Baishakh"),
        "jyeshtha": ("Jyeshtha", "Jyaistha", "Jyeshth", "Jeth", "Jaistha"),
        "ashadha": ("Ashadha", "Asadha", "Ashadh", "Asadh", "Asarh"),
        "shravana": ("Shravana", "Sravana", "Shravan", "Shraavana", "Sawan", "Saawan", "Savan"),
        "bhadrapada": ("Bhadrapada", "Bhadrapad", "Bhadra", "Bhadon", "Bhado"),
        "ashvin": ("Ashvin", "Ashvina", "Ashwin", "Asvina", "Aswin", "Asoj"),
        "kartika": ("Kartika", "Kartik", "Karthik", "Karthika", "Katik"),
        "margashirsha": ("Margashirsha", "Margashirsh", "Agrahayana", "Agahan", "Aghan", "Mangsir"),
        "pausha": ("Pausha", "Pausa", "Paush", "Poush"),
        "magha": ("Magha", "Magh", "Maagh"),
        "phalguna": ("Phalguna", "Phalgun", "Phagun", "Falgun"),
    }
)
SPAN_WORDS_AFTER = frozenset(
    {
        "months",
        "month",
        "season",
        "period",
        "rain",
        "rainfall",
        "of",
        "from",
        "between",
        "is",
        "are",
        "lasts",
        "runs",
        "spans",
        "extends",
        "falls",
        "fall",
        "comes",
        "brings",
        "bringing",
        "the",
        "its",
        "in",
        "with",
        "usually",
        "typically",
        "roughly",
        "about",
        "around",
        "mm",
        "cm",
    }
)
SPAN_WORDS_BEFORE = frozenset({"the", "a", "is", "are", "its", "of", "in"})
POINT_WORDS = frozenset(
    {
        "after",
        "before",
        "until",
        "till",
        "since",
        "outside",
        "except",
        "unlike",
        "beyond",
        "following",
        "preceding",
        "end",
        "start",
        "onset",
        "beginning",
        "early",
        "late",
        "mid",
    }
)
NEGATING_WORDS = frozenset(
    {
        "not",
        "no",
        "never",
        "nor",
        "neither",
        "without",
        "avoid",
        "avoided",
        "avoids",
        "stop",
        "stops",
        "stopped",
    }
)
EXCLUDING_BIGRAMS: Mapping[tuple[str, str], str] = MappingProxyType(
    {("rather", "than"): "not", ("other", "than"): "not", ("instead", "of"): "not"}
)
