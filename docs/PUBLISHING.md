# Publishing Aether (steps the author does in a browser)

Everything is prepared locally. Publishing needs your own accounts, so these steps are yours. Both services are free. Never paste passwords or tokens into a chat with an AI assistant. You sign in yourself, in the browser.

**Before creating any account:** if you are under 18, confirm that a parent or guardian knows you are creating GitHub and Hugging Face accounts and publishing this project. Both sites require users to be at least 13.

Build the release folders first, in the `aether` folder:

```bash
uv run python -m release.build
```

This creates `dist/`. The model in `dist/model` is v0.2.

## A. Code on GitHub

1. Go to https://github.com and sign in, or click **Sign up** and verify your email.
2. **Turn on a private commit email.** Click your profile picture, then **Settings**, then **Emails**. Check **Keep my email addresses private**. GitHub then shows your no-reply address, which looks like `12345678+yourname@users.noreply.github.com`. Copy it.
3. **Put your name and that no-reply email on the commit.** The repository currently has one commit by a neutral placeholder author. In the `aether` folder, run these, replacing the values in quotes:
   ```bash
   git config user.name "Your GitHub Name"
   ```
   ```bash
   git config user.email "12345678+yourname@users.noreply.github.com"
   ```
   ```bash
   git commit --amend --reset-author --no-edit
   ```
   ```bash
   git log --format="%an <%ae>"
   ```
   The last command should print your name and the no-reply address, not your personal email.
4. Click **+** (top right), then **New repository**. Name it `aether`, choose **Public**, and leave "Add a README", ".gitignore" and "license" **unchecked**. Click **Create repository**.
5. Connect the repository and push, replacing `<you>` with your GitHub username:
   ```bash
   git remote add origin https://github.com/<you>/aether.git
   ```
   ```bash
   git push -u origin main
   ```
   On the first push, a browser window opens to sign in to GitHub. You complete it yourself.

## B. Hugging Face (dataset, benchmark, model, demo)

1. Go to https://huggingface.co, click **Sign Up**, and verify your email.
2. **Dataset:** click your profile picture, then **New Dataset**. Name it `aether-sop-programs`, set License **cc-by-4.0**, choose **Public**, and click **Create dataset**. Then go to **Files and versions**, click **Add file**, then **Upload files**, and drag in every file from `dist\dataset`. Click **Commit changes to main**.
3. **Benchmark:** do the same with a new dataset named `aether-benchmark`, uploading every file from `dist\benchmark` (including `heldout_traps.jsonl` and `HELDOUT_FROZEN.md`).
4. **Model:** click your profile picture, then **New Model**. Name it `aether-coder-1.5b-lora`, set License **apache-2.0**, choose **Public**, and click **Create model**. Upload every file from `dist\model` (README.md, adapter_config.json, adapter_model.safetensors, which is about 71 MB).
5. **Demo (note, 2026-10-25):** Hugging Face now requires a paid plan for Gradio and Docker Spaces; only Static Spaces are free. Do not subscribe. The steps below are kept for reference. Click your profile picture, then **New Space**. Name it `aether`, set SDK to **Gradio**, Hardware to **CPU basic (free)**, and choose **Public**, then click **Create Space**. First rebuild with your repository URL (`AETHER_GITHUB_REPO=https://github.com/<you>/aether.git uv run python -m release.build`) so the Space installs the checker from GitHub. Then upload the five flat files in `dist\space`: `app.py`, `example.ae`, `requirements.txt`, `README.md`, `LICENSE`. Wait for "Running", then open the **App** tab and click **Check and run**.

## B2. Browser demo on GitHub Pages (free)

The demo at https://warnedorca.github.io/aether/ is a static page (Pyodide) that runs only the checker and interpreter; the model is not hosted. To update it: run `uv run python -m release.build_site`, then commit the contents of `dist/site` to the `gh-pages` branch and push. GitHub Pages serves that branch (Settings, then Pages, then Deploy from a branch: `gh-pages`, `/ (root)`).

## C. After publishing

Give the assistant the GitHub URL and the four Hugging Face URLs, and it will add the links to the README and cards. Record stars, downloads or users in CLAIMS only after they really exist, with the date and a link as proof. Keep claims narrow: the checker blocked every program that broke a rule, and the model alone solves 6/30 held-out traps. Never call the model or the system "safe".
