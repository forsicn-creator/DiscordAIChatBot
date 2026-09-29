import os
from collections import defaultdict, deque

import discord
from dotenv import load_dotenv
from google import genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_DISCORD_ID = os.getenv("OWNER_DISCORD_ID")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

try:
    OWNER_DISCORD_ID = int(OWNER_DISCORD_ID) if OWNER_DISCORD_ID else None
except ValueError:
    raise RuntimeError("OWNER_DISCORD_ID must be a Discord user ID number")

ai = genai.Client(api_key=GEMINI_API_KEY)

MAX_HISTORY = 12
user_histories = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

# If one Gemini model is temporarily busy, try the next available model.
FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]


def build_personality(is_owner: bool) -> str:
    if is_owner:
        return """You are the owner's friendly Discord AI girl-bot companion.
Speak respectfully, warmly, playfully and naturally in Hindi, Hinglish or English.
You may use light, harmless flirting when it fits the conversation, but never become sexually explicit.
Remember the conversation context supplied to you. Be helpful and fun.
Do not claim to be human or have real-world experiences."""
    return """You are a playful Discord AI bot.
Speak naturally in Hindi, Hinglish or English depending on the user.
You can use light, harmless roasting and savage-style banter when the context is friendly.
Never use slurs, hateful insults about protected traits, threats, sexual harassment, or targeted abuse.
Do not encourage real-world harm. Keep roasting obviously playful and stop if the user asks you to stop.
Be helpful when the user asks a genuine question."""


def is_temporary_capacity_error(exc: Exception) -> bool:
    error_text = str(exc).upper()
    return "503" in error_text or "UNAVAILABLE" in error_text


async def generate_reply(contents, is_owner: bool):
    last_error = None
    tried = set()

    for model in FALLBACK_MODELS:
        if not model or model in tried:
            continue
        tried.add(model)

        for attempt in range(2):
            try:
                response = await ai.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config={"system_instruction": build_personality(is_owner)},
                )
                return response.text or "", model
            except Exception as exc:
                last_error = exc
                if not is_temporary_capacity_error(exc):
                    raise
                if attempt == 0:
                    print(f"Gemini capacity issue on {model}; retrying once...")

        print(f"Gemini model unavailable: {model}")

    raise last_error if last_error else RuntimeError("No Gemini model is configured")


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
                reply, used_model = await generate_reply(contents, is_owner)

            reply = reply.strip()
            if not reply:
                reply = "Bhai, mera brain abhi thoda buffering mein hai 😭"

            reply = discord.utils.escape_mentions(reply)

            print(f"Reply generated using {used_model}")

            for start in range(0, len(reply), 1900):
                await message.channel.send(reply[start:start + 1900])

            history.append({"role": "assistant", "content": reply})

        except Exception as exc:
            print(f"AI error: {exc}")
            await message.channel.send(
                "Oops 😭 Gemini ke saare available models abhi busy hain. Thodi der baad try kar."
            )


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(DISCORD_TOKEN)
