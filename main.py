import os
import json
import asyncio
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# --- КОНФИГУРАЦИЯ ---
API_ID = 31601318
API_HASH = "2c68063c1f7640c125dc5794d1ec8a02"
SESSION_STRING = os.environ.get("SESSION_STRING")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
try:
    MY_USER_ID = int(os.environ.get("MY_USER_ID", "0"))
except:
    MY_USER_ID = 0

DB_FILE = "database.json"

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

USER_STATE = {}

# --- БАЗА ДАННЫХ ---
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

# --- КЛИЕНТЫ ---
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- ГЛАВНОЕ МЕНЮ ---
async def send_main_menu(event, text="🤖 **Панель Управления**\nВыберите действие:"):
    buttons = [
        [Button.inline("➕ Добавить Канал", b"add_channel"), Button.inline("➖ Удалить Канал", b"del_channel")],
        [Button.inline("➕ Добавить Слово", b"add_word"), Button.inline("➖ Удалить Слово", b"del_word")],
        [Button.inline("📋 Показать настройки", b"list_all")]
    ]
    await event.respond(text, buttons=buttons)

# --- ОБРАБОТЧИК БОТА (/start) ---
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id != MY_USER_ID: return
    USER_STATE[event.sender_id] = None
    await send_main_menu(event)

# --- ОБРАБОТЧИК КНОПОК ---
@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != MY_USER_ID: return
    data = event.data.decode()
    sender_id = event.sender_id

    if data == 'add_channel':
        USER_STATE[sender_id] = 'WAITING_CHANNEL_ADD'
        await event.respond("✍️ Пришли ссылку или юзернейм канала (@durov)", buttons=Button.inline("🔙 Отмена", b"cancel"))
    
    elif data == 'add_word':
        USER_STATE[sender_id] = 'WAITING_WORD_ADD'
        await event.respond("✍️ Пришли ключевое слово", buttons=Button.inline("🔙 Отмена", b"cancel"))

    elif data == 'del_channel':
        if not CONFIG['channels']:
            await event.answer("Список пуст!", alert=True)
            return
        buttons = [[Button.inline(f"❌ {ch['name']}", f"del_ch_{ch['id']}")] for ch in CONFIG['channels']]
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 Нажми для удаления:", buttons=buttons)

    elif data == 'del_word':
        if not CONFIG['keywords']:
            await event.answer("Список пуст!", alert=True)
            return
        buttons = [[Button.inline(f"❌ {w}", f"del_wd_{i}")] for i, w in enumerate(CONFIG['keywords'])]
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 Нажми для удаления:", buttons=buttons)

    elif data.startswith('del_ch_'):
        cid = int(data.split('_')[2])
        CONFIG['channels'] = [c for c in CONFIG['channels'] if c['id'] != cid]
        save_db(CONFIG)
        await event.answer("Удалено!")
        await send_main_menu(event, "Канал удален.")

    elif data.startswith('del_wd_'):
        idx = int(data.split('_')[2])
        try:
            CONFIG['keywords'].pop(idx)
            save_db(CONFIG)
            await event.answer("Удалено!")
        except: pass
        await send_main_menu(event, "Слово удалено.")

    elif data == 'list_all':
        msg = "**📢 Каналы:**\n" + "\n".join([f"• {c['name']}" for c in CONFIG['channels']])
        msg += "\n\n**🔑 Слова:**\n" + "\n".join([f"• {k}" for k in CONFIG['keywords']])
        await event.edit(msg, buttons=Button.inline("🔙 Меню", b"cancel"))

    elif data == 'cancel':
        USER_STATE[sender_id] = None
        await event.delete()
        await send_main_menu(event)

# --- ОБРАБОТЧИК ТЕКСТА ---
@bot_client.on(events.NewMessage())
async def input_handler(event):
    if event.sender_id != MY_USER_ID: return
    state = USER_STATE.get(event.sender_id)

    if state == 'WAITING_CHANNEL_ADD':
        try:
            entity = await user_client.get_entity(event.text.strip())
            # Сохраняем "чистый" ID (без -100) для удобства
            clean_id = int(str(entity.id).replace('-100', ''))
            
            title = entity.title if hasattr(entity, 'title') else entity.username
            if any(c['id'] == clean_id for c in CONFIG['channels']):
                await event.respond(f"⚠️ {title} уже есть.")
            else:
                CONFIG['channels'].append({"id": clean_id, "name": title})
                save_db(CONFIG)
                await event.respond(f"✅ {title} добавлен!")
            USER_STATE[event.sender_id] = None
            await send_main_menu(event)
        except Exception as e:
            await event.respond(f"❌ Ошибка: {e}")

    elif state == 'WAITING_WORD_ADD':
        word = event.text.strip().lower()
        if word not in CONFIG['keywords']:
            CONFIG['keywords'].append(word)
            save_db(CONFIG)
            await event.respond(f"✅ Слово '{word}' добавлено!")
        USER_STATE[event.sender_id] = None
        await send_main_menu(event)

# --- МОНИТОРИНГ ---
@user_client.on(events.NewMessage())
async def monitor_handler(event):
    # УБРАЛИ ПРОВЕРКУ event.out ЧТОБЫ ТЕСТИРОВАТЬ НА СЕБЕ
    # if event.out: return
    
    chat_id = event.chat_id
    # Нормализуем ID текущего чата
    current_clean_id = int(str(chat_id).replace('-100', ''))
    
    # Получаем список ID для слежки
    watched_ids = [int(str(c['id']).replace('-100', '')) for c in CONFIG['channels']]
    
    # Логируем для проверки
    logger.info(f"📩 Message in {current_clean_id}. Watched: {watched_ids}")

    if current_clean_id in watched_ids:
        text = (event.message.text or "") + (event.message.caption or "")
        
        found = None
        for kw in CONFIG['keywords']:
            if kw.lower() in text.lower():
                found = kw
                break
        
        if found:
            try:
                chat = await event.get_chat()
                link = f"https://t.me/{chat.username}/{event.id}" if chat.username else f"https://t.me/c/{current_clean_id}/{event.id}"
                
                msg = (f"🚨 **НАЙДЕНО: {found.upper()}**\n"
                       f"📢 {chat.title}\n"
                       f"🔗 [Ссылка]({link})\n\n"
                       f"{text[:200]}...")
                
                await bot_client.send_message(MY_USER_ID, msg, link_preview=False)
                logger.info("🔔 ALERT SENT")
            except Exception as e:
                logger.error(f"Error sending alert: {e}")

# --- ЗАПУСК ---
async def main():
    await asyncio.gather(user_client.start(), bot_client.run_until_disconnected())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
