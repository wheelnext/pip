from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING
import logging

from variantlib.api import get_variant_hashes_by_priority
from variantlib.loader import PluginLoader

from pip._internal.configuration import Configuration
from pip._internal.exceptions import ConfigurationError, PipError

if TYPE_CHECKING:
    from typing import Callable

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


@cache
def get_cached_variant_hashes_by_priority(
        variants_json: Optional[VariantJson] = None
        ) -> list[str]:
    if variants_json is None:
        return [None]

    parsed_json = variants_json.json()

    loader = PluginLoader()
    for provider_info in parsed_json.get("providers", {}).values():
        loader.load_plugin(provider_info["plugin-api"])

    variants = list(get_variant_hashes_by_priority(variants_json=parsed_json,
                                                   plugin_loader=loader))
    if variants:
        logger.info(f"Total Number of Compatible Variants: {len(variants):,}")  # noqa: G004
    return [*variants, None]
