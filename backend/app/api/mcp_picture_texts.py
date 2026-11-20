from __future__ import annotations

__all__ = [
    "CONFIRMATION_FIELD",
    "DECLARATION_FIELD",
    "GIVES_DESCRIPTION",
    "GIVE_DESCRIPTION",
    "LINK_STEP",
    "SHARED_DECLARATION_FIELD",
    "SHELL_STEP",
    "START_DESCRIPTION",
]

FORMATS = "PNG, JPEG, WebP or AVIF as they are; GIF as its first frame; HEIC, HEIF, TIFF or BMP made WebP; SVG cleaned"
SCREENS = (
    "Every picture is checked before review: its format and size, a repeat of a picture KalaVigyan holds, and one "
    "look by the cheapest vision model for identity documents (Aadhaar, PAN, passports, any card with a face and "
    "a number), faces in AI images and unsafe content. A flagged picture always waits for an Admin, with the "
    "reasons; location and camera details are removed."
)
START_DESCRIPTION = (
    "Start giving a picture (a photograph, a drawing or an AI-made illustration) of a craft, for one to twenty "
    "of its facts and optionally one of its stages, one of its materials or a picture slot of its page "
    "(MASTHEAD, RECORD), or a MISSING_PICTURE task from list_open_work. The picture travels outside the chat: "
    "this returns a single-use link to KalaVigyan, valid for 30 minutes and tied to this signed-in person, where "
    "they sign in, declare what the picture is (for an AI image the tool, model and prompt) and that they hold "
    "the rights, see it as it will be shown, and drop the file, from a phone too. An agent with a shell may "
    "instead pass the declaration here, after the person has confirmed it, and gets a presigned upload_url for "
    "the same slot: PUT the file's bytes to it. Whichever is used first closes the slot. When the picture is in "
    f"the chat already, use give_image instead. Accepted: {FORMATS}. An AI image is always shown as an "
    "illustration, never as a photograph, and never of a real person, place or object."
)
GIVE_DESCRIPTION = (
    "Give one picture that is already in the chat, for example one an AI tool made here, to a craft of "
    "KalaVigyan: pass it as image_url (an https link KalaVigyan's server fetches, at most 10 MB) or as "
    "image_base64 (at most 6 MB), with the declaration the person confirmed in this chat and their words of "
    "confirmation. Ask the person first, in their words: that they took or made the picture or hold the right to "
    "share it, that the Centre may publish it without their name, which cannot be revoked once approved, and "
    "for an AI image the tool and model and the prompt. Never fill the declaration in for them. The picture may "
    f"show a stage, a material, a picture slot or a MISSING_PICTURE task. Accepted: {FORMATS}. {SCREENS} The "
    "result says for the picture whether it is shown, waits for review or was refused, and why."
)
GIVES_DESCRIPTION = (
    "Give up to ten pictures of one craft under one declaration the person confirmed in this chat: the origin, "
    "for AI images the tool and model, and the rights; each picture carries its own caption, description, "
    "facts, prompt for an AI image, and stage, material, picture slot or task, and comes as image_url or "
    f"image_base64 (12 MB together at most). Each is checked and reviewed on its own. {SCREENS}"
)
DECLARATION_FIELD = (
    "Only after the person confirmed it in the chat: origin PHOTOGRAPH, DRAWING or AI_GENERATED, generator and "
    "prompt for an AI image, caption, altText, rightsConfirmed true (they took or made it, or hold the right to "
    "share it, and agree that the Centre publishes it without their name, which cannot be revoked once "
    "approved) and termsVersion 2026-11-19"
)
SHARED_DECLARATION_FIELD = (
    "Only after the person confirmed it in the chat: origin PHOTOGRAPH, DRAWING or AI_GENERATED, generator (the "
    "AI tool and model) for AI images, rightsConfirmed true and termsVersion 2026-11-19"
)
CONFIRMATION_FIELD = (
    "The person's own words in this chat confirming the declaration, quoted; it is kept with the pictures under "
    "their account"
)
SHELL_STEP = (
    "PUT the picture's bytes to upload_url within 30 minutes, for example curl --upload-file picture.png "
    "'<upload_url>'; or send the person the link. The slot works once."
)
LINK_STEP = (
    "Send the person the link. They sign in, declare the picture and its rights, see it as it will be shown, "
    "and drop the file within 30 minutes; it works once."
)
