def test_app_importable() -> None:
    from app.main import app

    assert app.title == "codegraph"
