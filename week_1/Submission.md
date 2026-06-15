## Setup and Installation

Before you run the code, you need to make sure you have the right libraries installed. You can install them using pip in your terminal:

```bash
pip install openai google-genai python-dotenv
```

You also need to set up your API keys. See `.env.example` for `.env` format:

## How to Run

Once your dependencies and keys are set up, just run the script normally from your terminal:

```bash
python chatbot.py
```

It will ask you to pick which model you want to talk to, and then you can just start chatting.

## Features and Functionalities

I added a few different systems to make this run smoothly and fix some of the common issues with AI chatbots. Here is what is happening under the hood:

- **Dual-Agent System**: The main chat is handled by whatever model you pick from OpenRouter (GPT OSS 120b or Owl Alpha). But there is a second AI, Gemini 2.5 Flash, running in the background acting as the brain for background tasks.

- **Intent Routing**: Every time you send a message, the `check_intent` function quickly asks Gemini if you are just making normal conversation or if you are trying to fact-check the bot. It returns a 0 for normal chat and a 1 for fact-checking.

- **The Verifier (Fact Checker)**: If the router catches that you want to verify something (like if you ask "are you sure?"), the `verify_last_message` function grabs the last thing you asked and the last thing the bot answered. It sends both to Gemini, who acts as a strict critic to tell you if the main bot was hallucinating or actually correct.

- **Auto-Summarization (Memory Compression)**: The bot counts your messages, once it hits 8 messages, the `make_summary` function triggers. It takes the whole chat history and asks Gemini to condense it into a strict bulleted list of facts. This becomes the new system memory, and the old messages are cleared out. You can also trigger this anytime by typing `/compress`.

- **Typewriter Effect**: The `get_ai_reply` and `verify_last_message` functions stream the data. For Gemini's giant chunks, there's a nested loop that breaks the chunk down and prints it letter by letter with a tiny sleep delay so it looks like it's actually typing.