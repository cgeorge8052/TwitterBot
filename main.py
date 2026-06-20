import discord
from discord.ext import commands, tasks
import feedparser
from dotenv import load_dotenv
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

load_dotenv()
token = os.getenv('RAILWAY_TOKEN')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Map of twitter username -> last seen tweet ID
SEEN_TWEETS_FILE = "seen_tweets.json"
TWITTER_ACCOUNTS = ["WorshipMyra_"]  # usernames to track, no @
ANNOUNCE_CHANNEL_ID = 1512486304959430746
ANNOUNCE_ROLE_ID = 1511368065365840053
CHECK_INTERVAL_MINUTES = 3

# Nitter RSS bridge — replace with a currently-working public instance
# or self-host your own Nitter instance for reliability
NITTER_RSS_URL = "https://nitter.net/{username}/rss"


def load_seen():
    if os.path.exists(SEEN_TWEETS_FILE):
        with open(SEEN_TWEETS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen(data):
    with open(SEEN_TWEETS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def parse_pubdate(entry):
    """Parse the pubDate from a feed entry into a timezone-aware datetime."""
    try:
        # feedparser usually provides published_parsed as a time.struct_time
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        # Fallback: parse the raw pubDate string
        if hasattr(entry, "published"):
            return parsedate_to_datetime(entry.published)
    except Exception as e:
        print(f"Failed to parse pubDate: {e}")
    return None

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_tweets():
    seen = load_seen()

    for username in TWITTER_ACCOUNTS:
        url = NITTER_RSS_URL.format(username=username)
        feed = feedparser.parse(url)

        if not feed.entries:
            print(f"No entries found for {username} (instance may be down)")
            continue

        latest_entry = feed.entries[0]
        latest_id = latest_entry.get("id", latest_entry.link)
        latest_pubdate = parse_pubdate(latest_entry)

        stored = seen.get(username, {})
        # Support both old format (string) and new format (dict) for backward compatibility
        if isinstance(stored, str):
            stored = {"id": stored, "pubdate": None}

        old_id = stored.get("id")
        old_pubdate_str = stored.get("pubdate")
        old_pubdate = datetime.fromisoformat(old_pubdate_str) if old_pubdate_str else None

        is_new_id = old_id != latest_id
        is_newer_pubdate = True
        if old_pubdate and latest_pubdate:
            is_newer_pubdate = latest_pubdate > old_pubdate

        if is_new_id and is_newer_pubdate:
            seen[username] = {
                "id": latest_id,
                "pubdate": latest_pubdate.isoformat() if latest_pubdate else None
            }
            save_seen(seen)

            match = re.search(r"/(\w+)/status/(\d+)", latest_entry.link)
            if match:
                tweet_username, tweet_id = match.groups()
                fx_link = f"https://fxtwitter.com/{tweet_username}/status/{tweet_id}"
            else:
                fx_link = latest_entry.link

            for guild in bot.guilds:
                channel = guild.get_channel(ANNOUNCE_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"<@&{ANNOUNCE_ROLE_ID}> **New tweet from Goddess:**\n{fx_link}"
                    )
        elif is_new_id and not is_newer_pubdate:
            print(f"⚠️ Skipped {username}: new ID but older/equal pubDate ({latest_pubdate} <= {old_pubdate}). Possible stale Nitter data.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not check_tweets.is_running():
        check_tweets.start()


bot.run(token)