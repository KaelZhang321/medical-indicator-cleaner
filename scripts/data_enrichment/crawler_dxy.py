"""Crawl DXY (丁香园) lab test encyclopedia for indicator metadata."""
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

logger = setup_logger("crawler_dxy")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class DxyCrawler:
    """Crawl DXY lab-test pages for aliases and reference ranges."""

    SEARCH_URL = "https://dxy.com/search"
    BASE_URL = "https://dxy.com"

    def __init__(self, cache_dir: str = "data/enrichment/cache_dxy", delay: float = 1.5) -> None:
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
        """HTTP GET with retry and rate limit."""
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    time.sleep(self.delay)
                    return resp.text
                logger.warning("HTTP %d for %s", resp.status_code, url)
            except requests.RequestException as exc:
                logger.warning("Request error (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 ** (attempt + 1))
        return None

    def search_indicator(self, name: str) -> str | None:
        """Search DXY for an indicator name and return the detail page URL."""
        url = f"{self.SEARCH_URL}?keyword={requests.utils.quote(name)}&type=lab"
        html = self._safe_get(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        # Look for lab-test result links
        for link in soup.select("a[href*='/lab-test/']"):
            href = link.get("href", "")
            if href.startswith("/"):
                href = self.BASE_URL + href
            return href
        return None

    def parse_detail_page(self, html: str) -> dict[str, Any]:
        """Extract structured data from a DXY lab-test detail page."""
        soup = BeautifulSoup(html, "lxml")
        result: dict[str, Any] = {
            "chinese_name": "",
            "english_name": "",
            "abbreviation": "",
            "aliases": [],
            "reference_ranges": [],
            "clinical_significance": "",
        }

        # Title / name
        title_el = soup.select_one("h1") or soup.select_one(".name")
        if title_el:
            result["chinese_name"] = title_el.get_text(strip=True)

        # Info table rows (varies by page structure)
        for row in soup.select("tr, .info-item, .detail-item"):
            text = row.get_text(separator="|", strip=True)
            lower = text.lower()
            if "英文" in text or "english" in lower:
                parts = text.split("|")
                if len(parts) >= 2:
                    result["english_name"] = parts[-1].strip()
            if "缩写" in text or "简称" in text:
                parts = text.split("|")
                if len(parts) >= 2:
                    result["abbreviation"] = parts[-1].strip()
            if "别名" in text or "又称" in text or "又名" in text:
                parts = text.split("|")
                if len(parts) >= 2:
                    aliases_raw = parts[-1].strip()
                    result["aliases"] = [a.strip() for a in re.split(r"[;；,，、/]", aliases_raw) if a.strip()]

        # Reference range table
        for table in soup.select("table"):
            headers = [th.get_text(strip=True) for th in table.select("th")]
            if any("参考" in h or "范围" in h or "正常" in h for h in headers):
                for tr in table.select("tbody tr, tr"):
                    cells = [td.get_text(strip=True) for td in tr.select("td")]
                    if len(cells) >= 2:
                        range_text = cells[-1] if cells[-1] else cells[-2]
                        range_match = re.search(r"([\d.]+)\s*[-~～]\s*([\d.]+)", range_text)
                        if range_match:
                            result["reference_ranges"].append({
                                "condition": cells[0] if len(cells) > 2 else "通用",
                                "ref_min": float(range_match.group(1)),
                                "ref_max": float(range_match.group(2)),
                                "raw": range_text,
                            })

        # Clinical significance
        for section in soup.select(".clinical, .significance, [class*='meaning']"):
            result["clinical_significance"] = section.get_text(strip=True)[:500]
            break

        return result

    def crawl_indicator(self, name: str) -> dict[str, Any] | None:
        """Search + parse one indicator. Uses cache to avoid repeat requests."""
        cache_key = re.sub(r"[^\w]", "_", name)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        detail_url = self.search_indicator(name)
        if not detail_url:
            logger.info("No DXY page found for: %s", name)
            return None

        html = self._safe_get(detail_url)
        if not html:
            return None

        data = self.parse_detail_page(html)
        data["source_url"] = detail_url
        data["query_name"] = name
        self._set_cache(cache_key, data)
        logger.info("Crawled DXY: %s → %s", name, data.get("chinese_name", ""))
        return data

    def crawl_all(self, names: list[str], output_path: str) -> list[dict]:
        """Batch crawl a list of indicator names."""
        results = []
        for name in tqdm(names, desc="爬取丁香园"):
            data = self.crawl_indicator(name)
            if data:
                results.append(data)
        ensure_dir(Path(output_path).parent)
        Path(output_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("DXY crawl saved to %s (%d results)", output_path, len(results))
        return results
