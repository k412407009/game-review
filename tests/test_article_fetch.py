from __future__ import annotations

from bs4 import BeautifulSoup

from api.article_fetch import (
    ExtractedArticle,
    _parse_wechat_article,
    compose_enriched_notes,
    resolve_auto_fetch_urls,
)


def test_resolve_auto_fetch_urls_prioritizes_reference_and_notes_wechat_links():
    urls = resolve_auto_fetch_urls(
        reference_url="https://example.com/report",
        notes=(
            "先看这个 https://mp.weixin.qq.com/s/abc123 ，"
            "再看这个 https://mp.weixin.qq.com/s/def456"
        ),
    )
    assert urls == [
        "https://example.com/report",
        "https://mp.weixin.qq.com/s/abc123",
    ]


def test_parse_wechat_article_extracts_core_fields_and_drops_footer_noise():
    html = """
    <html>
      <head><title>备用标题</title></head>
      <body>
        <h1 id="activity-name"># 月流水破亿，单日吸金480万</h1>
        <a id="js_name">游戏日报</a>
        <em id="publish_time">2026-04-07</em>
            <div id="js_content">
              <p>2026年第一个爆款SLG出现了。</p>
              <p>《Last Asylum: Plague》3月预估流水超过1.13亿元。</p>
              <p>这款产品采用黑死病题材，并把医生、医院经营、庇护所建设和联盟扩张串到同一条成长线里。</p>
              <p>这种从救治个体到守护文明的叙事递进，让题材和玩法形成了高度统一的记忆点。</p>
              <p>继续滑动看下一个</p>
              <p>微信扫一扫可打开此内容</p>
            </div>
      </body>
    </html>
    """
    article = _parse_wechat_article(
        BeautifulSoup(html, "html.parser"),
        "https://mp.weixin.qq.com/s/YpKqZkWzewAmfYybzR6PuA",
    )
    assert article.title == "月流水破亿，单日吸金480万"
    assert article.author == "游戏日报"
    assert article.published_at == "2026-04-07"
    assert "爆款SLG" in article.text
    assert "微信扫一扫可打开此内容" not in article.text


def test_compose_enriched_notes_appends_article_block():
    article = ExtractedArticle(
        url="https://mp.weixin.qq.com/s/demo",
        title="样例文章",
        author="测试号",
        published_at="2026-04-21",
        text="这里是正文。",
        source="wechat-html",
        truncated=False,
        original_chars=6,
    )
    result = compose_enriched_notes(notes="请重点看 D1。", articles=[article])
    assert result is not None
    assert "请重点看 D1。" in result
    assert "[自动抓取参考文章 1]" in result
    assert "样例文章" in result
    assert "这里是正文。" in result
