# DiscordAIChatBot

A Discord AI chatbot written in Python. It uses `discord.py` to receive Discord messages and Google's Gemini API to generate replies. The bot responds when a user mentions it and keeps a short conversation history per user.

## Features

- Replies to messages that mention the bot.
- Uses Gemini models, with fallback models and multiple API keys for retryable availability or rate-limit errors.
- Keeps up to eight recent messages total per user in memory.
- Supports Hindi, Hinglish, and English conversational replies.
- Allows safe member mentions while suppressing `@everyone` and `@here` notifications.
- Applies a configurable owner persona using `OWNER_DISCORD_ID`.

## Requirements

- Python 3.9 or newer
- A Discord application and bot token, with Message Content Intent enabled in the Discord Developer Portal
- One or more Google Gemini API keys

Install the Python dependencies used by the bot:

```bash
python -m pip install discord.py python-dotenv google-genai
```

## Configuration

Create a `.env` file in the project root. Set `DISCORD_TOKEN` and at least one of the three Gemini API key variables. `OWNER_DISCORD_ID` and `GEMINI_MODEL` are optional. Replace the example placeholders with actual values before running the bot. Never commit real tokens or API keys.

```dotenv
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY_1=your_first_gemini_api_key
GEMINI_API_KEY_2=your_second_gemini_api_key
GEMINI_API_KEY_3=your_third_gemini_api_key
OWNER_DISCORD_ID=your_discord_user_id
GEMINI_MODEL=gemini-3.8-flash
```

| Variable | Required | Description |
| --- | --- | --- |
| `DISCORD_TOKEN` | Yes | Token for the Discord bot. |
| `GEMINI_API_KEY_1` | One of these is required | First Gemini API key. |
| `GEMINI_API_KEY_2` | One of these is required | Optional second Gemini API key. |
| `GEMINI_API_KEY_3` | One of these is required | Optional third Gemini API key. |
| `OWNER_DISCORD_ID` | No | Numeric Discord user ID that enables the owner-specific personality. |
| `GEMINI_MODEL` | No | First model to try. Defaults to `gemini-3.8-flash`. If a request fails with a retryable availability or rate-limit error, the code tries `gemini-3.5-flash-lite`, `gemini-3.6-flash`, and `gemini-3.7-flash`, then tries the next configured API key. |

The example configuration is also available in [`.env.example`](.env.example). Copy it to `.env` and replace the placeholders with your own values.

## Run

From the project directory, start the bot with:

```bash
python main.py
```

Mention the bot in a Discord server channel to receive a reply. The bot's role and channel permissions must allow it to view and send messages.
