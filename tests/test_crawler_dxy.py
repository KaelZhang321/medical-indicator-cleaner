from __future__ import annotations

from scripts.data_enrichment.crawler_dxy import DxyCrawler


def test_search_indicator_returns_none_when_no_usable_result(monkeypatch) -> None:
    crawler = DxyCrawler(cache_dir="data/enrichment/cache_dxy_test")

    html = """
    <html><body>
      <a href="/search/index?keyword=甲胎蛋白">医学科普</a>
      <a href="/search/health/index?keyword=甲胎蛋白">医院医生</a>
    </body></html>
    """
    monkeypatch.setattr(crawler, "_safe_get", lambda _url: html)

    result = crawler.search_indicator("甲胎蛋白")

    assert result is None


def test_parse_detail_page_returns_empty_when_structure_missing() -> None:
    crawler = DxyCrawler(cache_dir="data/enrichment/cache_dxy_test")

    result = crawler.parse_detail_page("<html><body><h1>血铅检测</h1></body></html>")

    assert result["chinese_name"] == "血铅检测"
    assert result["aliases"] == []
    assert result["reference_ranges"] == []
