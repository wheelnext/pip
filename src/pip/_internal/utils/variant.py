from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING
import json
import logging

from variantlib.api import get_variant_hashes_by_priority
from variantlib.api import check_variant_supported
from variantlib.constants import VARIANT_DIST_INFO_FILENAME
from variantlib.variants_json import VariantsJson
from variantlib.models.variant import VariantDescription

from pip._internal.metadata import FilesystemWheel, get_wheel_distribution

if TYPE_CHECKING:
    from typing import Callable

    from pip._internal.models.link import Link
    from pip._internal.models.wheel import Wheel

logger = logging.getLogger(__name__)

VARIANT_DESCRIPTIONS: dict[Link, VariantDescription] = {}


@dataclass
class VariantJson:
    url: str
    getter: Callable([str], dict)

    def json(self) -> dict:
        logger.info("Fetching %(url)s", {"url": self.url})
        return self.getter(self.url)

    def __hash__(self) -> int:
        return hash(self.url)


def get_variants_json_filename(wheel: Wheel) -> str:
    # these are normalized, but with .replace("_", "-")
    return (
        f"{wheel.name.replace("-", "_")}-{wheel.version.replace("-", "_")}-"
        "variants.json"
    )


@cache
def get_cached_variant_hashes_by_priority(
        variants_json: Optional[VariantJson] = None
        ) -> list[str]:
    if variants_json is None:
        return [None]

    parsed_json = variants_json.json()
    variants = list(get_variant_hashes_by_priority(variants_json=parsed_json))
    if variants:
        logger.info(f"Total Number of Compatible Variants: {len(variants):,}")  # noqa: G004
    return [*variants, None]


def get_variant_description_for_link(link: Link) -> VariantDescription:
    return VARIANT_DESCRIPTIONS[link]


def variant_wheel_supported(wheel: Wheel, link: Link) -> bool:
    if wheel.variant_hash is None:
        VARIANT_DESCRIPTIONS[link] = VariantDescription()
        return True

    if link.scheme != "file":
        raise NotImplementedError

    wheel_dist = get_wheel_distribution(FilesystemWheel(link.file_path), "")
    variant_json = VariantsJson(json.loads(wheel_dist.read_text(VARIANT_DIST_INFO_FILENAME)))
    VARIANT_DESCRIPTIONS[link] = next(iter(variant_json.variants.values()))
    return check_variant_supported(metadata=variant_json)
