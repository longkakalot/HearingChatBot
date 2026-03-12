# modules/page_router.py
from __future__ import annotations

from typing import Optional, Dict, Any


DEFAULT_PAGE_ROUTER = {
    "audiogram_page_index": 0,   # page 1 (0-based)
    "tymp_page_index": 1,        # page 2 (0-based)
    "reflex_page_index": None,   # chưa dùng ở Phase 1
}


def get_default_page_router() -> Dict[str, Any]:
    return DEFAULT_PAGE_ROUTER.copy()


def get_tymp_page_index(router: Optional[Dict[str, Any]] = None) -> int:
    router = router or DEFAULT_PAGE_ROUTER
    return int(router.get("tymp_page_index", 1))


def get_audiogram_page_index(router: Optional[Dict[str, Any]] = None) -> int:
    router = router or DEFAULT_PAGE_ROUTER
    return int(router.get("audiogram_page_index", 0))


def get_reflex_page_index(router: Optional[Dict[str, Any]] = None):
    router = router or DEFAULT_PAGE_ROUTER
    return router.get("reflex_page_index", None)