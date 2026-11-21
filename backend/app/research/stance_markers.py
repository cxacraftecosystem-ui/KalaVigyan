from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .gate_thrift import NEGATION
from .hedges import HINDI_APPROXIMATION, HINDI_DOUBT, hedged
from .quotes import normalise_quote_text

__all__ = [
    "HEDGE_MARKERS",
    "NEGATION_MARKERS",
    "Markers",
    "hedge_marked",
    "negation_marked",
]

JOINERS = str.maketrans({chr(0x200C): None, chr(0x200D): None})


@dataclass(frozen=True)
class Markers:
    words: frozenset[str]
    endings: tuple[str, ...] = ()


def _markers(words: Iterable[str], endings: Iterable[str] = ()) -> Markers:
    return Markers(frozenset(_folded(word) for word in words), tuple(_folded(ending) for ending in endings))


def _folded(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(JOINERS)


NEGATION_MARKERS: Mapping[str, Markers] = MappingProxyType(
    {
        "hi": _markers(["नहीं", "नही", "न", "ना", "मत", "बिना", "बगैर", "बग़ैर"]),
        "mr": _markers(
            [
                "नाही",
                "नाहीत",
                "नव्हता",
                "नव्हती",
                "नव्हते",
                "नसतो",
                "नसते",
                "नसतात",
                "नसलेला",
                "नसलेली",
                "नसलेले",
                "नसलेल्या",
                "नसून",
                "नसावा",
                "नये",
                "नको",
                "न",
                "ना",
                "विना",
                "शिवाय",
            ]
        ),
        "gu": _markers(["નથી", "ન", "ના", "નહીં", "નહિ", "નહોતું", "નહોતો", "નહોતી", "નહોતા", "વિના", "વગર"]),
        "pa": _markers(["ਨਹੀਂ", "ਨਹੀ", "ਨਾ", "ਨ", "ਮਤ", "ਬਿਨਾਂ", "ਬਿਨਾ", "ਬਗੈਰ", "ਬਗ਼ੈਰ"]),
        "bn": _markers(["না", "নয়", "নেই", "নাই", "নি", "ছাড়া", "বিনা", "ব্যতীত"], ["নি"]),
        "as": _markers(
            ["নহয়", "নাই", "নাছিল", "নোহোৱা", "নোহোৱাকৈ", "নকৰে", "নকৰা", "নকৰিলে", "নাথাকে", "না", "বিনা", "অবিহনে"]
        ),
        "ta": _markers(
            [
                "இல்லை",
                "அல்ல",
                "அல்லாத",
                "அல்லாமல்",
                "இல்லாமல்",
                "இல்லாத",
                "இன்றி",
                "வேண்டாம்",
                "கூடாது",
                "மாட்டார்",
                "மாட்டான்",
                "மாட்டாள்",
                "மாட்டாது",
                "மாட்டேன்",
                "மாட்டார்கள்",
            ],
            ["ல்லை", "ாது", "ாமல்", "ாத"],
        ),
        "te": _markers(["లేదు", "కాదు", "లేని", "లేకుండా", "వద్దు", "కూడదు", "కాకుండా"], ["దు"]),
        "kn": _markers(["ಇಲ್ಲ", "ಅಲ್ಲ", "ಬೇಡ", "ಕೂಡದು", "ಇಲ್ಲದೆ", "ಇಲ್ಲದ", "ಅಲ್ಲದ", "ಅಲ್ಲದೆ"], ["ಲ್ಲ"]),
        "ml": _markers(["ഇല്ല", "അല്ല", "ഇല്ലാതെ", "ഇല്ലാത്ത", "അല്ലാത്ത", "അല്ലാതെ", "വേണ്ട", "കൂടാ"], ["ല്ല", "ാതെ", "ാത്ത"]),
        "or": _markers(
            ["ନାହିଁ", "ନାହି", "ନୁହେଁ", "ନୁହେ", "ନା", "ନ", "ବିନା", "ବ୍ୟତୀତ", "ନଥିଲା", "ନଥାଏ", "ନଥିବା", "ନଥିଲେ", "ନକରି", "ନକରିବା"]
        ),
        "ur": _markers(["نہیں", "نهیں", "نہ", "نه", "مت", "بغیر", "بنا", "نا"]),
    }
)
HEDGE_MARKERS: Mapping[str, Markers] = MappingProxyType(
    {
        "hi": _markers(
            [
                "शायद",
                "संभवतः",
                "संभवत",
                "सम्भवतः",
                "संभव",
                "सम्भव",
                "संभावना",
                "लगभग",
                "करीब",
                "क़रीब",
                "तकरीबन",
                "तक़रीबन",
                "अनुमानित",
                "अनुमानतः",
                "आसपास",
                "माना",
                "मानी",
                "माने",
                "कहा",
                "बताया",
                "प्रतीत",
                "सकता",
                "सकती",
                "सकते",
                "लगता",
                "लगती",
                "लगते",
            ]
        ),
        "mr": _markers(
            [
                "कदाचित",
                "बहुधा",
                "बहुतेक",
                "शक्य",
                "शक्यता",
                "संभव",
                "संभवतः",
                "सुमारे",
                "सुमार",
                "जवळपास",
                "जवळजवळ",
                "अंदाजे",
                "अंदाजित",
                "मानले",
                "मानला",
                "मानली",
                "मानतात",
                "म्हणतात",
                "म्हटले",
                "असावा",
                "असावी",
                "असावे",
                "असाव्यात",
                "शकतो",
                "शकते",
                "शकतात",
                "शकेल",
                "साधारणपणे",
                "आसपास",
            ]
        ),
        "gu": _markers(
            [
                "કદાચ",
                "સંભવતઃ",
                "સંભવત",
                "સંભવ",
                "શક્ય",
                "શક્યતા",
                "લગભગ",
                "આશરે",
                "અંદાજે",
                "અંદાજિત",
                "આસપાસ",
                "મનાય",
                "માનવામાં",
                "કહેવાય",
                "શકે",
                "શકાય",
                "હશે",
            ]
        ),
        "pa": _markers(
            [
                "ਸ਼ਾਇਦ",
                "ਸੰਭਵ",
                "ਸੰਭਵਤ",
                "ਸੰਭਾਵਨਾ",
                "ਸੰਭਾਵੀ",
                "ਲਗਭਗ",
                "ਤਕਰੀਬਨ",
                "ਕਰੀਬ",
                "ਅੰਦਾਜ਼ਨ",
                "ਅਨੁਮਾਨਿਤ",
                "ਆਸ-ਪਾਸ",
                "ਆਸਪਾਸ",
                "ਮੰਨਿਆ",
                "ਕਿਹਾ",
                "ਸਕਦਾ",
                "ਸਕਦੀ",
                "ਸਕਦੇ",
            ]
        ),
        "bn": _markers(
            [
                "সম্ভবত",
                "হয়তো",
                "হয়ত",
                "সম্ভব",
                "সম্ভাবনা",
                "প্রায়",
                "আনুমানিক",
                "আনুমানিকভাবে",
                "মোটামুটি",
                "কাছাকাছি",
                "মনে",
                "বলা",
                "পারে",
                "পারেন",
            ]
        ),
        "as": _markers(
            [
                "হয়তো",
                "হয়তু",
                "সম্ভৱতঃ",
                "সম্ভৱত",
                "সম্ভৱ",
                "সম্ভাৱনা",
                "প্ৰায়",
                "প্রায়",
                "আনুমানিক",
                "মোটামুটি",
                "পাৰে",
                "পাৰি",
                "বুলি",
            ]
        ),
        "ta": _markers(
            [
                "ஒருவேளை",
                "சுமார்",
                "கிட்டத்தட்ட",
                "ஏறத்தாழ",
                "தோராயமாக",
                "சாத்தியம்",
                "சாத்தியமான",
                "அளவில்",
                "நம்பப்படுகிறது",
                "கூறப்படுகிறது",
                "கருதப்படுகிறது",
            ],
            ["லாம்", "கூடும்"],
        ),
        "te": _markers(
            [
                "బహుశా",
                "సుమారు",
                "సుమారుగా",
                "దాదాపు",
                "దగ్గర",
                "అంచనా",
                "సాధ్యం",
                "సాధ్యమే",
                "నమ్ముతారు",
                "అంటారు",
                "చెబుతారు",
                "భావిస్తారు",
            ],
            ["వచ్చు", "వచ్చును"],
        ),
        "kn": _markers(
            [
                "ಬಹುಶಃ",
                "ಬಹುಶ",
                "ಸುಮಾರು",
                "ಸರಿಸುಮಾರು",
                "ಅಂದಾಜು",
                "ಸುಮಾರಾಗಿ",
                "ಹತ್ತಿರ",
                "ಸಾಧ್ಯತೆ",
                "ಸಾಧ್ಯ",
                "ನಂಬಲಾಗಿದೆ",
                "ಹೇಳಲಾಗುತ್ತದೆ",
                "ಎನ್ನಲಾಗಿದೆ",
            ],
            ["ಬಹುದು"],
        ),
        "ml": _markers(
            [
                "ഒരുപക്ഷേ",
                "ഒരുപക്ഷെ",
                "ഏകദേശം",
                "ഏതാണ്ട്",
                "ഉദ്ദേശം",
                "സാധ്യത",
                "സാധ്യമാണ്",
                "ചുറ്റും",
                "അടുത്ത്",
                "വിശ്വസിക്കപ്പെടുന്നു",
                "പറയപ്പെടുന്നു",
                "കരുതപ്പെടുന്നു",
                "കരുതുന്നു",
            ],
            ["കാം", "വാം", "യാം", "ക്കാം"],
        ),
        "or": _markers(
            ["ବୋଧହୁଏ", "ସମ୍ଭବତଃ", "ସମ୍ଭବତ", "ସମ୍ଭବ", "ସମ୍ଭାବନା", "ପ୍ରାୟ", "ପ୍ରାୟତଃ", "ଆନୁମାନିକ", "ପାଖାପାଖି", "ବିଶ୍ୱାସ", "କୁହାଯାଏ"],
            ["ପାରେ", "ପାରନ୍ତି"],
        ),
        "ur": _markers(
            [
                "شاید",
                "ممکن",
                "ممکنہ",
                "غالباً",
                "غالبا",
                "تقریباً",
                "تقریبا",
                "لگ بھگ",
                "قریب",
                "اندازاً",
                "اندازا",
                "اندازے",
                "سکتا",
                "سکتی",
                "سکتے",
                "مانا",
                "مانی",
                "کہا",
                "خیال",
            ]
        ),
    }
)


def negation_marked(text: str, language: str) -> bool:
    if language not in NEGATION_MARKERS:
        return NEGATION.search(normalise_quote_text(text)) is not None
    return _carries(text, NEGATION_MARKERS[language])


def hedge_marked(text: str, language: str) -> bool:
    if language not in HEDGE_MARKERS:
        return hedged(text)
    folded = normalise_quote_text(text)
    if language == "hi" and (HINDI_DOUBT.search(folded) or HINDI_APPROXIMATION.search(folded)):
        return True
    return _carries(text, HEDGE_MARKERS[language])


def _carries(text: str, markers: Markers) -> bool:
    words = _words(text)
    joined = f" {' '.join(words)} "
    phrases = [marker for marker in markers.words if " " in marker]
    if markers.words & set(words) or any(f" {phrase} " in joined for phrase in phrases):
        return True
    return any(
        word.endswith(ending) and len(word) > len(ending) for word in words for ending in markers.endings
    )


def _words(text: str) -> list[str]:
    stripped = (_bare(word) for word in normalise_quote_text(text).translate(JOINERS).split())
    return [word for word in stripped if word]


def _bare(word: str) -> str:
    start, end = 0, len(word)
    while start < end and unicodedata.category(word[start]).startswith(("P", "S")):
        start += 1
    while end > start and unicodedata.category(word[end - 1]).startswith(("P", "S")):
        end -= 1
    return word[start:end]
