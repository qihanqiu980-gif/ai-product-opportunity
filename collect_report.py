#!/usr/bin/env python3
"""Collect live AI product signals and build a dated report JSON.

Exact historical reports are replayed from locally archived daily snapshots.
GitHub Trending does not expose an official arbitrary-date API, so a past date
without a snapshot deliberately fails instead of fabricating a reconstruction.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
SNAPSHOT_ROOT = ROOT / "snapshots"
TIMEZONE = ZoneInfo("Asia/Shanghai")
USER_AGENT = "SignalBrief/1.0 (+https://github.com/)"
GITHUB_TRENDING_DAILY = "https://github.com/trending?since=daily"
GITHUB_TRENDING_WEEKLY = "https://github.com/trending?since=weekly"
PRODUCT_HUNT_FEED = "https://www.producthunt.com/feed"

AI_KEYWORDS = (
    " ai ",
    "agent",
    "agents",
    "llm",
    "mcp",
    "model",
    "inference",
    "prompt",
    "rag",
    "copilot",
    "automation",
    "browser",
    "coding",
    "developer tool",
    "skill",
    "memory",
    "eval",
    "observability",
    "生成",
    "智能",
    "模型",
    "自动化",
)

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Agent 技能与工具", ("agent", "mcp", "skill", "tool calling", "tools")),
    ("编码 Agent", ("coding", "code agent", "developer", "engineering", "copilot")),
    ("浏览器 Agent", ("browser", "web automation", "web agent")),
    ("知识与记忆", ("rag", "memory", "knowledge", "search", "retrieval")),
    ("可观测与评测", ("eval", "observability", "trace", "monitor")),
    ("模型与推理", ("model", "inference", "llm", "embedding")),
    ("内容生成", ("video", "image", "design", "audio", "content")),
)

CATEGORY_OPPORTUNITIES = {
    "Agent 技能与工具": "把通用技能包装成可审计、可配置、可复用的垂直工作流。",
    "编码 Agent": "从代码生成继续深入自动检查、评审、测试与交付物生成。",
    "浏览器 Agent": "围绕单一高频网页流程增加权限边界、失败恢复与人工接管。",
    "知识与记忆": "让用户能够查看、修正、授权和删除长期记忆，而不只是提升召回率。",
    "可观测与评测": "为具体行业预置评测集、质量门槛和合规审计流程。",
    "模型与推理": "围绕成本、延迟、隐私和部署约束形成面向场景的模型路由。",
    "内容生成": "把生成能力嵌入已有创作流程，并用素材管理和协作降低切换成本。",
    "AI 应用": "聚焦一个频繁发生、结果可核验的任务，而不是扩张成通用聊天入口。",
}


class CollectionError(RuntimeError):
    pass


def now_local() -> dt.datetime:
    return dt.datetime.now(TIMEZONE)


def parse_date(value: str) -> dt.date:
    if value == "today":
        return now_local().date()
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD 或 today") from error


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def local_date(value: str | None) -> dt.date | None:
    parsed = parse_timestamp(value)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(TIMEZONE).date()


def days_since(value: str | None, target_date: dt.date) -> int | None:
    created = local_date(value)
    return None if created is None else max(0, (target_date - created).days)


def clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, round(value)))


def compact_number(value: int | None) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def strip_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_text(url: str, *, headers: dict[str, str] | None = None) -> str:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/json",
    }
    request_headers.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise CollectionError(f"无法读取 {url}: {last_error}")


def github_api(path: str) -> tuple[dict[str, Any] | None, str | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = "https://api.github.com" + path
    try:
        return json.loads(fetch_text(url, headers=headers)), None
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None, None
        return None, f"GitHub API {error.code}: {path}"
    except (CollectionError, json.JSONDecodeError) as error:
        return None, str(error)


def parse_github_trending(document: str, since: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    blocks = re.findall(r'<article class="Box-row">(.*?)</article>', document, flags=re.S)
    for rank, block in enumerate(blocks, start=1):
        repository = re.search(
            r'<h2[^>]*>.*?<a[^>]+href="/([^"?#]+/[^"?#]+)"', block, flags=re.S
        )
        if not repository:
            continue
        slug = repository.group(1).strip("/")
        description_match = re.search(
            r'<p class="col-9[^>]*>(.*?)</p>', block, flags=re.S
        )
        language_match = re.search(
            r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', block, flags=re.S
        )
        stars_match = re.search(
            rf'href="/{re.escape(slug)}/stargazers"[^>]*>(.*?)</a>', block, flags=re.S
        )
        forks_match = re.search(
            rf'href="/{re.escape(slug)}/forks"[^>]*>(.*?)</a>', block, flags=re.S
        ) or re.search(
            rf'href="/{re.escape(slug)}/network/members"[^>]*>(.*?)</a>', block, flags=re.S
        )
        since_match = re.search(
            r'([\d,]+)\s+stars?\s+(today|this week|this month)', strip_markup(block), flags=re.I
        )

        def number(match: re.Match[str] | None) -> int | None:
            if not match:
                return None
            digits = re.sub(r"[^0-9]", "", strip_markup(match.group(1)))
            return int(digits) if digits else None

        owner, name = slug.split("/", 1)
        rows.append(
            {
                "identity": f"github:{slug.lower()}",
                "slug": slug,
                "owner": owner,
                "name": name,
                "url": f"https://github.com/{slug}",
                "rank": rank,
                "since": since,
                "description": strip_markup(description_match.group(1)) if description_match else "",
                "language": strip_markup(language_match.group(1)) if language_match else "",
                "totalStarsFromPage": number(stars_match),
                "forksFromPage": number(forks_match),
                "starsSince": number(since_match),
                "starsPeriod": since_match.group(2).lower() if since_match else since,
            }
        )
    return rows


def parse_product_hunt_feed(document: str) -> list[dict[str, Any]]:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(document)
    rows: list[dict[str, Any]] = []
    for rank, entry in enumerate(root.findall("atom:entry", namespace), start=1):
        title = entry.findtext("atom:title", default="", namespaces=namespace).strip()
        published = entry.findtext("atom:published", default="", namespaces=namespace)
        updated = entry.findtext("atom:updated", default="", namespaces=namespace)
        identifier = entry.findtext("atom:id", default="", namespaces=namespace)
        content = entry.findtext("atom:content", default="", namespaces=namespace)
        author = entry.findtext("atom:author/atom:name", default="", namespaces=namespace)
        url = ""
        for link in entry.findall("atom:link", namespace):
            if link.attrib.get("rel") == "alternate":
                url = link.attrib.get("href", "")
                break
        paragraphs = re.findall(r"<p>(.*?)</p>", html.unescape(content), flags=re.S)
        description = strip_markup(paragraphs[0]) if paragraphs else strip_markup(content)
        slug = url.rstrip("/").split("/")[-1] if url else identifier
        rows.append(
            {
                "identity": f"producthunt:{slug.lower()}",
                "id": identifier,
                "name": title,
                "maker": author,
                "url": url,
                "description": description,
                "publishedAt": published,
                "updatedAt": updated,
                "feedRank": rank,
            }
        )
    return rows


def is_ai_relevant(item: dict[str, Any]) -> bool:
    text = " " + " ".join(
        str(item.get(key, "")) for key in ("name", "description", "topics", "slug")
    ).lower() + " "
    return any(keyword in text for keyword in AI_KEYWORDS)


def categorize(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key, "")) for key in ("name", "description", "topics", "slug")
    ).lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "AI 应用"


def snapshot_path(report_date: dt.date, snapshot_root: Path = SNAPSHOT_ROOT) -> Path:
    return snapshot_root / report_date.isoformat() / "snapshot.json"


def load_snapshot(report_date: dt.date, snapshot_root: Path = SNAPSHOT_ROOT) -> dict[str, Any]:
    path = snapshot_path(report_date, snapshot_root)
    if not path.exists():
        raise CollectionError(
            f"{report_date.isoformat()} 没有本地快照，无法精确还原历史 Trending。"
            f"请从当天开始每日运行采集；现有快照目录：{snapshot_root}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def historical_snapshots(
    report_date: dt.date,
    history_days: int,
    snapshot_root: Path = SNAPSHOT_ROOT,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not snapshot_root.exists():
        return results
    minimum = report_date - dt.timedelta(days=history_days)
    for path in sorted(snapshot_root.glob("????-??-??/snapshot.json")):
        try:
            date_value = dt.date.fromisoformat(path.parent.name)
        except ValueError:
            continue
        if minimum <= date_value < report_date:
            try:
                results.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return results


def collect_live_snapshot(
    report_date: dt.date,
    *,
    snapshot_root: Path = SNAPSHOT_ROOT,
    enrich_limit: int = 10,
) -> dict[str, Any]:
    captured_at = now_local().isoformat(timespec="seconds")
    raw_daily = fetch_text(GITHUB_TRENDING_DAILY)
    raw_weekly = fetch_text(GITHUB_TRENDING_WEEKLY)
    raw_product_hunt = fetch_text(PRODUCT_HUNT_FEED)
    daily = parse_github_trending(raw_daily, "daily")
    weekly = parse_github_trending(raw_weekly, "weekly")
    product_hunt = parse_product_hunt_feed(raw_product_hunt)
    weekly_ranks = {item["identity"]: item["rank"] for item in weekly}
    api_errors: list[str] = []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in daily + weekly:
        if item["identity"] in seen:
            continue
        seen.add(item["identity"])
        item = dict(item)
        item["dailyRank"] = item["rank"] if item["since"] == "daily" else None
        item["weeklyRank"] = weekly_ranks.get(item["identity"])
        candidates.append(item)

    enrichment_candidates = [item for item in candidates if is_ai_relevant(item)]
    for item in enrichment_candidates[:enrich_limit]:
        repository, repository_error = github_api(f"/repos/{item['slug']}")
        release, release_error = github_api(f"/repos/{item['slug']}/releases/latest")
        if repository_error:
            api_errors.append(repository_error)
        if release_error:
            api_errors.append(release_error)
        if repository:
            item.update(
                {
                    "description": repository.get("description") or item.get("description", ""),
                    "createdAt": repository.get("created_at"),
                    "updatedAt": repository.get("updated_at"),
                    "pushedAt": repository.get("pushed_at"),
                    "totalStars": repository.get("stargazers_count"),
                    "forks": repository.get("forks_count"),
                    "language": repository.get("language") or item.get("language", ""),
                    "topics": repository.get("topics") or [],
                    "homepage": repository.get("homepage") or "",
                    "license": (repository.get("license") or {}).get("spdx_id"),
                }
            )
        if release:
            item["latestRelease"] = {
                "name": release.get("name") or release.get("tag_name"),
                "tag": release.get("tag_name"),
                "publishedAt": release.get("published_at"),
                "url": release.get("html_url"),
            }

    directory = snapshot_root / report_date.isoformat()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "github-trending-daily.html").write_text(raw_daily, encoding="utf-8")
    (directory / "github-trending-weekly.html").write_text(raw_weekly, encoding="utf-8")
    (directory / "producthunt-feed.xml").write_text(raw_product_hunt, encoding="utf-8")
    snapshot = {
        "schemaVersion": 1,
        "reportDate": report_date.isoformat(),
        "capturedAt": captured_at,
        "timezone": str(TIMEZONE),
        "mode": "live",
        "sources": {
            "githubDaily": daily,
            "githubWeekly": weekly,
            "githubRepositories": candidates,
            "productHuntFeed": product_hunt,
        },
        "sourceFiles": {
            "githubDaily": "github-trending-daily.html",
            "githubWeekly": "github-trending-weekly.html",
            "productHuntFeed": "producthunt-feed.xml",
        },
        "errors": sorted(set(api_errors)),
    }
    (directory / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return snapshot


def prior_seen_dates(history: list[dict[str, Any]]) -> dict[str, str]:
    seen: dict[str, str] = {}
    for snapshot in history:
        date_value = snapshot.get("reportDate", "")
        sources = snapshot.get("sources", {})
        for item in sources.get("githubRepositories", []) + sources.get("productHuntFeed", []):
            identity = item.get("identity")
            if identity and (identity not in seen or date_value < seen[identity]):
                seen[identity] = date_value
    return seen


def previous_github_values(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not history:
        return {}
    previous = sorted(history, key=lambda item: item.get("reportDate", ""))[-1]
    return {
        item.get("identity", ""): item
        for item in previous.get("sources", {}).get("githubRepositories", [])
        if item.get("identity")
    }


def novelty_axis(
    item: dict[str, Any],
    target_date: dt.date,
    seen_dates: dict[str, str],
    history_ready: bool,
    *,
    timestamp_key: str,
    date_label: str,
) -> dict[str, Any]:
    age = days_since(item.get(timestamp_key), target_date)
    identity = item.get("identity", "")
    first_seen = seen_dates.get(identity, target_date.isoformat())
    first_today = history_ready and identity not in seen_dates
    if age is not None and age <= 7:
        value = f"{date_label} {age} 天"
        score = 92 - age * 5
    elif age is not None and age <= 30:
        value = f"{date_label} {age} 天"
        score = 65 - age
    elif first_today:
        value = "今日首次捕获"
        score = 58
    elif age is not None:
        value = f"成熟项目 · {age} 天"
        score = 24
    else:
        value = "首发时间未知"
        score = 30
    return {
        "label": "新鲜度",
        "value": value,
        "score": clamp(score),
        "ageDays": age,
        "firstSeenAt": first_seen,
        "firstSeenToday": first_today,
    }


def momentum_axis(
    item: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    *,
    product_hunt: bool = False,
) -> dict[str, Any]:
    if product_hunt:
        rank = int(item.get("feedRank", 20))
        return {
            "label": "动量",
            "value": f"公开 Feed 第 {rank} 位",
            "score": clamp(78 - (rank - 1) * 3),
            "metric": "feed_position",
            "dataGap": "公开 Feed 不提供票数和精确日榜排名",
        }
    stars_since = int(item.get("starsSince") or 0)
    rank = int(item.get("dailyRank") or item.get("rank") or 25)
    prior = previous.get(item.get("identity", ""), {})
    total = item.get("totalStars") or item.get("totalStarsFromPage")
    previous_total = prior.get("totalStars") or prior.get("totalStarsFromPage")
    snapshot_delta = (
        int(total) - int(previous_total)
        if isinstance(total, int) and isinstance(previous_total, int)
        else None
    )
    score = clamp(28 + math.log10(stars_since + 1) * 21 + max(0, 14 - rank) * 2.2)
    value = f"+{stars_since:,} stars / {item.get('starsPeriod', 'today')}" if stars_since else f"Trending #{rank}"
    return {
        "label": "动量",
        "value": value,
        "score": score,
        "rankDaily": item.get("dailyRank"),
        "rankWeekly": item.get("weeklyRank"),
        "starsSince": stars_since,
        "snapshotStarDelta": snapshot_delta,
        "totalStars": total,
    }


def change_axis(item: dict[str, Any], target_date: dt.date, *, product_hunt: bool = False) -> dict[str, Any]:
    if product_hunt:
        updated = local_date(item.get("updatedAt"))
        published = local_date(item.get("publishedAt"))
        if published == target_date:
            value, score, material = "今日发布", 92, True
        elif updated == target_date:
            value, score, material = "今日 Feed 更新", 58, False
        else:
            value, score, material = "近期进入 Feed", 42, False
        return {
            "label": "实质变化",
            "value": value,
            "score": score,
            "material": material,
            "publishedAt": item.get("publishedAt"),
            "updatedAt": item.get("updatedAt"),
        }
    release = item.get("latestRelease") or {}
    release_age = days_since(release.get("publishedAt"), target_date)
    pushed_age = days_since(item.get("pushedAt"), target_date)
    if release_age is not None and release_age <= 7:
        value, score, material = f"近 {release_age} 天有 Release", 92 - release_age * 4, True
    elif pushed_age == 0:
        value, score, material = "今日有代码推送", 58, False
    elif pushed_age is not None and pushed_age <= 7:
        value, score, material = f"近 {pushed_age} 天活跃", 48, False
    else:
        value, score, material = "未确认重大更新", 24, False
    return {
        "label": "实质变化",
        "value": value,
        "score": clamp(score),
        "material": material,
        "pushedAt": item.get("pushedAt"),
        "latestRelease": release or None,
    }


def status_from_axes(axes: dict[str, dict[str, Any]], *, recent_label: str) -> str:
    novelty = axes["novelty"]
    momentum = axes["momentum"]
    change = axes["change"]
    age = novelty.get("ageDays")
    if age is not None and age <= 14:
        return recent_label
    if change.get("material"):
        return "重要更新"
    if novelty.get("firstSeenToday"):
        return "今日首次捕获"
    if momentum.get("score", 0) >= 68:
        return "热度异动"
    return "持续热门"


def source_ref(item: dict[str, Any]) -> dict[str, str]:
    return {"label": item.get("name") or item.get("slug") or "原始来源", "url": item.get("url", "")}


def prepare_github_items(
    snapshot: dict[str, Any],
    target_date: dt.date,
    history: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    sources = snapshot.get("sources", {})
    candidates = sources.get("githubRepositories", [])
    seen_dates = prior_seen_dates(history)
    previous = previous_github_values(history)
    history_ready = bool(history)
    enriched: list[dict[str, Any]] = []
    for raw in candidates:
        item = dict(raw)
        if not is_ai_relevant(item):
            continue
        axes = {
            "novelty": novelty_axis(
                item,
                target_date,
                seen_dates,
                history_ready,
                timestamp_key="createdAt",
                date_label="仓库创建",
            ),
            "momentum": momentum_axis(item, previous),
            "change": change_axis(item, target_date),
        }
        item["axes"] = axes
        item["category"] = categorize(item)
        item["status"] = status_from_axes(axes, recent_label="新仓库")
        item["heat"] = clamp(
            axes["momentum"]["score"] * 0.62
            + axes["novelty"]["score"] * 0.16
            + axes["change"]["score"] * 0.22
        )
        enriched.append(item)
    if not enriched:
        for raw in candidates[:limit]:
            item = dict(raw)
            axes = {
                "novelty": novelty_axis(
                    item,
                    target_date,
                    seen_dates,
                    history_ready,
                    timestamp_key="createdAt",
                    date_label="仓库创建",
                ),
                "momentum": momentum_axis(item, previous),
                "change": change_axis(item, target_date),
            }
            item.update(
                {
                    "axes": axes,
                    "category": categorize(item),
                    "status": status_from_axes(axes, recent_label="新仓库"),
                }
            )
            item["heat"] = axes["momentum"]["score"]
            enriched.append(item)
    enriched.sort(key=lambda item: (item.get("heat", 0), -(item.get("dailyRank") or 99)), reverse=True)
    results: list[dict[str, Any]] = []
    for item in enriched[:limit]:
        momentum = item["axes"]["momentum"]
        results.append(
            {
                "name": item.get("name", ""),
                "owner": item.get("owner", ""),
                "category": item["category"],
                "description": item.get("description") or "GitHub Trending 项目",
                "delta": (
                    f"GitHub Daily Trending #{item.get('dailyRank')}，"
                    f"近周期新增 {int(momentum.get('starsSince') or 0):,} stars"
                    if item.get("dailyRank")
                    else f"GitHub Weekly Trending #{item.get('weeklyRank')}"
                ),
                "metricLabel": "GitHub Trending · Daily" if item.get("dailyRank") else "GitHub Trending · Weekly",
                "metricValue": momentum["value"],
                "heat": item["heat"],
                "opportunity": CATEGORY_OPPORTUNITIES[item["category"]],
                "url": item.get("url", ""),
                "status": item["status"],
                "axes": item["axes"],
                "sourceMeta": {
                    "createdAt": item.get("createdAt"),
                    "pushedAt": item.get("pushedAt"),
                    "totalStars": item.get("totalStars") or item.get("totalStarsFromPage"),
                    "language": item.get("language"),
                    "license": item.get("license"),
                },
            }
        )
    return results


def prepare_product_hunt_items(
    snapshot: dict[str, Any],
    target_date: dt.date,
    history: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    candidates = snapshot.get("sources", {}).get("productHuntFeed", [])
    seen_dates = prior_seen_dates(history)
    history_ready = bool(history)
    results: list[dict[str, Any]] = []
    for raw in candidates:
        if not is_ai_relevant(raw):
            continue
        category = categorize(raw)
        axes = {
            "novelty": novelty_axis(
                raw,
                target_date,
                seen_dates,
                history_ready,
                timestamp_key="publishedAt",
                date_label="PH 发布",
            ),
            "momentum": momentum_axis(raw, {}, product_hunt=True),
            "change": change_axis(raw, target_date, product_hunt=True),
        }
        status = status_from_axes(axes, recent_label="近期发布")
        heat = clamp(
            axes["momentum"]["score"] * 0.48
            + axes["novelty"]["score"] * 0.30
            + axes["change"]["score"] * 0.22
        )
        results.append(
            {
                "name": raw.get("name", ""),
                "maker": raw.get("maker", ""),
                "category": category,
                "target": "关注新产品与 AI 工作流的早期用户",
                "description": raw.get("description") or "Product Hunt 公开 Feed 产品",
                "signal": (
                    f"公开 Feed 于 {raw.get('updatedAt', '')[:10]} 更新；"
                    "Feed 不提供票数与精确日榜排名"
                ),
                "heat": heat,
                "opportunity": CATEGORY_OPPORTUNITIES[category],
                "url": raw.get("url", ""),
                "status": status,
                "axes": axes,
                "sourceMeta": {
                    "publishedAt": raw.get("publishedAt"),
                    "updatedAt": raw.get("updatedAt"),
                    "feedRank": raw.get("feedRank"),
                },
            }
        )
        if len(results) >= limit:
            break
    return results


def choose_sources(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(source_ref(item))
        if len(sources) >= limit:
            break
    return sources


def build_trends(all_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fallback = all_items[:3]
    if not fallback:
        raise CollectionError("实时来源没有可用于判断的 AI 项目")

    newest = sorted(all_items, key=lambda item: item.get("axes", {}).get("novelty", {}).get("score", 0), reverse=True)
    momentum = sorted(all_items, key=lambda item: item.get("axes", {}).get("momentum", {}).get("score", 0), reverse=True)
    changed = sorted(all_items, key=lambda item: item.get("axes", {}).get("change", {}).get("score", 0), reverse=True)

    top_momentum = momentum[0]
    top_newest = newest[0]
    material = [item for item in changed if item.get("axes", {}).get("change", {}).get("material")]
    top_changed = material[0] if material else changed[0]
    material_count = len(material)
    return [
        {
            "rank": 1,
            "name": "动量上升",
            "score": top_momentum["axes"]["momentum"]["score"],
            "summary": f"{top_momentum['name']} 是当前增长最明显的公开信号。",
            "evidence": top_momentum["axes"]["momentum"]["value"],
            "sources": choose_sources(momentum, 3),
        },
        {
            "rank": 2,
            "name": "新建、发布与首次捕获",
            "score": top_newest["axes"]["novelty"]["score"],
            "summary": "把仓库创建、Product Hunt 发布与首次进入本地监控分开。",
            "evidence": f"当前最高新鲜度信号：{top_newest['name']} · {top_newest['axes']['novelty']['value']}。",
            "sources": choose_sources(newest, 3),
        },
        {
            "rank": 3,
            "name": "实质变化",
            "score": top_changed["axes"]["change"]["score"],
            "summary": "Release 与明确产品更新优先于普通代码推送。",
            "evidence": (
                f"确认 {material_count} 个实质更新；最高信号为 {top_changed['name']} · "
                f"{top_changed['axes']['change']['value']}。"
                if material_count
                else f"尚未确认重大 Release；{top_changed['name']} 的最高变化信号为“{top_changed['axes']['change']['value']}”。"
            ),
            "sources": choose_sources(changed, 3),
        },
    ]


def build_report(
    snapshot: dict[str, Any],
    target_date: dt.date,
    *,
    mode: str,
    history_days: int,
    github_limit: int,
    product_hunt_limit: int,
    snapshot_root: Path = SNAPSHOT_ROOT,
) -> dict[str, Any]:
    history = historical_snapshots(target_date, history_days, snapshot_root)
    github = prepare_github_items(snapshot, target_date, history, github_limit)
    product_hunt = prepare_product_hunt_items(snapshot, target_date, history, product_hunt_limit)
    all_items = sorted(github + product_hunt, key=lambda item: item.get("heat", 0), reverse=True)
    if not all_items:
        raise CollectionError("没有采集到 AI 相关项目，报告未生成")
    trends = build_trends(all_items)
    category_counts = Counter(item.get("category", "AI 应用") for item in all_items)
    leading_category = category_counts.most_common(1)[0][0]
    leading_items = [item for item in all_items if item.get("category") == leading_category]
    top = all_items[0]
    source_pool = choose_sources(all_items, 4)
    history_ready = bool(history)
    material_updates = [
        item for item in all_items if item.get("axes", {}).get("change", {}).get("material")
    ]
    recent_items = []
    for item in all_items:
        age = item.get("axes", {}).get("novelty", {}).get("ageDays")
        if age is not None and age <= 14:
            recent_items.append(item)

    def source_for(item: dict[str, Any]) -> list[dict[str, str]]:
        return [source_ref(item)]

    generated = now_local()
    weekday = "星期" + "一二三四五六日"[target_date.weekday()]
    confidence = "中高置信" if history_ready and len(all_items) >= 6 else "中等置信 · 基线建立中"
    opportunity_score = clamp(sum(item["heat"] for item in leading_items[:3]) / max(1, len(leading_items[:3])))
    collection_label = "历史快照回放" if mode == "replay" else "实时采集"

    report = {
        "meta": {
            "date": target_date.isoformat(),
            "weekday": weekday,
            "edition": "LIVE · " + target_date.strftime("%Y%m%d"),
            "title": "AI 产品机会日报",
            "subtitle": "从新鲜度、动量与实质变化识别可验证机会",
            "generatedAt": generated.strftime("%Y-%m-%d %H:%M %Z"),
            "capturedAt": snapshot.get("capturedAt", ""),
            "isDemo": False,
            "collectionMode": mode,
            "collectionLabel": collection_label,
        },
        "brief": [
            {
                "label": "技术供给",
                "text": f"当前公开信号主要集中在“{leading_category}”，最高动量来自 {top['name']}。",
                "emphasis": leading_category,
                "sources": choose_sources(leading_items or all_items, 3),
            },
            {
                "label": "三轴判断",
                "text": f"{len(recent_items)} 个信号属于近 14 天新建或发布，{len(material_updates)} 个确认存在实质变化；其余按动量或持续热门处理。",
                "emphasis": "实质变化",
                "sources": source_pool[:3],
            },
            {
                "label": "今日判断",
                "text": f"优先验证围绕“{leading_category}”的窄场景产品，不把总 Star 数直接当成今日机会。",
                "emphasis": "窄场景产品",
                "sources": choose_sources(leading_items or all_items, 3),
            },
        ],
        "stats": [
            {"label": "今日信号", "value": str(len(all_items)), "note": f"{len(github)} GitHub · {len(product_hunt)} 产品", "href": "#discoveries"},
            {"label": "近 14 天新建 / 发布", "value": str(len(recent_items)), "note": "GitHub 创建 · PH 发布", "href": "#discoveries"},
            {"label": "实质更新", "value": str(len(material_updates)), "note": "Release / 明确发布", "href": "#updates"},
            {"label": "历史基线", "value": f"{len(history)}/{history_days}", "note": "本地每日快照", "href": "#coverage"},
        ],
        "trendSignals": trends,
        "opportunity": {
            "eyebrow": "今日优先机会",
            "title": f"围绕{leading_category}的可审计垂直工作流",
            "thesis": CATEGORY_OPPORTUNITIES[leading_category],
            "score": opportunity_score,
            "confidence": confidence,
            "whyNow": [
                f"最高动量信号：{trends[0]['evidence']}",
                f"新鲜度信号：{trends[1]['evidence']}",
                f"变化信号：{trends[2]['evidence']}",
            ],
            "nextMove": "先选择一个每天重复发生、结果可核验的任务，用 7 天记录节省时间、失败率与人工接管次数。",
            "sources": choose_sources(leading_items or all_items, 4),
        },
        "github": github,
        "productHunt": product_hunt,
        "updates": [
            {
                "name": item["name"],
                "change": item["axes"]["change"]["value"],
                "url": (
                    item["axes"]["change"].get("latestRelease") or {}
                ).get("url") or item["url"],
            }
            for item in material_updates[:4]
        ],
        "crossOpportunities": [
            {
                "ability": "高动量公开项目",
                "demand": "用户希望快速采用，但需要明确失败边界",
                "concept": f"面向单一流程的{leading_category}产品包",
                "confidence": confidence,
                "sources": choose_sources(all_items, 3),
            },
            {
                "ability": "近期新建 / 发布与首次捕获信号",
                "demand": "产品经理需要区分新项目与旧项目重新升温",
                "concept": "带项目年龄、首次捕获和榜单变化的机会监控器",
                "confidence": "中高",
                "sources": trends[1]["sources"],
            },
            {
                "ability": "Release 与产品 Feed 更新",
                "demand": "团队只希望被真正重要的变化打扰",
                "concept": "把普通 push 与实质产品更新分级的变更雷达",
                "confidence": "中",
                "sources": trends[2]["sources"],
            },
        ],
        "recommendations": [
            {
                "rank": index,
                "name": item["name"],
                "source": "GitHub" if item in github else "Product Hunt",
                "why": f"{item['axes']['momentum']['value']}；{item['axes']['novelty']['value']}。",
                "cost": "先阅读原始页面与快速开始说明，预计 20–60 分钟完成最小验证。",
                "risk": "公开热度不等于稳定性；注意权限、依赖、数据与运行成本。",
                "assumption": "目标项目能够暴露一个明确、可重复且可人工核验的工作流。",
                "url": item["url"],
            }
            for index, item in enumerate(all_items[:2], start=1)
        ],
        "actions": [
            {"minutes": 5, "task": "先看三轴而不是总热度", "outcome": "记录项目年龄、动量和实质变化证据"},
            {"minutes": 10, "task": f"打开 {top['name']} 的原始页面", "outcome": "确认 README、Release 与实际能力边界", "url": top["url"], "linkLabel": f"打开 {top['name']}"},
            {"minutes": 10, "task": "选择一个可人工复核的窄流程", "outcome": "写清成功条件、权限边界和失败处理"},
            {"minutes": 5, "task": "定义 7 天验证指标", "outcome": "记录节省时间、成功率和人工接管次数"},
        ],
        "coverage": {
            "historyDays": history_days,
            "historySnapshots": len(history),
            "duplicatesExcluded": 0,
            "status": "完整" if history_ready else "基线建立中",
            "note": (
                f"{collection_label}于 {snapshot.get('capturedAt', '')}。"
                f"GitHub Trending 为采集时点快照；Product Hunt 使用公开 Feed，不猜测缺失的票数和精确排名。"
                f"当前已有 {len(history)} 个此前日期快照。"
            ),
            "snapshotPath": str(snapshot_path(target_date, snapshot_root).relative_to(ROOT)),
            "sources": [
                {"name": "GitHub Trending · Daily", "status": "实时" if mode == "live" else "快照", "url": GITHUB_TRENDING_DAILY},
                {"name": "GitHub Trending · Weekly", "status": "实时" if mode == "live" else "快照", "url": GITHUB_TRENDING_WEEKLY},
                {"name": "Product Hunt · Public Feed", "status": "实时 · 无票数排名", "url": PRODUCT_HUNT_FEED},
                {"name": "GitHub Repository / Release API", "status": "部分" if snapshot.get("errors") else "实时", "url": "https://api.github.com/"},
            ],
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="today", type=parse_date, help="today 或 YYYY-MM-DD")
    parser.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    parser.add_argument("--history-days", type=int, default=30)
    parser.add_argument("--github-limit", type=int, default=6)
    parser.add_argument("--product-hunt-limit", type=int, default=4)
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_ROOT))
    parser.add_argument("--output", help="输出 JSON，默认 <date>.json")
    args = parser.parse_args()

    target_date: dt.date = args.date
    today = now_local().date()
    snapshot_root = Path(args.snapshot_dir).expanduser().resolve()
    mode = args.mode
    if mode == "auto":
        mode = "live" if target_date == today else "replay"
    if mode == "live" and target_date != today:
        raise CollectionError(
            "实时来源只能代表当前采集时点。过去日期必须使用当日已保存的快照。"
        )

    snapshot = (
        collect_live_snapshot(target_date, snapshot_root=snapshot_root)
        if mode == "live"
        else load_snapshot(target_date, snapshot_root)
    )
    report = build_report(
        snapshot,
        target_date,
        mode=mode,
        history_days=max(1, args.history_days),
        github_limit=max(1, args.github_limit),
        product_hunt_limit=max(0, args.product_hunt_limit),
        snapshot_root=snapshot_root,
    )
    output = Path(args.output).expanduser().resolve() if args.output else ROOT / f"{target_date.isoformat()}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "date": target_date.isoformat(),
                "mode": mode,
                "json": str(output),
                "snapshot": str(snapshot_path(target_date, snapshot_root)),
                "github": len(report.get("github", [])),
                "productHunt": len(report.get("productHunt", [])),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectionError as error:
        print(f"采集失败：{error}", file=sys.stderr)
        raise SystemExit(2)
