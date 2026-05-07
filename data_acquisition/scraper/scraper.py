import re
import csv
import asyncio
from playwright.async_api import async_playwright

async def run():
    base_url = "https://www.meteorites-for-sale.com/catalog-updates.html"
    unique_urls = set()
    url_pattern = re.compile(r'https?://[^\s"\'<>]+?\.html')
    delay = 1.0 

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # BLOCK CAPTCHAS: This stops the pending blob/hcaptcha requests from hanging the script
        await page.route("**/*captcha*", lambda route: route.abort())

        for i in range(1, 6):
            target = f"{base_url}/{i}/"
            try:
                print(f"[>] Gathering URLs: Page {i}")
                # Using 'domcontentloaded' instead of 'networkidle' to ignore background JS noise
                await page.goto(target, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2) # Short buffer for any slow-rendering links
                content = await page.content()
                unique_urls.update(url_pattern.findall(content))
            except Exception as e:
                print(f" [!] Skip Page {i}: {e}")
                continue

        with open("scraper_unique_urls.txt", "w") as f:
            for url in sorted(list(unique_urls)):
                f.write(url + "\n")

        filtered_urls = []
        for url in unique_urls:
            path = url.split('.com/')[-1] if '.com/' in url else ""
            if re.search(r'\d', path) and 'g' in path.lower():
                filtered_urls.append(url)

        results = []
        print(f"[*] Processing {len(filtered_urls)} filtered URLs...")
        
        for url in filtered_urls:
            try:
                print(f"[>] Fetching data: {url}")
                # Using 'load' here to ensure the meta tags are populated
                await page.goto(url, wait_until="load", timeout=30000)
                
                try:
                    name = await page.get_attribute('meta[property="og:title"]', 'content')
                except:
                    name = ""

                try:
                    desc = await page.get_attribute('meta[name="description"]', 'content')
                except:
                    desc = ""

                try:
                    price = await page.get_attribute('meta[name="twitter:data1"]', 'content')
                except:
                    price = ""

                try:
                    category = await page.inner_text('span.posted_in a') if await page.query_selector('span.posted_in a') else ""
                except:
                    category = ""
                
                mass = ""
                if name:
                    mass_match = re.search(r'\s(\d+(?:\.\d+)?g)', name)
                    if mass_match:
                        mass = mass_match.group(1)

                # Printing data to console as requested
                print(f"    Name: {name}")
                print(f"    Description: {desc[:50]}...") # Truncated for clean console output
                print(f"    Price: {price}")
                print(f"    Category: {category}")
                print(f"    Mass: {mass}")
                
                results.append({
                    "name": name or "",
                    "description": desc or "",
                    "price": price or "",
                    "category": category or "",
                    "mass": mass or ""
                })
                
                await asyncio.sleep(delay) 
            except Exception as e:
                print(f"    [!] Error loading product page: {e}")
                continue

        await browser.close()

    with open('prices.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "description", "price", "category", "mass"])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Done. Processed {len(results)} items into prices.csv")

if __name__ == "__main__":
    asyncio.run(run())