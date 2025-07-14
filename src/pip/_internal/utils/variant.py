from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING
import logging

from pip._internal.build_env import BuildEnvironment
from pip._internal.metadata import FilesystemWheel, get_wheel_distribution

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable

    from pip._internal.package_finder import PackageFinder
    from pip._internal.models.link import Link
    from pip._internal.models.wheel import Wheel

try:
    from variantlib.api import get_variant_environment_dict
    from variantlib.api import get_variants_by_priority
    from variantlib.api import check_variant_supported
    from variantlib.constants import VARIANT_DIST_INFO_FILENAME
    from variantlib.variants_json import VariantsJson
    from variantlib.variant_dist_info import VariantDistInfo
    from variantlib.models.variant import VariantDescription
except ImportError:
    def get_variant_environment_dict(vdesc: Any) -> dict[str, str]:
        return {}

VARIANT_DESCRIPTIONS: dict[Link, VariantDescription] = {}

variantlib_logger = logging.getLogger("variantlib")
variantlib_logger.setLevel(logging.ERROR)


@dataclass
class VariantJson:
    url: str
    getter: Callable([str], dict)

    def json(self) -> dict:
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
def get_variants_json(variants_json: VariantJson) -> VariantsJson:
    return VariantsJson(variants_json.json())


@cache
def get_build_env(requires: list[str], finder: PackageFinder) -> BuildEnvironment:
    build_env = BuildEnvironment()
    finder.use_variants = False
    build_env.install_requirements(
        finder, requires, "normal", kind="variant providers"
    )
    finder.use_variants = True
    return build_env


@cache
def get_cached_variant_hashes_by_priority(
    variants_json: VariantJson | None,
    finder: PackageFinder,
) -> list[str]:
    if variants_json is None:
        return [None]

    variant_info = get_variants_json(variants_json)
    build_env = get_build_env(tuple(variant_info.get_provider_requires()), finder)

    with build_env:
        variants = list(
            get_variants_by_priority(
                variants_json=variant_info,
            )
        )
    return [*variants, None]


@cache
def store_variant_desc(
    link: Link,
    wheel: Wheel,
    variants_json: VariantJson | None,
) -> None:
    if wheel.variant_hash in (None, "00000000"):
        VARIANT_DESCRIPTIONS[link] = None
        return

    assert variants_json is not None
    parsed_json = get_variants_json(variants_json)
    VARIANT_DESCRIPTIONS[link] = parsed_json.variants[wheel.variant_hash]


def get_variant_description_for_link(link: Link) -> VariantDescription:
    return VARIANT_DESCRIPTIONS[link]


def variant_wheel_supported(wheel: Wheel, link: Link, finder: PackageFinder) -> bool:
    if wheel.variant_hash is None:
        VARIANT_DESCRIPTIONS[link] = None
        return True

    if link.scheme != "file":
        raise NotImplementedError

    wheel_dist = get_wheel_distribution(FilesystemWheel(link.file_path), "")
    variant_info = VariantDistInfo(wheel_dist.read_text(VARIANT_DIST_INFO_FILENAME))
    VARIANT_DESCRIPTIONS[link] = variant_info.variant_desc
    build_env = get_build_env(tuple(variant_info.get_provider_requires()), finder)

    with build_env:
        return check_variant_supported(variant_info=variant_info)
