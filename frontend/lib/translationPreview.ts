import { LANGUAGE_NAMES, TEXT_SCRIPTS, type PageLanguages } from "@/lib/documentLanguages";
import type { DraftPassage } from "@/lib/documentVariant";
import type { MonographDocument } from "@/lib/monographDocument";

export const TRANSLATION_PREVIEW_SLUG = "Kutch-Bandhani";
export const TRANSLATION_PREVIEW_LANGUAGE = "hi";
export const TRANSLATION_PREVIEW_TITLE = "Kutch Bandhani in Hindi";

export const TRANSLATION_PREVIEW_PASSAGES: readonly DraftPassage[] = [
  {
    key: "overview-76dd355cec",
    english: [
      "The GI application describes Kutch Bandhani as an ancient dyeing technique in which cloth is tied in intricate patterns with nails, beads or grain so that dye cannot seep into the tied ",
      "areas."
    ],
    texts: [
      "GI आवेदन Kutch Bandhani को रंगाई की एक प्राचीन तकनीक बताता है, जिसमें कपड़े को कीलों, मनकों या अनाज के साथ जटिल नमूनों में बाँधा जाता है ताकि रंग बँधे हुए ",
      "हिस्सों में न रिस सके।"
    ]
  },
  {
    key: "overview-b55d18a9bd",
    english: [
      "Bandhani is a tie-dye craft in which many parts of the cloth are tied tightly with thread to resist dyes, creating dot-like puckered ",
      "designs."
    ],
    texts: [
      "Bandhani बाँधकर रंगने का एक शिल्प है, जिसमें रंगों को रोकने के लिए कपड़े के कई हिस्सों को धागे से कसकर बाँधा जाता है, जिससे बिंदुओं जैसे उभरे हुए ",
      "नमूने बनते हैं।"
    ]
  },
  {
    key: "overview-f2e5d51065",
    english: ["Bandhani in its many variations is identified by light circular or square repeating motifs on a dark ", "ground."],
    texts: ["अपने अनेक रूपों में Bandhani की पहचान गहरी पृष्ठभूमि पर हल्के, गोल या चौकोर, बार-बार दोहराए जाने वाले ", "अलंकरणों से होती है।"]
  }
];

export function previewLanguages(document: MonographDocument): PageLanguages {
  const passages = document.translation?.passages ?? 0;
  const translated = document.translation?.translated ?? 0;
  const hindi = LANGUAGE_NAMES.hi;
  const gujarati = LANGUAGE_NAMES.gu;
  return {
    schemaVersion: 1,
    subject: { kind: document.subjectKind, slug: document.subjectSlug },
    languages: [
      { code: "gu", label: gujarati.label, autonym: gujarati.autonym, script: TEXT_SCRIPTS.gu, direction: "ltr", passages, translated: 0, offered: true },
      { code: "hi", label: hindi.label, autonym: hindi.autonym, script: TEXT_SCRIPTS.hi, direction: "ltr", passages, translated, offered: true }
    ]
  };
}
