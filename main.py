# -*- coding: utf-8 -*-
# Bot Locket Gold Auto – Bản FIX chạy Replit không cần tải Chromium
# © Tạ Ngọc Long

import asyncio, time, re, requests, shutil
from pathlib import Path
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

from playwright.async_api import async_playwright

# ========== CẤU HÌNH ==========
BOT_TOKEN = "8386047962:AAGgg8Rh5tbUV3kfxdeqhORCWLnW-eWbo6M"
BASE = "https://chungchi365.com"
LOGIN_URL = f"{BASE}/client/login"
LOCKET_URL = f"{BASE}/client/locket"
SAVE_DIR = Path("downloads")
SAVE_DIR.mkdir(exist_ok=True)
LOG_FILE = Path("frewhafa.txt")
# ==============================

# Conversation states
ASK_CONFIRM, ASK_ACCOUNT, ASK_PASSWORD = range(3)

# ---------- Hàm Playwright ----------
async def run_playwright_login_and_download(username: str, password: str, save_path: Path):
    try:
        chromium_path = "/usr/bin/chromium-browser"
        if not Path(chromium_path).exists():
            # fallback nếu chromium không có thì báo lỗi dễ hiểu
            raise FileNotFoundError("Chromium system không tồn tại trên Replit!")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                executable_path=chromium_path,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(LOGIN_URL, timeout=60000)
            try:
                await page.fill('input[name="username"]', username)
            except:
                try:
                    await page.fill('input[name="email"]', username)
                except:
                    pass
            try:
                await page.fill('input[name="password"]', password)
            except:
                el = await page.query_selector("input[type='password']")
                if el:
                    await el.fill(password)
            try:
                await page.click('button[type="submit"]')
            except:
                form = await page.query_selector("form")
                if form:
                    await form.evaluate("(f)=>f.submit()")
            await page.wait_for_timeout(2000)

            await page.goto(LOCKET_URL)
            await page.wait_for_timeout(1000)

            # Click tham gia hàng chờ
            for el in await page.query_selector_all("button,a"):
                try:
                    txt = (await el.inner_text()).lower()
                    if "tham gia" in txt or "nâng cấp" in txt:
                        await el.click()
                        break
                except:
                    pass

            # Chờ link file
            for i in range(12):
                await page.goto(LOCKET_URL)
                html = await page.content()
                match = re.search(r'https?://[^\s"\'<>]+\.mobileconfig', html)
                if match:
                    link = match.group(0)
                    cookies = await context.cookies()
                    s = requests.Session()
                    for c in cookies:
                        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
                    r = s.get(link, timeout=60)
                    r.raise_for_status()
                    with open(save_path, "wb") as f:
                        f.write(r.content)
                    await browser.close()
                    return True, str(save_path)
                await asyncio.sleep(5)

            await browser.close()
            return False, "Không tìm thấy link .mobileconfig sau khi chờ."
    except Exception as e:
        return False, f"Lỗi Playwright: {e}"

# ---------- Telegram Flow ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Có ✅", callback_data="yes"),
           InlineKeyboardButton("Không ❌", callback_data="no")]]
    await update.message.reply_text(
        "Bạn muốn lên Locket Gold đúng không?", reply_markup=InlineKeyboardMarkup(kb))
    return ASK_CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "no":
        await q.edit_message_text("Đã hủy. Gõ /start nếu muốn lại.")
        return ConversationHandler.END
    await q.edit_message_text("Nhập tài khoản Locket của bạn:")
    return ASK_ACCOUNT

async def get_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account"] = update.message.text.strip()
    await update.message.reply_text("Nhập mật khẩu Locket:")
    return ASK_PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    acc = context.user_data.get("account")
    chat_id = update.effective_chat.id
    save_path = SAVE_DIR / f"locket_{chat_id}.mobileconfig"
    await update.message.reply_text("Đang xử lý, vui lòng đợi 30–60s...")

    ok, msg = await run_playwright_login_and_download(acc, pwd, save_path)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {acc} | {chat_id} | {msg}\n")

    if ok:
        await update.message.reply_document(document=open(msg, "rb"),
                                            filename=Path(msg).name,
                                            caption="✅ Đã tải hồ sơ thành công!")
    else:
        await update.message.reply_text(f"❌ Lỗi: {msg}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Đã hủy thao tác.")
    return ConversationHandler.END

# ---------- Chạy Bot ----------
def main():
    while True:
        try:
            print("🚀 Đang khởi động bot...")
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            conv = ConversationHandler(
                entry_points=[CommandHandler("start", start)],
                states={
                    ASK_CONFIRM: [CallbackQueryHandler(confirm)],
                    ASK_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account)],
                    ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
                },
                fallbacks=[CommandHandler("cancel", cancel)],
            )
            app.add_handler(conv)
            app.run_polling(timeout=60, poll_interval=3)
        except Exception as e:
            print("⚠️ Lỗi:", e)
            time.sleep(10)

if __name__ == "__main__":
    open("frewhafa.txt", "a").close()
    main()
