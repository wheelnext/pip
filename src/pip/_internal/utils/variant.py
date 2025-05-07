from __future__ import annotations

from functools import cache
import logging

from variantlib.api import get_variant_hashes_by_priority
from variantlib.loader import PluginLoader

from pip._internal.configuration import Configuration
from pip._internal.exceptions import ConfigurationError, PipError

logger = logging.getLogger(__name__)


class VariantJson(dict):
    def __hash__(self):
        return hash(tuple(self.get("variants")))


@cache
def get_cached_variant_hashes_by_priority(
        variants_json: Optional[VariantJson] = None
        ) -> list[str]:
    if variants_json is None:
        return [None]

    loader = PluginLoader()
    for provider_info in variants_json.get("providers", {}).values():
        loader.load_plugin(provider_info["plugin-api"])

    variants = list(get_variant_hashes_by_priority(variants_json=variants_json,
                                                   plugin_loader=loader))
    if variants:
        logger.info(f"Total Number of Compatible Variants: {len(variants):,}")  # noqa: G004
    return [*variants, None]
