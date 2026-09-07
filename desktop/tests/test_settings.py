from plotdas_client.config import AppSettings, SettingsStore


def test_prefetch_count_is_persisted_and_does_not_change_connection_identity(tmp_path):
    store = SettingsStore(tmp_path)
    store.save(AppSettings(prefetch_count=3))
    store.save_prefetch_count(7)
    assert store.load().prefetch_count == 7
    assert AppSettings(prefetch_count=1) == AppSettings(prefetch_count=9)


def test_prefetch_count_is_clamped(tmp_path):
    store = SettingsStore(tmp_path)
    store.save_prefetch_count(100)
    assert store.load().prefetch_count == 20


def test_transfer_options_are_persisted(tmp_path):
    store = SettingsStore(tmp_path)
    store.save(
        AppSettings(
            max_background_transfers=4,
            prefetch_count=5,
            show_transfer_queue=True,
            active_project="alpha",
            data_source="/output/alpha",
        )
    )

    settings = store.load()
    assert settings.max_background_transfers == 4
    assert settings.prefetch_count == 5
    assert settings.show_transfer_queue is True
    assert settings.active_project == "alpha"
    assert settings.data_source == "/output/alpha"


def test_cache_limit_defaults_to_one_gb_and_is_persisted(tmp_path):
    store = SettingsStore(tmp_path)
    assert store.load().cache_limit_gb == 1.0
    store.save(AppSettings(cache_limit_gb=2.5))
    assert store.load().cache_limit_gb == 2.5
