#!/usr/bin/env python3
"""
ポイ活クローラー v1.3 - APIキー保護+リトライ対応
"""

import os
import re
import time
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

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


def summarize_gemini(all_data):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY

    prompt = "本日 " + TODAY + " のお得情報を以下の生データから抽出してください。\n\n"
    prompt += "【絶対ルール】\n"
    prompt += "- 合計1500文字以内に収めること（超重要）\n"
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
        "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.2}
    }

    # 3回リトライ（503対策）
    for attempt in range(3):
        try:
            resp = requests.post(api_url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            error_msg = str(e)
            # APIキーをエラーメッセージから除去
            if GEMINI_API_KEY:
                error_msg = error_msg.replace(GEMINI_API_KEY, "***")
            print("  Gemini試行" + str(attempt+1) + "/3 失敗: " + error_msg)
            if attempt < 2:
                print("  30秒待機してリトライ...")
                time.sleep(30)

    return "[要約失敗: Gemini API 3回リトライ後も応答なし。しばらく待って再実行してください]"


def send_discord(message):
    if not DISCORD_WEBHOOK:
        print(message)
        return

    if len(message) <= 1990:
        chunks = [message]
    else:
        chunks = []
        current = ""
        for line in message.split("\n"):
            if len(current) + len(line) + 1 > 1990:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(DISCORD_WEBHOOK, json={"content": chunk}, timeout=10)
            print("  Discord " + str(i+1) + "/" + str(len(chunks)) + " -> " + str(resp.status_code))
        except Exception as e:
            print("  Discord失敗: " + str(e))


def main():
    print("=== v1.3 " + TODAY + " ===")

    all_texts = []
    for t in TARGETS:
        print("  " + t["name"] + "...")
        text = crawl_site(t["url"])
        all_texts.append("\n=== " + t["name"] + " ===\n" + text)
        print("    " + str(len(text)) + "字")

    combined = "\n".join(all_texts)
    print("合計" + str(len(combined)) + "字")

    print("Gemini要約中...")
    summary = summarize_gemini(combined)

    report = "📋 **ポイ活日報 " + TODAY + "**\n\n" + summary
    print(report[:500])

    print("Discord送信...")
    send_discord(report)
    print("完了！")


if __name__ == "__main__":
    main()
