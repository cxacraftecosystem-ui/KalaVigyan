from __future__ import annotations

from datetime import date

from pydantic import Field, PrivateAttr

from app.research.base import ContractModel
from app.research.crafts import SLUG_MAX_CHARS
from app.services.field_photo_plates import ClearedPhoto, cleared_photos
from app.services.field_photo_thumbnails import PhotoThumbnail, field_photo_thumbnails
from app.services.object_store import media_bucket
from app.services.open_work_subjects import subject_by_key

from .mcp_protocol import ToolImage
from .mcp_tool_base import PICTURES, Arguments, Tool, ToolContext

__all__ = ["DESCRIPTION", "FIELD_PHOTO_TOOLS", "PLACE_STEP", "FieldPhotos", "ListFieldPhotos"]

CRAFT = "craft"
LIMIT_DEFAULT = 12
LIMIT_MAX = 24
DESCRIPTION = (
    "Lists the field photographs from KalaVigyan's field portals that a craft's page may show: only those "
    "already published on the craft's page, never an artisan's identity photograph. Each comes with its label, "
    "caption, alt text, credit, size and its address on the site, and the result shows each one as a "
    "thumbnail captioned with its label. A page's layout entry places one by its label, with its chapter, "
    "order and role (HERO for the masthead, OPENER, PLATE or FIGURE) and optionally a size, crop or caption. "
    "The site draws it with its credit as listed, in a page preview's pictures and on the published page."
)
PLACE_STEP = (
    "Look at each thumbnail and caption a photograph from what it shows, then place it by its label in the "
    "page's layout, where its chapter's story needs it; a page shows each picture once, and the preview's "
    "pictures draw it in its place."
)
LISTED = "{shown} of {total} field photographs of {slug} the page may show."
SEEN = " {seen} of them are shown below as thumbnails, each captioned with its label."
UNSEEN = (
    " {unseen} could not be shown as thumbnails just now; each opens at its picture_url, and the preview's "
    "pictures draw it where the layout places it."
)


class ListFieldPhotos(Arguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, description="The craft's slug")
    offset: int = Field(default=0, ge=0, description="Photographs to skip, for the next page of the list")
    limit: int = Field(default=LIMIT_DEFAULT, ge=1, le=LIMIT_MAX)


class FieldPhoto(ContractModel):
    label: str
    caption: str
    alt: str
    credit: str
    width: int
    height: int
    taken_on: date | None
    picture_url: str


class FieldPhotos(ContractModel):
    craft_slug: str
    photos: list[FieldPhoto]
    total: int
    next_offset: int | None
    message: str
    next_step: str
    _images: list[ToolImage] = PrivateAttr(default_factory=list)

    def showing(self, thumbnails: list[PhotoThumbnail]) -> FieldPhotos:
        self._images = [
            ToolImage(caption=f"{shown.label}: {shown.caption}", data=shown.data, mime=shown.mime)
            for shown in thumbnails
        ]
        return self

    def tool_images(self) -> list[ToolImage]:
        return list(self._images)


async def _list_field_photos(context: ToolContext, arguments: ListFieldPhotos) -> FieldPhotos:
    subject = await subject_by_key(context.session, CRAFT, arguments.craft_slug)
    photos, total = await cleared_photos(
        context.session, subject, limit=arguments.limit, offset=arguments.offset
    )
    objects = media_bucket()
    thumbnails = (
        await field_photo_thumbnails(context.session, photos, objects)
        if objects is not None and photos
        else []
    )
    following = arguments.offset + len(photos)
    reply = FieldPhotos(
        craft_slug=subject.slug,
        photos=[_listed(photo, context.site) for photo in photos],
        total=total,
        next_offset=following if following < total else None,
        message=_message(len(photos), total, subject.slug, len(thumbnails)),
        next_step=PLACE_STEP,
    )
    return reply.showing(thumbnails)


def _message(shown: int, total: int, slug: str, seen: int) -> str:
    said = LISTED.format(shown=shown, total=total, slug=slug)
    said += SEEN.format(seen=seen) if seen else ""
    return said + (UNSEEN.format(unseen=shown - seen) if seen < shown else "")


def _listed(photo: ClearedPhoto, site: str) -> FieldPhoto:
    return FieldPhoto(
        label=photo.label,
        caption=photo.caption,
        alt=photo.alt,
        credit=photo.credit,
        width=photo.width,
        height=photo.height,
        taken_on=photo.taken_on,
        picture_url=f"{site.rstrip('/')}{photo.src}",
    )


FIELD_PHOTO_TOOLS: tuple[Tool, ...] = (
    Tool(
        "list_field_photos",
        "List a craft's field photographs",
        DESCRIPTION,
        ListFieldPhotos,
        FieldPhotos,
        _list_field_photos,
        group=PICTURES,
    ),
)
