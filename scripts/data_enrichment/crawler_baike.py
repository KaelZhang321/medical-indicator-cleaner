"""Crawl Baidu Baike (百度百科) for indicator aliases."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.utils import ensure_dir, setup_logger

logger = setup_logger("crawler_baike")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class BaikeCrawler:
    """Extract indicator aliases from Baidu Baike info boxes."""

    SEARCH_URL = "https://baike.baidu.com/search/word"

    def __init__(self, cache_dir: str = "data/enrichment/cache_baike", delay: float = 2.0) -> None:
        self.cache_dir = Path(cache_dir)
        ensure_dir(self.cache_dir)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get_cached(self, key: str) -> dict | None:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _set_cache(self, key: str, data: dict) -> None:
        path = self.cache_dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _safe_get(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=15, allow_redirects=True)
                if resp.status_code == 200:
                    time.sleep(self.delay)
                    return resp.text
                logger.warning("HTTP %d for %s", resp.status_code, url)
            except requests.RequestException as exc:
                logger.warning("Request error (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 ** (attempt + 1))
        return None

    def crawl_aliases(self, name: str) -> dict[str, Any]:
        """Search Baidu Baike for an indicator and extract aliases from info box."""
        cache_key = re.sub(r"[^\w]", "_", name)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        result: dict[str, Any] = {"query_name": name, "aliases": [], "english_name": ""}

        url = f"https://baike.baidu.com/item/{requests.utils.quote(name)}"
        html = self._safe_get(url)
        if not html:
            return result

        soup = BeautifulSoup(html, "lxml")

        # Extract from info box (基本信息栏)
        alias_keywords = ["别名", "又称", "又名", "简称", "别称"]
        english_keywords = ["外文名", "英文名", "英文"]

        for dt in soup.select("dt"):
            label = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(strip=True)

            if any(kw in label for kw in alias_keywords):
                aliases = [a.strip() for a in re.split(r"[;；,，、/]", value) if a.strip()]
                result["aliases"].extend(aliases)

            if any(kw in label for kw in english_keywords):
                result["english_name"] = value.strip()

        # Also try key-value style info box (newer baike layout)
        for item in soup.select("[class*='basicInfo'] .basicInfo-item"):
            label_el = item.select_one("[class*='itemName'], dt, .name")
            value_el = item.select_one("[class*='itemValue'], dd, .value")
            if not label_el or not value_el:
                continue
            label = label_el.get_text(strip=True)
            value = value_el.get_text(strip=True)

            if any(kw in label for kw in alias_keywords):
                aliases = [a.strip() for a in re.split(r"[;；,，、/]", value) if a.strip()]
                result["aliases"].extend(aliases)

            if any(kw in label for kw in english_keywords):
                result["english_name"] = value.strip()

        # Deduplicate aliases
        result["aliases"] = list(dict.fromkeys(result["aliases"]))

        self._set_cache(cache_key, result)
        if result["aliases"]:
            logger.info("Baike: %s → %d aliases", name, len(result["aliases"]))
        return result

    def crawl_all(self, names: list[str], output_path: str) -> list[dict]:
        """Batch crawl aliases for a list of indicator names."""
        results = []
        for name in tqdm(names, desc="爬取百度百科"):
            data = self.crawl_aliases(name)
            results.append(data)
        ensure_dir(Path(output_path).parent)
        Path(output_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Baike crawl saved to %s (%d results)", output_path, len(results))
        return results
