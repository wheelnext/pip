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
    from variantlib.api import get_variant_environment_dict as _get_variant_environment_dict
    from variantlib.api import get_variants_by_priority
    from variantlib.api import check_variant_supported
    from variantlib.constants import VARIANT_DIST_INFO_FILENAME
    from variantlib.variants_json import VariantsJson
    from variantlib.variant_dist_info import VariantDistInfo
    from variantlib.models.variant import VariantDescription
except ImportError:
    def get_variant_environment_dict(vdesc: Any, variant_label: str | None) -> dict[str, str]:
        return {}
else:
    def get_variant_environment_dict(vdesc: Any, variant_label: str | None) -> dict[str, str]:
        assert vdesc.label == variant_label
        return _get_variant_environment_dict(vdesc)

VARIANT_DESCRIPTIONS: dict[Link, tuple[VariantDescription, str]] = {}

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
        f"{wheel.name.replace('-', '_')}-{wheel.version.replace('-', '_')}-"
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
        return []

    variant_info = get_variants_json(variants_json)
    build_env = get_build_env(tuple(variant_info.get_provider_requires()), finder)

    with build_env:
        return get_variants_by_priority(
            variants_json=variant_info,
        )


def store_variant_desc(
    link: Link,
    vdesc: VariantDescription | None,
    label: str | None,
) -> None:
    VARIANT_DESCRIPTIONS[link] = vdesc, label


def get_variant_description_for_link(link: Link) -> tuple[VariantDescription, str]:
    return VARIANT_DESCRIPTIONS.get(link, (None, None))


def variant_wheel_supported(wheel: Wheel, link: Link, finder: PackageFinder) -> bool:
    if wheel.variant_hash is None:
        VARIANT_DESCRIPTIONS[link] = None, None
        return True

    if link.scheme != "file":
        raise NotImplementedError

    wheel_dist = get_wheel_distribution(FilesystemWheel(link.file_path), "")
    variant_info = VariantDistInfo(wheel_dist.read_text(VARIANT_DIST_INFO_FILENAME))
    build_env = get_build_env(tuple(variant_info.get_provider_requires()), finder)

    with build_env:
        vdesc = check_variant_supported(variant_info=variant_info)

    VARIANT_DESCRIPTIONS[link] = vdesc, variant_info.variant_label
    return vdesc
