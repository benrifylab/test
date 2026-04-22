#!/usr/bin/env python3
"""
ポイ活クローラー v1.8 - Groq+OpenRouter+Gemini 3段フォールバック
"""

import os
import re
import time
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OR_API_KEY = os.environ.get("OR_API_KEY", "")
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

PROMPT = """あなたはポイ活の達人です。以下は本日{today}にクロールした日本のお得情報サイトの生データです。

今日使えるお得情報を抽出して以下のフォーマットで出力してください。

ルール:
- 必ず15件以上抽出
- 各案件は1行で書く
- 割引額、還元率、当選人数などの数字を含める
- 期限切れは含めない
- お得度が高い順

フォーマット:

🛒 EC・ネット通販
・案件名：内容（~M/D）

💳 クレカ・キャッシュレス
・案件名：内容（~M/D）

🍔 外食・フード
・案件名：内容（~M/D）

🎁 懸賞・無料
・案件名：内容（~M/D）

📱 携帯・通信
・案件名：内容（~M/D）

--- 生データ ---
{data}"""


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
        return "\n".join(dict.fromkeys(items))[:5000]
    except Exception:
        return ""


def call_groq(prompt):
    if not GROQ_API_KEY:
        print("  Groq: キーなし skip")
        return ""
    headers = {"Authorization": "Bearer " + GROQ_API_KEY, "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000, "temperature": 0.3
    }
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        print("  Groq出力: " + str(len(text)) + "字 OK")
        return text
    except Exception as e:
        print("  Groq失敗: " + str(e)[:150])
        return ""


def call_openrouter(prompt):
    if not OR_API_KEY:
        print("  OpenRouter: キーなし skip")
        return ""
    headers = {"Authorization": "Bearer " + OR_API_KEY, "Content-Type": "application/json"}
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000, "temperature": 0.3
    }
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        print("  OpenRouter出力: " + str(len(text)) + "字 OK")
        return text
    except Exception as e:
        print("  OpenRouter失敗: " + str(e)[:150])
        return ""


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        print("  Gemini: キーなし skip")
        return ""
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.3}
    }
    try:
        resp = requests.post(api_url, json=payload, timeout=120)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        print("  Gemini出力: " + str(len(text)) + "字 OK")
        return text
    except Exception as e:
        error_msg = str(e)
        if GEMINI_API_KEY:
            error_msg = error_msg.replace(GEMINI_API_KEY, "***")
        print("  Gemini失敗: " + error_msg[:150])
        return ""


def summarize(all_data):
    prompt = PROMPT.replace("{today}", TODAY).replace("{data}", all_data[:18000])

    # 1. Groq（最速）
    print("[1/3] Groq...")
    result = call_groq(prompt)
    if result and len(result) > 200:
        return result

    # 2. OpenRouter（無料Llama）
    print("[2/3] OpenRouter...")
    result = call_openrouter(prompt)
    if result and len(result) > 200:
        return result

    # 3. Gemini（バックアップ）
    print("[3/3] Gemini...")
    result = call_gemini(prompt)
    if result and len(result) > 200:
        return result

    return "本日はAI要約が取得できませんでした。次回の自動実行をお待ちください。"


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
<p class="t">""" + TODAY + """ 更新</p>
<br>
""" + body + """
<hr>
<p class="t">GitHub Actions + AI(Groq/OpenRouter/Gemini) 自動生成</p>
</body>
</html>"""

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML保存完了")


def git_push():
    try:
        subprocess.run(["git", "config", "user.name", "poi-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "add", "docs/"], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", "update " + TODAY], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Git push完了")
    except Exception as e:
        print("Git push失敗: " + str(e))


def send_discord(msg):
    if not DISCORD_WEBHOOK:
        print(msg)
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK, json={"content": msg[:1990]}, timeout=10)
        print("Discord -> " + str(resp.status_code))
    except Exception as e:
        print("Discord失敗: " + str(e))


def main():
    print("=== v1.8 " + TODAY + " ===")

    all_texts = []
    for t in TARGETS:
        print("  " + t["name"] + "...")
        text = crawl_site(t["url"])
        all_texts.append("\n=== " + t["name"] + " ===\n" + text)
        print("    " + str(len(text)) + "字")

    combined = "\n".join(all_texts)
    print("合計" + str(len(combined)) + "字")

    full = summarize(combined)

    save_html(full)
    git_push()

    pages_url = "https://" + GITHUB_REPO.split("/")[0] + ".github.io/" + GITHUB_REPO.split("/")[1] + "/"
    lines = full.strip().split("\n")
    short = "\n".join(lines[:15])
    if len(short) > 1500:
        short = short[:1500]

    discord_msg = "📋 **ポイ活日報 " + TODAY + "**\n\n"
    discord_msg += short
    discord_msg += "\n\n📖 全文→ " + pages_url

    send_discord(discord_msg)
    print("完了！")


if __name__ == "__main__":
    main()
