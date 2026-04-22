#!/usr/bin/env python3
"""
ポイ活クローラー v1.4 - GitHub Pages全文保存+Discord短縮版
"""

import os
import re
import time
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "benrifylab/test")
JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY = NOW.strftime("%Y/%m/%d %H:%M")
DATE_FILE = NOW.strftime("%Y%m%d_%H%M")

TARGETS = [
    {"name": "節約速報", "url": "https://setusoku.com/", "category": "総合"},
    {"name": "ココトク", "url": "https://kojinabi.com/", "category": "総合"},
    {"name": "Amazonタイムセール", "url": "https://www.amazon.co.jp/gp/goldbox", "category": "Amazon"},
    {"name": "楽天タイムセール", "url": "https://event.rakuten.co.jp/bargain/timesale/", "category": "楽天"},
    {"name": "楽天スーパーDEAL", "url": "https://event.rakuten.co.jp/superdeal/", "category": "楽天"},
    {"name": "Yahooお得ガイド", "url": "https://shopping.yahoo.co.jp/promotion/campaign/guide/", "category": "Yahoo"},
    {"name": "PayPayキャンペーン", "url": "https://paypay.ne.jp/notice/campaign/", "category": "PayPay"},
    {"name": "すき家", "url": "https://www.sukiya.jp/", "category": "外食"},
    {"name": "懸賞生活", "url": "https://www.knshow.com/list/", "category": "懸賞"},
    {"name": "チャンスイット", "url": "https://www.chance.com/present/", "category": "懸賞"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def crawl_site(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()
        items = []
        for el in soup.find_all(["h1", "h2", "h3", "h4", "a", "p", "li", "td"]):
            text = el.get_text(strip=True)
            if 10 < len(text) < 200:
                items.append(text)
        result = "\n".join(dict.fromkeys(items))
        return result[:6000]
    except Exception:
        return ""


def summarize_gemini(all_data, max_tokens=2500):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY

    prompt = "本日 " + TODAY + " のお得情報を以下の生データから抽出してください。\n\n"
    prompt += "【絶対ルール】\n"
    prompt += "- 1案件=1行で簡潔に書くこと\n"
    prompt += "- 15-20件抽出すること\n"
    prompt += "- 期限切れは除外\n"
    prompt += "- 数字（割引額/還元率/当選数）を必ず含める\n\n"
    prompt += "【出力フォーマット】\n"
    prompt += "🛒EC\n・案件：内容（~M/D）\n\n"
    prompt += "💳決済\n・案件：内容（~M/D）\n\n"
    prompt += "🍔外食\n・案件：内容（~M/D）\n\n"
    prompt += "🎁無料/懸賞\n・案件：内容（~M/D）\n\n"
    prompt += "📱携帯\n・案件：内容（~M/D）\n\n"
    prompt += "---\n"
    prompt += all_data[:28000]

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}
    }

    for attempt in range(3):
        try:
            resp = requests.post(api_url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            error_msg = str(e)
            if GEMINI_API_KEY:
                error_msg = error_msg.replace(GEMINI_API_KEY, "***")
            print("  Gemini試行" + str(attempt+1) + "/3: " + error_msg)
            if attempt < 2:
                time.sleep(30)

    return "[要約失敗: Gemini API応答なし]"


def save_html_report(full_report):
    """GitHub Pages用のHTMLを生成して保存"""
    os.makedirs("docs", exist_ok=True)

    # Markdownの簡易変換
    html_body = full_report
    html_body = html_body.replace("&", "&amp;")
    html_body = html_body.replace("<", "&lt;")
    html_body = html_body.replace(">", "&gt;")
    html_body = html_body.replace("\n", "<br>\n")
    # **太字** 変換
    import re as r
    html_body = r.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)

    html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ポイ活日報 """ + TODAY + """</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 700px; margin: 0 auto; padding: 16px; background: #1a1a2e; color: #e0e0e0; line-height: 1.7; }
h1 { color: #00d4ff; font-size: 1.3em; border-bottom: 2px solid #00d4ff; padding-bottom: 8px; }
strong { color: #ffd700; }
br + br { display: block; margin-top: 8px; }
.updated { color: #888; font-size: 0.85em; }
</style>
</head>
<body>
<h1>📋 ポイ活日報</h1>
<p class="updated">更新: """ + TODAY + """</p>
""" + html_body + """
</body>
</html>"""

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("  HTML保存完了: docs/index.html")


def git_push():
    """生成したHTMLをGitHubにpush"""
    try:
        subprocess.run(["git", "config", "user.name", "poi-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "add", "docs/"], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", "日報更新 " + TODAY], check=True)
            subprocess.run(["git", "push"], check=True)
            print("  Git push完了")
        else:
            print("  変更なし、pushスキップ")
    except Exception as e:
        print("  Git push失敗: " + str(e))


def send_discord(short_msg):
    if not DISCORD_WEBHOOK:
        print(short_msg)
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK, json={"content": short_msg}, timeout=10)
        print("  Discord -> " + str(resp.status_code))
    except Exception as e:
        print("  Discord失敗: " + str(e))


def main():
    print("=== v1.4 " + TODAY + " ===")

    # 1. クロール
    all_texts = []
    for t in TARGETS:
        print("  " + t["name"] + "...")
        text = crawl_site(t["url"])
        all_texts.append("\n=== " + t["name"] + " ===\n" + text)
        print("    " + str(len(text)) + "字")

    combined = "\n".join(all_texts)
    print("合計" + str(len(combined)) + "字")

    # 2. Gemini要約（全文版）
    print("Gemini要約中...")
    full_summary = summarize_gemini(combined, max_tokens=2500)

    # 3. GitHub Pages に全文保存
    full_report = "📋 ポイ活日報 " + TODAY + "\n\n" + full_summary
    save_html_report(full_report)
    git_push()

    # 4. Discord には短縮版 + リンク
    pages_url = "https://" + GITHUB_REPO.split("/")[0] + ".github.io/" + GITHUB_REPO.split("/")[1] + "/"

    # 全文から先頭を切り出してDiscord用に
    lines = full_summary.strip().split("\n")
    short_lines = []
    count = 0
    for line in lines:
        short_lines.append(line)
        if line.startswith("・"):
            count += 1
        if count >= 7:
            break

    short_text = "\n".join(short_lines)

    discord_msg = "📋 **ポイ活日報 " + TODAY + "**\n\n"
    discord_msg += short_text
    discord_msg += "\n\n...他多数\n\n"
    discord_msg += "📖 **全文はこちら →** " + pages_url

    # 2000文字に収める
    if len(discord_msg) > 1990:
        discord_msg = discord_msg[:1980] + "\n..." + pages_url

    print("Discord送信...")
    send_discord(discord_msg)
    print("完了！")


if __name__ == "__main__":
    main()
