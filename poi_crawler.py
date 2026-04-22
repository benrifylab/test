#!/usr/bin/env python3
"""
ポイ活クローラー v1.1 - 要約精度改善版
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
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()

        # リンクテキスト+タイトルを重点的に抽出
        items = []
        # 見出しとリンクを優先取得
        for el in soup.find_all(["h1", "h2", "h3", "h4", "a", "p", "li", "td"]):
            text = el.get_text(strip=True)
            if len(text) > 10 and len(text) < 200:
                items.append(text)

        result = "\n".join(dict.fromkeys(items))  # 重複除去
        return result[:6000]
    except Exception as e:
        return f"[クロール失敗: {e}]"


def summarize_gemini(all_data):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""あなたはポイ活・節約情報の専門家です。
以下は本日 {TODAY} に日本の各お得情報サイトからクロールした生テキストです。

【指示】
この中から「今日使えるお得情報」を **最低15件、最大25件** 抽出してください。

【出力フォーマット（厳守）】
各カテゴリの絵文字を付けて、1案件1〜2行で書いてください。

🛒 **EC・ネット通販**
- （案件名）：（何がどうお得か）（期限：〜月/日）

💳 **クレカ・キャッシュレス決済**
- （案件名）：（何がどうお得か）（期限：〜月/日）

🍔 **外食・フード**
- （案件名）：（何がどうお得か）（期限：〜月/日）

🎁 **懸賞・無料・プレゼント**
- （案件名）：（何がどうお得か）（期限：〜月/日）

📱 **携帯・通信**
- （案件名）：（何がどうお得か）（期限：〜月/日）

【ルール】
- 期限切れの案件は絶対に含めないこと
- 割引額・還元率・当選人数など数字を必ず含めること
- 重要度・お得度が高い順に並べること
- 情報が少ないカテゴリは無理に埋めなくてよい
- 日本語で出力

---
以下が生データです：

{all_data[:30000]}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 4096,
            "temperature": 0.3
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"[Gemini要約失敗: {e}]\n\n生データの先頭部分:\n{all_data[:500]}"


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
    print(f"=== ポイ活クローラー v1.1 起動 {TODAY} ===\n")

    all_texts = []
    for t in TARGETS:
        print(f"  {t['category']} | {t['name']}...")
        text = crawl_site(t["url"])
        all_texts.append(f"\n=== {t['name']}（{t['category']}）===\n{text}")
        print(f"    -> {len(text)}文字")

    combined = "\n\n".join(all_texts)
    print(f"\n合計: {len(combined)}文字\n")

    print("Gemini Flash で要約中...")
    summary = summarize_gemini(combined)

    report = f"📋 **ポイ活日報 {TODAY}**\n\n{summary}"

    # ログ出力
    print(f"\n{'='*50}")
    print(report[:2000])
    print(f"{'='*50}\n")

    print("Discord送信中...")
    send_discord(report)
    print("完了！")


if __name__ == "__main__":
    main()
