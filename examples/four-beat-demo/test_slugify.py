from slugify import slugify


def test_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_collapses_runs():
    assert slugify("a  --  b") == "a-b"


def test_symbols_only_becomes_empty():
    assert slugify("!!!") == ""
