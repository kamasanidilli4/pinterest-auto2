#!/usr/bin/env python3
"""
Amazon → Pinterest Auto-Poster
================================
Give an Amazon product link → it scrapes title, image, price
→ auto-posts to your "amazon deals" Pinterest board.

Usage:
    python amazon_pin_poster.py
    Then paste any Amazon product URL when prompted.
"""

import sys
import subprocess

# Auto-install dependencies before importing them
try:
    import bs4
    import PIL
    import selenium
    import webdriver_manager
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("Installing required packages (beautifulsoup4, pillow, selenium, webdriver-manager, curl_cffi)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4", "pillow", "selenium", "webdriver-manager", "curl_cffi", "--quiet"])
    print("✓ Installed. Proceeding...")
    from curl_cffi import requests as cffi_requests

import re
import time
import requests
import os
import io
import textwrap
import json
import random
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from py3pin.Pinterest import Pinterest

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PINTEREST_EMAIL    = "kdkr666@gmail.com"
PINTEREST_PASSWORD = "kamasanidilli@66"
PINTEREST_USERNAME = "kdkr666"
CRED_ROOT          = "data"

# Your "amazon deals" board ID (from example_usage.py output)
BOARD_ID = "1086000966334952385"

# ─── AMAZON SCRAPER ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


def resolve_url(url: str) -> str:
    """Follow redirects for short links (amzn.to, amzn.in, etc.) and strip tracking params."""
    if any(x in url for x in ["amzn.to", "amzn.in", "amzn.eu", "a.co"]):
        print(f"   🔗 Resolving short link...")
        try:
            # Use curl_cffi to seamlessly bypass any intermediate bot checks
            resp = cffi_requests.get(url, impersonate="chrome", allow_redirects=True, timeout=15)
            url = resp.url
            print(f"   ➜  {url[:80]}...")
        except Exception as e:
            print(f"   ⚠️  Could not resolve redirect: {e}")

    # Extract clean ASIN URL
    match = re.search(r"(https?://(?:www\.)?amazon\.[a-z.]+/(?:[^/]+/)?dp/[A-Z0-9]{10})", url)
    if match:
        return match.group(1)
        
    match_gp = re.search(r"(https?://(?:www\.)?amazon\.[a-z.]+/(?:[^/]+/)?gp/product/[A-Z0-9]{10})", url)
    if match_gp:
        return match_gp.group(1)
        
    return url.split("?")[0]  # fallback: strip query string


def scrape_amazon_product(url: str) -> dict:
    """Scrape product title, image, price and description from Amazon using robust TLS spoofing."""
    resolved_url = resolve_url(url)
    print(f"\n🔍 Scraping: {resolved_url}")

    html = ""
    # We will try up to 3 times to get past Amazon's bot detection
    for attempt in range(1, 4):
        try:
            # Using curl_cffi with impersonate="chrome" perfectly mocks a real browser's TLS signature
            resp = cffi_requests.get(resolved_url, impersonate="chrome", timeout=15)
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            
            # Check if we hit a captcha
            title_tag = soup.find("title")
            if title_tag and "Robot Check" in title_tag.text:
                print(f"   ⚠️ CAPTCHA detected on attempt {attempt}. Retrying...")
                time.sleep(2)
                continue
                
            # Quick check if it loaded properly
            if soup.find("span", id="productTitle") or soup.find("h1", id="title"):
                break # Success!
                
        except Exception as e:
            print(f"   ❌ Fetch error on attempt {attempt}: {e}")
            time.sleep(2)

    soup = BeautifulSoup(html, "html.parser")

    # ── Title ────────────────────────────────────────────────────────────────
    title = ""
    title_tag = soup.find("span", id="productTitle")
    if title_tag:
        title = title_tag.get_text(strip=True)

    if not title:
        title_tag = soup.find("h1", id="title")
        if title_tag:
            title = title_tag.get_text(strip=True)

    # ── Price ────────────────────────────────────────────────────────────────
    price = ""
    for price_id in ["priceblock_ourprice", "priceblock_dealprice", "priceblock_saleprice"]:
        price_tag = soup.find("span", id=price_id)
        if price_tag:
            price = price_tag.get_text(strip=True)
            break
    if not price:
        price_tag = soup.find("span", class_="a-price-whole")
        frac_tag  = soup.find("span", class_="a-price-fraction")
        symbol    = soup.find("span", class_="a-price-symbol")
        if price_tag:
            sym = symbol.get_text(strip=True) if symbol else "$"
            frac = frac_tag.get_text(strip=True) if frac_tag else "00"
            price = f"{sym}{price_tag.get_text(strip=True)}{frac}"

    # ── Images ───────────────────────────────────────────────────────────
    image_urls = []
    # Try high-res image from data attribute
    img_tag = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
    if img_tag:
        if img_tag.get("data-a-dynamic-image"):
            try:
                dyn_images = json.loads(img_tag.get("data-a-dynamic-image"))
                # Only take ONE resolution of the main image so we don't duplicate
                best_main_res = list(dyn_images.keys())[0]
                image_urls.append(best_main_res)
            except:
                pass
        
        if not image_urls:
            url = img_tag.get("data-old-hires") or img_tag.get("data-src") or img_tag.get("src") or ""
            if url: image_urls.append(url)

    # Try to get alternative images
    alt_images = soup.find(id="altImages")
    if alt_images:
        for img in alt_images.find_all("img"):
            src = img.get("src", "")
            if "images/I" in src:
                # Convert thumbnail to high res: safely remove size modifiers like ._AC_US40_ or ._SX425_
                hires = re.sub(r'\._.*?_\.', '.', src)
                if hires not in image_urls:
                    image_urls.append(hires)

    # Try to extract video URL from script tags
    video_url = ""
    for s in soup.find_all("script"):
        if s.string and "colorToVideoMappings" in s.string or "videos" in (s.string or ""):
            match = re.search(r'"url":"(https://[^"]+\.mp4)"', s.string)
            if match:
                video_url = match.group(1)
                break

    # Select the "best" image. Often the 2nd image is the best lifestyle image.
    best_image = ""
    if len(image_urls) > 1:
        # Consistently pick the 2nd image instead of randomizing
        best_image = image_urls[1]
    elif image_urls:
        best_image = image_urls[0]

    # ── Short Description ────────────────────────────────────────────────────
    description = ""
    feature_bullets = soup.find("div", id="feature-bullets")
    if feature_bullets:
        bullets = feature_bullets.find_all("span", class_="a-list-item")
        lines = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
        description = " | ".join(lines[:3])  # first 3 bullet points

    return {
        "title":       title[:100] if title else "Amazon Deal",
        "price":       price,
        "image_url":   best_image,
        "video_url":   video_url,
        "all_images":  image_urls,
        "description": description[:500] if description else "",
        "link":        url,
    }


# ─── IMAGE GENERATOR ─────────────────────────────────────────────────────────

def create_pinterest_image(product: dict, custom_headline: str, custom_layout: str = None, custom_theme_idx: int = None) -> str:
    """Generates a unique, native-looking Pinterest infographic (1000x1500)."""
    print("   🎨 Generating UNIQUE Pinterest Infographic...")
    width, height = 1000, 1500
    
    # Randomize design elements for infinite unique combinations
    align = random.choice(["center", "left"])
    panel_shape = random.choice(["rounded", "sharp", "none"])
    btn_shape = random.choice(["pill", "sharp", "rounded"])
    headline_box = random.choice([True, False])

    colors = [
        {"bg": (0, 0, 0), "text1": (235, 235, 235), "text2": (220, 40, 40), "accent": (46, 204, 113), "panel": (20, 20, 20)},
        {"bg": (245, 245, 245), "text1": (30, 30, 30), "text2": (230, 50, 50), "accent": (255, 60, 60), "panel": (255, 255, 255)},
        {"bg": (20, 30, 48), "text1": (240, 240, 240), "text2": (255, 204, 0), "accent": (0, 204, 255), "panel": (30, 45, 70)},
        {"bg": (45, 10, 20), "text1": (250, 240, 240), "text2": (255, 150, 150), "accent": (255, 50, 100), "panel": (60, 15, 25)},
        # New Themes
        {"bg": (10, 30, 20), "text1": (240, 250, 240), "text2": (100, 255, 150), "accent": (30, 180, 80), "panel": (15, 45, 30)},
        {"bg": (25, 10, 35), "text1": (250, 240, 255), "text2": (255, 150, 255), "accent": (150, 50, 255), "panel": (40, 20, 60)},
        {"bg": (20, 20, 25), "text1": (245, 245, 250), "text2": (255, 140, 0), "accent": (255, 100, 0), "panel": (35, 35, 45)},
        {"bg": (255, 240, 245), "text1": (50, 30, 40), "text2": (200, 50, 100), "accent": (220, 80, 120), "panel": (255, 255, 255)}
    ]
    if custom_theme_idx is not None and 0 <= int(custom_theme_idx) < len(colors):
        theme = colors[int(custom_theme_idx)]
    else:
        theme = random.choice(colors)

    img = Image.new('RGB', (width, height), color=theme["bg"])
    draw = ImageDraw.Draw(img)

    # Fonts
    font_bold = os.path.join(os.getcwd(), "Roboto-Bold.ttf")
    font_reg = os.path.join(os.getcwd(), "Roboto-Regular.ttf")
    
    if not os.path.exists(font_bold):
        print("   ⬇️ Downloading fonts for the first time...")
        import urllib.request
        try:
            urllib.request.urlretrieve("https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf", font_bold)
            urllib.request.urlretrieve("https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf", font_reg)
        except Exception as e:
            print(f"   ⚠️ Failed to download fonts: {e}")

    try:
        font_headline = ImageFont.truetype(font_bold, 80)
        font_title = ImageFont.truetype(font_bold, 55)
        font_desc = ImageFont.truetype(font_reg, 45)
        font_btn = ImageFont.truetype(font_bold, 75)
    except Exception as e:
        print(f"   ⚠️ Could not load downloaded font: {e}")
        try:
            font_headline = ImageFont.truetype("arialbd.ttf", 80)
            font_title = ImageFont.truetype("arialbd.ttf", 55)
            font_desc = ImageFont.truetype("arial.ttf", 45)
            font_btn = ImageFont.truetype("arialbd.ttf", 75)
        except:
            print("   ⚠️ Falling back to default (text will be small).")
            font_headline = font_title = font_desc = font_btn = ImageFont.load_default()

    # Top Headline Banner
    line1, line2 = "", ""
    if "|" in custom_headline:
        parts = custom_headline.split("|", 1)
        line1 = parts[0].strip().upper()
        line2 = parts[1].strip().upper()
    else:
        wrapper_head = textwrap.TextWrapper(width=20)
        head_lines = wrapper_head.wrap(text=custom_headline.upper())
        line1 = head_lines[0] if len(head_lines) > 0 else ""
        line2 = head_lines[1] if len(head_lines) > 1 else ""

    if headline_box:
        box_y = 30 if line2 else 50
        box_h = 200 if line2 else 120
        draw.rectangle([0, box_y, width, box_y+box_h], fill=theme["accent"])
        head_color1 = (255,255,255) if sum(theme["accent"]) < 380 else (0,0,0)
        head_color2 = head_color1
    else:
        head_color1 = theme["text1"]
        head_color2 = theme["text2"]

    if not line2:
        draw.text((width//2, 110), line1, font=font_headline, fill=head_color1, anchor="mm")
    else:
        draw.text((width//2, 85), line1, font=font_headline, fill=head_color1, anchor="mm")
        draw.text((width//2, 175), line2, font=font_headline, fill=head_color2, anchor="mm")

    # Download Product Image
    img_bottom = 250
    try:
        resp = requests.get(product["image_url"], stream=True, timeout=10)
        resp.raise_for_status()
        prod_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        
        # Add white background for transparency
        bg_for_prod = Image.new("RGBA", prod_img.size, (255,255,255,255))
        bg_for_prod.paste(prod_img, (0,0), prod_img)
        prod_img = bg_for_prod.convert("RGBA")
        
        # Larger image size
        img_size = (850, 750)
        prod_img.thumbnail(img_size, Image.Resampling.LANCZOS)
        
        img_x = (width - prod_img.width) // 2
        img_y = 260
        
        # Draw panel behind image
        panel_rect = [img_x-20, img_y-20, img_x+prod_img.width+20, img_y+prod_img.height+20]
        if panel_shape == "rounded":
            draw.rounded_rectangle(panel_rect, radius=40, fill=theme["panel"])
        elif panel_shape == "sharp":
            draw.rectangle(panel_rect, fill=theme["panel"])
        
        img.paste(prod_img, (img_x, img_y), prod_img)
        img_bottom = img_y + prod_img.height + 20
    except Exception as e:
        print(f"   ⚠️ Could not load product image for poster: {e}")

    # Set up alignment variables
    x_pos = width // 2 if align == "center" else 60
    anchor_pos = "mm" if align == "center" else "lm"

    # Main Title
    y_text = img_bottom + 80
    wrapper = textwrap.TextWrapper(width=30)
    title_lines = wrapper.wrap(text=product['title'])
    for line in title_lines[:2]:
        draw.text((x_pos, y_text), line, font=font_title, fill=theme["text1"], anchor=anchor_pos)
        y_text += 70

    # Extra Qualities (Description)
    y_text += 20
    desc_wrapper = textwrap.TextWrapper(width=40)
    desc_text = product.get('description', '')
    if desc_text:
        bullets = [b.strip() for b in desc_text.split('|') if b.strip()]
        for bullet in bullets[:3]:
            wrapped_bullet = desc_wrapper.wrap(f"• {bullet}")
            for line in wrapped_bullet[:2]:
                draw.text((x_pos, y_text), line, font=font_desc, fill=theme["text2"] if align == "center" else theme["text1"], anchor=anchor_pos)
                y_text += 55
            y_text += 15
    
    # CTA Button
    btn_y = height - 160
    btn_w = 700
    btn_h = 110
    btn_x = (width - btn_w) // 2
    
    if btn_shape == "pill":
        draw.rounded_rectangle([btn_x, btn_y, btn_x+btn_w, btn_y+btn_h], radius=55, fill=theme["accent"])
    elif btn_shape == "rounded":
        draw.rounded_rectangle([btn_x, btn_y, btn_x+btn_w, btn_y+btn_h], radius=20, fill=theme["accent"])
    else:
        draw.rectangle([btn_x, btn_y, btn_x+btn_w, btn_y+btn_h], fill=theme["accent"])
    
    # Text on button
    btn_text_color = (255, 255, 255) if sum(theme["accent"]) < 380 else (0, 0, 0)
    btn_label = "SHOP NOW"
    draw.text((width//2, btn_y + 55), btn_label, font=font_btn, fill=btn_text_color, anchor="mm")

    out_path = os.path.join(os.getcwd(), f"generated_pin_{random.randint(1000,9999)}.jpg")
    img.convert('RGB').save(out_path, quality=98)
    return out_path


# ─── PINTEREST POSTER ────────────────────────────────────────────────────────

def post_to_pinterest(product: dict, headline: str, custom_layout: str = None, custom_theme_idx: int = None) -> tuple:
    """Create a pin on the amazon deals board. Returns (success_bool, error_message)."""
    print("\n📌 Connecting to Pinterest...")
    pinterest = Pinterest(
        email=PINTEREST_EMAIL,
        password=PINTEREST_PASSWORD,
        username=PINTEREST_USERNAME,
        cred_root=CRED_ROOT,
    )

    # Build pin title & description
    pin_title = product["title"]
    price_str = f" — {product['price']}" if product["price"] else ""
    pin_description = (
        f"🛒 {product['title']}{price_str}\n\n"
        f"{product['description']}\n\n"
        f"👉 Shop now: {product['link']}\n\n"
        f"#AmazonDeals #AmazonFinds #Shopping #Deal"
    )

    if not product["image_url"] and not product.get("video_url") and not product.get("local_media_path"):
        print("❌ Could not find product image or video. Pinterest needs media.")
        print("   Try a different Amazon product link.")
        return False, "Could not find product image or media."

    print(f"\n📦 Product  : {product['title']}")
    print(f"💰 Price    : {product['price'] or 'N/A'}")
    if product.get('video_url'):
        print(f"🎥 Video    : {product['video_url'][:80]}...")
    else:
        print(f"🖼  Image    : {product['image_url'][:80]}...")
    print(f"\n📌 Posting to Pinterest board '{BOARD_ID}'...")

    image_path = None
    
    # Check if user uploaded custom media
    if product.get('local_media_path'):
        image_path = product['local_media_path']
        print(f"   📂 Using custom uploaded media: {image_path}")
    else:
        # We always generate the pin (infographic) instead of uploading raw video
        # because py3pin upload-image endpoint does not support .mp4 files!
        image_path = create_pinterest_image(product, headline, custom_layout, custom_theme_idx)

    try:
        response = pinterest.upload_pin(
            board_id=BOARD_ID,
            image_file=image_path,
            description=pin_description,
            title=pin_title,
            link=product["link"],
        )
        result = response.json().get("resource_response", {}).get("data", {})

        if result and result.get("id"):
            print(f"\n✅ Pin posted successfully!")
            print(f"   Pin ID : {result['id']}")
            print(f"   View   : https://pinterest.com/pin/{result['id']}/")
            return True, result['id']
        else:
            err_msg = str(response.json()) if response else "Unknown error"
            print(f"⚠️  Unexpected response: {err_msg}")
            return False, f"Unexpected response from Pinterest: {err_msg}"

    except Exception as e:
        print(f"❌ Pinterest error: {e}")
        return False, f"Pinterest error: {str(e)}"


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🛒 Amazon → Pinterest Auto-Poster")
    print("=" * 60)

    while True:
        print("\nPaste an Amazon product URL (or type 'quit' to exit):")
        url = input("  URL: ").strip()

        if url.lower() in ("quit", "exit", "q"):
            print("Bye! 👋")
            break

        if not url or not any(x in url.lower() for x in ["amazon", "amzn.to", "amzn.in", "amzn.eu", "a.co"]):
            print("❌ That doesn't look like an Amazon URL. Try again.")
            continue

        headline = input("  Custom Headline (Use '|' to split into 2 lines, or press Enter for default):\n  > ").strip()
        if not headline:
            headline = "DON'T BUY THIS | UNTIL YOU SEE THIS!"

        # Scrape
        product = scrape_amazon_product(url)

        if not product:
            print("❌ Couldn't scrape that page. Try another link.")
            continue

        if not product["title"] or product["title"] == "Amazon Deal":
            print("⚠️  Amazon is blocking the scrape (bot detection).")
            print("   Tip: Try the product's direct link (not a search/redirect link).")
            continue

        # Post
        success, err = post_to_pinterest(product, headline)

        if success:
            print("\n▶ Post another? (paste next URL or type 'quit')")
        else:
            print("\n▶ Try again with a different link, or type 'quit'.")

        time.sleep(2)  # small delay between posts


if __name__ == "__main__":
    main()
