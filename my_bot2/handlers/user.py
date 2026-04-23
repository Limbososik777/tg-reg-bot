from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.db import Database
from keyboards.inline import (
    confirm_booking_kb,
    days_calendar_kb,
    main_menu_kb,
    portfolio_kb,
    slots_kb,
    subscription_check_kb,
)
from states.booking import BookingStates
from utils.scheduler import remove_reminder_job, schedule_booking_reminder
from utils.subscription import is_user_subscribed

router = Router()


def user_router(db: Database, config: Config, scheduler: AsyncIOScheduler):
    @router.message(F.text == "/start")
    async def start_cmd(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            (
                "<b>Привет!</b>\n"
                "Я помогу записаться на маникюр.\n\n"
                "Выберите действие в меню:"
            ),
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=message.from_user.id == config.admin_id),
        )

    @router.callback_query(F.data == "back_main")
    async def back_main(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(
            "<b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=callback.from_user.id == config.admin_id),
        )
        await callback.answer()

    @router.callback_query(F.data == "show_prices")
    async def show_prices(callback: CallbackQuery):
        await callback.message.answer(
            "<b>Прайсы</b>\n\nФренч — <b>1000₽</b>\nКвадрат — <b>500₽</b>",
            parse_mode="HTML",
        )
        await callback.answer()

    @router.callback_query(F.data == "show_portfolio")
    async def show_portfolio(callback: CallbackQuery):
        await callback.message.answer(
            "<b>Портфолио</b>\nНажмите кнопку ниже:",
            parse_mode="HTML",
            reply_markup=portfolio_kb(),
        )
        await callback.answer()

    @router.callback_query(F.data == "book_start")
    async def booking_start(callback: CallbackQuery, state: FSMContext):
        subscribed = await is_user_subscribed(
            bot=callback.bot,
            channel_id=config.channel_id,
            user_id=callback.from_user.id,
        )
        if not subscribed:
            await callback.message.answer(
                "Для записи необходимо подписаться на канал",
                reply_markup=subscription_check_kb(config.channel_link),
            )
            await callback.answer()
            return

        existing = await db.get_booking_by_user(callback.from_user.id)
        if existing:
            await callback.message.answer(
                (
                    "<b>У вас уже есть активная запись:</b>\n"
                    f"Дата: <b>{existing[5]}</b>\n"
                    f"Время: <b>{existing[6]}</b>\n\n"
                    "Отмените текущую запись, чтобы выбрать другую."
                ),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        days = await db.get_open_days()
        if not days:
            await callback.message.answer("Пока нет доступных дней для записи.")
            await callback.answer()
            return

        await state.set_state(BookingStates.choosing_date)
        await callback.message.answer(
            "<b>Выберите дату:</b>",
            parse_mode="HTML",
            reply_markup=days_calendar_kb(days),
        )
        await callback.answer()

    @router.callback_query(F.data == "check_subscription")
    async def check_subscription(callback: CallbackQuery):
        subscribed = await is_user_subscribed(
            bot=callback.bot,
            channel_id=config.channel_id,
            user_id=callback.from_user.id,
        )
        if subscribed:
            await callback.message.answer(
                "Подписка подтверждена ✅\nТеперь вы можете записаться.",
                reply_markup=main_menu_kb(is_admin=callback.from_user.id == config.admin_id),
            )
        else:
            await callback.message.answer(
                "Подписка не найдена. Подпишитесь и нажмите «Проверить подписку» снова.",
                reply_markup=subscription_check_kb(config.channel_link),
            )
        await callback.answer()

    @router.callback_query(BookingStates.choosing_date, F.data.startswith("pick_day:"))
    async def pick_day(callback: CallbackQuery, state: FSMContext):
        day = callback.data.split(":", 1)[1]
        slots = await db.get_free_slots(day)
        if not slots:
            await callback.message.answer("На эту дату свободного времени нет.")
            await callback.answer()
            return
        await state.update_data(day=day)
        await state.set_state(BookingStates.choosing_time)
        await callback.message.answer(
            f"<b>Дата:</b> {day}\n<b>Выберите время:</b>",
            parse_mode="HTML",
            reply_markup=slots_kb(slots),
        )
        await callback.answer()

    @router.callback_query(BookingStates.choosing_time, F.data.startswith("pick_slot:"))
    async def pick_slot(callback: CallbackQuery, state: FSMContext):
        _, slot_id, time_value = callback.data.split(":", 2)
        await state.update_data(slot_id=int(slot_id), time_value=time_value)
        await state.set_state(BookingStates.entering_name)
        await callback.message.answer("Введите ваше имя:")
        await callback.answer()

    @router.message(BookingStates.entering_name)
    async def save_name(message: Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await state.set_state(BookingStates.entering_phone)
        await message.answer("Введите номер телефона:")

    @router.message(BookingStates.entering_phone)
    async def save_phone(message: Message, state: FSMContext):
        await state.update_data(phone=message.text.strip())
        data = await state.get_data()
        await state.set_state(BookingStates.confirming)
        await message.answer(
            (
                "<b>Проверьте данные:</b>\n\n"
                f"Дата: <b>{data['day']}</b>\n"
                f"Время: <b>{data['time_value']}</b>\n"
                f"Имя: <b>{data['name']}</b>\n"
                f"Телефон: <b>{data['phone']}</b>"
            ),
            parse_mode="HTML",
            reply_markup=confirm_booking_kb(),
        )

    @router.callback_query(F.data == "cancel_booking_flow")
    async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.answer("Запись отменена.")
        await callback.answer()

    @router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
    async def confirm_booking(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        booking_id = await db.create_booking(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            name=data["name"],
            phone=data["phone"],
            day=data["day"],
            time_value=data["time_value"],
            slot_id=data["slot_id"],
        )
        if not booking_id:
            await callback.message.answer(
                "Не удалось создать запись. Возможно, слот уже занят или у вас уже есть запись."
            )
            await callback.answer()
            return

        job_id = schedule_booking_reminder(
            scheduler=scheduler,
            bot=callback.bot,
            booking_id=booking_id,
            user_id=callback.from_user.id,
            day=data["day"],
            time_value=data["time_value"],
        )
        await db.set_booking_reminder_job(booking_id, job_id)

        await callback.message.answer(
            (
                "<b>Запись подтверждена ✅</b>\n\n"
                f"Дата: <b>{data['day']}</b>\n"
                f"Время: <b>{data['time_value']}</b>"
            ),
            parse_mode="HTML",
        )

        await notify_admin_and_channel(
            bot=callback.bot,
            config=config,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            name=data["name"],
            phone=data["phone"],
            day=data["day"],
            time_value=data["time_value"],
        )
        await state.clear()
        await callback.answer()

    @router.callback_query(F.data == "my_booking")
    async def my_booking(callback: CallbackQuery):
        booking = await db.get_booking_by_user(callback.from_user.id)
        if not booking:
            await callback.message.answer("Активной записи нет.")
        else:
            await callback.message.answer(
                (
                    "<b>Ваша запись:</b>\n"
                    f"Дата: <b>{booking[5]}</b>\n"
                    f"Время: <b>{booking[6]}</b>\n"
                    f"Имя: <b>{booking[3]}</b>\n"
                    f"Телефон: <b>{booking[4]}</b>"
                ),
                parse_mode="HTML",
            )
        await callback.answer()

    @router.callback_query(F.data == "cancel_my_booking")
    async def cancel_my_booking(callback: CallbackQuery):
        booking = await db.cancel_booking_by_user(callback.from_user.id)
        if not booking:
            await callback.message.answer("У вас нет активной записи.")
            await callback.answer()
            return

        remove_reminder_job(scheduler, booking[4])

        await callback.message.answer("Ваша запись отменена. Слот снова доступен ✅")
        await callback.bot.send_message(
            config.admin_id,
            (
                "<b>Клиент отменил запись</b>\n"
                f"ID: <code>{callback.from_user.id}</code>\n"
                f"Дата: <b>{booking[2]}</b>\n"
                f"Время: <b>{booking[3]}</b>"
            ),
            parse_mode="HTML",
        )
        await callback.answer()

    return router


async def notify_admin_and_channel(
    bot: Bot,
    config: Config,
    user_id: int,
    username: str | None,
    name: str,
    phone: str,
    day: str,
    time_value: str,
) -> None:
    username_text = f"@{username}" if username else "—"
    text = (
        "<b>Новая запись</b>\n\n"
        f"Клиент: <b>{name}</b>\n"
        f"Телефон: <b>{phone}</b>\n"
        f"Telegram ID: <code>{user_id}</code>\n"
        f"Username: {username_text}\n"
        f"Дата: <b>{day}</b>\n"
        f"Время: <b>{time_value}</b>"
    )

    await bot.send_message(config.admin_id, text, parse_mode="HTML")
    if config.schedule_channel_id:
        await bot.send_message(
            config.schedule_channel_id,
            (
                "<b>Обновление расписания</b>\n"
                f"Забронировано: <b>{day}</b> в <b>{time_value}</b>"
            ),
            parse_mode="HTML",
        )
