import base64
import re
import requests
from bs4 import BeautifulSoup, NavigableString
import os
import cloudscraper

# ================= CONFIG =================
WP_URL = "https://blog.mexc.com/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
POST_ID = 304134  # ID bài Hamster Kombat Cipher Code
CHECK_WORD = "TABS"   # Word hiện có trên bài. Chỉ update khi scrape != CHECK_WORD

# ================= SCRAPE SITE 1 =================
def scrape_cipher_site1():
    url = "https://miningcombo.com/hamster/"
    print(f"[+] Scraping cipher from {url}")
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Word
    word_tag = soup.find(
        "p",
        class_=lambda c: c and "has-text-align-left" in c.split()
    )
    if not word_tag:
        raise RuntimeError("❌ Không tìm thấy thẻ <p> chứa Word (site1)")
    
    strong_tag = word_tag.find("strong", string=lambda s: s and "Word:" in s)
    if not strong_tag:
        raise RuntimeError("❌ Không tìm thấy thẻ <strong>Word:</strong> (site1)")
    
    # Lấy phần text phía sau strong (ví dụ: BRICK)
    word = strong_tag.next_sibling
    if not word:
        raise RuntimeError("❌ Không tìm thấy nội dung sau Word: (site1)")
    
    word = str(word).strip()
    print(f"[+] Found Word: {word}")

    # Cipher lines (dựa vào p.has-text-color nằm ngay sau p chứa Word)
    cipher_tag = None
    for sibling in word_tag.find_next_siblings("p"):
        classes = sibling.get("class", [])
        if "has-text-color" in classes:
            cipher_tag = sibling
            break

    if not cipher_tag:
        raise RuntimeError("❌ Không tìm thấy thẻ cipher codes (site1)")

    raw = cipher_tag.get_text(separator="\n", strip=True).replace("\xa0", " ")
    raw_lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

    pretty_lines = []
    for line in raw_lines:
        m = re.match(r"^\s*([A-Za-z])\s*[:=]?\s*(.*)$", line)
        if not m:
            continue
        letter = m.group(1).upper()
        tail = m.group(2).strip()

        symbols = []
        for ch in tail:
            # nhận cả dot glyph & biến thể
            if ch in (".", "•", "∙", "·", "●"):
                symbols.append("•")
            # nhận mọi biến thể dấu gạch
            elif ch in ("_", "-", "–", "—", "−", "━", "─", "﹣", "－"):
                symbols.append("—")
            # bỏ qua khoảng trắng/khác
        pretty_lines.append(f"{letter} = {' '.join(symbols)}")

    print("[+] Scraped (site1)")
    return word, pretty_lines

# ================= SCRAPE SITE 2 =================
def scrape_cipher_site2():
    url = "https://hamster-combo.com/daily-morse-code-hamster-kombat/"
    print(f"[+] Scraping cipher from {url}")
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    div_morse = soup.find("div", class_="morse-code")
    if not div_morse:
        raise RuntimeError("❌ Không tìm thấy <div class='morse-code'> (site2)")

    word = ""
    pretty_lines = []
    for letter_div in div_morse.find_all("div", class_="letter", recursive=False):
        spans = letter_div.find_all("span")
        if len(spans) < 2:
            continue
        letter = spans[0].get_text(strip=True).upper()
        morse = spans[-1].get_text(strip=True)  # thường nằm trong span cuối
        word += letter
        pretty_lines.append(f"{letter} = {morse}")

    print("[+] Scraped (site2)")
    return word, pretty_lines

# ============== FETCH CURRENT POST ============
def fetch_current_content():
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {"Authorization": f"Basic {token}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    url = f"{WP_URL}/{POST_ID}"
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"❌ Không lấy được post: {r.status_code} {r.text[:300]}")
    post = r.json()
    return post.get("content", {}).get("rendered", "")

# ================ UPDATE POST ================
def update_post(word, pretty_lines, old_content):
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {"Authorization": f"Basic {token}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    soup = BeautifulSoup(old_content, "html.parser")

    # --- Update Cipher Code line ---
    strong_cc = soup.find("strong", string=lambda t: t and "Cipher Code:" in t)
    if not strong_cc:
        raise RuntimeError("❌ Không tìm thấy <strong>Cipher Code:</strong>")
    p_cc = strong_cc.find_parent("p")
    br_first = p_cc.find("br")
    if br_first:
        to_remove = []
        for sib in list(strong_cc.next_siblings):
            if sib is br_first:
                break
            to_remove.append(sib)
        for node in to_remove:
            node.extract()
        br_first.insert_before(NavigableString(" " + word))
    else:
        for sib in list(strong_cc.next_siblings):
            sib.extract()
        strong_cc.insert_after(NavigableString(" " + word))
    print("[+] Updated Cipher Code line")

    # --- Update Morse heading ---
    h3 = soup.find("h3", class_="wp-block-heading")
    if not h3:
        h3 = soup.find("h3", string=lambda t: t and "Morse for" in t)
    if not h3:
        raise RuntimeError("❌ Không tìm thấy H3 cho phần Morse")
    strong_in_h3 = h3.find("strong")
    new_h3_text = f"Morse for “{word}”:"
    if strong_in_h3:
        strong_in_h3.string = new_h3_text
    else:
        h3.string = new_h3_text
    print("[+] Updated Morse heading")

    # --- Insert new UL ---
    next_tag = h3.find_next_sibling()
    if next_tag and next_tag.name == "ul":
        print("⚠️ Đã có UL ngay sau H3 -> bỏ qua không chèn mới")
    else:
        new_ul = soup.new_tag("ul")
        new_ul["class"] = ["wp-block-list"]
        for line in pretty_lines:
            li = soup.new_tag("li")
            li.string = line
            new_ul.append(li)
        h3.insert_after(new_ul)
        print("[+] Inserted new UL after H3")

    new_content = str(soup)

    # --- Push update ---
    url_update = f"{WP_URL}/{POST_ID}"
    payload = {"content": new_content, "status": "publish"}
    up = requests.post(url_update, headers=headers, json=payload, timeout=20)
    print("🚀 Update status:", up.status_code)
    print("📄 Update response:", up.text[:300])
    if up.status_code == 200:
        print("✅ Post updated & published thành công!")

# ================= MAIN =================
if __name__ == "__main__":
    try:
        word, pretty_lines = scrape_cipher_site1()
    except Exception as e:
        print("❌ Site1 lỗi:", e)
        word, pretty_lines = None, None

    if word and word.strip() != CHECK_WORD.strip():
        print(f"✅ Word mới ({word}) KHÁC CHECK_WORD ({CHECK_WORD}) -> Update (site1)")
        old = fetch_current_content()
        update_post(word, pretty_lines, old)
    else:
        print("⚠️ Site1 trùng CHECK_WORD hoặc lỗi -> thử site2")
        try:
            word2, pretty_lines2 = scrape_cipher_site2()
            if word2.strip() != CHECK_WORD.strip():
                print(f"✅ Word mới ({word2}) KHÁC CHECK_WORD ({CHECK_WORD}) -> Update (site2)")
                old = fetch_current_content()
                update_post(word2, pretty_lines2, old)
            else:
                print(f"⚠️ Word site2 ({word2}) trùng CHECK_WORD ({CHECK_WORD}) -> Không update")
        except Exception as e:
            print("❌ Site2 cũng lỗi:", e)
