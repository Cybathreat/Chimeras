"""
Chimeras v3.0 — Web Search Tool

Provides web search capability for ARIA (recon) and Marksman (exploit research).
Uses Tavily API (free tier: 1000 searches/month) with DuckDuckGo fallback.

Integration:
    ARIA uses web_search for: CVE lookups, public info gathering, subdomain discovery
    Marksman uses web_search for: PoC search, exploit-db lookups, CVE details

Wired into core/scope.py as part of the 'passive_recon' tool category.
"""

import json
import logging
import os
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def _tavily_search(query: str, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Search via Tavily API. Returns None if no API key or request fails."""
    api_key = os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")
    if not api_key:
        return None

    try:
        import urllib.request
        import urllib.parse

        url = "https://api.tavily.com/search"
        payload = json.dumps({
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", "")[:500],
                    "score": item.get("score", 0),
                })
            return results
    except Exception as e:
        logger.debug(f"Tavily search failed: {e}")
        return None


def _duckduckgo_search(query: str, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Fallback search via DuckDuckGo HTML. Returns None if request fails."""
    try:
        import urllib.request
        import urllib.parse
        import re

        encoded_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Extract result titles and URLs from DuckDuckGo HTML
        results = []
        # DuckDuckGo HTML uses class="result__a" for links
        link_pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')
        for match in link_pattern.finditer(html):
            raw_url = match.group(1)
            title = match.group(2).strip()
            # DuckDuckGo uses redirect URLs — extract actual URL
            if "uddg=" in raw_url:
                actual_url = urllib.parse.unquote(
                    raw_url.split("uddg=")[1].split("&")[0]
                )
            else:
                actual_url = raw_url
            if title and actual_url:
                results.append({
                    "title": title,
                    "url": actual_url,
                    "content": "",
                    "score": 0,
                })
            if len(results) >= max_results:
                break

        return results if results else None
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed: {e}")
        return None


def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the web for information.

    Tries Tavily API first (if TAVILY_API_KEY is set), falls back to DuckDuckGo.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dict with:
            - query: the original query
            - results: list of {title, url, content, score}
            - source: "tavily" or "duckduckgo"
            - success: bool
            - error: error message if failed
    """
    # Try Tavily first
    results = _tavily_search(query, max_results)
    if results is not None:
        return {
            "query": query,
            "results": results,
            "source": "tavily",
            "success": True,
            "error": None,
        }

    # Fallback to DuckDuckGo
    results = _duckduckgo_search(query, max_results)
    if results is not None:
        return {
            "query": query,
            "results": results,
            "source": "duckduckgo",
            "success": True,
            "error": None,
        }

    # Both failed
    return {
        "query": query,
        "results": [],
        "source": None,
        "success": False,
        "error": "All search providers failed. Set TAVILY_API_KEY for reliable search.",
    }


def search_cve(cve_id: str) -> Dict[str, Any]:
    """Search for a specific CVE. Convenience wrapper."""
    return web_search(f"{cve_id} CVE vulnerability exploit", max_results=5)


def search_exploit(service: str, version: str = "") -> Dict[str, Any]:
    """Search for exploits for a service/version. Convenience wrapper."""
    query = f"{service} {version} exploit PoC" if version else f"{service} exploit PoC"
    return web_search(query, max_results=5)