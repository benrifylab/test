#!/usr/bin/env python3
"""
ポイ活クローラー v3.2 - Secret名一致版
"""

import os, re, time, glob, requests, subprocess
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OR_API_KEY = os.environ.get("OR_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS", "")
COHERE_API_KEY = os.environ.get("COHERE", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
HF_API_KEY = os.environ.get("HF_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "benrifylab/test")

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY = NOW.strftime("%Y/%m/%d %H:%M")
FILESTAMP = NOW.strftime("%Y%m%d%H%M%S")

TARGETS = [
    {"name": "節約速報", "url": "https://setusoku.com/"},
    {"name": "ココトク", "url": "https://kojinabi.com/"},
    {"name": "超得ニュース", "url": "https://superprofitnews.main.jp/"},
    {"name": "Amazonタイムセール", "url": "https://www.amazon.co.jp/gp/goldbox"},
    {"name": "Amazonクーポン", "url": "https://www.amazon.co.jp/Coupon/b?node=5765238051"},
    {"name": "楽天タイムセール", "url": "https://event.rakuten.co.jp/bargain/timesale/"},
    {"name": "楽天スーパーDEAL", "url": "https://event.rakuten.co.jp/superdeal/"},
    {"name": "楽天マラソン", "url": "https://event.rakuten.co.jp/campaign/point-up/marathon/"},
    {"name": "Yahooお得ガイド", "url": "https://shopping.yahoo.co.jp/promotion/campaign/guide/"},
    {"name": "PayPayキャンペーン", "url": "https://paypay.ne.jp/notice/campaign/"},
    {"name": "PayPay自治体", "url": "https://paypay.ne.jp/event/support-local/"},
    {"name": "Yahooズバトク", "url": "https://toku.yahoo.co.jp/"},
    {"name": "ポイ探", "url": "https://www.poitan.jp/"},
    {"name": "キャンペーン総合", "url": "https://www.card-reviews.com/entry/cashless-overall-promotions-202002"},
    {"name": "Vポイント", "url": "https://cpn.tsite.jp/list/all"},
    {"name": "すき家", "url": "https://www.sukiya.jp/"},
    {"name": "吉野家", "url": "https://www.yoshinoya.com/campaign/"},
    {"name": "松屋", "url": "https://www.matsuyafoods.co.jp/matsunoya/campaign/"},
    {"name": "マクドナルド", "url": "https://www.mcdonalds.co.jp/campaign/"},
    {"name": "ケンタッキー", "url": "https://www.kfc.co.jp/campaign"},
    {"name": "モスバーガー", "url": "https://www.mos.jp/campaign/"},
    {"name": "ガスト", "url": "https://www.skylark.co.jp/gusto/campaign/"},
    {"name": "セブンイレブン", "url": "https://www.sej.co.jp/campaign/"},
    {"name": "ファミマ", "url": "https://www.family.co.jp/campaign.html"},
    {"name": "ローソン", "url": "https://www.lawson.co.jp/campaign/"},
    {"name": "ウエルシア", "url": "https://www.welcia-yakkyoku.co.jp/campaign/"},
    {"name": "マツキヨ", "url": "https://www.matsukiyo.co.jp/mkc/campaign"},
    {"name": "懸賞生活", "url": "https://www.knshow.com/list/"},
    {"name": "チャンスイット", "url": "https://www.chance.com/present/"},
    {"name": "懸賞当確", "url": "https://www.ken-kaku.com/"},
    {"name": "価格comスマホ", "url": "https://kakaku.com/keitai/campaign/"},
    {"name": "クーポンサイト", "url": "https://xn--eckvas1f0ewfnc.com/"},
    {"name": "楽天ふるさと納税", "url": "https://event.rakuten.co.jp/furusato/"},
    {"name": "ポイ活案件", "url": "https://rankup-labo.com/recommend/"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PROMPT = """あなたはポイ活の達人です。本日{today}の生データからお得情報を抽出してください。

ルール:
- できるだけ多く抽出（20件以上目標）
- 形式: 番号. 【引用元サイト名】案件名：お得内容（~期限M/D）
- 数字（割引額/還元率/当選数）を必ず含める
- 期限切れ除外、お得度順
- カテゴリヘッダー: 🛒EC 💳決済 🍔外食 🎁懸賞 📱携帯 🏪コンビニ 💊ドラッグストア 🏠ふるさと納税 🏷その他

--- 生データ ---
{data}"""

PAGE_CSS = """body{font-family:-apple-system,'Hiragino Sans',sans-serif;max-width:750px;margin:0 auto;padding:16px;background:#0d1117;color:#c9d1d9;line-height:1.8;font-size:14px}
h1{color:#58a6ff;border-bottom:2px solid #30363d;padding-bottom:8px}b{color:#ffa657}a{color:#58a6ff}
.t{color:#8b949e;font-size:0.85em}.src{color:#8b949e;font-size:0.8em}
.back{display:inline-block;margin:10px 0;padding:6px 16px;background:#21262d;color:#58a6ff;text-decoration:none;border-radius:6px}
hr{border-color:#21262d}"""


def crawl(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script","style","nav","footer","header","aside","form","iframe"]): t.decompose()
        items = []
        for el in soup.find_all(["h1","h2","h3","h4","a","p","li"]):
            t = el.get_text(strip=True)
            if 15 < len(t) < 150: items.append(t)
        return "\n".join(dict.fromkeys(items))[:2000]
    except: return ""


def _oai(url, key, model, prompt, maxtok=3500):
    h = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    p = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": maxtok, "temperature": 0.2}
    r = requests.post(url, json=p, headers=h, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ai_groq(prompt):
    if not GROQ_API_KEY: return ""
    try:
        t = _oai("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY, "llama-3.3-70b-versatile", prompt)
        print("  Groq:" + str(len(t)) + "字"); return t
    except Exception as e: print("  Groq失敗:" + str(e)[:80]); return ""

def ai_cerebras(prompt):
    if not CEREBRAS_API_KEY: return ""
    try:
        t = _oai("https://api.cerebras.ai/v1/chat/completions", CEREBRAS_API_KEY, "llama-3.3-70b", prompt)
        print("  Cerebras:" + str(len(t)) + "字"); return t
    except Exception as e: print("  Cerebras失敗:" + str(e)[:80]); return ""

def ai_openrouter(prompt):
    if not OR_API_KEY: return ""
    try:
        t = _oai("https://openrouter.ai/api/v1/chat/completions", OR_API_KEY, "meta-llama/llama-3.3-70b-instruct:free", prompt)
        print("  OR:" + str(len(t)) + "字"); return t
    except Exception as e: print("  OR失敗:" + str(e)[:80]); return ""

def ai_mistral(prompt):
    if not MISTRAL_API_KEY: return ""
    try:
        t = _oai("https://api.mistral.ai/v1/chat/completions", MISTRAL_API_KEY, "mistral-small-latest", prompt, 3000)
        print("  Mistral:" + str(len(t)) + "字"); return t
    except Exception as e: print("  Mistral失敗:" + str(e)[:80]); return ""

def ai_cohere(prompt):
    if not COHERE_API_KEY: return ""
    try:
        h = {"Authorization": "Bearer " + COHERE_API_KEY, "Content-Type": "application/json"}
        p = {"model": "command-r", "message": prompt, "max_tokens": 3000, "temperature": 0.2}
        r = requests.post("https://api.cohere.com/v1/chat", json=p, headers=h, timeout=120)
        r.raise_for_status()
        t = r.json()["text"]
        print("  Cohere:" + str(len(t)) + "字"); return t
    except Exception as e: print("  Cohere失敗:" + str(e)[:80]); return ""

def ai_hf(prompt):
    if not HF_API_KEY: return ""
    try:
        h = {"Authorization": "Bearer " + HF_API_KEY, "Content-Type": "application/json"}
        p = {"inputs": prompt, "parameters": {"max_new_tokens": 2000, "temperature": 0.2}}
        r = requests.post("https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3", json=p, headers=h, timeout=120)
        r.raise_for_status()
        t = r.json()[0]["generated_text"]
        if prompt in t: t = t.replace(prompt, "")
        print("  HF:" + str(len(t)) + "字"); return t
    except Exception as e: print("  HF失敗:" + str(e)[:80]); return ""

def ai_gemini(prompt):
    if not GEMINI_API_KEY: return ""
    try:
        u = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
        p = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 3500, "temperature": 0.2}}
        r = requests.post(u, json=p, timeout=120)
        r.raise_for_status()
        t = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print("  Gemini:" + str(len(t)) + "字"); return t
    except Exception as e:
        e2 = str(e).replace(GEMINI_API_KEY, "***") if GEMINI_API_KEY else str(e)
        print("  Gemini失敗:" + e2[:80]); return ""

ENGINES = [
    ("Groq", ai_groq),
    ("Cerebras", ai_cerebras),
    ("OpenRouter", ai_openrouter),
    ("Mistral", ai_mistral),
    ("Cohere", ai_cohere),
    ("HuggingFace", ai_hf),
    ("Gemini", ai_gemini),
]

def call_ai(prompt):
    for name, func in ENGINES:
        print("  " + name + "...")
        r = func(prompt)
        if r and len(r) > 150: return r
        time.sleep(3)
    return ""


def save_html(summary, filename):
    os.makedirs("docs", exist_ok=True)
    body = summary.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","\n<br>")
    body = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', body)
    body = re.sub(r'【(.+?)】', r'<span class="src">【\1】</span>', body)
    html = "<!DOCTYPE html><html lang=ja><head><meta charset=UTF-8>"
    html += "<meta name=viewport content='width=device-width,initial-scale=1.0'>"
    html += "<title>ポイ活日報 " + TODAY + "</title><style>" + PAGE_CSS + "</style></head><body>"
    html += "<a class=back href=./>← 一覧</a><h1>📋 ポイ活お得ランキング</h1>"
    html += "<p class=t>" + TODAY + " ｜ " + str(len(TARGETS)) + "サイト巡回 ｜ 7AI Engine</p><br>"
    html += body + "<hr><p class=t>" + str(len(TARGETS)) + "サイト自動巡回 / Groq,Cerebras,OpenRouter,Mistral,Cohere,HF,Gemini</p></body></html>"
    with open("docs/" + filename, "w", encoding="utf-8") as f: f.write(html)

def make_index():
    files = sorted(glob.glob("docs/2*.html"), reverse=True)
    html = "<!DOCTYPE html><html lang=ja><head><meta charset=UTF-8>"
    html += "<meta name=viewport content='width=device-width,initial-scale=1.0'>"
    html += "<title>ポイ活アーカイブ</title><style>" + PAGE_CSS + "</style></head><body>"
    html += "<h1>📋 ポイ活日報アーカイブ</h1>"
    html += "<p class=t>" + str(len(TARGETS)) + "サイト / 7AI / 1日3回自動</p><ul>"
    for f in files[:90]:
        s = os.path.basename(f).replace(".html","")
        d = s[0:4]+"/"+s[4:6]+"/"+s[6:8]+" "+s[8:10]+":"+s[10:12]+":"+s[12:14] if len(s)==14 else s
        html += "<li><a href=" + os.path.basename(f) + ">" + d + "</a></li>"
    html += "</ul><hr></body></html>"
    with open("docs/index.html", "w", encoding="utf-8") as f: f.write(html)

def git_push():
    try:
        subprocess.run(["git","config","user.name","poi-bot"], check=True)
        subprocess.run(["git","config","user.email","bot@example.com"], check=True)
        subprocess.run(["git","add","docs/"], check=True)
        if subprocess.run(["git","diff","--cached","--quiet"]).returncode != 0:
            subprocess.run(["git","commit","-m","update "+FILESTAMP], check=True)
            subprocess.run(["git","push"], check=True)
            print("Git push完了")
    except Exception as e: print("Git push失敗:" + str(e))

def send_discord(msg):
    if DISCORD_WEBHOOK:
        try: requests.post(DISCORD_WEBHOOK, json={"content": msg[:1990]}, timeout=10)
        except: pass


def main():
    print("=== v3.2 " + TODAY + " / " + str(len(TARGETS)) + "サイト / 7AI ===\n")

    site_data = []
    for t in TARGETS:
        print("  " + t["name"])
        text = crawl(t["url"])
        if text: site_data.append("【" + t["name"] + "】\n" + text)

    combined = "\n---\n".join(site_data)
    print("\n" + str(len(site_data)) + "サイト / " + str(len(combined)) + "字\n")

    batches = [combined[i:i+5500] for i in range(0, len(combined), 5500)]
    print(str(len(batches)) + "バッチ\n")

    results = []
    for i, b in enumerate(batches[:5]):
        print("バッチ" + str(i+1))
        p = PROMPT.replace("{today}", TODAY).replace("{data}", b)
        r = call_ai(p)
        if r: results.append(r)
        time.sleep(5)

    if len(results) > 1:
        print("\n統合中...")
        merged = "\n".join(results)
        mp = "以下の断片を統合してお得ランキングTOP100を作成。重複排除、お得度順。\n"
        mp += "形式: 番号. 【引用元】案件：内容（~期限）\n"
        mp += "カテゴリ: 🛒💳🍔🎁📱🏪💊🏠🏷\n---\n" + merged[:5500]
        final = call_ai(mp)
        if not final or len(final) < 200: final = merged
    elif results:
        final = results[0]
    else:
        final = "AI要約取得失敗。次回をお待ちください。"

    pf = FILESTAMP + ".html"
    save_html(final, pf)
    make_index()
    git_push()

    base = "https://" + GITHUB_REPO.split("/")[0] + ".github.io/" + GITHUB_REPO.split("/")[1] + "/"
    lines = final.strip().split("\n")
    short = "\n".join(lines[:12])
    if len(short) > 1400: short = short[:1400]
    msg = "📋 **ポイ活ランキング " + TODAY + "**\n(" + str(len(TARGETS)) + "サイト/7AI)\n\n"
    msg += short + "\n\n📖 " + base + pf + "\n📚 " + base
    send_discord(msg)
    print("\n完了！")

if __name__ == "__main__":
    main()
