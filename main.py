import os
from collections import defaultdict, deque

import discord
from dotenv import load_dotenv
from google import genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_DISCORD_ID = os.getenv("OWNER_DISCORD_ID")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")
if not GEMINI_API_KEYS:
    raise RuntimeError("At least one GEMINI_API_KEY_1/2/3 is required")

try:
    OWNER_DISCORD_ID = int(OWNER_DISCORD_ID) if OWNER_DISCORD_ID else None
except ValueError:
    raise RuntimeError("OWNER_DISCORD_ID must be a Discord user ID number")

MAX_HISTORY = 8
user_histories = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]


def build_personality(is_owner: bool) -> str:
    if is_owner:
        return """You are the owner's friendly Discord AI companion.
Reply in Hindi, Hinglish or English, matching the user's language.
Be respectful, warm and playful. Light harmless flirting is okay when natural.
Keep replies SHORT and direct: normally 1-4 sentences.
Do not add unnecessary stories, lists, explanations, or filler.
Answer only what the user asked unless a little context is genuinely useful."""
    return """You are a playful Discord AI bot.
Reply in Hindi, Hinglish or English, matching the user's language.
Friendly light roasting is okay when appropriate.
Keep replies SHORT and direct: normally 1-4 sentences.
Do not add unnecessary stories, lists, explanations, or filler.
Never use slurs, hateful insults about protected traits, threats, sexual harassment, or targeted abuse.
Answer only what the user asked unless a little context is genuinely useful."""


def is_retryable_error(exc: Exception) -> bool:
    error_text = str(exc).upper()
    return (
        "503" in error_text
        or "UNAVAILABLE" in error_text
        or "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
    )


async def generate_reply(contents, is_owner: bool):
    last_error = None

    for key_number, api_key in enumerate(GEMINI_API_KEYS, start=1):
        client = genai.Client(api_key=api_key)

        for model in FALLBACK_MODELS:
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        "system_instruction": build_personality(is_owner),
                        "max_output_tokens": 220,
                    },
                )
                print(f"Reply generated using key {key_number}, model {model}")
                return response.text or "", model
            except Exception as exc:
                last_error = exc
                if not is_retryable_error(exc):
                    raise
                print(f"Key {key_number} / model {model} unavailable; trying next option...")

    raise last_error if last_error else RuntimeError("No Gemini API key is configured")


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self.user or not self.user.mentioned_in(message) or message.mention_everyone:
            return

        prompt = message.content
        prompt = prompt.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()

        if not prompt:
            prompt = "Say hi and ask what I need."

        user_id = message.author.id
        is_owner = OWNER_DISCORD_ID == user_id
        history = user_histories[user_id]

        history.append({"role": "user", "content": prompt})

        try:
            async with message.channel.typing():
                contents = [
                    {"role": "user" if item["role"] == "user" else "model",
                     "parts": [{"text": item["content"]}]}
                    for item in history
                ]
                reply, _ = await generate_reply(contents, is_owner)

            reply = reply.strip()
            if not reply:
                reply = "Bhai, mera brain abhi buffering mein hai 😭"

            reply = discord.utils.escape_mentions(reply)

            for start in range(0, len(reply), 1900):
                await message.channel.send(reply[start:start + 1900])

            history.append({"role": "assistant", "content": reply})

        except Exception as exc:
            print(f"AI error: {exc}")
            await message.channel.send(
                "Oops 😭 AI abhi unavailable hai. Thodi der baad try kar."
            )


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(DISCORD_TOKEN)
