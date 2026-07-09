# 🍵 matcha-watch

A Telegram bot that notifies you when **Wako** or **Isuzu** matcha from
[Marukyu Koyamaen](https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha)
comes back in stock.

Runs entirely on **GitHub Actions** — no need to keep your own machine or server running.

![status](https://img.shields.io/badge/status-active-brightgreen)
![python](https://img.shields.io/badge/python-3.12-blue)
![runs on](https://img.shields.io/badge/runs%20on-GitHub%20Actions-2088FF)

---

## How it works

```
┌─────────────────────┐      every 2 min       ┌──────────────────────┐
│  GitHub Actions cron │ ─────────────────────▶ │  src/watch.py         │
│  (runs every 2 min,  │                        │  1. Checks if we're  │
│   watch.py filters   │                        │     inside the       │
│   the Mon-Fri         │                        │     Mon-Fri           │
│   9:00-17:30 JST      │                        │     9:00-17:30 JST    │
│   window internally) │                        │     window            │
└─────────────────────┘                        │  2. Downloads each    │
                                                 │     product page      │
                                                 │  3. Looks for the     │
                                                 │     "out of stock"    │
                                                 │     text              │
                                                 │  4. Compares against  │
                                                 │     state/state.json  │
                                                 └──────────┬───────────┘
                                                             │
                                     stock transition, or session
                                          open/close moment?
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │   Telegram Bot API   │
                                                  │   sendMessage()      │
                                                  └─────────────────────┘
```

- **Stock detection:** each product page shows the text *"This product is
  currently out of stock and unavailable."* when it's sold out in every
  size. If that text is **not** present, the product is considered available
  (policy: notify if **any** size/variant is in stock).
- **Anti-spam:** the state (`available` / `out of stock`) of each product is
  stored in [`state/state.json`](state/state.json), which the workflow commits
  back to the repo. A notification only fires on the **transition** from
  out-of-stock to available. While it stays available, you won't get repeat
  alerts. Once it sells out and restocks again, you'll get a new alert.
- **Session open/close messages:** you'll get a Telegram message at the start
  of the checking window (~9:00 AM JST) and another at the end (~5:30 PM JST),
  once per day, so you know the bot is actively watching (and when it stops
  for the day).
- **Time window:** the site only restocks matcha **Monday to Friday,
  9:00 AM–5:30 PM Japan time (JST)**. The check script itself verifies the
  current JST time on every run and skips the stock check (and Telegram
  calls) outside that window, so no minutes are wasted chasing restocks that
  can't happen. JST has no daylight saving time, so this window is fixed
  year-round.

---

## 🚀 Setup (one-time)

### 1. Fork or clone this repository

### 2. Create the repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**
and add:

| Secret               | Value                                                |
|-----------------------|-------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`  | The token from [@BotFather](https://t.me/BotFather)   |
| `TELEGRAM_CHAT_ID`    | Your Telegram chat/bot `chat_id`                       |

> These values are never shown in logs or code — GitHub automatically masks them.

### 3. Enable GitHub Actions

Go to the **Actions** tab of the repository and confirm the workflows are
enabled (on a fork, GitHub pauses them by default — click "I understand my
workflows, go ahead and enable them").

### 4. Test the notification

In the **Actions** tab, select the **"Test Telegram Notification"** workflow
→ **Run workflow**. You should get a confirmation message on Telegram within
seconds. This validates your secrets are set up correctly, without waiting
for the cron or the JST time window.

### 5. Done!

The **"Matcha Stock Check"** workflow is already running automatically every
2 minutes. `watch.py` internally checks whether it's currently Monday-Friday,
9:00 AM-5:30 PM JST, and only performs the stock check (and sends
notifications) inside that window. You can also trigger it manually anytime
from **Actions → Matcha Stock Check → Run workflow** to test it outside
business hours (it will simply log that it's outside the window and exit).

---

## 📁 Repository structure

```
matcha-watch/
├── .github/workflows/
│   ├── check.yml              # Main cron (every 2 min; window logic lives in watch.py)
│   └── test-notification.yml  # Manual trigger to test Telegram
├── src/
│   └── watch.py                # Stock check + session open/close + notification logic
├── state/
│   └── state.json               # Last known state per product + session flags
├── tests/
│   └── test_availability.py    # Unit tests for stock and time-window logic
├── requirements.txt
└── README.md
```

---

## 🛠️ Running locally (optional, for testing)

```bash
git clone <your-fork>
cd matcha-watch
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="123456789"

python src/watch.py
```

Run the tests:

```bash
python tests/test_availability.py
```

---

## ⚠️ Known notes and limitations

- **Site anti-bot measures:** Marukyu Koyamaen has publicly stated it detects
  and blocks third-party bots during restocks. This project makes spaced-out
  requests (every 2 min) with standard browser headers to minimize the risk
  of being blocked, but there's **no absolute guarantee** the site won't
  change its protection (Cloudflare, CAPTCHA, etc.) in the future. If the
  workflow starts failing consistently with a 403 error, check the job logs
  in the Actions tab — you'll likely need to adjust headers or add a proxy.
- **HTML changes:** if Marukyu Koyamaen redesigns its shop and changes the
  exact "out of stock" wording, the detector in `src/watch.py` (the
  `OUT_OF_STOCK_MARKER` constant) will need updating.
- **Restocks are random:** the site itself states there's no fixed restock
  schedule within business hours — it can happen any time during the
  Mon-Fri Japan business window, hence the 2-minute check interval.
- **GitHub Actions minutes:** on public repos, Actions is free and unlimited.
  On private repos, it counts against your monthly free quota (2,000 min/month
  on the Free plan). This cron runs every 2 minutes around the clock, but
  `watch.py` exits almost immediately outside the Mon-Fri 9:00-17:30 JST
  window, so actual billed minutes stay low.

---

## 📄 License

MIT — use it, modify it, and share it freely.
