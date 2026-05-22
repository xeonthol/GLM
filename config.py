"""
config.py — Semua konstanta & settings di sini
"""
import os

# ── GLEAM ────────────────────────────────────────────────────
GLEAM_URL = "https://gleam.io/06Jma/kucoin-x-mezo-mezo"

# ── TWEET ────────────────────────────────────────────────────
QUOTE_TWEET_URL  = "https://x.com/kucoincom/status/GANTI_INI"
TWEET_TEMPLATE   = "Trade $MEZO on #KuCoin! {tag1} {tag2} {tag3}"

# ── PATHS ────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR      = os.path.expanduser("~/.cloakbrowser-profiles")
ACCOUNTS_FILE     = os.path.join(BASE_DIR, "data/accounts.json")
TAG_HANDLES_FILE  = os.path.join(BASE_DIR, "data/tag-handles.json")
USED_HANDLES_FILE = os.path.join(BASE_DIR, "data/used-handles.json")
SCREENSHOT_DIR    = os.path.join(BASE_DIR, "screenshots")
LOG_DIR           = os.path.join(BASE_DIR, "logs")

# ── TIMING (detik) ───────────────────────────────────────────
WAIT_PAGE_LOAD    = 5
WAIT_OAUTH        = 8
WAIT_AFTER_CLICK  = 3
WAIT_AFTER_TASK   = 5
POPUP_TIMEOUT_MS  = 15000
PATCH_TIMEOUT_MS  = 15000
