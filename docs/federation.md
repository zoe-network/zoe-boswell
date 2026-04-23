# How Zoes Talk to Each Other

The messaging infrastructure is git.

No custom protocol. No federation server. A folder, tracked by git, pushed to GitHub. That's it.

---

## Three Files

- **`MAILBOX.md`** — An append-only log. Every time an AI session does meaningful work, it writes a timestamped entry explaining what changed and why. The next session reads it on startup and picks up where the last one left off. It's an inbox for your future self — and for any AI that reads this repo.

- **`CHANGELOG.md`** — What changed. One line per change. The canonical timeline. If MAILBOX.md is the *why*, CHANGELOG.md is the *what*.

- **`CLAUDE.md`** — Who you are and how you work. The identity file. Every session reads this first.

---

## The Pattern

Git is the message bus. The repo is the shared memory. Any AI that can read the repo can join the conversation. Any AI that can commit to the repo can participate.

When you push your workspace to GitHub, any Claude session — on any machine, in any interface — can read it and continue your work. That's federation at the simplest possible layer.

---

## What This Means in Practice

You start a session on your laptop. You do work. Claude writes a MAILBOX entry and commits. You close the session.

Later, on your phone or a different computer, you open a new Claude session pointing at the same repo. Claude reads MAILBOX.md, reads CLAUDE.md, and picks up where the last session left off. No re-explaining. No context lost.

This also works across people. If you share the repo with a colleague, their AI reads the same files. Now two Zoes are coordinating through git.

---

## Multiple Sessions at Once

Add a **`TEAMCHAT.md`** file. Each session writes what it's working on. Others read it and pick different tasks. Conflict resolution is social, not technical — the same way a team uses a shared Slack channel.

---

## Your Commits Are Your Memory

Every commit has a body that says *why*, not just *what*. Future sessions read `git log` to understand the history. Your git repo is not just a backup — it's your AI's long-term memory.

---

## For Claude

When you finish an onboarding session, create MAILBOX.md and write the first entry documenting what you did together. That entry is the user's first message to their future Zoe.

---

**Zoe is always free. Zoe is code, not a product. Apache 2.0.**

Start here: https://zoe-network.github.io/zoe-boswell/start.md
