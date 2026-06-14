from collections import Counter

from app.services.skillgap import RESOURCE_CATALOG, roadmap_from_missing_counts


def test_priority_follows_frequency():
    counts = Counter({"docker": 5, "kubernetes": 3, "rust": 1})
    roadmap = roadmap_from_missing_counts("u1", "backend engineer", counts)
    by_skill = {item.skill: item.priority for item in roadmap.items}
    assert by_skill["docker"] == 1  # most frequent gap = top priority
    assert by_skill["docker"] < by_skill["kubernetes"] <= by_skill["rust"]


def test_unknown_skill_gets_fallback_resources():
    roadmap = roadmap_from_missing_counts("u1", "any", Counter({"quantum basket weaving": 2}))
    item = roadmap.items[0]
    assert item.skill not in RESOURCE_CATALOG
    assert item.resources  # search fallbacks provided
    assert all(url.startswith("https://") for url in item.resources)
