import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS work_days (
                    day TEXT PRIMARY KEY,
                    is_closed INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT NOT NULL,
                    time TEXT NOT NULL,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(day, time)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    day TEXT NOT NULL,
                    time TEXT NOT NULL,
                    slot_id INTEGER NOT NULL UNIQUE,
                    reminder_job_id TEXT
                )
                """
            )
            await db.commit()

    async def add_work_day(self, day: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    "INSERT INTO work_days(day, is_closed) VALUES (?, 0)",
                    (day,),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def close_day(self, day: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "UPDATE work_days SET is_closed = 1 WHERE day = ?",
                (day,),
            )
            await db.execute(
                "UPDATE time_slots SET is_available = 0 WHERE day = ?",
                (day,),
            )
            await db.commit()
            return cur.rowcount > 0

    async def get_open_days(self) -> list[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT wd.day
                FROM work_days wd
                WHERE wd.is_closed = 0
                  AND date(wd.day) >= date('now', 'localtime')
                  AND date(wd.day) <= date('now', 'localtime', '+1 month')
                  AND EXISTS (
                      SELECT 1 FROM time_slots ts
                      WHERE ts.day = wd.day AND ts.is_available = 1
                  )
                ORDER BY date(wd.day)
                """
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def add_time_slot(self, day: str, time_value: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            work_day_cur = await db.execute(
                "SELECT day, is_closed FROM work_days WHERE day = ?",
                (day,),
            )
            work_day = await work_day_cur.fetchone()
            if not work_day or work_day[1] == 1:
                return False
            try:
                await db.execute(
                    "INSERT INTO time_slots(day, time, is_available) VALUES (?, ?, 1)",
                    (day, time_value),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_time_slot(self, day: str, time_value: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            # If slot is booked, booking should be canceled by admin first.
            booking_cur = await db.execute(
                """
                SELECT b.id
                FROM bookings b
                JOIN time_slots ts ON ts.id = b.slot_id
                WHERE ts.day = ? AND ts.time = ?
                """,
                (day, time_value),
            )
            if await booking_cur.fetchone():
                return False

            cur = await db.execute(
                "DELETE FROM time_slots WHERE day = ? AND time = ?",
                (day, time_value),
            )
            await db.commit()
            return cur.rowcount > 0

    async def get_free_slots(self, day: str) -> list[tuple[int, str]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT id, time
                FROM time_slots
                WHERE day = ? AND is_available = 1
                ORDER BY time
                """,
                (day,),
            )
            return await cur.fetchall()

    async def get_booking_by_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT id, user_id, username, name, phone, day, time, slot_id, reminder_job_id
                FROM bookings WHERE user_id = ?
                """,
                (user_id,),
            )
            return await cur.fetchone()

    async def create_booking(
        self,
        user_id: int,
        username: str | None,
        name: str,
        phone: str,
        day: str,
        time_value: str,
        slot_id: int,
    ) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            existing_cur = await db.execute(
                "SELECT id FROM bookings WHERE user_id = ?",
                (user_id,),
            )
            if await existing_cur.fetchone():
                return None

            slot_cur = await db.execute(
                "SELECT is_available FROM time_slots WHERE id = ?",
                (slot_id,),
            )
            slot = await slot_cur.fetchone()
            if not slot or slot[0] != 1:
                return None

            await db.execute(
                "UPDATE time_slots SET is_available = 0 WHERE id = ?",
                (slot_id,),
            )
            cur = await db.execute(
                """
                INSERT INTO bookings(user_id, username, name, phone, day, time, slot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, name, phone, day, time_value, slot_id),
            )
            await db.commit()
            return cur.lastrowid

    async def set_booking_reminder_job(self, booking_id: int, job_id: str | None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE bookings SET reminder_job_id = ? WHERE id = ?",
                (job_id, booking_id),
            )
            await db.commit()

    async def cancel_booking_by_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT id, slot_id, day, time, reminder_job_id
                FROM bookings WHERE user_id = ?
                """,
                (user_id,),
            )
            booking = await cur.fetchone()
            if not booking:
                return None
            await db.execute(
                "UPDATE time_slots SET is_available = 1 WHERE id = ?",
                (booking[1],),
            )
            await db.execute("DELETE FROM bookings WHERE id = ?", (booking[0],))
            await db.commit()
            return booking

    async def cancel_booking_by_id(self, booking_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT id, user_id, slot_id, day, time, reminder_job_id
                FROM bookings WHERE id = ?
                """,
                (booking_id,),
            )
            booking = await cur.fetchone()
            if not booking:
                return None
            await db.execute(
                "UPDATE time_slots SET is_available = 1 WHERE id = ?",
                (booking[2],),
            )
            await db.execute("DELETE FROM bookings WHERE id = ?", (booking[0],))
            await db.commit()
            return booking

    async def get_schedule_for_day(self, day: str) -> list[tuple[str, str | None, str | None, int | None]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT ts.time, b.name, b.phone, b.id
                FROM time_slots ts
                LEFT JOIN bookings b ON b.slot_id = ts.id
                WHERE ts.day = ?
                ORDER BY ts.time
                """,
                (day,),
            )
            return await cur.fetchall()

    async def get_bookings_next_days(
        self,
        days_count: int = 7,
    ) -> list[tuple[str, str, str, str, int]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT b.day, b.time, b.name, b.phone, b.id
                FROM bookings b
                WHERE date(b.day) >= date('now', 'localtime')
                  AND date(b.day) < date('now', 'localtime', ?)
                ORDER BY date(b.day), b.time
                """,
                (f"+{days_count} day",),
            )
            return await cur.fetchall()

    async def get_bookings_for_restore(self) -> list[tuple[int, int, str, str]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, user_id, day, time FROM bookings"
            )
            return await cur.fetchall()
