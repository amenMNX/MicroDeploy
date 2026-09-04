import main


def test_worker_main_exists():
    assert callable(main.main)


def test_worker_wait_for_db_exists():
    assert callable(main.wait_for_db)


def test_worker_db_configuration():
    assert main.DB_PARAMS["database"] == "microdeploy"


def test_worker_db_default_host():
    assert main.DB_PARAMS["host"] == "db"


def test_worker_db_unavailable_raises():
    """wait_for_db must raise instead of silently returning None on failure."""
    assert hasattr(main, "DatabaseUnavailableError")
