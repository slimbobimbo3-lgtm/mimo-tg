import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from backend.config import BOT_TOKEN

log = logging.getLogger("mimo-tg.bot")


async def cmd_start(message: Message):
    import main as m
    url = "http://localhost:8765"
    try:
        from backend.tunnel import get_url
        url = get_url() or url
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть MiMo App", web_app=WebAppInfo(url=url))]
    ])
    await message.answer(
        "<b>MiMo Code</b> — Remote Assistant\n\nНажмите кнопку чтобы открыть Mini App.",
        reply_markup=kb, parse_mode="HTML"
    )


async def start_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, F.text == "/start")
    asyncio.create_task(dp.start_polling(bot))
    log.info("Polling started")
    await asyncio.Event().wait()


async def stop_bot():
    pass
