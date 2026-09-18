from io import BytesIO

import pytest

from catchain.storage.object_store import LocalObjectStore


def test_local_object_store_is_immutable_and_hash_checked(tmp_path):
    store = LocalObjectStore(tmp_path)
    content = b"immutable document"
    digest = __import__("hashlib").sha256(content).hexdigest()

    first = store.put_immutable("raw/acr/project/document.pdf", BytesIO(content), digest)
    second = store.put_immutable("raw/acr/project/document.pdf", BytesIO(content), digest)

    assert first.created is True
    assert second.created is False
    assert store.open("raw/acr/project/document.pdf").read() == content
    with pytest.raises(ValueError, match="does not match"):
        store.put_immutable("raw/acr/project/bad.pdf", BytesIO(b"bad"), digest)


def test_local_object_store_rejects_traversal(tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(ValueError, match="traversal"):
        store.put_immutable("../secret", BytesIO(b"x"), "a" * 64)

