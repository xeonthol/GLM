"""
helpers.py — Semua helper functions
"""
import os, json, time, random, logging
from datetime import datetime
from config import *

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def get_logger(account_id: int):
    name = f"acc{account_id}"
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(f"[%(asctime)s] [ACC#{account_id}] %(message)s", "%H:%M:%S")
    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # File
    fh = logging.FileHandler(os.path.join(LOG_DIR, f"acc{account_id}_{datetime.now().strftime('%Y%m%d')}.log"))
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ══════════════════════════════════════════════════════════════
# ACCOUNTS
# ══════════════════════════════════════════════════════════════
def load_account(account_id: int) -> dict:
    with open(ACCOUNTS_FILE) as f:
        accounts = json.load(f)["accounts"]
    acc = next((a for a in accounts if a["id"] == account_id), None)
    if not acc:
        raise ValueError(f"Account #{account_id} tidak ditemukan di {ACCOUNTS_FILE}")
    return acc


# ══════════════════════════════════════════════════════════════
# TAG HANDLES
# ══════════════════════════════════════════════════════════════
def load_used_handles() -> list:
    try:
        with open(USED_HANDLES_FILE) as f:
            return json.load(f).get("used", [])
    except FileNotFoundError:
        return []

def save_used_handles(handles: list):
    os.makedirs(os.path.dirname(USED_HANDLES_FILE), exist_ok=True)
    with open(USED_HANDLES_FILE, "w") as f:
        json.dump({"used": handles}, f, indent=2)

def pick_handles(count=3) -> list:
    with open(TAG_HANDLES_FILE) as f:
        data = json.load(f)
    all_handles = data.get("handles", [])
    all_handles = [h.lstrip("@") for h in all_handles]
    used = load_used_handles()
    available = [h for h in all_handles if h not in used]
    if len(available) < count:
        save_used_handles([])
        available = all_handles
    return random.sample(available, count)

def mark_handles_used(handles: list):
    used = load_used_handles()
    for h in handles:
        h = h.lstrip("@")
        if h not in used:
            used.append(h)
    save_used_handles(used)


# ══════════════════════════════════════════════════════════════
# BROWSER
# ══════════════════════════════════════════════════════════════
def launch_browser(account: dict):
    from cloakbrowser import launch_persistent_context

    profile_dir = os.path.join(PROFILES_DIR, f"account-{account['id']}")
    os.makedirs(profile_dir, exist_ok=True)

    fp_platforms = ["windows","mac","linux","windows","mac","windows","linux","windows","mac","linux"]
    fp_plat = fp_platforms[(account["id"] - 1) % len(fp_platforms)]

    opts = {
        "userDataDir": profile_dir,
        "headless": False,
        "args": [
            f"--fingerprint={10000 + account['id']}",
            f"--fingerprint-platform={fp_plat}",
            "--disable-popup-blocking",
        ],
    }

    proxy = account.get("proxy", "")
    if proxy:
        opts["proxy"] = {"server": proxy}

    return launch_persistent_context(**opts)


def inject_x_cookies(ctx, account: dict) -> bool:
    cookies = account.get("cookies", {})
    if not isinstance(cookies, dict) or "auth_token" not in cookies:
        return False
    for domain in [".x.com", ".twitter.com"]:
        ctx.add_cookies([
            {"name": "auth_token", "value": cookies["auth_token"], "domain": domain, "path": "/"},
            {"name": "ct0",        "value": cookies.get("ct0",""), "domain": domain, "path": "/"},
        ])
    return True


# ══════════════════════════════════════════════════════════════
# OAUTH POPUP
# ══════════════════════════════════════════════════════════════
def handle_oauth_popup(popup, logger, label="OAuth") -> bool:
    logger.info(f"[{label}] Popup: {popup.url[:80]}")
    try:
        popup.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception as e:
        logger.warning(f"[{label}] load state warning: {e}")
    time.sleep(3)

    # Dismiss cookie banner
    try:
        popup.evaluate('''() => {
            const b = Array.from(document.querySelectorAll("button"))
                .find(b => /accept all|accept cookies/i.test(b.textContent));
            if (b) b.click();
        }''')
        time.sleep(1)
    except: pass

    # Cara 1: data-testid
    try:
        popup.wait_for_selector('[data-testid="OAuth_Consent_Button"]', timeout=8000)
        popup.click('[data-testid="OAuth_Consent_Button"]')
        logger.info(f"[{label}] ✅ Authorized via data-testid!")
        time.sleep(WAIT_OAUTH)
        return True
    except: pass

    # Cara 2: koordinat
    btn = popup.evaluate('''() => {
        for (const b of document.querySelectorAll("button")) {
            if (/^(Authorize app|Allow)$/.test(b.textContent.trim())) {
                const r = b.getBoundingClientRect();
                if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
        }
        return null;
    }''')
    if btn:
        popup.mouse.click(btn["x"], btn["y"])
        logger.info(f"[{label}] ✅ Authorized via coords!")
        time.sleep(WAIT_OAUTH)
        return True

    btns = popup.evaluate('() => Array.from(document.querySelectorAll("button")).map(b => b.textContent.trim())')
    logger.error(f"[{label}] ❌ Gagal authorize. Buttons: {btns}")
    return False


# ══════════════════════════════════════════════════════════════
# ANGULAR / GLEAM HELPERS
# ══════════════════════════════════════════════════════════════
def force_continue_enabled(page):
    page.evaluate('''() => {
        document.querySelectorAll('[ng-click*="enterLinkClick"]').forEach(el => {
            try {
                const s = angular.element(el).scope();
                if (!s) return;
                s.hasVisited       = () => true;
                s.continueDisabled = () => false;
                const em = s.entry_method;
                if (em?.config) {
                    em.config.continueDisabled = () => false;
                    em.config.canSubmitForm    = () => true;
                    em.config.isTimerTriggered = true;
                    em.config.remainingSeconds = 0;
                }
                s.$apply();
            } catch(e) {}
        });
    }''')
    time.sleep(1)


def click_continue(page, logger) -> bool:
    force_continue_enabled(page)

    btn = page.evaluate('''() => {
        for (const b of document.querySelectorAll("a, button")) {
            if (b.textContent.trim() === "Continue") {
                const r = b.getBoundingClientRect();
                if (r.width > 0 && r.height > 0)
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
        }
        return null;
    }''')

    if not btn:
        logger.error("Continue button tidak ketemu")
        return False

    # Klik + tunggu PATCH request Gleam
    try:
        with page.expect_response(
            lambda r: "gleam.io" in r.url and r.request.method in ("PATCH", "POST"),
            timeout=PATCH_TIMEOUT_MS
        ) as resp_info:
            page.mouse.click(btn["x"], btn["y"])

        resp = resp_info.value
        logger.info(f"  PATCH {resp.status} — {resp.url[:60]}")

        if resp.status in (200, 201, 204):
            logger.info("  ✅ Continue + PATCH OK!")
            time.sleep(WAIT_AFTER_TASK)
            return True
        else:
            logger.warning(f"  ⚠️ PATCH returned {resp.status}")
            return False

    except Exception as e:
        # Fallback: klik biasa tanpa tunggu PATCH
        logger.warning(f"  expect_response timeout: {e} — klik biasa")
        page.mouse.click(btn["x"], btn["y"])
        time.sleep(WAIT_AFTER_TASK)
        return True


def is_task_done(page, idx: int) -> bool:
    return page.evaluate(f'''() => {{
        const v = Array.from(document.querySelectorAll('[ng-click*="enterLinkClick"]'))
            .filter(e => e.getBoundingClientRect().width > 0);
        return v[{idx}] ? !!v[{idx}].querySelector('.fa-check, .icon-check, [class*="check"]') : true;
    }}''')


def get_entry_count(page) -> str:
    return page.evaluate(
        r'() => document.body.innerText.match(/Your Entries[^\d]*(\d+)/)?.[1] || "?"'
    )


def get_task_summary(page) -> list:
    return page.evaluate('''() =>
        Array.from(document.querySelectorAll('[ng-click*="enterLinkClick"]'))
            .filter(e => e.getBoundingClientRect().width > 0)
            .map(e => ({
                text: e.textContent.trim().replace(/\s+/g," ").substring(0,60),
                done: !!e.querySelector('.fa-check, .icon-check, [class*="check"]')
            }))
    ''')
