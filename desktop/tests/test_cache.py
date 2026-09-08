from plotdas_client.cache import CacheManager


def test_cache_paths_are_project_and_date_scoped(tmp_path):
    image, metadata = CacheManager(tmp_path).paths_for(
        "xinjing", "/srv/output/xinjing/20230308/images/120000_120100.png"
    )
    assert image.parent.name == "images"
    assert image.parent.parent.name == "20230308"
    assert metadata.parent.name == "metadata"


def test_cache_limit_is_enforced_per_project(tmp_path):
    cache = CacheManager(tmp_path, max_bytes_per_project=10)
    old_image, _ = cache.paths_for("alpha", "/output/20230308/old.png")
    new_image, _ = cache.paths_for("alpha", "/output/20230308/new.png")
    other_image, _ = cache.paths_for("beta", "/output/20230308/other.png")
    for path in (old_image, new_image, other_image):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"12345678")
    old_image.touch()
    new_image.touch()

    cache.enforce_limit("alpha", protected=(new_image,))

    assert not old_image.exists()
    assert new_image.exists()
    assert other_image.exists()


def test_clear_cache_removes_files(tmp_path):
    cache = CacheManager(tmp_path)
    image, metadata = cache.paths_for("alpha", "/output/20230308/a.png")
    image.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"image")
    metadata.write_text("{}", encoding="utf-8")

    assert cache.clear() == 2
    assert not image.exists()
    assert not metadata.exists()


def test_cache_cleanup_never_removes_active_download_files(tmp_path):
    cache = CacheManager(tmp_path, max_bytes_per_project=1)
    image, _ = cache.paths_for("alpha", "/output/20230308/a.png")
    partial = image.with_suffix(image.suffix + ".part")
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"active download")

    cache.enforce_limit("alpha")
    removed = cache.clear()

    assert removed == 0
    assert partial.exists()
