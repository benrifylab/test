#!/usr/bin/env python3
"""
ポイ活クローラー v1.0
GitHub Actions + Gemini Flash + Discord（完全無料構成）
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y年%m月%d日 %H:%M")

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def crawl_site(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:8000]
    except Exception as e:
        return f"[クロール失敗: {e}]"


def summarize_gemini(all_data):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""あなたはポイ活の達人です。以下は各お得情報サイトから取得した生テキストです。
本日 {TODAY} 時点で有効な「お得情報」を抽出し、以下の形式で簡潔にまとめてください。

【出力ルール】
- カテゴリ別に分類（EC, クレカ/決済, 外食, 懸賞/無料, 携帯）
- 各案件は1-2行で「何がどうお得か」「期限」を明記
- 期限切れは除外
- 最大20件に絞る（重要度順）
- 日本語で出力

---
{all_data[:25000]}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048}
    }
    try:
        resp = requests.post(url, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"[Gemini要約失敗: {e}]"


def send_discord(message):
    if not DISCORD_WEBHOOK:
        print("[SKIP] Discord Webhook未設定")
        print(message)
        return
    chunks = [message[i:i + 1990] for i in range(0, len(message), 1990)]
    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(DISCORD_WEBHOOK, json={"content": chunk}, timeout=10)
            print(f"  [Discord] {i+1}/{len(chunks)} -> {resp.status_code}")
        except Exception as e:
            print(f"  [Discord] 失敗: {e}")


def main():
    print(f"=== ポイ活クローラー起動 {TODAY} ===\n")

    all_texts = []
    for t in TARGETS:
        print(f"  {t['category']} | {t['name']}...")
        text = crawl_site(t["url"])
        all_texts.append(f"\n### {t['name']}（{t['category']}）\n{text}")
        print(f"    -> {len(text)}文字")

    combined = "\n---\n".join(all_texts)
    print(f"\n合計: {len(combined)}文字\n")

    print("Gemini Flash で要約中...")
    summary = summarize_gemini(combined)

    report = f"**ポイ活日報 {TODAY}**\n\n{summary}"
    print(report)

    print("\nDiscord送信中...")
    send_discord(report)
    print("完了！")


if __name__ == "__main__":
    main()
