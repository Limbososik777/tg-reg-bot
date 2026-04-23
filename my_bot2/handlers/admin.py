from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.db import Database
from keyboards.inline import admin_menu_kb
from states.booking import AdminStates
from utils.scheduler import remove_reminder_job

router = Router()


def normalize_day(raw: str) -> str | None:
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_time(raw: str) -> str | None:
    value = raw.strip()
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def format_day_ru(day: str) -> str:
    weekdays = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    date_obj = datetime.strptime(day, "%Y-%m-%d")
    return f"{date_obj.strftime('%d.%m.%Y')} ({weekdays[date_obj.weekday()]})"


def admin_router(db: Database, config: Config, scheduler: AsyncIOScheduler):
    def is_admin(user_id: int) -> bool:
        return user_id == config.admin_id

    @router.callback_query(F.data == "admin_menu")
    async def admin_menu(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.clear()
        await callback.message.answer(
            "<b>Админ-панель</b>\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=admin_menu_kb(),
        )
        await callback.answer()

    @router.callback_query(F.data == "admin_add_day")
    async def admin_add_day(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.adding_day)
        await callback.message.answer("Введите дату в формате YYYY-MM-DD:")
        await callback.answer()

    @router.message(AdminStates.adding_day)
    async def admin_add_day_save(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        day = normalize_day(message.text)
        if not day:
            await message.answer("Неверная дата. Используйте формат YYYY-MM-DD или DD.MM.YYYY")
            return
        ok = await db.add_work_day(day)
        await message.answer(
            "Рабочий день добавлен ✅" if ok else "Не удалось добавить день (возможно уже есть)."
        )
        await state.clear()

    @router.callback_query(F.data == "admin_add_slot")
    async def admin_add_slot(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.adding_slot_day)
        await callback.message.answer("Введите дату для слота (YYYY-MM-DD):")
        await callback.answer()

    @router.message(AdminStates.adding_slot_day)
    async def admin_add_slot_day(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        day = normalize_day(message.text)
        if not day:
            await message.answer("Неверная дата. Используйте формат YYYY-MM-DD или DD.MM.YYYY")
            return
        await state.update_data(day=day)
        await state.set_state(AdminStates.adding_slot_time)
        await message.answer("Введите время слота (HH:MM):")

    @router.message(AdminStates.adding_slot_time)
    async def admin_add_slot_time(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        time_value = normalize_time(message.text)
        if not time_value:
            await message.answer("Неверное время. Используйте формат HH:MM")
            return
        data = await state.get_data()
        ok = await db.add_time_slot(data["day"], time_value)
        await message.answer("Слот добавлен ✅" if ok else "Не удалось добавить слот.")
        await state.clear()

    @router.callback_query(F.data == "admin_delete_slot")
    async def admin_delete_slot(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.deleting_slot_day)
        await callback.message.answer("Введите дату слота для удаления (YYYY-MM-DD):")
        await callback.answer()

    @router.message(AdminStates.deleting_slot_day)
    async def admin_delete_slot_day(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        day = normalize_day(message.text)
        if not day:
            await message.answer("Неверная дата. Используйте формат YYYY-MM-DD или DD.MM.YYYY")
            return
        await state.update_data(day=day)
        await state.set_state(AdminStates.deleting_slot_time)
        await message.answer("Введите время слота (HH:MM):")

    @router.message(AdminStates.deleting_slot_time)
    async def admin_delete_slot_time(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        time_value = normalize_time(message.text)
        if not time_value:
            await message.answer("Неверное время. Используйте формат HH:MM")
            return
        data = await state.get_data()
        ok = await db.remove_time_slot(data["day"], time_value)
        await message.answer(
            "Слот удален ✅"
            if ok
            else "Не удалось удалить слот. Если слот забронирован, сначала отмените запись."
        )
        await state.clear()

    @router.callback_query(F.data == "admin_close_day")
    async def admin_close_day(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.closing_day)
        await callback.message.answer("Введите дату для полного закрытия (YYYY-MM-DD):")
        await callback.answer()

    @router.message(AdminStates.closing_day)
    async def admin_close_day_save(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        day = normalize_day(message.text)
        if not day:
            await message.answer("Неверная дата. Используйте формат YYYY-MM-DD или DD.MM.YYYY")
            return
        ok = await db.close_day(day)
        await message.answer("День закрыт ✅" if ok else "Не удалось закрыть день.")
        await state.clear()

    @router.callback_query(F.data == "admin_view_day")
    async def admin_view_day(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.viewing_day)
        await callback.message.answer("Введите дату для просмотра расписания (YYYY-MM-DD):")
        await callback.answer()

    @router.message(AdminStates.viewing_day)
    async def admin_view_day_save(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        day = normalize_day(message.text)
        if not day:
            await message.answer("Неверная дата. Используйте формат YYYY-MM-DD или DD.MM.YYYY")
            return
        schedule = await db.get_schedule_for_day(day)
        if not schedule:
            await message.answer("На выбранную дату слоты не найдены.")
            await state.clear()
            return
        lines = [f"<b>Расписание на {day}</b>"]
        for time_value, name, phone, booking_id in schedule:
            if booking_id:
                lines.append(f"{time_value} — занято ({name}, {phone}, booking_id={booking_id})")
            else:
                lines.append(f"{time_value} — свободно")
        await message.answer("\n".join(lines), parse_mode="HTML")
        await state.clear()

    @router.callback_query(F.data == "admin_cancel_booking")
    async def admin_cancel_booking(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await state.set_state(AdminStates.cancel_booking)
        await callback.message.answer("Введите booking_id для отмены:")
        await callback.answer()

    @router.callback_query(F.data == "admin_view_week")
    async def admin_view_week(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа", show_alert=True)
            return

        bookings = await db.get_bookings_next_days(7)
        if not bookings:
            await callback.message.answer("На ближайшие 7 дней записей нет.")
            await callback.answer()
            return

        lines = ["<b>Записи на ближайшие 7 дней</b>"]
        current_day = None
        for day, time_value, name, phone, booking_id in bookings:
            if day != current_day:
                current_day = day
                lines.append(f"\n<b>{format_day_ru(day)}</b>")
            lines.append(f"• {time_value} — {name}, {phone} (booking_id={booking_id})")

        await callback.message.answer("\n".join(lines), parse_mode="HTML")
        await callback.answer()

    @router.message(AdminStates.cancel_booking)
    async def admin_cancel_booking_save(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        try:
            booking_id = int(message.text.strip())
        except ValueError:
            await message.answer("Неверный booking_id.")
            return
        booking = await db.cancel_booking_by_id(booking_id)
        if not booking:
            await message.answer("Запись не найдена.")
            await state.clear()
            return
        remove_reminder_job(scheduler, booking[5])
        await message.answer("Запись клиента отменена ✅")
        await message.bot.send_message(
            booking[1],
            (
                "<b>Ваша запись была отменена администратором.</b>\n"
                f"Дата: <b>{booking[3]}</b>\n"
                f"Время: <b>{booking[4]}</b>"
            ),
            parse_mode="HTML",
        )
        await state.clear()

    return router
