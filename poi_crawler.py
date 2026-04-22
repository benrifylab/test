#!/usr/bin/env python3
"""
ポイ活クローラー v1.5 - 全文保存修正版
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


def call_gemini(prompt, max_tokens=3000):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY
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
            print("  Gemini試行" + str(attempt + 1) + "/3: " + error_msg)
            if attempt < 2:
                time.sleep(30)
    return ""


def make_full_summary(all_data):
    prompt = "あなたはポイ活・節約の専門家です。本日 " + TODAY + " の生データから、今日使えるお得情報を全て抽出してください。\n\n"
    prompt += "【ルール】\n"
    prompt += "- 20-30件を目標に、できるだけ多く抽出\n"
    prompt += "- カテゴリ別に分類\n"
    prompt += "- 各案件は「案件名：お得内容（期限）」の形式\n"
    prompt += "- 割引額・還元率・当選人数など数字を必ず含める\n"
    prompt += "- 期限切れは除外\n\n"
    prompt += "【カテゴリ】\n"
    prompt += "🛒 EC・ネット通販\n"
    prompt += "💳 クレカ・キャッシュレス決済\n"
    prompt += "🍔 外食・フード\n"
    prompt += "🎁 懸賞・無料・プレゼント\n"
    prompt += "📱 携帯・通信\n"
    prompt += "🏷️ その他お得情報\n\n"
    prompt += "---\n" + all_data[:28000]
    return call_gemini(prompt, max_tokens=3000)


def make_short_summary(full_summary):
    prompt = "以下のお得情報まとめから、最もお得度が高いTOP8件だけを選んで、超短縮版を作ってください。\n\n"
    prompt += "【ルール】\n"
    prompt += "- 合計800文字以内\n"
    prompt += "- 1件1行、30文字以内\n"
    prompt += "- カテゴリの絵文字は残す\n\n"
    prompt += full_summary
    return call_gemini(prompt, max_tokens=600)


def save_html(full_summary):
    os.makedirs("docs", exist_ok=True)

    # HTML変換
    body = full_summary
    body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', body)

    # カテゴリ絵文字を見出しに
    body = body.replace("🛒", '<h2 style="color:#4fc3f7">🛒')
    body = body.replace("💳", '<h2 style="color:#ffd54f">💳')
    body = body.replace("🍔", '<h2 style="color:#ff8a65">🍔')
    body = body.replace("🎁", '<h2 style="color:#ce93d8">🎁')
    body = body.replace("📱", '<h2 style="color:#81c784">📱')
    body = body.replace("🏷", '<h2 style="color:#90a4ae">🏷')

    # 見出し閉じタグを追加（次の行の前に）
    lines = body.split("\n")
    result_lines = []
    in_h2 = False
    for line in lines:
        if "<h2" in line and in_h2:
            result_lines.append("</h2>")
        if "<h2" in line:
            in_h2 = True
            result_lines.append(line)
        else:
            if in_h2 and line.strip() == "":
                result_lines.append("</h2>")
                in_h2 = False
            result_lines.append(line)
    if in_h2:
        result_lines.append("</h2>")

    body_html = "<br>\n".join(result_lines)

    html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ポイ活日報</title>
<style>
* { box-sizing: border-box; }
body {
  font-family: -apple-system, 'Hiragino Sans', sans-serif;
  max-width: 720px; margin: 0 auto; padding: 16px;
  background: #0d1117; color: #c9d1d9; line-height: 1.8;
}
h1 { color: #58a6ff; font-size: 1.4em; border-bottom: 2px solid #58a6ff; padding-bottom: 8px; }
h2 { font-size: 1.1em; margin-top: 20px; margin-bottom: 4px; }
strong { color: #ffa657; }
.time { color: #8b949e; font-size: 0.85em; }
.item { padding: 4px 0; border-bottom: 1px solid #21262d; }
</style>
</head>
<body>
<h1>📋 ポイ活日報</h1>
<p class="time">""" + TODAY + """ 更新</p>
""" + body_html + """
<hr style="border-color:#21262d; margin-top:30px;">
<p class="time">GitHub Actions + Gemini Flash で自動生成（完全無料）</p>
</body>
</html>"""

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  HTML保存完了")


def git_push():
    try:
        subprocess.run(["git", "config", "user.name", "poi-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "add", "docs/"], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", "update " + TODAY], check=True)
            subprocess.run(["git", "push"], check=True)
            print("  Git push完了")
        else:
            print("  変更なしskip")
    except Exception as e:
        print("  Git push失敗: " + str(e))


def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print(msg)
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK, json={"content": msg[:1990]}, timeout=10)
        print("  Discord -> " + str(resp.status_code))
    except Exception as e:
        print("  Discord失敗: " + str(e))


def main():
    print("=== v1.5 " + TODAY + " ===")

    # 1. クロール
    all_texts = []
    for t in TARGETS:
        print("  " + t["name"] + "...")
        text = crawl_site(t["url"])
        all_texts.append("\n=== " + t["name"] + " (" + t["category"] + ") ===\n" + text)
        print("    " + str(len(text)) + "字")

    combined = "\n".join(all_texts)
    print("合計" + str(len(combined)) + "字")

    # 2. 全文要約（GitHub Pages用）
    print("Gemini全文要約中...")
    full_summary = make_full_summary(combined)
    if not full_summary:
        full_summary = "Gemini API応答なし。次回の自動実行をお待ちください。"
    print("  全文: " + str(len(full_summary)) + "字")

    # 3. HTML保存 + push
    save_html(full_summary)
    git_push()

    # 4. Discord用に短縮版を別途生成
    print("Discord短縮版生成中...")
    short = make_short_summary(full_summary)
    if not short:
        short = full_summary[:800]

    pages_url = "https://" + GITHUB_REPO.split("/")[0] + ".github.io/" + GITHUB_REPO.split("/")[1] + "/"
    discord_msg = "📋 **ポイ活日報 " + TODAY + "**\n\n"
    discord_msg += short
    discord_msg += "\n\n📖 全文 → " + pages_url

    print("Discord送信...")
    send_discord(discord_msg)
    print("完了！")


if __name__ == "__main__":
    main()
