# RSS to Telegram Bot

This bot reads an RSS feed and publishes new posts to a Telegram channel.

## Features

- Asynchronous RSS feed checking.
- Publication history stored in a local SQLite database (to avoid duplicates).
- **Smart message formatting**:
  - Short posts (<1024 chars) are sent as photos with captions.
  - Long posts (>1024 chars) are sent as text messages to preserve full content (up to 4096 chars).
- Text formatting support (paragraph preservation).

## Installation

1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Create a `.env` file based on the example (or just add your variables):
    ```env
    TELEGRAM_BOT_API_TOKEN=your_token
    TELEGRAM_CHANNEL_ID=@your_channel
    RSS_FEED_URL=https://gromada.org.ua/rss/267/
    MONOBANK_LINK=https://send.monobank.ua/your_jar
    ```

## Running

```bash
python main.py
```

