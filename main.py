import os
import json
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- ТВОИ ДАННЫЕ (УЖЕ ВПИСАНЫ) ---
API_ID = 31601318
API_HASH = "2c68063c1f7640c125dc5794d1ec8a02"

# Сессию берем из переменных Railway
SESSION_STRING = os.environ.get("SESSION_STRING")

DB_FILE = "database.json"

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_db():
    if not os.path.exists(DB_FILE):
        return {"channels": [], "keywords": []}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"channels": [], "keywords": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

CONFIG = load_db()

if not SESSION_STRING:
    logger.error("❌ ОШИБКА: Добавь SESSION_STRING в переменные Railway!")
    exit(1)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
async def command_handler(event):
    global CONFIG
    text = event.text.split()
    command = text[0].lower()
    
    if command == '.add' and len(text) > 1:
        try:
            entity = await client.get_entity(text[1])
            chat_id = entity.id
            title = entity.title if hasattr(entity, 'title') else entity.username
            if any(c['id'] == chat_id for c in CONFIG['channels']):
                await event.edit(f"⚠️ **{title}** уже есть.")
                return
            CONFIG['channels'].append({"id": chat_id, "name": title})
            save_db(CONFIG)
            await event.edit(f"✅ Добавлен: **{title}**")
        except:
            await event.edit("❌ Не нашел канал.")

    elif command == '.del' and len(text) > 1:
        target = text[1].lower()
        initial = len(CONFIG['channels'])
        CONFIG['channels'] = [c for c in CONFIG['channels'] if target not in c['name'].lower()]
        if len(CONFIG['channels']) < initial:
            save_db(CONFIG)
            await event.edit(f"🗑 Удален канал: {text[1]}")
        else:
            await event.edit("🤔 Не нашел такого.")

    elif command == '.key' and len(text) > 1:
        word = " ".join(text[1:]).lower()
        if word not in CONFIG['keywords']:
            CONFIG['keywords'].append(word)
            save_db(CONFIG)
            await event.edit(f"✅ Слово добавлено: **{word}**")
        else:
            await event.edit("⚠️ Такое слово уже есть.")

    elif command == '.unkey' and len(text) > 1:
        word = " ".join(text[1:]).lower()
        if word in CONFIG['keywords']:
            CONFIG['keywords'].remove(word)
            save_db(CONFIG)
            await event.edit(f"🗑 Слово удалено: **{word}**")
        else:
            await event.edit("🤔 Такого слова нет.")

    elif command == '.list':
        msg = "**📋 НАСТРОЙКИ:**\n\n**Каналы:**\n"
        for c in CONFIG['channels']: msg += f"• {c['name']}\n"
        msg += "\n**Слова:**\n"
        for k in CONFIG['keywords']: msg += f"• {k}\n"
        await event.edit(msg)

@client.on(events.NewMessage())
async def monitor_handler(event):
    if event.out: return
    watched_ids = [c['id'] for c in CONFIG['channels']]
    if event.chat_id in watched_ids:
        text = (event.message.text or "") + (event.message.caption or "")
        if any(kw in text.lower() for kw in CONFIG['keywords']):
            await client.forward_messages('me', event.message)

async def main():
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
