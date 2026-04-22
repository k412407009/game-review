"""Article extraction helpers for review context enrichment.

目标:
  1. 支持显式参考文章 URL (`reference_url`)
  2. 自动识别 `notes` 中的 mp.weixin 链接
  3. 直接在服务端抓正文, 产出适合喂给 Compass 的结构化文本

实现策略:
  - 优先复用 ppt-master 里验证过的思路: curl_cffi 伪装 Chrome TLS 指纹
  - 微信文章走定向解析 (#activity-name / #js_name / #publish_time / #js_content)
  - 其他网页走通用正文提取
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from curl_cffi import requests as curl_requests  # type: ignore

    _CURL_IMPERSONATE = "chrome120"
except ImportError:
    curl_requests = None
    _CURL_IMPERSONATE = None

try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:  # pragma: no cover - warning suppression is best effort
    pass

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"]+")
CONTENT_SELECTORS: tuple[dict[str, object], ...] = (
    {"id": "js_content"},
    {"class_": re.compile(r"article-content|detail-content|content-text|main-content", re.I)},
    {"id": "content"},
    {"id": "article"},
    {"name": "article"},
    {"name": "main"},
)
WECHAT_FOOTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^微信扫一扫可打开此内容"),
    re.compile(r"^继续滑动看下一个"),
    re.compile(r"^预览时标签不可点"),
    re.compile(r"^Read more$", re.I),
    re.compile(r"^Scan to Follow$", re.I),
    re.compile(r"^Got It$", re.I),
    re.compile(r"^Cancel$", re.I),
    re.compile(r"^Allow$", re.I),
)
WECHAT_EXTRA_STRIP_SELECTORS: tuple[str, ...] = (
    "#meta_content",
    "#js_tags",
    "#js_pc_qr_code",
    "#js_preview_link",
    ".wx_profile_card_inner",
    ".wx_follow_card",
    ".qr_code_pc_outer",
    ".original_primary_card_tips",
    ".js_ad_link",
)
MAX_AUTO_FETCH_URLS = 2
MAX_EXTRACTED_CHARS_PER_ARTICLE = 8000
MAX_COMBINED_CONTEXT_CHARS = 24000


@dataclass(slots=True)
class ExtractedArticle:
    url: str
    title: str
    author: str
    published_at: str
    text: str
    source: str
    truncated: bool
    original_chars: int


@dataclass(slots=True)
class ContextBundle:
    notes: str | None
    enriched_notes: str | None
    urls: list[str]
    articles: list[ExtractedArticle]
    skipped_urls: list[str]


def find_notes_wechat_urls(notes: str | None) -> list[str]:
    if not notes:
        return []
    urls: list[str] = []
    for raw in URL_RE.findall(notes):
        url = raw.rstrip(").,，。；;!！?？")
        if "mp.weixin.qq.com" in url:
            urls.append(url)
    return _dedupe(urls)


def resolve_auto_fetch_urls(
    *,
    reference_url: str | None,
    notes: str | None,
) -> list[str]:
    urls: list[str] = []
    if reference_url:
        urls.append(reference_url.strip())
    urls.extend(find_notes_wechat_urls(notes))
    return _dedupe(urls)[:MAX_AUTO_FETCH_URLS]


def fetch_context_bundle(
    *,
    reference_url: str | None,
    notes: str | None,
    output_dir: Path | None = None,
) -> ContextBundle:
    urls = resolve_auto_fetch_urls(reference_url=reference_url, notes=notes)
    if not urls:
        return ContextBundle(
            notes=notes,
            enriched_notes=notes,
            urls=[],
            articles=[],
            skipped_urls=[],
        )

    articles: list[ExtractedArticle] = []
    skipped: list[str] = []
    for url in urls:
        try:
            article = extract_article(url)
            articles.append(article)
        except Exception as exc:
            skipped.append(url)
            log.warning("article fetch skipped: %s (%s: %s)", url, type(exc).__name__, exc)

    enriched_notes = compose_enriched_notes(notes=notes, articles=articles)

    if output_dir is not None:
        save_context_bundle(output_dir=output_dir, articles=articles, enriched_notes=enriched_notes)

    return ContextBundle(
        notes=notes,
        enriched_notes=enriched_notes,
        urls=urls,
        articles=articles,
        skipped_urls=skipped,
    )


def extract_article(url: str) -> ExtractedArticle:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "mp.weixin.qq.com" in host:
        article = _parse_wechat_article(soup, url)
    else:
        article = _parse_generic_article(soup, url)

    clean_text = _normalize_text(article.text)
    original_chars = len(clean_text)
    truncated = False
    if len(clean_text) > MAX_EXTRACTED_CHARS_PER_ARTICLE:
        clean_text = clean_text[:MAX_EXTRACTED_CHARS_PER_ARTICLE].rstrip() + "\n\n[正文已截断]"
        truncated = True

    return ExtractedArticle(
        url=article.url,
        title=article.title.strip() or "Untitled",
        author=article.author.strip(),
        published_at=article.published_at.strip(),
        text=clean_text,
        source=article.source,
        truncated=truncated,
        original_chars=original_chars,
    )


def compose_enriched_notes(
    *,
    notes: str | None,
    articles: Iterable[ExtractedArticle],
) -> str | None:
    base = (notes or "").strip()
    blocks: list[str] = []
    for idx, article in enumerate(articles, start=1):
        header = [
            f"[自动抓取参考文章 {idx}]",
            f"- 标题: {article.title}",
            f"- 链接: {article.url}",
            f"- 作者: {article.author or '(未识别)'}",
            f"- 日期: {article.published_at or '(未识别)'}",
            f"- 来源: {article.source}",
            "- 正文:",
            article.text,
        ]
        blocks.append("\n".join(header).strip())

    combined = "\n\n".join(part for part in [base, *blocks] if part)
    if not combined:
        return None
    if len(combined) <= MAX_COMBINED_CONTEXT_CHARS:
        return combined
    return combined[:MAX_COMBINED_CONTEXT_CHARS].rstrip() + "\n\n[上下文已截断]"


def save_context_bundle(
    *,
    output_dir: Path,
    articles: list[ExtractedArticle],
    enriched_notes: str | None,
) -> None:
    context_dir = output_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "articles": [asdict(article) for article in articles],
        "enriched_notes": enriched_notes,
    }
    (context_dir / "article_context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if enriched_notes:
        (context_dir / "enriched_notes.txt").write_text(enriched_notes, encoding="utf-8")

    for idx, article in enumerate(articles, start=1):
        lines = [
            f"# {article.title}",
            "",
            f"- url: {article.url}",
            f"- author: {article.author or '(未识别)'}",
            f"- published_at: {article.published_at or '(未识别)'}",
            f"- source: {article.source}",
            "",
            article.text,
            "",
        ]
        (context_dir / f"article_{idx}.md").write_text("\n".join(lines), encoding="utf-8")


def _fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if curl_requests is not None:
        response = curl_requests.get(
            url,
            headers=headers,
            timeout=30,
            verify=False,
            impersonate=_CURL_IMPERSONATE,
        )
    else:
        response = requests.get(url, headers=headers, timeout=30, verify=False)

    response.raise_for_status()
    if getattr(response, "apparent_encoding", None):
        response.encoding = response.apparent_encoding
    return response.text


def _parse_wechat_article(soup: BeautifulSoup, url: str) -> ExtractedArticle:
    for css in WECHAT_EXTRA_STRIP_SELECTORS:
        for node in soup.select(css):
            node.decompose()

    content = soup.select_one("#js_content")
    if content is None:
        raise ValueError("未找到微信公众号正文节点 #js_content")

    for node in content.find_all(["script", "style", "iframe", "noscript"]):
        node.decompose()

    title = _text_of_first(
        soup.select_one("#activity-name"),
        soup.select_one("meta[property='og:title']"),
        soup.title,
    )
    title = re.sub(r"^\s*#\s*", "", title)

    author = _text_of_first(
        soup.select_one("#js_name"),
        soup.select_one("meta[name='author']"),
    )
    published_at = _text_of_first(
        soup.select_one("#publish_time"),
        soup.select_one("meta[property='article:published_time']"),
        soup.select_one("meta[name='publishdate']"),
    )

    lines: list[str] = []
    for raw_line in content.get_text("\n", strip=True).splitlines():
        line = _normalize_inline_whitespace(raw_line)
        if not line:
            continue
        if any(pattern.search(line) for pattern in WECHAT_FOOTER_PATTERNS):
            continue
        lines.append(line)

    text = _normalize_text("\n".join(lines))
    if len(text) < 120:
        raise ValueError("微信公众号正文过短，疑似抓取失败")

    return ExtractedArticle(
        url=url,
        title=title or "Untitled",
        author=author,
        published_at=published_at,
        text=text,
        source="wechat-html",
        truncated=False,
        original_chars=len(text),
    )


def _parse_generic_article(soup: BeautifulSoup, url: str) -> ExtractedArticle:
    content = _find_main_content(soup)
    if content is None:
        raise ValueError("未找到正文节点")

    for node in content.find_all(["script", "style", "iframe", "noscript", "nav", "footer", "aside"]):
        node.decompose()

    title = _text_of_first(
        soup.select_one("meta[property='og:title']"),
        soup.title,
    )
    author = _text_of_first(
        soup.select_one("meta[name='author']"),
        soup.select_one("meta[property='article:author']"),
    )
    published_at = _text_of_first(
        soup.select_one("meta[property='article:published_time']"),
        soup.select_one("meta[name='publishdate']"),
        soup.select_one("meta[name='date']"),
    )
    text = _normalize_text(content.get_text("\n", strip=True))
    if len(text) < 120:
        raise ValueError("网页正文过短，疑似抓取失败")

    return ExtractedArticle(
        url=url,
        title=title or "Untitled",
        author=author,
        published_at=published_at,
        text=text,
        source="generic-html",
        truncated=False,
        original_chars=len(text),
    )


def _find_main_content(soup: BeautifulSoup) -> Tag | None:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"]):
        tag.decompose()

    best: Tag | None = None
    best_score = 0
    for selector in CONTENT_SELECTORS:
        if "name" in selector:
            elements = soup.find_all(selector["name"])
        else:
            elements = soup.find_all(attrs=selector)
        for element in elements:
            text = element.get_text(" ", strip=True)
            if len(text) < 150:
                continue
            score = len(text) + (len(element.find_all("p")) * 80)
            if score > best_score:
                best = element
                best_score = score

    if best is not None:
        return best

    candidates = soup.find_all("div")
    for element in candidates:
        text = element.get_text(" ", strip=True)
        if len(text) < 200:
            continue
        score = len(text) + (len(element.find_all("p")) * 60)
        if score > best_score:
            best = element
            best_score = score
    return best or soup.body


def _text_of_first(*nodes: object) -> str:
    for node in nodes:
        if node is None:
            continue
        if hasattr(node, "get"):
            content = node.get("content")  # type: ignore[call-arg]
            if isinstance(content, str) and content.strip():
                return content.strip()
        text = getattr(node, "get_text", None)
        if callable(text):
            value = text(strip=True)
            if isinstance(value, str) and value:
                return value.strip()
        string = getattr(node, "string", None)
        if isinstance(string, str) and string.strip():
            return string.strip()
    return ""


def _normalize_inline_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _normalize_inline_whitespace(raw_line)
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        lines.append(line)
    normalized = "\n".join(lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _dedupe(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in urls:
        url = raw.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered
