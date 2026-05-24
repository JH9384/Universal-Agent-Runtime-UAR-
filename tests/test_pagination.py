"""Tests for uar.core.pagination."""

import pytest

from uar.core.pagination import (
    CursorPaginator,
    CursorToken,
    maybe_paginate,
)


class TestCursorToken:
    def test_roundtrip(self):
        token = CursorToken(
            offset=20, page_size=10, checksum="abc", extra={"k": 1}
        )
        encoded = token.encode()
        decoded = CursorToken.decode(encoded)
        assert decoded.offset == 20
        assert decoded.page_size == 10
        assert decoded.checksum == "abc"
        assert decoded.extra == {"k": 1}

    def test_decode_padding(self):
        # Short tokens need padding
        token = CursorToken(offset=0, page_size=5, checksum="x", extra={})
        encoded = token.encode()
        decoded = CursorToken.decode(encoded)
        assert decoded.offset == 0


class TestCursorPaginator:
    def test_first_page(self):
        data = list(range(100))
        paginator = CursorPaginator(data, page_size=20)
        page = paginator.first_page()
        assert page.data == list(range(20))
        assert page.total == 100
        assert page.has_more is True
        assert page.next_cursor is not None
        assert page.previous_cursor is None

    def test_last_page(self):
        data = list(range(45))
        paginator = CursorPaginator(data, page_size=20)
        # page 1: 0-19, page 2: 20-39, page 3: 40-44
        p1 = paginator.first_page()
        p2 = paginator.next_page(p1.next_cursor)
        p3 = paginator.next_page(p2.next_cursor)
        assert p3.data == [40, 41, 42, 43, 44]
        assert p3.has_more is False
        assert p3.next_cursor is None
        assert p3.previous_cursor is not None

    def test_checksum_mismatch_raises(self):
        data = list(range(10))
        paginator = CursorPaginator(data, page_size=3)
        p1 = paginator.first_page()
        # Mutate data and create new paginator — old cursor is stale
        data.append(99)
        new_paginator = CursorPaginator(data, page_size=3)
        with pytest.raises(ValueError, match="checksum mismatch"):
            new_paginator.next_page(p1.next_cursor)

    def test_all_pages(self):
        data = list(range(25))
        paginator = CursorPaginator(data, page_size=10)
        pages = paginator.all_pages()
        assert len(pages) == 3
        assert pages[0].data == list(range(10))
        assert pages[1].data == list(range(10, 20))
        assert pages[2].data == list(range(20, 25))

    def test_empty_data(self):
        paginator = CursorPaginator([], page_size=10)
        page = paginator.first_page()
        assert page.data == []
        assert page.has_more is False
        assert page.next_cursor is None

    def test_page_size_one(self):
        data = ["a", "b", "c"]
        paginator = CursorPaginator(data, page_size=1)
        pages = paginator.all_pages()
        assert len(pages) == 3
        assert pages[0].data == ["a"]
        assert pages[1].data == ["b"]
        assert pages[2].data == ["c"]


class TestMaybePaginate:
    def test_first_page_without_cursor(self):
        data = list(range(50))
        page = maybe_paginate(data, cursor=None, page_size=20)
        assert page.data == list(range(20))
        assert page.has_more is True

    def test_next_page_with_cursor(self):
        data = list(range(50))
        p1 = maybe_paginate(data, cursor=None, page_size=20)
        p2 = maybe_paginate(data, cursor=p1.next_cursor, page_size=20)
        assert p2.data == list(range(20, 40))

    def test_extra_metadata(self):
        data = list(range(10))
        page = maybe_paginate(
            data, cursor=None, page_size=5, extra={"q": "test"}
        )
        token = CursorToken.decode(page.next_cursor)
        assert token.extra == {"q": "test"}
