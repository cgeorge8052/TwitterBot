import discord
from discord.ext import commands, tasks
import feedparser
from dotenv import load_dotenv
import json
import os
import re

load_dotenv()
token = os.getenv('RAILWAY_TOKEN')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Map of twitter username -> last seen tweet ID
SEEN_TWEETS_FILE = "seen_tweets.json"
TWITTER_ACCOUNTS = ["WorshipMyra_"]  # usernames to track, no @
ANNOUNCE_CHANNEL = "🍸⫽social-posts"
ANNOUNCE_ROLE_NAME = "socials"
CHECK_INTERVAL_MINUTES = 1

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

        match = re.search(r"/(\w+)/status/(\d+)", latest_entry.link)
        if match:
            tweet_username, tweet_id = match.groups()
            fx_link = f"https://fxtwitter.com/{tweet_username}/status/{tweet_id}"
        else:
            fx_link = latest_entry.link  # fallback if pattern doesn't match

        if seen.get(username) != latest_id:
            seen[username] = latest_id
            save_seen(seen)

            for guild in bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=ANNOUNCE_CHANNEL)
                role = discord.utils.get(guild.roles, name=ANNOUNCE_ROLE_NAME)
                if channel:
                    await channel.send(
                        f"**New tweet from Goddess {role.mention} :**\n{fx_link}"
                    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not check_tweets.is_running():
        check_tweets.start()


bot.run(token)
