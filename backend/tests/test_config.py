from app.config import normalize_db_url


def test_normalize_db_url():
    assert normalize_db_url("postgres://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert normalize_db_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert normalize_db_url("postgresql+psycopg://x") == "postgresql+psycopg://x"


def test_gunicorn_config_is_single_gevent_worker():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "gconf", Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.workers == 1
    assert "gevent" in mod.worker_class.lower()
