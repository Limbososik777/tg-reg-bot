from datetime import datetime

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

RU_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def main_menu_kb(is_admin: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="Записаться", callback_data="book_start")
    builder.button(text="Моя запись", callback_data="my_booking")
    builder.button(text="Отменить запись", callback_data="cancel_my_booking")
    builder.button(text="Прайсы", callback_data="show_prices")
    builder.button(text="Портфолио", callback_data="show_portfolio")
    if is_admin:
        builder.button(text="Админ-панель", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def subscription_check_kb(channel_link: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="Подписаться", url=channel_link)
    builder.button(text="Проверить подписку", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()


def days_calendar_kb(days: list[str]):
    builder = InlineKeyboardBuilder()
    for day in days:
        date_obj = datetime.strptime(day, "%Y-%m-%d")
        weekday_ru = RU_WEEKDAYS[date_obj.weekday()]
        builder.button(
            text=f"{date_obj.strftime('%d.%m')} ({weekday_ru})",
            callback_data=f"pick_day:{day}",
        )
    builder.adjust(2)
    return builder.as_markup()


def slots_kb(slots: list[tuple[int, str]]):
    builder = InlineKeyboardBuilder()
    for slot_id, time_value in slots:
        builder.button(text=time_value, callback_data=f"pick_slot:{slot_id}:{time_value}")
    builder.button(text="Назад", callback_data="book_start")
    builder.adjust(3, 1)
    return builder.as_markup()


def confirm_booking_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="confirm_booking")
    builder.button(text="Отмена", callback_data="cancel_booking_flow")
    builder.adjust(2)
    return builder.as_markup()


def portfolio_kb():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Смотреть портфолио",
        url="https://ru.pinterest.com/crystalwithluv/_created/",
    )
    return builder.as_markup()


def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить рабочий день", callback_data="admin_add_day")
    builder.button(text="Добавить слот", callback_data="admin_add_slot")
    builder.button(text="Удалить слот", callback_data="admin_delete_slot")
    builder.button(text="Закрыть день", callback_data="admin_close_day")
    builder.button(text="Расписание на дату", callback_data="admin_view_day")
    builder.button(text="Записи на 7 дней", callback_data="admin_view_week")
    builder.button(text="Отменить запись клиента", callback_data="admin_cancel_booking")
    builder.button(text="В главное меню", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()
