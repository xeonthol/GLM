#!/usr/bin/env python3
"""
run.py — Gleam Bot main runner
Usage: python run.py <account_id>
"""
import sys, os, time, subprocess
from helpers import *
from config  import *


# ══════════════════════════════════════════════════════════════
# TASK: LOGIN via X OAuth
# ══════════════════════════════════════════════════════════════
def task_login(page, ctx, logger) -> bool:
    logger.info("🔐 LOGIN via X OAuth...")

    page.goto(GLEAM_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(WAIT_PAGE_LOAD)

    # Cek sudah login
    logged = page.evaluate(r'''() => {
        const t = document.body?.innerText || "";
        return /Entering as \w+/.test(t);
    }''')
    if logged:
        handle = page.evaluate(r'() => (document.body.innerText.match(/Entering as (\w+)/) || [])[1] || "?"')
        logger.info(f"✅ Sudah login sebagai @{handle}")
        return True

    # Klik login with X
    clicked = page.evaluate('''() => {
        for (const b of document.querySelectorAll("a, button, [ng-click]")) {
            const t = b.textContent.replace(/\s+/g," ").trim().toLowerCase();
            const href = b.getAttribute("href") || "";
            const nc   = b.getAttribute("ng-click") || "";
            if (t.includes("login with x") || /twitter|x\.com/.test(href) || /twitter/i.test(nc)) {
                const r = b.getBoundingClientRect();
                if (r.width > 0) { b.click(); return true; }
            }
        }
        return false;
    }''')

    if not clicked:
        logger.error("Login button tidak ketemu!")
        page.screenshot(path=f"{SCREENSHOT_DIR}/login_fail.png")
        return False

    # Tunggu OAuth popup
    logger.info("Menunggu OAuth popup...")
    popup = None
    for i in range(20):
        time.sleep(1)
        for p in ctx.pages:
            if p != page and any(k in p.url for k in ["oauth2/authorize","x.com/i/oauth","twitter.com/oauth"]):
                popup = p
                logger.info(f"Popup ditemukan ({i+1}s)")
                break
        if popup: break

    if not popup:
        logger.error("OAuth popup tidak muncul!")
        page.screenshot(path=f"{SCREENSHOT_DIR}/nopopup.png")
        return False

    handle_oauth_popup(popup, logger, "Login")
    time.sleep(5)

    # Verifikasi
    ok = page.evaluate(r'() => /Entering as \w+/.test(document.body?.innerText || "")')
    if ok:
        handle = page.evaluate(r'() => (document.body.innerText.match(/Entering as (\w+)/) || [])[1] || "?"')
        logger.info(f"✅ Login berhasil sebagai @{handle}")
        return True

    logger.error("Login gagal setelah OAuth")
    page.screenshot(path=f"{SCREENSHOT_DIR}/login_fail2.png")
    return False


# ══════════════════════════════════════════════════════════════
# TASK: FOLLOW @username
# ══════════════════════════════════════════════════════════════
def task_follow(page, ctx, logger, idx: int, username: str) -> bool:
    logger.info(f"🐦 FOLLOW @{username} (idx={idx})...")

    if is_task_done(page, idx):
        logger.info("  ✅ Sudah selesai, skip")
        return True

    popup = None

    # expect_popup SEBELUM klik
    try:
        with page.expect_popup(timeout=POPUP_TIMEOUT_MS) as popup_info:
            page.evaluate(f'''() => {{
                const v = Array.from(document.querySelectorAll('[ng-click*="enterLinkClick"]'))
                    .filter(e => e.getBoundingClientRect().width > 0);
                if (v[{idx}]) v[{idx}].click();
            }}''')
        popup = popup_info.value
        logger.info(f"  Popup: {popup.url[:70]}")
    except Exception as e:
        logger.warning(f"  expect_popup miss: {e} — polling...")

    # Fallback: poll tabs
    if not popup:
        for i in range(15):
            time.sleep(1)
            for p in ctx.pages:
                if p != page and any(k in p.url for k in [
                    "oauth2/authorize","x.com/i/oauth","intent/follow","x.com/i/follow"
                ]):
                    popup = p
                    logger.info(f"  Tab ditemukan via poll ({i+1}s)")
                    break
            if popup: break

    if popup:
        if any(k in popup.url for k in ["oauth2/authorize","x.com/i/oauth"]):
            handle_oauth_popup(popup, logger, f"Follow/{username}")
        elif "intent/follow" in popup.url or username.lower() in popup.url.lower():
            logger.info("  Follow intent page, klik Follow...")
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(2)
                popup.evaluate('() => { const b = document.querySelector(\'[data-testid="follow"]\'); if(b) b.click(); }')
                time.sleep(3)
            except Exception as e:
                logger.warning(f"  Follow intent error: {e}")
            finally:
                try: popup.close()
                except: pass
        else:
            logger.warning(f"  Unknown popup: {popup.url}")
    else:
        logger.warning("  Tidak ada popup — mungkin sudah follow")

    result = click_continue(page, logger)
    done   = is_task_done(page, idx)
    logger.info(f"  {'✅ Done' if done else '⬜ Belum done'}")
    return done


# ══════════════════════════════════════════════════════════════
# TASK: QUOTE TWEET
# ══════════════════════════════════════════════════════════════
def task_quote_tweet(page, ctx, logger) -> str:
    logger.info("💬 QUOTE TWEET...")

    handles    = pick_handles(3)
    tags       = [f"@{h}" for h in handles]
    tweet_text = TWEET_TEMPLATE.format(tag1=tags[0], tag2=tags[1], tag3=tags[2])
    logger.info(f"  Text: {tweet_text}")
    logger.info(f"  Quote: {QUOTE_TWEET_URL}")

    text_enc   = tweet_text.replace(" ", "%20").replace("#", "%23").replace("@", "%40")
    compose_url = f"https://x.com/intent/tweet?text={text_enc}&url={QUOTE_TWEET_URL}"

    tweet_page = ctx.new_page()
    tweet_page.goto(compose_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    # Dismiss cookie banner
    tweet_page.evaluate('''() => {
        const b = Array.from(document.querySelectorAll("button"))
            .find(b => /accept all/i.test(b.textContent));
        if (b) b.click();
    }''')
    time.sleep(1)

    tweet_url = "?"
    try:
        tweet_page.wait_for_selector(
            '[data-testid="tweetButton"], [data-testid="tweetButtonInline"]',
            timeout=10000
        )
        tweet_page.click('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]')
        time.sleep(5)
        logger.info("  ✅ Tweet posted!")

        # Ambil URL tweet dari timeline
        tweet_page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        tweet_url = tweet_page.evaluate('''() => {
            for (const a of document.querySelectorAll('a[href*="/status/"]')) {
                if (a.href.includes("/status/")) return a.href;
            }
            return null;
        }''') or "?"
        logger.info(f"  Tweet URL: {tweet_url}")
    except Exception as e:
        logger.error(f"  Tweet gagal: {e}")
        tweet_page.screenshot(path=f"{SCREENSHOT_DIR}/tweet_fail.png")

    tweet_page.close()
    mark_handles_used(handles)
    return tweet_url


# ══════════════════════════════════════════════════════════════
# TASK: SUBMIT REPOST LINK
# ══════════════════════════════════════════════════════════════
def task_submit_repost(page, logger, idx: int, repost_url: str) -> bool:
    logger.info(f"📎 SUBMIT REPOST LINK (idx={idx})...")

    if is_task_done(page, idx):
        logger.info("  ✅ Sudah selesai, skip")
        return True

    # Expand task
    page.evaluate(f'''() => {{
        const v = Array.from(document.querySelectorAll('[ng-click*="enterLinkClick"]'))
            .filter(e => e.getBoundingClientRect().width > 0);
        if (v[{idx}]) v[{idx}].click();
    }}''')
    time.sleep(2)

    # Isi input
    filled = page.evaluate(f'''(url) => {{
        const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="url"], textarea'))
            .filter(e => e.getBoundingClientRect().width > 0);
        for (const inp of inputs) {{
            inp.focus();
            inp.value = url;
            inp.dispatchEvent(new Event("input",  {{bubbles:true}}));
            inp.dispatchEvent(new Event("change", {{bubbles:true}}));
            return true;
        }}
        return false;
    }}''', repost_url)

    if not filled:
        logger.error("  Input field tidak ketemu")
        return False

    logger.info(f"  URL: {repost_url}")
    time.sleep(1)
    click_continue(page, logger)

    done = is_task_done(page, idx)
    logger.info(f"  {'✅ Done' if done else '⬜ Belum done'}")
    return done


# ══════════════════════════════════════════════════════════════
# TASK: SUBMIT KUCOIN UID
# ══════════════════════════════════════════════════════════════
def task_submit_uid(page, logger, account: dict, idx: int) -> bool:
    logger.info(f"🔑 SUBMIT KUCOIN UID (idx={idx})...")

    if is_task_done(page, idx):
        logger.info("  ✅ Sudah selesai, skip")
        return True

    uid = account.get("kucoin_uid", "")
    if not uid:
        logger.error("  kucoin_uid tidak ada di accounts.json!")
        return False

    # Expand task
    page.evaluate(f'''() => {{
        const v = Array.from(document.querySelectorAll('[ng-click*="enterLinkClick"]'))
            .filter(e => e.getBoundingClientRect().width > 0);
        if (v[{idx}]) v[{idx}].click();
    }}''')
    time.sleep(2)

    # Isi input
    filled = page.evaluate(f'''(uid) => {{
        const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], textarea'))
            .filter(e => e.getBoundingClientRect().width > 0);
        for (const inp of inputs) {{
            inp.focus();
            inp.value = uid;
            inp.dispatchEvent(new Event("input",  {{bubbles:true}}));
            inp.dispatchEvent(new Event("change", {{bubbles:true}}));
            return true;
        }}
        return false;
    }}''', str(uid))

    if not filled:
        logger.error("  Input field tidak ketemu")
        return False

    logger.info(f"  UID: {uid}")
    time.sleep(1)
    click_continue(page, logger)

    done = is_task_done(page, idx)
    logger.info(f"  {'✅ Done' if done else '⬜ Belum done'}")
    return done


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <account_id>")
        sys.exit(1)

    account_id = int(sys.argv[1])
    logger     = get_logger(account_id)
    logger.info(f"🚀 Gleam Bot start — ACC#{account_id}")
    logger.info(f"   URL: {GLEAM_URL}")

    # Kill stale chrome
    subprocess.run("pkill -f 'chrome.*account-' 2>/dev/null", shell=True)
    time.sleep(1)

    acc = load_account(account_id)
    logger.info(f"   Handle: @{acc.get('handle','?')}")

    ctx  = launch_browser(acc)
    inject_x_cookies(ctx, acc)
    page = ctx.new_page()

    try:
        # 1. Login
        if not task_login(page, ctx, logger):
            logger.error("❌ Login gagal, abort!")
            return

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # 2. Follow @kucoincom
        task_follow(page, ctx, logger, idx=0, username="kucoincom")
        time.sleep(2)

        # 3. Follow @MezoNetwork
        task_follow(page, ctx, logger, idx=1, username="MezoNetwork")
        time.sleep(2)

        # 4. Quote tweet
        repost_url = task_quote_tweet(page, ctx, logger)
        time.sleep(2)

        # Reload Gleam setelah buka Twitter
        page.goto(GLEAM_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(WAIT_PAGE_LOAD)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # 5. Submit repost link
        task_submit_repost(page, logger, idx=2, repost_url=repost_url)
        time.sleep(2)

        # 6. Submit KuCoin UID
        task_submit_uid(page, logger, acc, idx=3)
        time.sleep(2)

        # Summary
        entries = get_entry_count(page)
        tasks   = get_task_summary(page)
        logger.info("=" * 50)
        logger.info(f"📊 Total Entries: {entries}")
        for t in tasks:
            logger.info(f"   {'✅' if t['done'] else '⬜'} {t['text'][:60]}")
        logger.info("🎉 SELESAI!")

        page.screenshot(path=f"{SCREENSHOT_DIR}/acc{account_id}_done.png")

    except Exception as e:
        logger.error(f"💥 Error: {e}")
        import traceback; traceback.print_exc()
        page.screenshot(path=f"{SCREENSHOT_DIR}/acc{account_id}_error.png")

    finally:
        time.sleep(3)
        ctx.close()


if __name__ == "__main__":
    main()
