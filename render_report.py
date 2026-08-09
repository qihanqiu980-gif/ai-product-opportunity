#!/usr/bin/env python3
"""Render a structured AI product opportunity report into standalone HTML."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from string import Template
from typing import Any


ROOT = Path(__file__).resolve().parent


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def normalize_typography(markup: str) -> str:
    """Convert CSS font pixel values to rem and enforce a 15px minimum."""

    def to_rem(match: re.Match[str]) -> str:
        pixels = max(15.0, float(match.group(1)))
        rem = pixels / 16
        formatted = f"{rem:.4f}".rstrip("0").rstrip(".")
        return formatted + "rem"

    def normalize_declaration(match: re.Match[str]) -> str:
        declaration = match.group(0)
        return re.sub(r"(\d+(?:\.\d+)?)px", to_rem, declaration)

    markup = re.sub(r"font-size:\s*[^;]+;", normalize_declaration, markup)
    return re.sub(r"font:\s*[^;]+;", normalize_declaration, markup)


def icon(name: str, size: int = 18) -> str:
    paths = {
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
        "github": '<path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.58 9.58 0 0 1 12 6.84a9.6 9.6 0 0 1 2.5.34c1.91-1.3 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.86v2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"/>',
        "product": '<path d="M7 4h6.5a5.5 5.5 0 0 1 0 11H7V4Z"/><path d="M7 15v5M7 8h6.5a1.5 1.5 0 0 1 0 3H7"/>',
        "spark": '<path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z"/><path d="m18.5 15 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "check": '<path d="m5 12 4 4L19 6"/>',
        "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/>',
    }
    body = paths.get(name, paths["spark"])
    return (
        '<svg aria-hidden="true" width="'
        + str(size)
        + '" height="'
        + str(size)
        + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        + 'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        + body
        + "</svg>"
    )


def external_link(url: str, label: str) -> str:
    return (
        '<a class="source-link" href="'
        + esc(url)
        + '" target="_blank" rel="noreferrer">'
        + esc(label)
        + icon("arrow", 15)
        + "</a>"
    )


def render_evidence_links(
    sources: list[dict[str, Any]] | None,
    *,
    theme: str = "light",
    label: str = "依据来源",
) -> str:
    valid_sources = [
        source
        for source in (sources or [])
        if isinstance(source, dict) and source.get("url") and source.get("label")
    ]
    if not valid_sources:
        return ""
    theme_class = " evidence-links-dark" if theme == "dark" else ""
    links = "".join(
        '<a href="'
        + esc(source["url"])
        + '" target="_blank" rel="noreferrer">'
        + esc(source["label"])
        + icon("arrow", 12)
        + "</a>"
        for source in valid_sources
    )
    return (
        '<div class="evidence-links'
        + theme_class
        + '" aria-label="'
        + esc(label)
        + '"><span>'
        + esc(label)
        + "</span>"
        + links
        + "</div>"
    )


def discover_archive_entries(
    data_dir: Path,
    html_dir: Path,
    current_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return dated reports that have a corresponding navigable HTML page."""

    current_date = str(current_data.get("meta", {}).get("date", ""))
    reports: dict[str, dict[str, Any]] = {}
    for json_path in sorted(data_dir.glob("????-??-??.json")):
        try:
            candidate = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = candidate.get("meta", {})
        date = str(meta.get("date", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        if date != current_date and not (html_dir / f"{date}.html").exists():
            continue
        reports[date] = {
            "date": date,
            "weekday": str(meta.get("weekday", "")),
            "mode": str(meta.get("collectionMode", "")),
        }

    if current_date:
        meta = current_data.get("meta", {})
        reports[current_date] = {
            "date": current_date,
            "weekday": str(meta.get("weekday", "")),
            "mode": str(meta.get("collectionMode", "")),
        }
    return [reports[date] for date in sorted(reports, reverse=True)]


def render_archive_picker(entries: list[dict[str, Any]], current_date: str) -> str:
    if not entries:
        return ""
    latest_date = entries[0]["date"]
    options = []
    for entry in entries:
        date = str(entry.get("date", ""))
        if date == current_date and date == latest_date:
            suffix = "最新"
        elif date == current_date:
            suffix = "当前查看"
        elif date == latest_date:
            suffix = "最新"
        else:
            suffix = str(entry.get("weekday", "")) or "历史日报"
        selected = " selected" if date == current_date else ""
        options.append(
            '<option value="'
            + esc(date + ".html")
            + '"'
            + selected
            + ">"
            + esc(date + " · " + suffix)
            + "</option>"
        )
    return (
        '<label class="archive-picker" for="report-archive">'
        '<span class="archive-picker-label">历史日报</span>'
        '<span class="archive-select-shell">'
        + icon("clock", 16)
        + '<select id="report-archive" aria-label="按日期查看历史日报">'
        + "".join(options)
        + "</select></span></label>"
    )


def render_brief(items: list[dict[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(items, start=1):
        text = esc(item.get("text", ""))
        emphasis = esc(item.get("emphasis", ""))
        if emphasis:
            text = text.replace(emphasis, "<strong>" + emphasis + "</strong>")
        rows.append(
            '<li><span class="brief-number">'
            + f"{index:02d}"
            + '</span><div><span class="eyebrow">'
            + esc(item.get("label", ""))
            + "</span><p>"
            + text
            + "</p>"
            + render_evidence_links(item.get("sources"), label="查看依据")
            + "</div></li>"
        )
    return "".join(rows)


def render_stats(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        href = item.get("href")
        tag = "a" if href else "div"
        href_attr = ' href="' + esc(href) + '"' if href else ""
        rows.append(
            "<"
            + tag
            + ' class="stat"'
            + href_attr
            + '><span class="stat-value">'
            + esc(item.get("value", "—"))
            + '</span><div><span class="stat-label">'
            + esc(item.get("label", ""))
            + '</span><span class="stat-note">'
            + esc(item.get("note", ""))
            + "</span></div></"
            + tag
            + ">"
        )
    return "".join(rows)


def render_trends(items: list[dict[str, Any]], cover: bool = False) -> str:
    rows = []
    for item in items[:3] if cover else items:
        score = max(0, min(100, int(item.get("score", 0))))
        score_label = f"趋势评分：{score} / 100"
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        rows.append(
            '<article class="trend-row">'
            + '<span class="trend-rank" aria-hidden="true">'
            + f"{int(item.get('rank', 0)):02d}"
            + "</span>"
            + '<div class="trend-copy"><div class="trend-title-line"><h3>'
            + esc(item.get("name", ""))
            + '</h3></div><p class="trend-summary">'
            + esc(item.get("summary", ""))
            + '</p><div class="trend-track" role="img" aria-label="'
            + esc(score_label)
            + '"><span style="width:'
            + str(score)
            + '%"></span></div>'
            + (
                '<div class="trend-sources trend-sources-cover">'
                + render_evidence_links(sources[:1], label="首要来源")
                + "</div>"
                if cover
                else '<div class="trend-evidence"><span>信号依据</span><p>'
                + esc(item.get("evidence", ""))
                + '</p></div><div class="trend-sources">'
                + render_evidence_links(sources, label="原始来源")
                + "</div>"
            )
            + '</div><div class="trend-score" aria-label="'
            + esc(score_label)
            + '"><strong>'
            + str(score)
            + '</strong><span>趋势分</span></div></article>'
        )
    return "".join(rows)


def render_discovery_rows(data: dict[str, Any]) -> str:
    rows: list[str] = []
    index = 0
    for project in data.get("github", []):
        index += 1
        rows.append(
            discovery_row(
                index=index,
                source="github",
                source_label="GitHub",
                name=project.get("name", ""),
                maker=project.get("owner", ""),
                category=project.get("category", ""),
                description=project.get("description", ""),
                signal=project.get("delta", ""),
                metric=project.get("metricLabel", "") + " · " + project.get("metricValue", ""),
                heat=int(project.get("heat", 0)),
                opportunity=project.get("opportunity", ""),
                url=project.get("url", "#"),
                status=project.get("status", "新发现"),
                axes=project.get("axes"),
            )
        )
    for product in data.get("productHunt", []):
        index += 1
        rows.append(
            discovery_row(
                index=index,
                source="product",
                source_label="Product Hunt",
                name=product.get("name", ""),
                maker=product.get("maker", ""),
                category=product.get("category", ""),
                description=product.get("description", ""),
                signal=product.get("signal", ""),
                metric="目标用户 · " + product.get("target", ""),
                heat=int(product.get("heat", 0)),
                opportunity=product.get("opportunity", ""),
                url=product.get("url", "#"),
                status=product.get("status", "新发现"),
                axes=product.get("axes"),
            )
        )
    return "".join(rows)


def discovery_row(
    *,
    index: int,
    source: str,
    source_label: str,
    name: str,
    maker: str,
    category: str,
    description: str,
    signal: str,
    metric: str,
    heat: int,
    opportunity: str,
    url: str,
    status: str,
    axes: dict[str, Any] | None = None,
) -> str:
    source_icon = "github" if source == "github" else "product"
    heat = max(0, min(100, heat))
    axis_text = " ".join(
        str((axes or {}).get(key, {}).get("value", ""))
        for key in ("novelty", "momentum", "change")
    )
    search_text = " ".join([name, maker, category, description, signal, opportunity, axis_text]).lower()
    axis_labels = {"novelty": "新鲜度", "momentum": "动量", "change": "实质变化"}
    axis_rows = "".join(
        '<div class="signal-axis"><b>'
        + axis_labels[key]
        + "</b><span>"
        + esc((axes or {}).get(key, {}).get("value", "—"))
        + "</span></div>"
        for key in ("novelty", "momentum", "change")
        if (axes or {}).get(key)
    )
    axis_markup = (
        '<div class="signal-axes" aria-label="三轴判断">' + axis_rows + "</div>"
        if axis_rows
        else ""
    )
    return (
        '<article class="discovery-row" data-source="'
        + esc(source)
        + '" data-search="'
        + esc(search_text)
        + '">'
        + '<div class="discovery-index">'
        + f"{index:02d}"
        + "</div>"
        + '<div class="discovery-main"><div class="tag-line"><span class="source-tag source-'
        + esc(source)
        + '">'
        + icon(source_icon, 14)
        + esc(source_label)
        + '</span><span class="category-tag">'
        + esc(category)
        + '</span><span class="status-tag">'
        + esc(status)
        + "</span></div><h3>"
        + esc(name)
        + '<span class="maker"> / '
        + esc(maker)
        + "</span></h3><p>"
        + esc(description)
        + "</p></div>"
        + '<div class="discovery-evidence" data-label="变化与证据"><p>'
        + esc(signal)
        + "</p>"
        + axis_markup
        + '<div class="heat"><span>'
        + esc(metric)
        + '</span><div class="heat-track"><i style="width:'
        + str(heat)
        + '%"></i></div></div></div>'
        + '<div class="discovery-opportunity" data-label="产品机会"><p>'
        + esc(opportunity)
        + "</p>"
        + external_link(url, "查看原始页面")
        + "</div></article>"
    )


def render_updates(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-inline">今日没有需要重复出现的重要更新。</div>'
    return "".join(
        '<article class="update-row"><span class="update-dot"></span><div><h3>'
        + esc(item.get("name", ""))
        + "</h3><p>"
        + esc(item.get("change", ""))
        + "</p></div>"
        + external_link(item.get("url", "#"), "查看更新")
        + "</article>"
        for item in items
    )


def render_cross(items: list[dict[str, Any]]) -> str:
    return "".join(
        '<div class="matrix-row"><div data-label="技术供给">'
        + esc(item.get("ability", ""))
        + '</div><div data-label="需求信号">'
        + esc(item.get("demand", ""))
        + '</div><div class="matrix-concept" data-label="产品概念">'
        + esc(item.get("concept", ""))
        + render_evidence_links(item.get("sources"), label="验证来源")
        + '</div><div data-label="置信度"><span class="confidence">'
        + esc(item.get("confidence", ""))
        + "</span></div></div>"
        for item in items
    )


def render_recommendations(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            '<article class="recommendation"><div class="recommendation-rank">'
            + f"{int(item.get('rank', 0)):02d}"
            + '</div><div class="recommendation-head"><span class="eyebrow">'
            + esc(item.get("source", ""))
            + "</span><h3>"
            + esc(item.get("name", ""))
            + "</h3><p>"
            + esc(item.get("why", ""))
            + "</p>"
            + external_link(item.get("url", "#"), "打开项目")
            + '</div><dl><div><dt>运行成本</dt><dd>'
            + esc(item.get("cost", ""))
            + "</dd></div><div><dt>主要风险</dt><dd>"
            + esc(item.get("risk", ""))
            + "</dd></div><div><dt>核心假设</dt><dd>"
            + esc(item.get("assumption", ""))
            + "</dd></div></dl></article>"
        )
    return "".join(rows)


def render_actions(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        action_link = (
            external_link(item["url"], item.get("linkLabel", "打开相关来源"))
            if item.get("url")
            else ""
        )
        rows.append(
            '<li><span class="action-time">'
            + esc(item.get("minutes", 0))
            + ' min</span><div><strong>'
            + esc(item.get("task", ""))
            + "</strong><p>"
            + esc(item.get("outcome", ""))
            + "</p>"
            + action_link
            + "</div></li>"
        )
    return "".join(rows)


def render_sources(items: list[dict[str, Any]]) -> str:
    return "".join(
        '<li><span class="source-status"></span><div><strong>'
        + esc(item.get("name", ""))
        + "</strong><span>"
        + esc(item.get("status", ""))
        + "</span></div>"
        + external_link(item.get("url", "#"), "来源")
        + "</li>"
        for item in items
    )


def render_cover_watch(data: dict[str, Any]) -> str:
    picks: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_pick(item: dict[str, Any], source: str, summary: str) -> None:
        name = str(item.get("name", "")).strip()
        identity = name.casefold()
        if not name or identity in seen:
            return
        seen.add(identity)
        picks.append(
            {
                "name": name,
                "source": source,
                "summary": summary,
                "url": item.get("url", ""),
            }
        )

    for item in data.get("recommendations", [])[:2]:
        add_pick(item, item.get("source", ""), item.get("why", ""))
    for item in data.get("github", []):
        add_pick(item, item.get("category", ""), item.get("opportunity", ""))
    for item in data.get("productHunt", []):
        add_pick(item, item.get("category", ""), item.get("opportunity", ""))
    rows = []
    for index, item in enumerate(picks[:4], start=1):
        title = (
            '<a href="'
            + esc(item["url"])
            + '" target="_blank" rel="noreferrer">'
            + esc(item["name"])
            + "</a>"
            if item.get("url")
            else esc(item["name"])
        )
        rows.append(
            '<li><span>'
            + f"{index:02d}"
            + '</span><div><div><strong>'
            + title
            + '</strong><small>'
            + esc(item["source"])
            + "</small></div><p>"
            + esc(item["summary"])
            + "</p></div></li>"
        )
    return "".join(rows)


def render_cover_stats(items: list[dict[str, Any]]) -> str:
    return "".join(
        '<div><strong>'
        + esc(item.get("value", "—"))
        + '</strong><span>'
        + esc(item.get("label", ""))
        + '</span></div>'
        for item in items[:4]
    )


def render_cover_actions(items: list[dict[str, Any]]) -> str:
    return "".join(
        '<li><span>'
        + esc(item.get("minutes", 0))
        + 'm</span><p>'
        + esc(item.get("task", ""))
        + '</p></li>'
        for item in items[:3]
    )


PAGE = Template(
    """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light">
  <title>$page_title</title>
  <style>
    :root {
      --bg: oklch(1 0 0);
      --surface: oklch(0.975 0.006 240);
      --surface-strong: oklch(0.945 0.012 240);
      --ink: oklch(0.19 0.018 245);
      --muted: oklch(0.49 0.022 245);
      --faint: oklch(0.65 0.016 245);
      --line: oklch(0.90 0.012 240);
      --line-strong: oklch(0.82 0.018 240);
      --primary: oklch(0.49 0.14 160);
      --primary-dark: oklch(0.36 0.11 160);
      --primary-soft: oklch(0.95 0.04 160);
      --blue: oklch(0.54 0.18 250);
      --blue-dark: oklch(0.40 0.14 250);
      --blue-soft: oklch(0.95 0.035 250);
      --amber: oklch(0.70 0.15 74);
      --amber-soft: oklch(0.96 0.035 74);
      --danger: oklch(0.56 0.17 28);
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
      --space-xs: 4px;
      --space-sm: 8px;
      --space-md: 12px;
      --space-lg: 16px;
      --space-xl: 24px;
      --space-2xl: 32px;
      --space-3xl: 48px;
      --space-4xl: 64px;
      --shadow-hover: 0 12px 30px oklch(0.19 0.018 245 / 0.08);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: var(--bg);
      font-synthesis: none;
      text-rendering: optimizeLegibility;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; background: var(--bg); color: var(--ink); }
    a { color: inherit; }
    button, input, select { font: inherit; }
    svg { display: block; flex: 0 0 auto; }
    ::selection { background: var(--primary-soft); color: var(--primary-dark); }

    .share-cover { display: none; }

    .report-shell {
      width: min(1440px, 100%);
      margin: 0 auto;
      border-inline: 1px solid var(--line);
      min-height: 100vh;
    }

    .topbar {
      min-height: 68px;
      padding: 0 var(--space-2xl);
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-xl);
      background: var(--bg);
      position: sticky;
      top: 0;
      z-index: 20;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 760;
      letter-spacing: -0.02em;
    }

    .brand-mark {
      width: 28px;
      height: 28px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 3px;
      align-items: end;
    }

    .brand-mark i { display: block; background: var(--primary); border-radius: 2px; }
    .brand-mark i:nth-child(1) { height: 42%; }
    .brand-mark i:nth-child(2) { height: 72%; }
    .brand-mark i:nth-child(3) { height: 100%; background: var(--ink); }

    .topbar-meta {
      display: flex;
      align-items: center;
      gap: var(--space-lg);
      color: var(--muted);
      font-size: 13px;
    }

    .topbar-current-date { white-space: nowrap; font-variant-numeric: tabular-nums; }
    .archive-picker { display: flex; align-items: center; gap: 10px; }
    .archive-picker-label { color: var(--ink); font-size: 15px; font-weight: 700; white-space: nowrap; }
    .archive-select-shell {
      position: relative;
      width: 210px;
      min-width: 0;
      display: flex;
      align-items: center;
      color: var(--blue-dark);
    }
    .archive-select-shell > svg {
      position: absolute;
      left: 12px;
      z-index: 1;
      pointer-events: none;
    }
    .archive-select-shell::after {
      content: "⌄";
      position: absolute;
      right: 12px;
      top: 50%;
      translate: 0 -56%;
      color: var(--muted);
      font-size: 16px;
      line-height: 1;
      pointer-events: none;
    }
    .archive-select-shell select {
      width: 100%;
      min-height: 44px;
      padding: 0 34px 0 38px;
      appearance: none;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius-sm);
      outline: 0;
      color: var(--ink);
      background: var(--surface);
      font-size: 15px;
      font-weight: 650;
      font-variant-numeric: tabular-nums;
      cursor: pointer;
      transition: 180ms ease;
    }
    .archive-select-shell select:hover { border-color: var(--blue); background: var(--blue-soft); }
    .archive-select-shell select:focus-visible {
      border-color: var(--blue);
      box-shadow: 0 0 0 3px oklch(0.54 0.18 250 / 0.18);
    }

    .live-pill, .demo-pill, .replay-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 30px;
      padding: 0 10px;
      border-radius: var(--radius-sm);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    .live-pill { background: var(--primary-soft); color: var(--primary-dark); }
    .demo-pill { background: var(--amber-soft); color: oklch(0.42 0.11 62); }
    .replay-pill { background: var(--blue-soft); color: var(--blue-dark); }
    .live-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(360px, 0.75fr);
      border-bottom: 1px solid var(--line);
    }

    .hero-main {
      padding: 72px clamp(32px, 6vw, 88px) 64px;
      border-right: 1px solid var(--line);
    }

    .kicker {
      display: flex;
      align-items: center;
      gap: var(--space-md);
      margin-bottom: var(--space-xl);
      color: var(--primary-dark);
      font: 700 11px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .kicker::before { content: ""; width: 28px; height: 2px; background: var(--primary); }

    h1 {
      max-width: 780px;
      margin: 0;
      font-size: 4.625rem;
      line-height: 1.02;
      letter-spacing: -0.04em;
      font-weight: 780;
    }

    .hero-subtitle {
      margin: var(--space-xl) 0 0;
      max-width: 660px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.6;
    }

    .hero-date {
      margin-top: var(--space-3xl);
      display: flex;
      align-items: baseline;
      gap: var(--space-lg);
      font-variant-numeric: tabular-nums;
    }

    .hero-date strong { font-size: 22px; letter-spacing: -0.03em; }
    .hero-date span { color: var(--muted); font-size: 13px; }

    .hero-brief {
      padding: 48px 32px;
      background: var(--surface);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 40px;
    }

    .brief-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0; }
    .brief-list li {
      display: grid;
      grid-template-columns: 36px 1fr;
      gap: 12px;
      padding: 20px 0;
      border-bottom: 1px solid var(--line);
    }
    .brief-list li:first-child { padding-top: 0; }
    .brief-list li:last-child { border-bottom: 0; padding-bottom: 0; }
    .brief-number {
      color: var(--faint);
      font: 600 11px/1.4 ui-monospace, "SFMono-Regular", Menlo, monospace;
    }
    .eyebrow {
      display: block;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.3;
      font-weight: 720;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .brief-list p { margin: 7px 0 0; font-size: 16px; line-height: 1.62; }
    .brief-list strong { color: var(--primary-dark); font-weight: 730; }
    .brief-list .evidence-links { margin-top: 9px; }
    .brief-list .evidence-links a { min-height: 28px; }

    .source-summary {
      display: flex;
      justify-content: space-between;
      gap: var(--space-lg);
      padding-top: 18px;
      border-top: 1px solid var(--line-strong);
      color: var(--muted);
      font-size: 12px;
    }
    .source-summary strong { color: var(--ink); }

    .stat-band {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      border-bottom: 1px solid var(--line);
    }
    .stat {
      min-height: 116px;
      padding: 24px 32px;
      display: flex;
      align-items: center;
      gap: 18px;
      border-right: 1px solid var(--line);
      color: inherit;
      text-decoration: none;
      transition: 180ms ease;
    }
    .stat:last-child { border-right: 0; }
    a.stat:hover { background: var(--surface); }
    a.stat:focus-visible { outline: 3px solid oklch(0.49 0.14 160 / 0.22); outline-offset: -3px; }
    .stat-value {
      min-width: 72px;
      font-size: 38px;
      line-height: 1;
      font-weight: 760;
      letter-spacing: -0.045em;
      font-variant-numeric: tabular-nums;
    }
    .stat-label, .stat-note { display: block; }
    .stat-label { font-size: 13px; font-weight: 700; }
    .stat-note { margin-top: 5px; color: var(--muted); font-size: 11px; }

    .workspace {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
    }

    .sidebar {
      border-right: 1px solid var(--line);
      padding: 32px 24px;
    }
    .sidebar-inner { position: sticky; top: 100px; }
    .sidebar-title {
      margin: 0 0 12px;
      color: var(--faint);
      font: 700 10px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .section-nav { display: grid; gap: 2px; }
    .section-nav a {
      min-height: 40px;
      padding: 0 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--muted);
      text-decoration: none;
      border-radius: var(--radius-sm);
      font-size: 13px;
      transition: 180ms ease;
    }
    .section-nav a:hover, .section-nav a:focus-visible {
      color: var(--ink);
      background: var(--surface);
      outline: none;
    }
    .section-nav span {
      font: 600 10px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      color: var(--faint);
    }

    .sidebar-note {
      margin-top: 36px;
      padding-top: 24px;
      border-top: 1px solid var(--line);
    }
    .sidebar-note strong { display: block; font-size: 12px; }
    .sidebar-note p { margin: 8px 0 0; color: var(--muted); font-size: 11px; line-height: 1.6; }

    main { min-width: 0; }
    .report-section { padding: 64px clamp(28px, 5vw, 72px); border-bottom: 1px solid var(--line); }
    .report-section:last-child { border-bottom: 0; }
    .section-heading {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(240px, 0.52fr);
      gap: 48px;
      align-items: end;
      margin-bottom: 36px;
    }
    .section-number {
      display: block;
      margin-bottom: 12px;
      color: var(--primary-dark);
      font: 700 11px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: 0.12em;
    }
    .section-heading h2 {
      margin: 0;
      font-size: 30px;
      line-height: 1.18;
      letter-spacing: -0.035em;
    }
    .section-heading p { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.65; }

    .signal-layout {
      display: grid;
      grid-template-columns: minmax(0, 0.82fr) minmax(380px, 1.18fr);
      gap: 32px;
      align-items: start;
    }

    .opportunity-panel {
      background: var(--ink);
      color: var(--bg);
      padding: 32px;
      border-radius: var(--radius-lg);
      position: sticky;
      top: 104px;
    }
    .opportunity-panel .eyebrow { color: oklch(0.78 0.10 160); }
    .opportunity-panel h3 { margin: 12px 0 16px; font-size: 29px; line-height: 1.15; letter-spacing: -0.035em; }
    .opportunity-panel > p { margin: 0; color: oklch(0.84 0.012 245); font-size: 15px; line-height: 1.7; }
    .score-line {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin: 30px 0 24px;
      padding-top: 24px;
      border-top: 1px solid oklch(1 0 0 / 0.16);
    }
    .score-line strong { font-size: 58px; line-height: 0.9; letter-spacing: -0.06em; }
    .score-line span { color: oklch(0.78 0.10 160); font-size: 12px; font-weight: 700; }
    .why-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 12px; }
    .why-list li { display: grid; grid-template-columns: 18px 1fr; gap: 10px; color: oklch(0.88 0.01 245); font-size: 13px; line-height: 1.55; }
    .why-list li::before { content: "✓"; color: oklch(0.78 0.10 160); font-weight: 800; }
    .next-move {
      margin-top: 28px;
      padding: 16px;
      border-radius: var(--radius-sm);
      background: oklch(1 0 0 / 0.08);
    }
    .next-move span { color: oklch(0.72 0.01 245); font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
    .next-move p { margin: 7px 0 0; color: var(--bg); font-size: 13px; line-height: 1.6; }

    .evidence-links {
      margin-top: 12px;
      display: flex;
      align-items: center;
      gap: 7px;
      flex-wrap: wrap;
    }
    .evidence-links > span {
      color: var(--faint);
      font-size: 10px;
      font-weight: 720;
      letter-spacing: 0.04em;
    }
    .evidence-links a {
      min-height: 30px;
      padding: 0 8px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--blue-dark);
      background: var(--bg);
      font-size: 10px;
      font-weight: 700;
      text-decoration: none;
      transition: 180ms ease;
    }
    .evidence-links a:hover { border-color: var(--blue); background: var(--blue-soft); }
    .evidence-links a:focus-visible { outline: 3px solid oklch(0.54 0.18 250 / 0.20); outline-offset: 2px; }
    .evidence-links-dark { margin-top: 20px; padding-top: 18px; border-top: 1px solid oklch(1 0 0 / 0.16); }
    .evidence-links-dark > span { color: oklch(0.72 0.01 245); }
    .evidence-links-dark a {
      border-color: oklch(1 0 0 / 0.20);
      color: var(--bg);
      background: oklch(1 0 0 / 0.08);
    }
    .evidence-links-dark a:hover { border-color: oklch(0.78 0.10 160); background: oklch(1 0 0 / 0.14); }

    .trend-list { border-top: 1px solid var(--line); }
    .trend-list-heading {
      min-height: 48px;
      padding: 0 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
    }
    .trend-list-heading span { font-size: 17px; font-weight: 740; letter-spacing: -0.015em; }
    .trend-list-heading small { color: var(--primary-dark); font-size: 15px; font-weight: 720; }
    .trend-row {
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr) 72px;
      gap: 16px;
      padding: 24px 0;
      border-bottom: 1px solid var(--line);
    }
    .trend-rank {
      padding-top: 4px;
      color: var(--faint);
      font: 650 15px/1.5 ui-monospace, "SFMono-Regular", Menlo, monospace;
    }
    .trend-copy { min-width: 0; }
    .trend-title-line h3 { margin: 0; font-size: 20px; line-height: 1.3; letter-spacing: -0.025em; }
    .trend-summary { margin: 8px 0 12px; color: var(--muted); font-size: 16px; line-height: 1.58; }
    .trend-score {
      min-width: 72px;
      padding: 8px;
      align-self: start;
      color: var(--primary-dark);
      background: var(--primary-soft);
      border-radius: var(--radius-sm);
      text-align: center;
    }
    .trend-score strong {
      display: block;
      font: 760 24px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: -0.04em;
      font-variant-numeric: tabular-nums;
    }
    .trend-score span { display: block; margin-top: 4px; font-size: 15px; font-weight: 720; }
    .trend-evidence { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--line); }
    .trend-evidence > span { color: var(--faint); font-size: 15px; font-weight: 720; letter-spacing: 0.04em; }
    .trend-evidence p { margin: 4px 0 0; color: var(--muted); font-size: 15px; line-height: 1.55; }
    .trend-sources .evidence-links { margin-top: 12px; gap: 8px; }
    .trend-sources .evidence-links > span { color: var(--blue-dark); }
    .trend-sources .evidence-links a { gap: 4px; border-color: var(--line-strong); background: var(--blue-soft); }
    .trend-sources-cover .evidence-links { margin-top: 8px; }
    .trend-track, .heat-track { height: 4px; border-radius: 4px; background: var(--surface-strong); overflow: hidden; }
    .trend-track span, .heat-track i { display: block; height: 100%; background: var(--primary); border-radius: inherit; }

    .discovery-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 20px;
    }
    .filter-group { display: flex; gap: 8px; flex-wrap: wrap; }
    .filter-button {
      min-height: 40px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--bg);
      color: var(--muted);
      cursor: pointer;
      font-size: 12px;
      font-weight: 680;
      transition: 180ms ease;
    }
    .filter-button:hover { border-color: var(--line-strong); color: var(--ink); background: var(--surface); }
    .filter-button[aria-pressed="true"] { background: var(--ink); border-color: var(--ink); color: var(--bg); }
    .filter-button:focus-visible, .search-box:focus-within { outline: 3px solid oklch(0.49 0.14 160 / 0.22); outline-offset: 2px; }
    .search-box {
      width: min(280px, 100%);
      min-height: 44px;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      gap: 9px;
      color: var(--muted);
      background: var(--bg);
    }
    .search-box input { min-width: 0; width: 100%; border: 0; outline: 0; background: transparent; color: var(--ink); font-size: 13px; }
    .search-box input::placeholder { color: var(--faint); }

    .discovery-header, .discovery-row {
      display: grid;
      grid-template-columns: 42px minmax(250px, 1.15fr) minmax(210px, 0.85fr) minmax(240px, 1fr);
      gap: 24px;
    }
    .discovery-header {
      padding: 12px 16px;
      color: var(--faint);
      font: 700 10px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border-block: 1px solid var(--line);
      background: var(--surface);
    }
    .discovery-row {
      padding: 24px 16px;
      border-bottom: 1px solid var(--line);
      transition: 180ms ease;
    }
    .discovery-row:hover { background: var(--surface); box-shadow: var(--shadow-hover); position: relative; z-index: 1; }
    .discovery-row[hidden] { display: none; }
    .discovery-index { color: var(--faint); font: 650 11px/1.5 ui-monospace, "SFMono-Regular", Menlo, monospace; }
    .tag-line { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 10px; }
    .source-tag, .category-tag, .status-tag {
      min-height: 24px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 0 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 720;
    }
    .source-github { color: var(--ink); background: var(--surface-strong); }
    .source-product { color: var(--blue-dark); background: var(--blue-soft); }
    .category-tag { color: var(--primary-dark); background: var(--primary-soft); }
    .status-tag { color: var(--muted); border: 1px solid var(--line); }
    .discovery-main h3 { margin: 0; font-size: 18px; line-height: 1.3; letter-spacing: -0.02em; }
    .maker { color: var(--faint); font-size: 12px; font-weight: 500; }
    .discovery-main p, .discovery-evidence p, .discovery-opportunity p { margin: 8px 0 0; color: var(--muted); font-size: 13px; line-height: 1.62; }
    .signal-axes {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 8px;
    }
    .signal-axis { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px; align-items: baseline; }
    .signal-axis b { color: var(--faint); font-size: 15px; font-weight: 720; }
    .signal-axis span { color: var(--ink); font-size: 15px; font-weight: 620; line-height: 1.45; }
    .heat { margin-top: 18px; }
    .heat > span { display: block; margin-bottom: 7px; color: var(--faint); font-size: 10px; }
    .heat-track i { background: var(--blue); }
    .source-link {
      width: fit-content;
      min-height: 36px;
      margin-top: 14px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--blue-dark);
      font-size: 12px;
      font-weight: 700;
      text-decoration: none;
    }
    .source-link:hover { text-decoration: underline; text-underline-offset: 3px; }
    .source-link:focus-visible { outline: 3px solid oklch(0.54 0.18 250 / 0.20); outline-offset: 2px; border-radius: 4px; }
    .empty-state {
      display: none;
      padding: 56px 24px;
      text-align: center;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
    }
    .empty-state strong { display: block; color: var(--ink); margin-bottom: 8px; }

    .update-list { border-top: 1px solid var(--line); }
    .update-row {
      display: grid;
      grid-template-columns: 12px minmax(0, 1fr) auto;
      gap: 18px;
      align-items: start;
      padding: 22px 0;
      border-bottom: 1px solid var(--line);
    }
    .update-dot { width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: var(--amber); }
    .update-row h3 { margin: 0; font-size: 16px; }
    .update-row p { margin: 6px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .update-row .source-link { margin-top: 0; }
    .empty-inline { padding: 28px; background: var(--surface); color: var(--muted); border-radius: var(--radius-md); }

    .matrix { border: 1px solid var(--line); border-radius: var(--radius-md); overflow: hidden; }
    .matrix-head, .matrix-row {
      display: grid;
      grid-template-columns: 0.8fr 1fr 1.3fr 110px;
      gap: 20px;
      padding: 16px 20px;
    }
    .matrix-head {
      background: var(--surface);
      color: var(--faint);
      font: 700 10px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .matrix-row { border-top: 1px solid var(--line); font-size: 13px; line-height: 1.55; }
    .matrix-concept { font-weight: 690; color: var(--primary-dark); }
    .matrix-concept .evidence-links { margin-top: 10px; font-weight: 400; }
    .confidence {
      min-height: 26px;
      padding: 0 8px;
      display: inline-flex;
      align-items: center;
      border-radius: 6px;
      background: var(--primary-soft);
      color: var(--primary-dark);
      font-size: 10px;
      font-weight: 730;
    }

    .recommendation-list { display: grid; gap: 16px; }
    .recommendation {
      display: grid;
      grid-template-columns: 44px minmax(240px, 0.9fr) minmax(360px, 1.1fr);
      gap: 24px;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
    }
    .recommendation-rank { color: var(--primary-dark); font: 750 18px/1 ui-monospace, "SFMono-Regular", Menlo, monospace; }
    .recommendation-head h3 { margin: 8px 0; font-size: 24px; line-height: 1.2; letter-spacing: -0.025em; }
    .recommendation-head p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.62; }
    .recommendation dl { margin: 0; display: grid; gap: 0; }
    .recommendation dl div { padding: 0 0 14px; margin-bottom: 14px; border-bottom: 1px solid var(--line); }
    .recommendation dl div:last-child { padding: 0; margin: 0; border: 0; }
    .recommendation dt { color: var(--faint); font-size: 10px; font-weight: 720; letter-spacing: 0.06em; }
    .recommendation dd { margin: 6px 0 0; font-size: 12px; line-height: 1.58; }

    .action-layout { display: grid; grid-template-columns: minmax(0, 0.78fr) minmax(380px, 1.22fr); gap: 40px; }
    .action-intro {
      padding: 32px;
      border-radius: var(--radius-lg);
      background: var(--primary-soft);
      color: var(--primary-dark);
    }
    .action-intro span { font: 700 11px/1 ui-monospace, "SFMono-Regular", Menlo, monospace; letter-spacing: 0.08em; }
    .action-intro strong { display: block; margin-top: 16px; font-size: 52px; line-height: 0.9; letter-spacing: -0.055em; }
    .action-intro p { margin: 18px 0 0; max-width: 32ch; font-size: 14px; line-height: 1.65; }
    .action-list { list-style: none; padding: 0; margin: 0; border-top: 1px solid var(--line); }
    .action-list li { display: grid; grid-template-columns: 74px 1fr; gap: 18px; padding: 20px 0; border-bottom: 1px solid var(--line); }
    .action-time { color: var(--primary-dark); font: 700 11px/1.5 ui-monospace, "SFMono-Regular", Menlo, monospace; }
    .action-list strong { font-size: 14px; }
    .action-list p { margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .action-list .source-link { min-height: 30px; margin-top: 8px; font-size: 10px; }

    .coverage-grid { display: grid; grid-template-columns: minmax(0, 0.85fr) minmax(400px, 1.15fr); gap: 44px; }
    .coverage-summary {
      padding: 28px;
      background: var(--surface);
      border-radius: var(--radius-md);
    }
    .coverage-summary strong { display: block; font-size: 24px; letter-spacing: -0.03em; }
    .coverage-summary p { margin: 12px 0 0; color: var(--muted); font-size: 13px; line-height: 1.65; }
    .coverage-meta { margin-top: 22px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .coverage-meta div { padding: 14px; background: var(--bg); border: 1px solid var(--line); border-radius: var(--radius-sm); }
    .coverage-meta span, .coverage-meta b { display: block; }
    .coverage-meta span { color: var(--faint); font-size: 10px; }
    .coverage-meta b { margin-top: 5px; font-size: 16px; }
    .artifact-links { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--line); }
    .artifact-links > span { display: block; margin-bottom: 9px; color: var(--faint); font-size: 10px; font-weight: 720; letter-spacing: 0.06em; }
    .artifact-links div { display: flex; flex-wrap: wrap; gap: 8px; }
    .artifact-links a {
      min-height: 34px;
      padding: 0 10px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--bg);
      color: var(--blue-dark);
      font-size: 10px;
      font-weight: 700;
      text-decoration: none;
    }
    .artifact-links a:hover { border-color: var(--blue); background: var(--blue-soft); }
    .artifact-links a:focus-visible { outline: 3px solid oklch(0.54 0.18 250 / 0.20); outline-offset: 2px; }
    .source-list { list-style: none; padding: 0; margin: 0; border-top: 1px solid var(--line); }
    .source-list li {
      display: grid;
      grid-template-columns: 10px minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 16px 0;
      border-bottom: 1px solid var(--line);
    }
    .source-status { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); }
    .source-list strong, .source-list span { display: block; }
    .source-list strong { font-size: 13px; }
    .source-list div span { margin-top: 3px; color: var(--faint); font-size: 10px; }
    .source-list .source-link { margin-top: 0; }

    footer {
      min-height: 90px;
      padding: 24px 32px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 24px;
      color: var(--muted);
      font-size: 11px;
    }
    footer strong { color: var(--ink); }

    html[data-capture="cover"] body { min-width: 1080px; background: var(--bg); }
    html[data-capture="cover"] .report-shell { display: none; }
    html[data-capture="cover"] .share-cover {
      width: 1080px;
      height: 1440px;
      padding: 64px 72px 54px;
      display: flex;
      flex-direction: column;
      background: var(--bg);
      overflow: hidden;
      position: relative;
    }
    html[data-capture="cover"] .share-cover::after {
      content: "";
      position: absolute;
      inset: 0;
      border: 1px solid var(--line);
      pointer-events: none;
    }
    .cover-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 28px;
      border-bottom: 1px solid var(--line);
    }
    .cover-brand { display: flex; align-items: center; gap: 14px; font-size: 23px; font-weight: 780; letter-spacing: -0.03em; }
    .cover-brand .brand-mark { width: 34px; height: 34px; }
    .cover-edition { color: var(--muted); font: 700 13px/1 ui-monospace, "SFMono-Regular", Menlo, monospace; letter-spacing: 0.08em; }
    .cover-hero { padding: 54px 0 46px; display: grid; grid-template-columns: minmax(0, 1fr) 176px; gap: 44px; align-items: end; }
    .cover-kicker { color: var(--primary-dark); font: 700 13px/1 ui-monospace, "SFMono-Regular", Menlo, monospace; letter-spacing: 0.12em; }
    .cover-hero h1 { margin-top: 20px; font-size: 70px; line-height: 1.02; max-width: 760px; }
    .cover-date-box {
      padding: 22px 20px;
      background: var(--ink);
      color: var(--bg);
      border-radius: var(--radius-md);
    }
    .cover-date-box strong { display: block; font-size: 36px; letter-spacing: -0.05em; }
    .cover-date-box span { display: block; margin-top: 6px; color: oklch(0.78 0.01 245); font-size: 13px; }
    .cover-brief {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border-block: 1px solid var(--line);
    }
    .cover-brief article { min-height: 158px; padding: 24px 24px 24px 0; border-right: 1px solid var(--line); }
    .cover-brief article + article { padding-left: 24px; }
    .cover-brief article:last-child { border-right: 0; padding-right: 0; }
    .cover-brief span { color: var(--muted); font-size: 12px; font-weight: 720; letter-spacing: 0.06em; }
    .cover-brief p { margin: 12px 0 0; font-size: 17px; line-height: 1.55; letter-spacing: -0.012em; }
    .cover-brief strong { color: var(--primary-dark); }
    .cover-main { flex: 1; min-height: 0; display: grid; grid-template-columns: 0.86fr 1.14fr; gap: 48px; padding-top: 44px; }
    .cover-section-label { margin-bottom: 18px; display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 12px; font-weight: 740; letter-spacing: 0.06em; }
    .cover-section-label::before { content: ""; width: 20px; height: 2px; background: var(--primary); }
    .cover-trends .trend-row { grid-template-columns: 32px minmax(0, 1fr) 60px; gap: 12px; padding: 16px 0; }
    .cover-trends .trend-title-line h3 { font-size: 17px; }
    .cover-trends .trend-summary { font-size: 15px; margin: 4px 0 12px; line-height: 1.48; }
    .cover-trends .trend-score { min-width: 60px; padding: 8px 4px; }
    .cover-trends .trend-score strong { font-size: 20px; }
    .cover-trends .trend-score span { font-size: 15px; }
    .cover-trends .trend-sources .evidence-links > span { display: none; }
    .cover-trends .trend-sources .evidence-links a {
      min-height: 28px;
      padding-inline: 0;
      border: 0;
      background: transparent;
    }
    .cover-mini-stats {
      margin-top: 26px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      border-block: 1px solid var(--line);
    }
    .cover-mini-stats div { padding: 17px 0; }
    .cover-mini-stats div:nth-child(odd) { border-right: 1px solid var(--line); }
    .cover-mini-stats div:nth-child(even) { padding-left: 20px; }
    .cover-mini-stats div:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
    .cover-mini-stats strong { display: block; font-size: 24px; letter-spacing: -0.04em; }
    .cover-mini-stats span { display: block; margin-top: 5px; color: var(--muted); font-size: 10px; }
    .cover-watch { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
    .cover-watch li { display: grid; grid-template-columns: 32px 1fr; gap: 14px; padding: 15px 0; border-bottom: 1px solid var(--line); }
    .cover-watch > li > span { color: var(--faint); font: 650 11px/1.5 ui-monospace, "SFMono-Regular", Menlo, monospace; }
    .cover-watch li div div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .cover-watch strong { font-size: 16px; }
    .cover-watch strong a { color: inherit; text-decoration: none; }
    .cover-watch small { color: var(--blue-dark); font-size: 10px; font-weight: 700; }
    .cover-watch p { margin: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 1.48; }
    .cover-opportunity {
      margin-top: 32px;
      padding: 26px 28px;
      background: var(--primary-soft);
      color: var(--primary-dark);
      border-radius: var(--radius-md);
      display: grid;
      grid-template-columns: 1fr 78px;
      gap: 24px;
      align-items: center;
    }
    .cover-opportunity span { font-size: 11px; font-weight: 720; letter-spacing: 0.06em; }
    .cover-opportunity h2 { margin: 8px 0 7px; font-size: 22px; line-height: 1.2; letter-spacing: -0.03em; }
    .cover-opportunity p { margin: 0; font-size: 12px; line-height: 1.5; }
    .cover-score { text-align: right; }
    .cover-score strong { display: block; font-size: 48px; line-height: 0.9; letter-spacing: -0.06em; }
    .cover-score small { display: block; margin-top: 6px; font-size: 10px; }
    .cover-actions { margin: 24px 0 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
    .cover-actions li { display: grid; grid-template-columns: 38px 1fr; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); }
    .cover-actions span { color: var(--primary-dark); font: 700 10px/1.5 ui-monospace, "SFMono-Regular", Menlo, monospace; }
    .cover-actions p { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.45; }
    .cover-footer {
      padding-top: 26px;
      border-top: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      color: var(--muted);
      font-size: 11px;
    }
    .cover-footer strong { color: var(--ink); }

    @media (max-width: 1100px) {
      .hero { grid-template-columns: 1fr; }
      .hero-main { border-right: 0; border-bottom: 1px solid var(--line); }
      .hero-brief { display: grid; grid-template-columns: 1fr auto; align-items: end; }
      .stat-band { grid-template-columns: repeat(2, 1fr); }
      .stat:nth-child(2) { border-right: 0; }
      .stat:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
      .workspace { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); padding: 14px 24px; overflow-x: auto; }
      .sidebar-inner { position: static; }
      .sidebar-title, .sidebar-note { display: none; }
      .section-nav { display: flex; width: max-content; }
      .section-nav a { gap: 12px; }
      .discovery-header, .discovery-row { grid-template-columns: 38px minmax(240px, 1.1fr) minmax(220px, 0.9fr); }
      .discovery-header span:last-child { display: none; }
      .discovery-opportunity { grid-column: 2 / -1; padding-top: 16px; border-top: 1px dashed var(--line); }
      .recommendation { grid-template-columns: 40px 1fr; }
      .recommendation dl { grid-column: 2; }
    }

    @media (max-width: 900px) {
      .topbar-current-date { display: none; }
    }

    @media (max-width: 760px) {
      .report-shell { border: 0; }
      .topbar { min-height: 60px; padding: 0 18px; }
      .topbar-meta > span:not(.demo-pill):not(.live-pill):not(.replay-pill) { display: none; }
      .topbar-meta > .demo-pill, .topbar-meta > .live-pill, .topbar-meta > .replay-pill { display: none; }
      .topbar-meta { min-width: 0; gap: 8px; }
      .archive-picker-label { display: none; }
      .archive-select-shell { width: min(220px, calc(100vw - 96px)); }
      .brand span:last-child { display: none; }
      .hero-main { padding: 48px 20px 40px; }
      .hero-main h1 { font-size: 42px; }
      .hero-subtitle { font-size: 16px; }
      .hero-date { margin-top: 32px; display: block; }
      .hero-date span { display: block; margin-top: 6px; }
      .hero-brief { display: block; padding: 32px 20px; }
      .source-summary { margin-top: 28px; }
      .stat-band { grid-template-columns: 1fr 1fr; }
      .stat { min-height: 104px; padding: 18px; display: block; }
      .stat-value { font-size: 31px; }
      .stat-label { margin-top: 8px; }
      .sidebar { padding-inline: 12px; }
      .report-section { padding: 48px 20px; }
      .section-heading { grid-template-columns: 1fr; gap: 14px; margin-bottom: 28px; }
      .section-heading h2 { font-size: 27px; }
      .signal-layout { grid-template-columns: 1fr; }
      .opportunity-panel { position: static; }
      .trend-row { grid-template-columns: 28px minmax(0, 1fr) 64px; gap: 12px; }
      .trend-score { min-width: 64px; padding-inline: 4px; }
      .trend-sources .evidence-links { align-items: stretch; }
      .discovery-toolbar { align-items: stretch; flex-direction: column; }
      .search-box { width: 100%; }
      .discovery-header { display: none; }
      .discovery-row { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 12px; padding: 22px 0; }
      .discovery-main, .discovery-evidence, .discovery-opportunity { grid-column: 2; }
      .discovery-evidence, .discovery-opportunity { padding-top: 16px; border-top: 1px dashed var(--line); }
      .discovery-evidence::before, .discovery-opportunity::before {
        content: attr(data-label);
        display: block;
        margin-bottom: 7px;
        color: var(--faint);
        font-size: 10px;
        font-weight: 720;
        letter-spacing: 0.06em;
      }
      .update-row { grid-template-columns: 10px 1fr; }
      .update-row .source-link { grid-column: 2; }
      .matrix { border: 0; border-radius: 0; }
      .matrix-head { display: none; }
      .matrix-row { grid-template-columns: 1fr; gap: 14px; padding: 20px 0; }
      .matrix-row > div::before {
        content: attr(data-label);
        display: block;
        margin-bottom: 5px;
        color: var(--faint);
        font-size: 10px;
        font-weight: 720;
        letter-spacing: 0.06em;
      }
      .recommendation { grid-template-columns: 28px 1fr; padding: 22px 18px; gap: 12px; }
      .recommendation dl { grid-column: 2; }
      .action-layout, .coverage-grid { grid-template-columns: 1fr; }
      .action-intro strong { font-size: 44px; }
      .coverage-grid { gap: 28px; }
      footer { align-items: flex-start; flex-direction: column; }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition-duration: 0.01ms !important; }
    }

    @media (pointer: coarse) {
      .evidence-links a, .source-link, .artifact-links a { min-height: 44px; }
    }

    @media print {
      .topbar, .sidebar, .discovery-toolbar { display: none; }
      .report-shell { width: 100%; border: 0; }
      .workspace { grid-template-columns: 1fr; }
      .report-section { break-inside: avoid; }
      .opportunity-panel { position: static; }
    }
  </style>
  <script>
    if (new URLSearchParams(location.search).get("capture") === "cover") {
      document.documentElement.dataset.capture = "cover";
    }
  </script>
</head>
<body>
  <section class="share-cover" id="share-cover" aria-label="日报视觉摘要">
    <header class="cover-top">
      <div class="cover-brand">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span>SIGNAL BRIEF</span>
      </div>
      <span class="cover-edition">$edition · $demo_label</span>
    </header>
    <div class="cover-hero">
      <div>
        <span class="cover-kicker">AI PRODUCT OPPORTUNITY</span>
        <h1>$title</h1>
      </div>
      <div class="cover-date-box">
        <strong>$cover_date</strong>
        <span>$weekday</span>
      </div>
    </div>
    <div class="cover-brief">$cover_brief</div>
    <div class="cover-main">
      <div class="cover-trends">
        <div class="cover-section-label">今日趋势雷达</div>
        $cover_trends
        <div class="cover-mini-stats">$cover_stats</div>
      </div>
      <div>
        <div class="cover-section-label">今日值得看</div>
        <ol class="cover-watch">$cover_watch</ol>
        <div class="cover-opportunity">
          <div>
            <span>$opportunity_eyebrow</span>
            <h2>$opportunity_title</h2>
            <p>$opportunity_next</p>
          </div>
          <div class="cover-score">
            <strong>$opportunity_score</strong>
            <small>机会指数</small>
          </div>
        </div>
        <ol class="cover-actions">$cover_actions</ol>
      </div>
    </div>
    <footer class="cover-footer">
      <span><strong>$new_count</strong> $discovery_count_suffix · <strong>$update_count</strong> 个重要更新 · 排除 <strong>$duplicate_count</strong> 个重复项</span>
      <span>GitHub Trending × Product Hunt</span>
    </footer>
  </section>

  <div class="report-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span>SIGNAL BRIEF</span>
      </div>
      <div class="topbar-meta">
        $archive_picker
        <span class="topbar-current-date">$date · $weekday</span>
        $status_pill
      </div>
    </header>

    <section class="hero">
      <div class="hero-main">
        <div class="kicker">$edition · AI PRODUCT INTELLIGENCE</div>
        <h1>$title</h1>
        <p class="hero-subtitle">$subtitle</p>
        <div class="hero-date">
          <strong>$date</strong>
          <span>$weekday · 生成于 $generated_at</span>
        </div>
      </div>
      <aside class="hero-brief">
        <ol class="brief-list">$brief_rows</ol>
        <div class="source-summary">
          <span><strong>来源</strong> GitHub · Product Hunt</span>
          <span><strong>去重</strong> 最近 $history_days 天</span>
        </div>
      </aside>
    </section>

    <section class="stat-band" aria-label="今日概览">$stat_rows</section>

    <div class="workspace">
      <aside class="sidebar">
        <div class="sidebar-inner">
          <p class="sidebar-title">Report index</p>
          <nav class="section-nav" aria-label="日报章节">
            <a href="#signals">趋势与判断 <span>01</span></a>
            <a href="#discoveries">$discovery_nav_label <span>02</span></a>
            <a href="#updates">重要更新 <span>03</span></a>
            <a href="#opportunities">交叉机会 <span>04</span></a>
            <a href="#experience">值得体验 <span>05</span></a>
            <a href="#actions">行动清单 <span>06</span></a>
            <a href="#coverage">数据覆盖 <span>07</span></a>
          </nav>
          <div class="sidebar-note">
            <strong>阅读顺序</strong>
            <p>先看趋势与今日机会，再用原始链接验证证据。动态指标以页面标注的查询时间为准。</p>
          </div>
        </div>
      </aside>

      <main>
        <section class="report-section" id="signals">
          <header class="section-heading">
            <div><span class="section-number">01 / SIGNALS</span><h2>趋势雷达与今日判断</h2></div>
            <p>把分散的项目热度转成可验证的产品判断。分数表达优先级，不代表精确市场规模。</p>
          </header>
          <div class="signal-layout">
            <article class="opportunity-panel">
              <span class="eyebrow">$opportunity_eyebrow</span>
              <h3>$opportunity_title</h3>
              <p>$opportunity_thesis</p>
              <div class="score-line"><strong>$opportunity_score</strong><span>$opportunity_confidence</span></div>
              <ul class="why-list">$opportunity_reasons</ul>
              <div class="next-move"><span>下一步验证</span><p>$opportunity_next</p></div>
              $opportunity_sources
            </article>
            <div class="trend-list">
              <div class="trend-list-heading"><span>今日趋势雷达</span><small>优先级评分 / 100</small></div>
              $trend_rows
            </div>
          </div>
        </section>

        <section class="report-section" id="discoveries">
          <header class="section-heading">
            <div><span class="section-number">02 / DISCOVERIES</span><h2>$discovery_heading</h2></div>
            <p>$discovery_description</p>
          </header>
          <div class="discovery-toolbar">
            <div class="filter-group" role="group" aria-label="按来源筛选">
              <button class="filter-button" type="button" data-filter="all" aria-pressed="true">全部</button>
              <button class="filter-button" type="button" data-filter="github" aria-pressed="false">GitHub</button>
              <button class="filter-button" type="button" data-filter="product" aria-pressed="false">Product Hunt</button>
            </div>
            <label class="search-box">
              $search_icon
              <input id="discovery-search" type="search" placeholder="搜索项目、分类或机会" autocomplete="off">
            </label>
          </div>
          <div class="discovery-header"><span>#</span><span>项目与价值</span><span>变化与证据</span><span>产品机会</span></div>
          <div id="discovery-list">$discovery_rows</div>
          <div class="empty-state" id="discovery-empty"><strong>没有匹配结果</strong>换一个关键词，或恢复“全部”来源。</div>
        </section>

        <section class="report-section" id="updates">
          <header class="section-heading">
            <div><span class="section-number">03 / UPDATES</span><h2>重要更新</h2></div>
            <p>$updates_description</p>
          </header>
          <div class="update-list">$update_rows</div>
        </section>

        <section class="report-section" id="opportunities">
          <header class="section-heading">
            <div><span class="section-number">04 / CROSS SIGNALS</span><h2>技术供给 × 用户需求</h2></div>
            <p>产品概念只是待验证假设。置信度同时考虑能力成熟度、需求频率和差异化空间。</p>
          </header>
          <div class="matrix">
            <div class="matrix-head"><span>技术供给</span><span>需求信号</span><span>产品概念</span><span>置信度</span></div>
            $cross_rows
          </div>
        </section>

        <section class="report-section" id="experience">
          <header class="section-heading">
            <div><span class="section-number">05 / EXPERIENCE</span><h2>今日最值得体验</h2></div>
            <p>优先选择能快速暴露能力边界的项目，并在动手前明确运行成本、风险与核心假设。</p>
          </header>
          <div class="recommendation-list">$recommendation_rows</div>
        </section>

        <section class="report-section" id="actions">
          <header class="section-heading">
            <div><span class="section-number">06 / ACTIONS</span><h2>30 分钟行动清单</h2></div>
            <p>把阅读转成一次低风险验证；不自动克隆、安装或运行陌生项目。</p>
          </header>
          <div class="action-layout">
            <div class="action-intro">
              <span>TODAY'S WINDOW</span>
              <strong>30 min</strong>
              <p>今天只验证一个流程和一个关键假设。完成比收藏更多项目更有价值。</p>
            </div>
            <ol class="action-list">$action_rows</ol>
          </div>
        </section>

        <section class="report-section" id="coverage">
          <header class="section-heading">
            <div><span class="section-number">07 / COVERAGE</span><h2>数据覆盖与去重状态</h2></div>
            <p>日报的可信度来自可见的数据缺口。无法读取的动态指标不会被猜测或补写。</p>
          </header>
          <div class="coverage-grid">
            <div class="coverage-summary">
              <strong>历史去重：$coverage_status</strong>
              <p>$coverage_note</p>
              <div class="coverage-meta">
                <div><span>检索范围</span><b>$history_days 天</b></div>
                <div><span>排除重复</span><b>$duplicate_count 项</b></div>
              </div>
              <div class="artifact-links">
                <span>本日报源文件</span>
                <div>
                  <a href="$json_filename">结构化数据 JSON $arrow_icon</a>
                  <a href="render_report.py">HTML 生成器 $arrow_icon</a>
                  <a href="collect_report.py">实时采集器 $arrow_icon</a>
                  <a href="capture-report.mjs">PNG 截图脚本 $arrow_icon</a>
                  $snapshot_artifact
                </div>
              </div>
            </div>
            <ul class="source-list">$source_rows</ul>
          </div>
        </section>
      </main>
    </div>

    <footer>
      <span><strong>Signal Brief</strong> · $date · $collection_label</span>
      <span>所有项目判断都应回到原始页面验证</span>
    </footer>
  </div>

  <script>
    (function () {
      var activeFilter = "all";
      var search = "";
      var buttons = Array.from(document.querySelectorAll(".filter-button"));
      var rows = Array.from(document.querySelectorAll(".discovery-row"));
      var empty = document.getElementById("discovery-empty");
      var input = document.getElementById("discovery-search");
      var archive = document.getElementById("report-archive");

      if (archive) {
        archive.addEventListener("change", function () {
          if (archive.value) window.location.assign(archive.value);
        });
      }

      function applyFilters() {
        var visible = 0;
        rows.forEach(function (row) {
          var sourceMatch = activeFilter === "all" || row.dataset.source === activeFilter;
          var searchMatch = !search || row.dataset.search.indexOf(search) !== -1;
          row.hidden = !(sourceMatch && searchMatch);
          if (!row.hidden) visible += 1;
        });
        empty.style.display = visible ? "none" : "block";
      }

      buttons.forEach(function (button) {
        button.addEventListener("click", function () {
          activeFilter = button.dataset.filter;
          buttons.forEach(function (item) {
            item.setAttribute("aria-pressed", item === button ? "true" : "false");
          });
          applyFilters();
        });
      });

      input.addEventListener("input", function () {
        search = input.value.trim().toLowerCase();
        applyFilters();
      });
    })();
  </script>
</body>
</html>
"""
)


def build_html(
    data: dict[str, Any],
    archive_entries: list[dict[str, Any]] | None = None,
) -> str:
    meta = data.get("meta", {})
    opportunity = data.get("opportunity", {})
    coverage = data.get("coverage", {})
    brief = data.get("brief", [])
    cover_brief = "".join(
        '<article><span>'
        + esc(item.get("label", ""))
        + "</span><p>"
        + esc(item.get("text", "")).replace(
            esc(item.get("emphasis", "")),
            "<strong>" + esc(item.get("emphasis", "")) + "</strong>",
        )
        + "</p></article>"
        for item in brief[:3]
    )
    reasons = "".join("<li>" + esc(reason) + "</li>" for reason in opportunity.get("whyNow", []))
    is_demo = bool(meta.get("isDemo"))
    collection_mode = str(meta.get("collectionMode", "demo" if is_demo else "live"))
    collection_label = str(
        meta.get(
            "collectionLabel",
            meta.get("demoLabel", "视觉样例") if is_demo else "实时采集",
        )
    )
    if is_demo:
        status_pill = '<span class="demo-pill">' + esc(collection_label) + "</span>"
    elif collection_mode == "replay":
        status_pill = '<span class="replay-pill">历史快照回放</span>'
    else:
        status_pill = '<span class="live-pill"><i class="live-dot"></i>已完成实时采集</span>'
    snapshot_value = str(coverage.get("snapshotPath", ""))
    snapshot_artifact = (
        '<a href="' + esc(snapshot_value) + '">当日采集快照 ' + icon("arrow", 12) + "</a>"
        if snapshot_value
        else ""
    )
    values = {
        "page_title": esc(meta.get("title", "AI 产品机会日报")) + "｜" + esc(meta.get("date", "")),
        "title": esc(meta.get("title", "AI 产品机会日报")),
        "subtitle": esc(meta.get("subtitle", "")),
        "date": esc(meta.get("date", "")),
        "weekday": esc(meta.get("weekday", "")),
        "edition": esc(meta.get("edition", "")),
        "generated_at": esc(meta.get("generatedAt", "")),
        "demo_label": esc(collection_label),
        "collection_label": esc(collection_label),
        "status_pill": status_pill,
        "archive_picker": render_archive_picker(
            archive_entries or [], str(meta.get("date", ""))
        ),
        "cover_date": esc(meta.get("date", "")[5:].replace("-", ".")),
        "cover_brief": cover_brief,
        "brief_rows": render_brief(brief),
        "stat_rows": render_stats(data.get("stats", [])),
        "trend_rows": render_trends(data.get("trendSignals", [])),
        "cover_trends": render_trends(data.get("trendSignals", []), cover=True),
        "cover_watch": render_cover_watch(data),
        "cover_stats": render_cover_stats(data.get("stats", [])),
        "cover_actions": render_cover_actions(data.get("actions", [])),
        "discovery_rows": render_discovery_rows(data),
        "update_rows": render_updates(data.get("updates", [])),
        "cross_rows": render_cross(data.get("crossOpportunities", [])),
        "recommendation_rows": render_recommendations(data.get("recommendations", [])),
        "action_rows": render_actions(data.get("actions", [])),
        "source_rows": render_sources(coverage.get("sources", [])),
        "search_icon": icon("search", 17),
        "arrow_icon": icon("arrow", 12),
        "json_filename": esc(str(meta.get("date", "")) + ".json"),
        "snapshot_artifact": snapshot_artifact,
        "discovery_heading": "今日新发现" if is_demo else "今日信号项目",
        "discovery_nav_label": "新发现" if is_demo else "信号项目",
        "discovery_description": (
            "统一比较 GitHub 的技术供给与 Product Hunt 的市场信号；不会为了数量降低筛选标准。"
            if is_demo
            else "每个项目分别标注新鲜度、动量与实质变化；成熟热项不会再被误写成今天上线。"
        ),
        "updates_description": (
            "只收录最近 30 天出现过、但今天发生实质变化的项目；它们不会重复计入新发现。"
            if is_demo
            else "只有 Release 或明确产品发布进入这里；普通 push 只作为活跃证据，不自动升级为重要更新。"
        ),
        "opportunity_eyebrow": esc(opportunity.get("eyebrow", "今日优先机会")),
        "opportunity_title": esc(opportunity.get("title", "")),
        "opportunity_thesis": esc(opportunity.get("thesis", "")),
        "opportunity_score": esc(opportunity.get("score", "—")),
        "opportunity_confidence": esc(opportunity.get("confidence", "")),
        "opportunity_reasons": reasons,
        "opportunity_next": esc(opportunity.get("nextMove", "")),
        "opportunity_sources": render_evidence_links(
            opportunity.get("sources"), theme="dark", label="判断依据"
        ),
        "history_days": esc(coverage.get("historyDays", 30)),
        "duplicate_count": esc(coverage.get("duplicatesExcluded", 0)),
        "coverage_status": esc(coverage.get("status", "未知")),
        "coverage_note": esc(coverage.get("note", "")),
        "new_count": esc(len(data.get("github", [])) + len(data.get("productHunt", []))),
        "discovery_count_suffix": "个新发现" if is_demo else "个今日信号",
        "update_count": esc(len(data.get("updates", []))),
    }
    return normalize_typography(PAGE.safe_substitute(values))


def validate(data: dict[str, Any]) -> None:
    required = ("meta", "brief", "stats", "trendSignals", "opportunity", "coverage")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError("缺少必需字段: " + ", ".join(missing))
    if not data.get("meta", {}).get("date"):
        raise ValueError("meta.date 不能为空")

    def require_sources(section_name: str, items: list[dict[str, Any]]) -> None:
        for index, item in enumerate(items, start=1):
            sources = item.get("sources")
            if not isinstance(sources, list) or not any(
                isinstance(source, dict) and source.get("label") and source.get("url")
                for source in sources
            ):
                raise ValueError(f"{section_name}[{index}] 至少需要一个可点击 sources 来源")

    require_sources("brief", data.get("brief", []))
    require_sources("trendSignals", data.get("trendSignals", []))
    require_sources("crossOpportunities", data.get("crossOpportunities", []))
    require_sources("opportunity", [data.get("opportunity", {})])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="日报 JSON 文件")
    parser.add_argument("--out-dir", help="输出目录，默认与脚本同目录")
    parser.add_argument("--no-latest", action="store_true", help="不更新 latest.html")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else ROOT
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    validate(data)
    date = str(data["meta"]["date"])
    html_path = out_dir / (date + ".html")
    latest_html = out_dir / "latest.html"
    index_html = out_dir / "index.html"
    archive_entries = discover_archive_entries(input_path.parent, out_dir, data)
    html_path.write_text(build_html(data, archive_entries), encoding="utf-8")
    if not args.no_latest:
        shutil.copyfile(html_path, latest_html)
        shutil.copyfile(html_path, index_html)

    print(json.dumps(
        {
            "html": str(html_path),
            "latestHtml": None if args.no_latest else str(latest_html),
            "indexHtml": None if args.no_latest else str(index_html),
            "date": date,
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
