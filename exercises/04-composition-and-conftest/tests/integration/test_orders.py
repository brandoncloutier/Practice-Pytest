def test_app_config_live_mode_is_true_in_integration_tests(app_config):
    assert app_config.live_mode is True


def test_app_config_still_has_root_attributes(app_config):
    # The override extends the root SimpleNamespace rather than replacing
    # it, so attributes set in the root conftest.py's app_config (like
    # `env`) should still be present here too.
    assert app_config.env == "test"
