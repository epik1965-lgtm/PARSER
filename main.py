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

# Безопасное получение ID (чтобы не падало при сборке)
try:
    MY_USER_ID = int(os.environ.get("MY_USER_ID", "0"))
except:
    MY_USER_ID = 0

DB_FILE = "database.json"

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояние диалога
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
if not SESSION_STRING:
    logger.error("❌ Нет SESSION_STRING")
    exit(1)

user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- ГЛАВНОЕ МЕНЮ ---
async def send_main_menu(event, text="🤖 **Панель Управления**\nВыберите действие:"):
    buttons = [
        [Button.inline("➕ Добавить Каналы", b"add_channel"), Button.inline("➖ Удалить Канал", b"del_channel")],
        [Button.inline("➕ Добавить Слова", b"add_word"), Button.inline("➖ Удалить Слово", b"del_word")],
        [Button.inline("📋 Показать настройки", b"list_all")]
    ]
    await event.respond(text, buttons=buttons)

# --- ОБРАБОТЧИК /start ---
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

    # Добавление КАНАЛОВ (паком)
    if data == 'add_channel':
        USER_STATE[sender_id] = 'WAITING_CHANNEL_ADD'
        await event.respond(
            "✍️ **Пришли список каналов (каждый с новой строки).**\n\n"
            "Пример:\n"
            "`@durov`\n"
            "`https://t.me/telegram`\n"
            "`@news`",
            buttons=Button.inline("🔙 Отмена", b"cancel")
        )
    
    # Добавление СЛОВ (паком)
    elif data == 'add_word':
        USER_STATE[sender_id] = 'WAITING_WORD_ADD'
        await event.respond(
            "✍️ **Пришли список слов/фраз (каждое с новой строки).**\n\n"
            "Пример:\n"
            "`биткоин`\n"
            "`искусственный интеллект`\n"
            "`smm`", 
            buttons=Button.inline("🔙 Отмена", b"cancel")
        )

    # Удаление
    elif data == 'del_channel':
        if not CONFIG['channels']:
            await event.answer("Список пуст!", alert=True)
            return
        buttons = []
        for ch in CONFIG['channels']:
            buttons.append([Button.inline(f"❌ {ch['name']}", f"del_ch_{ch['id']}")])
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 **Нажми на канал для удаления:**", buttons=buttons)

    elif data == 'del_word':
        if not CONFIG['keywords']:
            await event.answer("Список пуст!", alert=True)
            return
        buttons = []
        for i, word in enumerate(CONFIG['keywords']):
            buttons.append([Button.inline(f"❌ {word}", f"del_wd_{i}")])
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 **Нажми на слово для удаления:**", buttons=buttons)

    # Логика удаления
    elif data.startswith('del_ch_'):
        cid = int(data.split('_')[2])
        CONFIG['channels'] = [c for c in CONFIG['channels'] if c['id'] != cid]
        save_db(CONFIG)
        await event.answer("Удалено!")
        # Обновляем меню удаления, чтобы можно было удалить еще
        await callback_handler(event) # Рекурсивный вызов для обновления списка

    elif data.startswith('del_wd_'):
        idx = int(data.split('_')[2])
        try:
            CONFIG['keywords'].pop(idx)
            save_db(CONFIG)
            await event.answer("Удалено!")
            # Костыль: при удалении по индексу список смещается, поэтому лучше выйти в меню
            await send_main_menu(event, "Слово удалено.") 
        except:
            await event.answer("Ошибка", alert=True)

    elif data == 'list_all':
        msg = "**📋 НАСТРОЙКИ:**\n\n**📢 Каналы:**\n"
        if not CONFIG['channels']: msg += "— Пусто —\n"
        for c in CONFIG['channels']: msg += f"• `{c['name']}`\n"
        
        msg += "\n**🔑 Слова:**\n"
        if not CONFIG['keywords']: msg += "— Пусто —\n"
        for k in CONFIG['keywords']: msg += f"• `{k}`\n"
        await event.edit(msg, buttons=Button.inline("🔙 Меню", b"cancel"))

    elif data == 'cancel':
        USER_STATE[sender_id] = None
        await event.delete()
        await send_main_menu(event)

# --- ОБРАБОТЧИК ВВОДА (ПАКЕТНОЕ ДОБАВЛЕНИЕ) ---
@bot_client.on(events.NewMessage())
async def input_handler(event):
    if event.sender_id != MY_USER_ID: return
    state = USER_STATE.get(event.sender_id)

    # 1. ПАКЕТНОЕ ДОБАВЛЕНИЕ КАНАЛОВ
    if state == 'WAITING_CHANNEL_ADD':
        lines = event.text.split('\n') # Разбиваем по строкам
        status_msg = await event.respond(f"⏳ Обрабатываю {len(lines)} каналов...")
        
        added_count = 0
        errors = []

        for line in lines:
            link = line.strip()
            if not link: continue # Пропуск пустых строк
            
            try:
                entity = await user_client.get_entity(link)
                chat_id = entity.id
                title = entity.title if hasattr(entity, 'title') else entity.username
                
                # Проверка дублей
                if any(c['id'] == chat_id for c in CONFIG['channels']):
                    errors.append(f"{title}: уже есть")
                else:
                    CONFIG['channels'].append({"id": chat_id, "name": title})
                    added_count += 1
            except Exception as e:
                errors.append(f"{link}: не найден")
        
        save_db(CONFIG)
        
        # Формируем отчет
        report = f"✅ **Успешно добавлено:** {added_count}\n"
        if errors:
            report += "\n⚠️ **Ошибки:**\n" + "\n".join(errors)
        
        await status_msg.edit(report)
        USER_STATE[event.sender_id] = None
        await asyncio.sleep(2)
        await send_main_menu(event)

    # 2. ПАКЕТНОЕ ДОБАВЛЕНИЕ СЛОВ
    elif state == 'WAITING_WORD_ADD':
        lines = event.text.split('\n')
        added_count = 0
        
        for line in lines:
            word = line.strip().lower()
