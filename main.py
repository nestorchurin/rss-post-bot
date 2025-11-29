from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
import os
import dotenv
import asyncio
import aiohttp
import aiosqlite
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import html
import re

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
dotenv.load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
RSS_FEED_URL = os.getenv("RSS_FEED_URL")
MONOBANK_LINK = os.getenv("MONOBANK_LINK")

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DB_NAME = "rss_posts.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                link TEXT PRIMARY KEY,
                published_date TEXT
            )
        """)
        await db.commit()

async def post_exists(link):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT 1 FROM posts WHERE link = ?", (link,))
        return await cursor.fetchone() is not None

async def add_post(link):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO posts (link, published_date) VALUES (?, ?)", (link, datetime.now().isoformat()))
        await db.commit()

def clean_html(html_content):
    if not html_content:
        return ""
    
    # Unescape HTML entities to ensure tags are recognized
    html_content = html.unescape(html_content)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove images as we send them separately
    for img in soup.find_all('img'):
        img.decompose()
        
    # Replace paragraphs with double newlines
    for p in soup.find_all('p'):
        p.insert_after('\n\n')
        p.unwrap()
        
    # Replace br with newline
    for br in soup.find_all('br'):
        br.replace_with('\n')
        
    text = soup.get_text()
    
    # Clean up excessive whitespace
    # Preserve empty lines that might be paragraph breaks
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(lines)
    
    # Remove excessive newlines (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

async def fetch_rss():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(RSS_FEED_URL) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logging.error(f"Error fetching RSS: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Exception fetching RSS: {e}")
            return None

async def send_item(item):
    link = item.find('link').text.strip() if item.find('link') else None
    if not link:
        return

    title = item.find('title').text.strip() if item.find('title') else "Без назви"
    
    # Try full-text, fall back to description
    full_text_tag = item.find('full-text')
    description_tag = item.find('description')
    
    content_html = ""
    if full_text_tag and full_text_tag.string:
        content_html = full_text_tag.string
    elif description_tag and description_tag.string:
        content_html = description_tag.string
        
    text_content = clean_html(content_html)
    
    # Limit text length for Telegram caption (1024 chars) or message (4096 chars)
    # If we send photo, caption limit is 1024.
    
    enclosure = item.find('enclosure')
    image_url = enclosure['url'] if enclosure else None

    # Escape title and text content to prevent HTML parsing errors in Telegram
    safe_title = html.escape(title)
    safe_text = html.escape(text_content)

    # Construct message
    message_text = f"<b>{safe_title}</b>\n\n"
    message_text += f"{safe_text[:900]}..." if len(safe_text) > 900 else safe_text
    message_text += f"\n\n<a href=\"{link}\">Посилання</a>"
    if MONOBANK_LINK:
        message_text += f" | <a href=\"{MONOBANK_LINK}\">Підтримати</a>"

    try:
        if image_url:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=message_text,
                parse_mode=ParseMode.HTML
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
        
        await add_post(link)
        logging.info(f"Posted: {title}")
        # Sleep to avoid hitting rate limits
        await asyncio.sleep(3) 
        
    except Exception as e:
        logging.error(f"Error sending post {link}: {e}")

async def process_feed(first_run=False):
    xml_content = await fetch_rss()
    if not xml_content:
        return

    soup = BeautifulSoup(xml_content, 'xml')
    items = soup.find_all('item')

    if not items:
        return

    if first_run:
        # On first run, we only care about the latest post (items[0])
        # We want to send it if it's new.
        # We also want to mark ALL older posts as seen so they aren't sent later.
        
        latest_item = items[0]
        latest_link = latest_item.find('link').text.strip() if latest_item.find('link') else None
        
        if latest_link and not await post_exists(latest_link):
            # Send the latest post
            await send_item(latest_item)
            
        # Mark ALL items as seen (including the one we just sent, and the older ones)
        for item in items:
            link = item.find('link').text.strip() if item.find('link') else None
            if link and not await post_exists(link):
                await add_post(link)
                
    else:
        # Normal operation: process all items from oldest to newest
        for item in reversed(items):
            link = item.find('link').text.strip() if item.find('link') else None
            if not link:
                continue

            if await post_exists(link):
                continue
            
            await send_item(item)

async def scheduler():
    await init_db()
    first_run = True
    while True:
        logging.info("Checking feed...")
        await process_feed(first_run=first_run)
        first_run = False
        await asyncio.sleep(300) # Check every 5 minutes

async def main():
    # Start scheduler
    asyncio.create_task(scheduler())
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

