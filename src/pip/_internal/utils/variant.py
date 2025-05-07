from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING
import logging

from variantlib.api import get_variant_hashes_by_priority
from variantlib.loader import PluginLoader

if TYPE_CHECKING:
    from typing import Callable

    from pip._internal.models.wheel import Wheel

logger = logging.getLogger(__name__)


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
