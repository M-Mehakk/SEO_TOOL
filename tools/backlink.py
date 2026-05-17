from flask import Blueprint, render_template, request
from urllib.parse import urlparse
import requests, re, time
from bs4 import BeautifulSoup
from collections import Counter
from ddgs import DDGS

# ✅ SINGLE Blueprint
backlink_bp = Blueprint('backlink', __name__)

# ================= INTENT DETECTION =================
def detect_intent(keyword):
    keyword_lower = keyword.lower()

    transactional = ['buy','price','cheap','discount','deal','shop','purchase']
    informational = ['how','what','why','guide','tutorial','learn','tips']
    commercial = ['best','top','review','compare','vs','tool','software']

    if any(x in keyword_lower for x in transactional):
        return "Transactional 🛒"
    elif any(x in keyword_lower for x in informational):
        return "Informational 📚"
    elif any(x in keyword_lower for x in commercial):
        return "Commercial 🛍️"
    else:
        return "General 🌐"


# ================= CONTENT =================
def get_website_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text.lower()

        if "cloudflare" in html or "access denied" in html or len(html) < 500:
            print("⚠️ Block detected → fallback")

            text = ""
            with DDGS() as ddgs:
                results = list(ddgs.text(url, max_results=5)) or []
                for r in results:
                    text += " " + r.get("title", "") + " " + r.get("body", "")

            return None, text, len(text.split())

        soup = BeautifulSoup(response.text, "lxml")

        for tag in soup(["script","style","nav","footer","header","aside","noscript"]):
            tag.decompose()

        content = soup.get_text(" ", strip=True)
        content = re.sub(r'\s+', ' ', content)

        word_count = len(re.findall(r'\b\w+\b', content))

        return response.text, content[:20000], word_count

    except Exception as e:
        print("Content error:", e)
        return None, "", 0


# ================= KEYWORDS =================
def extract_keywords_with_intent(url, content):

    if not content or len(content) < 200:
        domain = urlparse(url).netloc.split('.')[0]
        return [{"keyword": domain, "intent": "General 🌐", "source": "fallback"}]

    words = re.findall(r'\b[a-z]{4,}\b', content.lower())
    freq = Counter(words)

    stopwords = {'this','that','with','from','have','your','more','click','home'}
    bad_words = {"www","http","https","com"}

    filtered = {w:c for w,c in freq.items() if w not in stopwords and w not in bad_words and c > 1}

    if not filtered:
        domain = urlparse(url).netloc.split('.')[0]
        return [{"keyword": domain, "intent": "General 🌐", "source": "fallback"}]

    sorted_words = sorted(filtered.items(), key=lambda x: x[1], reverse=True)

    return [{
        "keyword": w,
        "intent": detect_intent(w),
        "source": "content"
    } for w, _ in sorted_words[:10]]


# ================= BACKLINKS =================
def find_backlinks(url, keywords):
    domain = urlparse(url).netloc
    backlinks = []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f'"{domain}"', max_results=10)) or []

            for r in results:
                link = r.get("href")
                title = r.get("title")

                if link and domain not in str(link):
                    backlinks.append({
                        "title": title[:100] if title else "Link found",
                        "link": link,
                        "score": 65
                    })

    except Exception as e:
        print("Backlink error:", e)

    return backlinks or [{
        "title": "Manual backlink search",
        "link": f"https://www.google.com/search?q=link:{domain}",
        "score": 40
    }]


# ================= OPPORTUNITIES =================
def find_opportunities(keywords):
    opportunities = keywords[:1]

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{keywords[0]} write for us", max_results=6)) or []

            return [{
                "title": r.get("title"),
                "link": r.get("href")
            } for r in results if r.get("title") and r.get("href")]

    except:
        return [{
            "title": "Find guest posts",
            "link": f"https://www.google.com/search?q={keywords[0]}+write+for+us"
        }]


# ================= ROUTE =================
@backlink_bp.route("/backlink-finder", methods=["GET", "POST"])
def backlinks():
    result = None

    if request.method == "POST":
        url = request.form.get("url", "").strip()

        if not url:
            return render_template("backlinks.html", error="Enter URL")

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        html, content, wc = get_website_content(url)
        keywords = extract_keywords_with_intent(url, content)
        kw_list = [k["keyword"] for k in keywords]

        result = {
            "url": url,
            "keywords": keywords,
            "backlinks": find_backlinks(url, kw_list),
            "opportunities": find_opportunities(kw_list),
            "word_count": wc
        }

    return render_template("backlinks.html", result=result)