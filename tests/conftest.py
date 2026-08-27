from __future__ import annotations

import pytest

from gsis_notifier.models import Article, GeneratedDraft


@pytest.fixture
def article() -> Article:
    return Article(
        doi="10.1080/10095020.2026.2709960",
        title="A verified geospatial test article",
        link="https://www.tandfonline.com/doi/full/10.1080/10095020.2026.2709960",
        abstract=(
            "This study maps urban heat using satellite imagery and evaluates "
            "spatial patterns across three districts."
        ),
        keywords=["urban heat", "satellite imagery", "spatial patterns", "remote sensing"],
        published_online="2026-08-20",
    )


@pytest.fixture
def draft() -> GeneratedDraft:
    return GeneratedDraft(
        emoji="🛰️",
        english_intro=(
            "This study maps #urban_heat with #satellite_imagery and evaluates "
            "#spatial_patterns across three districts using #remote_sensing."
        ),
        chinese_intro=(
            "本研究利用 #卫星影像 绘制 #城市热 环境，并通过 #遥感 评估三个区域的 #空间格局。"
        ),
    )
