import asyncio
import os

from async_lru import alru_cache
from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient
from telethon.tl import functions, types
from tortoise import Model, fields, Tortoise

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
client = TelegramClient('anon', api_id, api_hash)


@alru_cache(maxsize=32)
async def get_entity(channel_name: str) -> types.Channel:
    return await client.get_entity(channel_name)


class Channel(Model):
    name = fields.TextField()
    channel_id = fields.BigIntField(null=True)
    last_message_id = fields.BigIntField(null=True)
    blaklist_words = fields.TextField(default='')
    forward_to_channel_id = fields.BigIntField(null=True)

    def __str__(self):
        return f'Channel: {self.name}'

    async def fetch_id(self) -> None:
        logger.info("Получаем внутренний id")
        entity = await get_entity(self.name)
        self.channel_id = entity.id
        await self.save()
        logger.success("Готово")

    async def create_reserve_channel(self):
        logger.info("Создаем канал дублер")
        channel_title = (await get_entity(self.name)).title
        result = await client(
            functions.channels.CreateChannelRequest(title=f'AdBlocked {channel_title}', about="")
        )
        new_chat_id = result.chats[0].id
        self.forward_to_channel_id = new_chat_id
        await self.save()
        logger.success("Готово")


async def init_db():
    await Tortoise.init(
        db_url="sqlite://telegram.adblock.sqlite3",
        modules={'models': ['__main__']}
    )
    await Tortoise.generate_schemas()


async def fetch_forward_messages(channel: Channel) -> None:
    last_message_id = channel.last_message_id
    new_messages_count = 0
    params = {
        'entity': await get_entity(channel.name),
        'reverse': True,
        'offset_id': channel.last_message_id
    }
    async for message in client.iter_messages(**params):
        if (
                message.text and
                any(bad_word in message.text for bad_word in channel.blaklist_words.split(','))
        ):
            logger.warning(message.text)
            logger.success("Фильтр сработал")
            continue
        logger.info(f"Отправляем сообщение {message.id} в канал-дублер")
        await message.forward_to(channel.forward_to_channel_id)

        last_message_id = message.id
        new_messages_count += 1

    if new_messages_count:
        logger.success(f"Собрано {new_messages_count} новых сообщений")
    channel.last_message_id = last_message_id
    await channel.save()


async def main():
    await client.connect()
    while True:
        async for channel in Channel.all():
            logger.info(f"Собираем с канала {channel}")
            if not channel.channel_id:
                await channel.fetch_id()
            if not channel.forward_to_channel_id:
                await channel.create_reserve_channel()
            if not channel.last_message_id:
                last_message = await client.get_messages(channel.channel_id)
                channel.last_message_id = last_message[0].id
                await channel.save()
            await fetch_forward_messages(channel)
        await asyncio.sleep(30.0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Exiting")
