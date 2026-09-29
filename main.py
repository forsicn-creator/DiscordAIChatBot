import os
import re
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

ALLOWED_MENTIONS = discord.AllowedMentions(
    users=True,
    roles=False,
    everyone=False,
    replied_user=False,
)


def build_personality(is_owner: bool, allowed_user_ids: set[int]) -> str:
    mention_rule = (
        "You may mention ONLY these Discord user IDs: "
        + ", ".join(str(user_id) for user_id in sorted(allowed_user_ids))
        + ". Copy their exact <@USER_ID> format when mentioning them."
        if allowed_user_ids
        else
        "There are no target member mentions available in this message. Do not invent any Discord user ID or <@USER_ID> mention."
    )

    if is_owner:
        return f"""You are the owner's friendly Discord AI companion.
Reply in Hindi, Hinglish or English, matching the user's language.
Be respectful, warm, playful and natural. Light harmless flirting is okay when natural.
Write complete, natural conversational replies, usually 2-6 sentences.
Do not abruptly stop, trail off, or leave a thought unfinished.
Be concise without sounding robotic. Avoid unnecessary stories, long lists, repetition, or filler.
{mention_rule}
Never mention @everyone or @here."""
    return f"""You are a playful Discord AI bot.
Reply in Hindi, Hinglish or English, matching the user's language.
Friendly light roasting is okay when appropriate.
Write complete, natural conversational replies, usually 2-6 sentences.
Do not abruptly stop, trail off, or leave a thought unfinished.
Be concise without sounding robotic. Avoid unnecessary stories, long lists, repetition, or filler.
Never use slurs, hateful insults about protected traits, threats, sexual harassment, or targeted abuse.
{mention_rule}
Never mention @everyone or @here."""


def sanitize_mentions(text: str, allowed_user_ids: set[int]) -> str:
    text = text.replace("@everyone", "@\u200beveryone")
    text = text.replace("@here", "@\u200bhere")

    def replace_unknown(match: re.Match) -> str:
        user_id = int(match.group(1))
        if user_id in allowed_user_ids:
            return match.group(0)
        return "@member"

    return re.sub(r"<@!?(\d+)>", replace_unknown, text)


def is_retryable_error(exc: Exception) -> bool:
    error_text = str(exc).upper()
    return (
        "503" in error_text
        or "UNAVAILABLE" in error_text
        or "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
    )


async def generate_reply(contents, is_owner: bool, allowed_user_ids: set[int]):
    last_error = None
    system_instruction = build_personality(is_owner, allowed_user_ids)

    for key_number, api_key in enumerate(GEMINI_API_KEYS, start=1):
        client = genai.Client(api_key=api_key)

        for model in FALLBACK_MODELS:
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        "system_instruction": system_instruction,
                        "max_output_tokens": 600,
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

        allowed_user_ids = {
            member.id for member in message.mentions
            if member.id != self.user.id
        }

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
                reply, _ = await generate_reply(contents, is_owner, allowed_user_ids)

            reply = reply.strip()
            if not reply:
                reply = "Bhai, mera brain abhi buffering mein hai 😭"

            reply = sanitize_mentions(reply, allowed_user_ids)

            for start in range(0, len(reply), 1900):
                await message.channel.send(
                    reply[start:start + 1900],
                    allowed_mentions=ALLOWED_MENTIONS,
                )

            history.append({"role": "assistant", "content": reply})

        except Exception as exc:
            print(f"AI error: {exc}")
            await message.channel.send(
                "Oops 😭 AI abhi unavailable hai. Thodi der baad try kar.",
                allowed_mentions=ALLOWED_MENTIONS,
            )


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(DISCORD_TOKEN)
