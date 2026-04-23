import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database.db import Database
from handlers.admin import admin_router
from handlers.user import user_router
from utils.scheduler import restore_scheduler_jobs


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    db = Database(config.database_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    scheduler = AsyncIOScheduler()
    scheduler.start()
    await restore_scheduler_jobs(scheduler=scheduler, bot=bot, db=db)

    dp.include_router(user_router(db=db, config=config, scheduler=scheduler))
    dp.include_router(admin_router(db=db, config=config, scheduler=scheduler))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
