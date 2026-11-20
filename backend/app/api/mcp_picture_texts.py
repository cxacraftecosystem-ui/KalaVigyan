from __future__ import annotations

__all__ = [
    "CONFIRMATION_FIELD",
    "DECLARATION_FIELD",
    "GIVE_DESCRIPTION",
    "LINK_STEP",
    "SHELL_STEP",
]

FORMATS = "PNG, JPEG, WebP or AVIF as they are; GIF as its first frame; HEIC, HEIF, TIFF or BMP made WebP; SVG cleaned"
GIVE_DESCRIPTION = (
    "Give up to ten pictures (photographs, drawings or AI-made illustrations) of one craft, each for its facts "
    "and optionally a stage, a material, a picture slot (MASTHEAD, RECORD) or a MISSING_PICTURE task. A picture "
    "already in the chat comes as image_url (fetched by the server, at most 10 MB) or image_base64 (at most 6 MB, "
    "12 MB together) with its caption and alt_text, under one declaration and the person's own words of "
    "confirmation. Ask the person first, in their words: that they took or made the picture or hold the right "
    "to share it, that the Centre may publish it without their name, which cannot be revoked once approved, and "
    "for an AI image the tool, model and prompt; never fill the declaration in for them. A picture still outside "
    "the chat comes as upload true: it returns a single-use link, valid for 30 minutes, where the person signs "
    "in, declares the picture and drops the file, and with a confirmed declaration also a presigned upload_url "
    f"to PUT the bytes to. Accepted: {FORMATS}. Every picture is checked before review: format, size, a repeat, "
    "and one look by the cheapest vision model for identity documents (Aadhaar, PAN, passports, any card with a "
    "face and a number), faces in AI images and unsafe content; a flagged picture always waits for an Admin, and "
    "location and camera details are removed. An AI image is always shown as an illustration, never of a real "
    "person, place or object. Each picture is answered on its own: shown, waiting, refused and why, or its slot."
)
DECLARATION_FIELD = (
    "Only after the person confirmed it in the chat: origin PHOTOGRAPH, DRAWING or AI_GENERATED, generator (the "
    "AI tool and model) for an AI image, rights_confirmed true (they took or made it, or hold the right to share "
    "it, and agree that the Centre publishes it without their name, which cannot be revoked once approved) and "
    "terms_version 2026-11-19"
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
