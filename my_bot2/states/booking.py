from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


class AdminStates(StatesGroup):
    adding_day = State()
    adding_slot_day = State()
    adding_slot_time = State()
    deleting_slot_day = State()
    deleting_slot_time = State()
    closing_day = State()
    viewing_day = State()
    cancel_booking = State()
