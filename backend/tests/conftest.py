import pytest
from sqlalchemy import text

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("test")
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    yield _db
    _db.session.rollback()
    tables = ", ".join(f'"{t.name}"' for t in reversed(_db.metadata.sorted_tables))
    _db.session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    _db.session.commit()


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture(autouse=True)
def _tmp_storage(app, tmp_path):
    app.config["LOCAL_STORAGE_DIR"] = str(tmp_path / "recordings")
    app.extensions.pop("qi_storage", None)
    yield
    app.extensions.pop("qi_storage", None)
