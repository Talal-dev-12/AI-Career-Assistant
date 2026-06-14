from app.services.matching import canonicalize, compute_match, extract_skills


def test_java_does_not_match_inside_javascript():
    skills = extract_skills("We use JavaScript and TypeScript daily")
    assert "javascript" in skills
    assert "java" not in skills


def test_aliases_map_to_canonical_skills():
    assert canonicalize(["PostgreSQL", "k8s", "PyTorch"]) == {
        "sql",
        "kubernetes",
        "deep learning",
    }


def test_compute_match_overlap_and_missing():
    profile = {"skills": ["Python", "FastAPI"], "locations": [], "target_roles": []}
    match = compute_match(
        "u1",
        profile,
        "ext-1",
        "Backend Engineer",
        "Requirements: Python, FastAPI, Docker, Kubernetes",
        None,
    )
    assert match.skill_overlap == ["fastapi", "python"]
    assert match.missing_skills == ["docker", "kubernetes"]
    assert 0 < match.score < 100


def test_location_and_role_bonuses_increase_score():
    plain = {"skills": ["Python"]}
    boosted = {
        "skills": ["Python"],
        "locations": ["Lahore"],
        "target_roles": ["Backend Engineer"],
    }
    job = ("ext-1", "Backend Engineer", "We need Python", "Lahore, Pakistan")
    low = compute_match("u1", plain, *job)
    high = compute_match("u1", boosted, *job)
    assert high.score == low.score + 30.0
