import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_id: int
    channel_id: int
    channel_link: str
    schedule_channel_id: int | None
    database_path: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "")
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    channel_id = int(os.getenv("CHANNEL_ID", "0"))
    channel_link = os.getenv("CHANNEL_LINK", "https://t.me/your_channel")
    schedule_channel_raw = os.getenv("SCHEDULE_CHANNEL_ID", "")
    schedule_channel_id = int(schedule_channel_raw) if schedule_channel_raw else None
    database_path = os.getenv("DATABASE_PATH", "bot.db")

    if not token:
        raise ValueError("BOT_TOKEN is not set")
    if admin_id == 0:
        raise ValueError("ADMIN_ID is not set")
    if channel_id == 0:
        raise ValueError("CHANNEL_ID is not set")

    return Config(
        bot_token=token,
        admin_id=admin_id,
        channel_id=channel_id,
        channel_link=channel_link,
        schedule_channel_id=schedule_channel_id,
        database_path=database_path,
    )
