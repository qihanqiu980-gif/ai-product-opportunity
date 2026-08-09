#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value.startsWith("--")) {
      args[value.slice(2)] = argv[index + 1];
      index += 1;
    }
  }
  return args;
}

function findPlaywright() {
  try {
    return require("playwright");
  } catch {}

  const runtimeRoot = path.join(os.homedir(), ".cache", "codex-runtimes");
  if (!fs.existsSync(runtimeRoot)) {
    throw new Error("找不到 Playwright。请先在 Codex 桌面端加载 workspace dependencies。");
  }

  const runtimes = fs
    .readdirSync(runtimeRoot)
    .map((name) => path.join(runtimeRoot, name, "dependencies", "node", "node_modules", "playwright"))
    .filter((candidate) => fs.existsSync(candidate));

  if (!runtimes.length) {
    throw new Error("Codex workspace runtime 中没有 Playwright。");
  }
  return require(runtimes[0]);
}

function chromePath() {
  const candidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

const args = parseArgs(process.argv.slice(2));
if (!args.html || !args.png) {
  throw new Error("用法: node capture-report.mjs --html <report.html> --png <cover.png>");
}

const htmlPath = path.resolve(args.html);
const pngPath = path.resolve(args.png);
const playwright = findPlaywright();
const launchOptions = { headless: true };
const executablePath = chromePath();
if (executablePath) {
  launchOptions.executablePath = executablePath;
}

const browser = await playwright.chromium.launch(launchOptions);
try {
  const page = await browser.newPage({
    viewport: { width: 1080, height: 1440 },
    deviceScaleFactor: 1,
  });
  const consoleErrors = [];
  const pageErrors = [];
  const qa = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(`${page.url()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => pageErrors.push(`${page.url()}: ${error.message}`));

  async function inspect(label) {
    await page.evaluate(() => document.fonts?.ready);
    const result = await page.evaluate((currentLabel) => {
      const textElements = new Set();
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (!node.textContent || !node.textContent.trim() || !node.parentElement) continue;
        const style = getComputedStyle(node.parentElement);
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          Number(style.opacity) === 0 ||
          node.parentElement.getClientRects().length === 0
        ) continue;
        textElements.add(node.parentElement);
      }

      const fontSamples = Array.from(textElements).map((element) => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === "string" ? element.className : "",
        text: element.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
        size: Number.parseFloat(getComputedStyle(element).fontSize),
      }));
      const smallText = fontSamples.filter((sample) => sample.size < 14.99);
      const minimumFontPx = fontSamples.length
        ? Math.min(...fontSamples.map((sample) => sample.size))
        : null;
      const rootWidth = Math.max(
        document.documentElement.scrollWidth,
        document.body?.scrollWidth || 0,
      );
      const cover = document.querySelector("#share-cover");
      const coverRect = cover?.getBoundingClientRect();
      return {
        label: currentLabel,
        viewport: { width: innerWidth, height: innerHeight },
        minimumFontPx,
        smallText: smallText.slice(0, 12),
        horizontalOverflowPx: Math.max(0, rootWidth - innerWidth),
        coverRect: coverRect && getComputedStyle(cover).display !== "none"
          ? { width: coverRect.width, height: coverRect.height }
          : null,
      };
    }, label);
    qa.push(result);
    return result;
  }

  const coverUrl = pathToFileURL(htmlPath).href + "?capture=cover";
  await page.goto(coverUrl, { waitUntil: "load" });
  await inspect("cover");
  await page.locator("#share-cover").screenshot({
    path: pngPath,
    animations: "disabled",
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await inspect("desktop");
  if (args.desktop) {
    await page.screenshot({ path: path.resolve(args.desktop), fullPage: true, animations: "disabled" });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await inspect("mobile");
  if (args.mobile) {
    await page.screenshot({ path: path.resolve(args.mobile), fullPage: true, animations: "disabled" });
  }

  const qaFailures = qa.flatMap((result) => {
    const failures = [];
    if (result.minimumFontPx !== null && result.minimumFontPx < 14.99) {
      failures.push(`${result.label}: 最小字号 ${result.minimumFontPx}px`);
    }
    if (result.horizontalOverflowPx > 1) {
      failures.push(`${result.label}: 横向溢出 ${result.horizontalOverflowPx}px`);
    }
    if (
      result.label === "cover" &&
      (!result.coverRect || Math.abs(result.coverRect.width - 1080) > 1 || Math.abs(result.coverRect.height - 1440) > 1)
    ) {
      failures.push(`${result.label}: 封面尺寸不是 1080×1440`);
    }
    return failures;
  });
  if (consoleErrors.length || pageErrors.length || qaFailures.length) {
    throw new Error(
      [
        ...qaFailures,
        ...consoleErrors.map((error) => `console: ${error}`),
        ...pageErrors.map((error) => `pageerror: ${error}`),
      ].join("\n"),
    );
  }

  const latestPath = args["no-latest"] ? null : path.join(path.dirname(pngPath), "latest.png");
  if (latestPath) {
    fs.copyFileSync(pngPath, latestPath);
  }
  process.stdout.write(
    JSON.stringify({ png: pngPath, latestPng: latestPath, qa, consoleErrors, pageErrors }) + "\n",
  );
} finally {
  await browser.close();
}
