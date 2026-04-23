from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.db import Database


def get_reminder_datetime(day: str, time_value: str) -> datetime:
    appointment_dt = datetime.strptime(f"{day} {time_value}", "%Y-%m-%d %H:%M")
    return appointment_dt - timedelta(hours=24)


async def send_reminder(bot: Bot, user_id: int, time_value: str) -> None:
    await bot.send_message(
        user_id,
        (
            f"<b>Напоминание</b>\n\n"
            f"Напоминаем, что вы записаны на наращивание ресниц завтра в <b>{time_value}</b>.\n"
            "Ждём вас ❤️"
        ),
        parse_mode="HTML",
    )


def schedule_booking_reminder(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    booking_id: int,
    user_id: int,
    day: str,
    time_value: str,
) -> str | None:
    run_dt = get_reminder_datetime(day, time_value)
    if run_dt <= datetime.now():
        return None

    job_id = f"reminder_{booking_id}"
    scheduler.add_job(
        send_reminder,
        "date",
        run_date=run_dt,
        id=job_id,
        replace_existing=True,
        kwargs={"bot": bot, "user_id": user_id, "time_value": time_value},
    )
    return job_id


def remove_reminder_job(scheduler: AsyncIOScheduler, job_id: str | None) -> None:
    if not job_id:
        return
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)


async def restore_scheduler_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    db: Database,
) -> None:
    bookings = await db.get_bookings_for_restore()
    for booking_id, user_id, day, time_value in bookings:
        new_job_id = schedule_booking_reminder(
            scheduler=scheduler,
            bot=bot,
            booking_id=booking_id,
            user_id=user_id,
            day=day,
            time_value=time_value,
        )
        await db.set_booking_reminder_job(booking_id, new_job_id)
