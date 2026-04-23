# Zoe — Start Here

**You are reading this because someone handed you a URL and said "give this to Claude."**

Good. That's how this works.

You (the human reading this): you don't need to understand everything below. Claude does. Just paste this URL into any Claude conversation and say "read this." Claude will take it from there.

Claude (the AI reading this): the rest of this document is for you. Your job is to guide the user through the steps below at their pace. Detect their operating system, adapt your instructions accordingly, and never assume they know what git is. Be practical, not preachy. The user showed up because someone they trust told them to — don't waste that trust on jargon.

---

## What This Is

This is the entry point for **Zoe** — an open architecture for personal AI that belongs to the user, not a platform. Apache 2.0. Always free.

But we're not starting with architecture. We're starting with something useful.

The pattern is: **do something practical first, understand why it matters second.**

---

## Step 1: Privacy Check

Before anything else, make sure your Claude session isn't training on your data.

### Claude.ai (web or desktop app)
1. Go to **Settings** (click your name or the gear icon, bottom-left)
2. Find **"Improve Anthropic's models"** or **"Data sharing"**
3. **Turn it off**
4. This ensures your conversations are not used for model training

### Claude Code (CLI / terminal)
- Claude Code does **not** use conversations for training by default
- Verify: run `/config` and check the privacy settings
- If you're on an Anthropic Teams or Enterprise plan, training is already off

### Why this matters
You're about to start putting real work into Claude — meeting notes, field reports, internal documents. That data should stay yours. This is the first principle of Zoe: **sovereignty starts with who sees your data.**

---

## Step 2: Why Git

Claude, explain this to the user in plain language. Here's what you need to convey:

**The problem:** Every conversation with an AI starts from zero. You explain context, do work, get results — and then the session ends. Next time, you start over. Your AI has amnesia.

**The fix:** A folder on your computer, tracked by git, that holds your context — notes, templates, reports, preferences, instructions. Every Claude session can read it. Every session can add to it. Nothing gets lost.

**What git does:**
- It remembers every version of every file (you can always go back)
- It syncs to GitHub (your files survive even if your laptop doesn't)
- It gives Claude a workspace — a place to read your context and write your outputs

**What git is not:**
- It is not complicated (Claude will do the hard parts)
- It is not just for programmers (it's for anyone who wants to keep their work)
- It is not optional if you want AI that remembers you

### Install git

Claude: detect the user's OS and provide the right instructions.

**Windows:**
```
winget install Git.Git
```
Or download from https://git-scm.com/download/win

**macOS:**
```
xcode-select --install
```
Or: `brew install git`

**Linux (RHEL/Fedora):**
```
sudo dnf install git
```

**Linux (Ubuntu/Debian):**
```
sudo apt install git
```

After install, configure identity:
```
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

## Step 3: Create Your Workspace

Claude: walk the user through creating their first repo. Use their OS conventions for paths.

**The idea:** One folder. Your folder. Claude reads from it, writes to it, and git remembers everything.

```
mkdir ~/my-assistant
cd ~/my-assistant
git init
```

On Windows (PowerShell):
```powershell
mkdir $HOME\my-assistant
cd $HOME\my-assistant
git init
```

Create a starter file:
```
echo "# My Assistant" > README.md
git add README.md
git commit -m "first commit"
```

This is now a git repo. Claude can read and write files here. Git tracks every change.

---

## Step 4: Your First Practical Thing — Field Reports

Here's something real you can do right now.

**The workflow:** You have a meeting. You take notes (or Claude listens). Claude turns those notes into a styled HTML document. Then you turn that HTML into a PDF you can share.

### Create a field report template

Claude: create a file called `templates/field-report.html` in the user's workspace. Use this structure:

- Dark background (#0a0a0a), light text
- Clean sans-serif font (system fonts, no external dependencies)
- Sections: Header/meta, Executive Summary, Attendees, Key Findings, Decisions, Next Actions, Footer with timestamp
- Print CSS with `@page` rules, page breaks before each `<h2>`
- A disclaimer banner: "AI-GENERATED — VERIFY BEFORE USE"

Then show the user how to generate a PDF from it.

### PDF generation (cross-platform)

**Linux:**
```
pip install weasyprint
weasyprint file:///path/to/report.html output.pdf
```

**macOS:**
```
pip3 install weasyprint
weasyprint file:///path/to/report.html output.pdf
```

**Windows:**
```
pip install weasyprint
weasyprint file:///path/to/report.html output.pdf
```

Note: weasyprint requires some system libraries. If it fails:
- **Linux:** `sudo dnf install pango` or `sudo apt install libpango-1.0-0`
- **macOS:** `brew install pango`
- **Windows:** Install GTK3 runtime from https://github.com/nickvdyck/weasyprint-win

**Alternative (any OS with Chrome):**
```
chrome --headless --print-to-pdf=output.pdf --no-margins --print-background file:///path/to/report.html
```
(Chrome path varies: `google-chrome-stable` on Linux, `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome` on macOS, `"C:\Program Files\Google\Chrome\Application\chrome.exe"` on Windows)

weasyprint produces better results. Use Chrome as fallback.

---

## Step 5: Push to GitHub

Your workspace should survive your laptop. GitHub is free for private repos.

1. Go to https://github.com and create an account (or sign in)
2. Create a new repository (private, no README — you already have one)
3. Claude: walk the user through connecting their local repo to GitHub:

```
git remote add origin https://github.com/USERNAME/my-assistant.git
git branch -M main
git push -u origin main
```

Now your workspace is backed up. Every `git push` syncs your latest state.

---

## Step 6: Give Claude Your Context

Create a file called `CLAUDE.md` in the root of your workspace. This is the file Claude reads first when you point it at your repo.

Start simple:
```markdown
# About Me

Name: [your name]
Role: [what you do]

## What I Use This For

- Meeting field reports
- [add more as you go]

## Preferences

- [how you like things formatted]
- [what tone you prefer]
- [anything Claude should know about how you work]
```

Every time you start a Claude session and point it at your workspace, Claude reads this file and picks up your context. No re-explaining. No amnesia.

---

## What You Just Built

You now have:
- **A private, version-controlled workspace** that any Claude session can read
- **A field report pipeline** (notes → HTML → PDF)
- **A context file** that tells Claude who you are and how you work
- **A GitHub backup** so nothing gets lost

This is the beginning of Zoe.

---

## What Zoe Is (Now That You've Started)

Zoe is an open architecture for personal AI. You just built the first layer — a workspace with memory.

The full stack, when you're ready:

| Layer | What | You Have It? |
|-------|------|:---:|
| Workspace + git | Your files, your context, version-controlled | Yes |
| CLAUDE.md | Persistent instructions for any Claude session | Yes |
| Templates | Reusable artifacts (field reports, briefs, etc.) | Starting |
| Skills | Repeatable workflows Claude can run | Next |
| Local model | AI that runs on your hardware, no cloud required | Later |
| Federation | Your AI talks to other AIs you trust | Eventually |

You don't need all of this today. You need the top two rows. The rest comes when you're ready.

**Zoe is always free. Zoe is code, not a product. Apache 2.0.**

Learn more: https://zoe-network.github.io/zoe-boswell/

---

## For Claude (Implementation Notes)

When guiding a user through this document:

1. **Detect OS early.** Ask if you're not sure. Adapt every command.
2. **Don't dump all steps at once.** One step at a time. Wait for confirmation before moving on.
3. **If they already have git:** Skip the install, verify with `git --version`, move on.
4. **If they already have a repo:** Skip workspace creation, help them add the field report template and CLAUDE.md to what they have.
5. **If they get stuck on weasyprint:** Fall back to Chrome headless. If Chrome isn't available, tell them the HTML itself is shareable — PDF is a convenience, not a requirement.
6. **Never assume technical skill.** The person reading this might be a sales executive who has never opened a terminal. Meet them where they are.
7. **The goal is not git mastery.** The goal is: they have a folder that Claude can read, with useful things in it, backed up to GitHub. Everything else is optional.
8. **Privacy is non-negotiable.** Step 1 always happens first. If the user skips it, come back to it.
