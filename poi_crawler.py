#!/usr/bin/env python3
"""
ポイ活クローラー v1.6 - モデル変更で出力安定化
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

# 思考トークンを使わないモデル = 出力に全トークンを使える
GEMINI_MODEL = "gemini-2.0-flash"


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
        return result[:5000]
    except Exception:
        return ""


def call_gemini(prompt, max_tokens=4000):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/" + GEMINI_MODEL + ":generateContent?key=" + GEMINI_API_KEY
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}
    }
    for attempt in range(3):
        try:
            resp = requests.post(api_url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print("  Gemini出力: " + str(len(text)) + "字")
            return text
        except Exception as e:
            error_msg = str(e)
            if GEMINI_API_KEY:
                error_msg = error_msg.replace(GEMINI_API_KEY, "***")
            print("  Gemini試行" + str(attempt + 1) + "/3: " + error_msg)
            if attempt < 2:
                time.sleep(30)
    return ""


def make_full_summary(all_data):
    prompt = "あなたはポイ活の達人です。以下は本日" + TODAY + "にクロールした日本のお得情報サイトの生データです。\n\n"
    prompt += "この中から今日使えるお得情報を抽出して、以下のフォーマットで出力してください。\n\n"
    prompt += "ルール:\n"
    prompt += "- 必ず15件以上抽出すること\n"
    prompt += "- 各案件は1行で「案件名：内容（期限）」と書く\n"
    prompt += "- 割引額、還元率、当選人数などの数字を含める\n"
    prompt += "- 期限切れの案件は含めない\n"
    prompt += "- お得度が高い順に並べる\n\n"
    prompt += "出力フォーマット:\n\n"
    prompt += "🛒 EC・ネット通販\n"
    prompt += "・案件名：内容（~M/D）\n"
    prompt += "・案件名：内容（~M/D）\n\n"
    prompt += "💳 クレカ・キャッシュレス\n"
    prompt += "・案件名：内容（~M/D）\n\n"
    prompt += "🍔 外食・フード\n"
    prompt += "・案件名：内容（~M/D）\n\n"
    prompt += "🎁 懸賞・無料\n"
    prompt += "・案件名：内容（~M/D）\n\n"
    prompt += "📱 携帯・通信\n"
    prompt += "・案件名：内容（~M/D）\n\n"
    prompt += "--- 以下が生データ ---\n"
    prompt += all_data[:20000]
    return call_gemini(prompt, max_tokens=4000)


def save_html(full_summary):
    os.makedirs("docs", exist_ok=True)

    body = full_summary
    body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = body.replace("\n", "\n<br>")
    body = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', body)

    html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ポイ活日報</title>
<style>
body{font-family:-apple-system,'Hiragino Sans',sans-serif;max-width:700px;margin:0 auto;padding:16px;background:#0d1117;color:#c9d1d9;line-height:1.8;font-size:15px}
h1{color:#58a6ff;border-bottom:2px solid #30363d;padding-bottom:8px}
b{color:#ffa657}
.t{color:#8b949e;font-size:0.85em}
hr{border-color:#21262d}
</style>
</head>
<body>
<h1>📋 ポイ活日報</h1>
<p class="t">""" + TODAY + """ 更新 ｜ 自動生成</p>
<br>
""" + body + """
<hr>
<p class="t">GitHub Actions + Gemini 2.0 Flash で自動生成</p>
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
    print("=== v1.6 " + TODAY + " ===")

    # 1. クロール
    all_texts = []
    for t in TARGETS:
        print("  " + t["name"] + "...")
        text = crawl_site(t["url"])
        all_texts.append("\n=== " + t["name"] + " ===\n" + text)
        print("    " + str(len(text)) + "字")

    combined = "\n".join(all_texts)
    print("合計" + str(len(combined)) + "字")

    # 2. Gemini全文要約
    print("Gemini 2.0 Flash 全文要約中...")
    full = make_full_summary(combined)
    if not full:
        full = "本日のGemini API応答なし。次回自動実行をお待ちください。"

    # 3. GitHub Pages保存
    save_html(full)
    git_push()

    # 4. Discord送信（先頭+リンク）
    pages_url = "https://" + GITHUB_REPO.split("/")[0] + ".github.io/" + GITHUB_REPO.split("/")[1] + "/"

    # 全文から先頭10行を切り出し
    lines = full.strip().split("\n")
    top_lines = lines[:15]
    short = "\n".join(top_lines)
    if len(short) > 1500:
        short = short[:1500]

    discord_msg = "📋 **ポイ活日報 " + TODAY + "**\n\n"
    discord_msg += short
    discord_msg += "\n\n...続きは↓\n📖 " + pages_url

    send_discord(discord_msg)
    print("完了！")


if __name__ == "__main__":
    main()
