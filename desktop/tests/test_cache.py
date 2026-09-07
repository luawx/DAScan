from plotdas_client.cache import CacheManager


def test_cache_paths_are_project_and_date_scoped(tmp_path):
    image, metadata = CacheManager(tmp_path).paths_for(
        "xinjing", "/srv/output/xinjing/20230308/images/120000_120100.png"
    )
    assert image.parent.name == "images"
    assert image.parent.parent.name == "20230308"
    assert metadata.parent.name == "metadata"
