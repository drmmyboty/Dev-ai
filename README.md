# Dev AI — $0 deployment starter

This build is designed so the **owner does not have to pay for AI requests**. The server uses a configurable OpenAI-compatible provider, with OpenRouter's `openrouter/free` as the default example. OpenRouter currently lists a free-model router at $0, but free availability and limits can change.

## Important
The app intentionally does **not** ship with a shared API key. Add your own provider key as an environment variable. That keeps the project public without exposing a secret in GitHub. Anyone can fork the repo and use their own provider key.

## Run on Android/Pydroid
1. Extract the folder.
2. Install packages: `pip install -r requirements.txt`
3. For local HTTP testing, set `DEV_AI_SECURE_COOKIES=0`.
4. Set `DEV_AI_API_KEY` if you want AI responses.
5. Run `python app.py`.

## Public hosting
Upload the folder to GitHub and deploy it to a Python host that supports Flask/Gunicorn. Add the environment variables from `.env.example`. Use the host's HTTPS URL.

## Features
- account signup/login/logout
- change password while logged in
- per-user chat history
- developer AI prompts
- multi-language coding, including Luau/Roblox
- code/debug/explain/refactor/convert workflows via prompting
- plugin discovery (no automatic execution)
- configurable app name/model/provider URL

## Limitations
- Forgot-password is not included because it needs an email delivery flow.
- The editor is currently a simple web text area rather than Monaco/Ace.
- SQLite is used for the $0 starter. On hosts with ephemeral storage, users should switch to a persistent database.
- A free AI model is still subject to provider rate limits; it is not unlimited.
