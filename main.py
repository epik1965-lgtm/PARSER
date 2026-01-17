import os
import json
import asyncio
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# === КОНФИГУРАЦИЯ ===
API_ID = 31601318
API_HASH = "2c68063c1f7640c125dc5794d1ec8a02"
SESSION_STRING = os.environ.get("SESSION_STRING")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Получаем ID пользователей (строка вида "12345,67890")
ALLOWED_USERS_STR = os.environ.get("ALLOWED_USERS", "0")
try:
    # Превращаем строку "id1,id2" в список чисел [id1, id2]
    ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(',') if uid.strip().isdigit()]
except:
    ALLOWED_USERS = []

DB_FILE = "database.json"

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

USER_STATE = {}

# === ФУНКЦИИ БАЗЫ ДАННЫХ ===
# Структура БД теперь:
# {
#   "user_id_1": {"channels": [], "keywords": []},
#   "user_id_2": {"channels": [], "keywords": []}
# }
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Конвертируем ключи в int, так как JSON хранит ключи как строки
            return {int(k): v for k, v in data.items()}
    except:
        return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_user_config(user_id):
    """Возвращает конфиг конкретного пользователя или создает пустой"""
    db = load_db()
    if user_id not in db:
        db[user_id] = {"channels": [], "keywords": []}
        save_db(db)
    return db[user_id]

def update_user_config(user_id, config_data):
    """Сохраняет конфиг конкретного пользователя"""
    db = load_db()
    db[user_id] = config_data
    save_db(db)

# === ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ===
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# === МЕНЮ БОТА ===
async def send_main_menu(event, text="🤖 **Панель Управления**\nВыберите действие:"):
    buttons = [
        [Button.inline("➕ Добавить Канал", b"add_channel"), Button.inline("➖ Удалить Канал", b"del_channel")],
        [Button.inline("➕ Добавить Слово", b"add_word"), Button.inline("➖ Удалить Слово", b"del_word")],
        [Button.inline("📋 Показать настройки", b"list_all")]
    ]
    await event.respond(text, buttons=buttons)

# === ОБРАБОТЧИК /start ===
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id not in ALLOWED_USERS:
        return
    USER_STATE[event.sender_id] = None
    await send_main_menu(event)

# === ОБРАБОТЧИК КНОПОК ===
@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    sender_id = event.sender_id
    if sender_id not in ALLOWED_USERS:
        return
    
    data = event.data.decode()
    user_config = get_user_config(sender_id)

    if data == 'add_channel':
        USER_STATE[sender_id] = 'WAITING_CHANNEL_ADD'
        await event.respond("✍️ Пришли ссылку или юзернейм канала (@durov)", buttons=Button.inline("🔙 Отмена", b"cancel"))
    
    elif data == 'add_word':
        USER_STATE[sender_id] = 'WAITING_WORD_ADD'
        await event.respond("✍️ Пришли ключевое слово", buttons=Button.inline("🔙 Отмена", b"cancel"))

    elif data == 'del_channel':
        if not user_config['channels']:
            await event.answer("Список пуст!", alert=True)
            return
        
        buttons = []
        for ch in user_config['channels']:
            # В callback data добавляем ID канала, чтобы знать что удалять
            btn = Button.inline(f"❌ {ch['name']}", f"del_ch_{ch['id']}")
            buttons.append([btn])
            
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 Нажми для удаления:", buttons=buttons)

    elif data == 'del_word':
        if not user_config['keywords']:
            await event.answer("Список пуст!", alert=True)
            return
            
        buttons = []
        for i, w in enumerate(user_config['keywords']):
            btn = Button.inline(f"❌ {w}", f"del_wd_{i}")
            buttons.append([btn])
            
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 Нажми для удаления:", buttons=buttons)

    elif data.startswith('del_ch_'):
        cid = int(data.split('_')[2])
        new_channels = [c for c in user_config['channels'] if c['id'] != cid]
        user_config['channels'] = new_channels
        
        update_user_config(sender_id, user_config)
        await event.answer("Удалено!")
        await send_main_menu(event, "Канал удален.")

    elif data.startswith('del_wd_'):
        idx = int(data.split('_')[2])
        try:
            user_config['keywords'].pop(idx)
            update_user_config(sender_id, user_config)
            await event.answer("Удалено!")
        except:
            pass
        await send_main_menu(event, "Слово удалено.")

    elif data == 'list_all':
        msg = "**📢 Твои каналы:**\n"
        for c in user_config['channels']:
            msg += f"• {c['name']}\n"
            
        msg += "\n\n**🔑 Твои слова:**\n"
        for k in user_config['keywords']:
            msg += f"• {k}\n"
            
        await event.edit(msg, buttons=Button.inline("🔙 Меню", b"cancel"))

    elif data == 'cancel':
        USER_STATE[sender_id] = None
        await event.delete()
        await send_main_menu(event)

# === ОБРАБОТЧИК ТЕКСТА (ВВОД ССЫЛОК И СЛОВ) ===
@bot_client.on(events.NewMessage())
async def input_handler(event):
    sender_id = event.sender_id
    if sender_id not in ALLOWED_USERS:
        return
        
    state = USER_STATE.get(sender_id)
    if not state:
        return

    user_config = get_user_config(sender_id)

    if state == 'WAITING_CHANNEL_ADD':
        try:
            # Используем user_client для поиска, так как бот может не видеть канал
            entity = await user_client.get_entity(event.text.strip())
            clean_id = int(str(entity.id).replace('-100', ''))
            title = entity.title if hasattr(entity, 'title') else (entity.username or "Unknown")
            
            # Проверка дублей
            is_exist = any(c['id'] == clean_id for c in user_config['channels'])
            
            if is_exist:
                await event.respond(f"⚠️ {title} уже есть в твоем списке.")
            else:
                user_config['channels'].append({"id": clean_id, "name": title})
                update_user_config(sender_id, user_config)
                await event.respond(f"✅ {title} добавлен!")
                
            USER_STATE[sender_id] = None
            await send_main_menu(event)
        except Exception as e:
            await event.respond(f"❌ Ошибка (проверь ссылку или вступи в канал): {e}")

    elif state == 'WAITING_WORD_ADD':
        word = event.text.strip().lower()
        if word not in user_config['keywords']:
            user_config['keywords'].append(word)
            update_user_config(sender_id, user_config)
            await event.respond(f"✅ Слово '{word}' добавлено!")
            
        USER_STATE[sender_id] = None
        await send_main_menu(event)

# === МОНИТОРИНГ НОВЫХ СООБЩЕНИЙ ===
@user_client.on(events.NewMessage())
async def monitor_handler(event):
    # УБРАЛИ ПРОВЕРКУ event.out ЧТОБЫ ТЕСТИРОВАТЬ НА СЕБЕ
    
    chat_id = event.chat_id
    current_clean_id = int(str(chat_id).replace('-100', ''))
    
    # Загружаем полную базу всех пользователей
    full_db = load_db()
    
    # 1. Сначала извлекаем текст сообщения (один раз для всех)
    try:
        msg_text = getattr(event.message, 'text', '') or ""
        msg_caption = getattr(event.message, 'caption', '') or ""
        full_text = (msg_text + msg_caption).lower()
    except:
        full_text = ""
        
    if not full_text:
        return

    logger.info(f"📩 Message in {current_clean_id}")

    # 2. Проходим по каждому пользователю и проверяем ЕГО настройки
    for user_id, config in full_db.items():
        if user_id not in ALLOWED_USERS:
            continue
            
        # Список ID каналов, за которыми следит ЭТОТ пользователь
        user_channel_ids = [int(str(c['id']).replace('-100', '')) for c in config.get('channels', [])]
        
        # Если сообщение пришло из канала, который интересен этому пользователю
        if current_clean_id in user_channel_ids:
            found_keyword = None
            
            # Ищем ключевые слова ЭТОГО пользователя
            for kw in config.get('keywords', []):
                if kw.lower() in full_text:
                    found_keyword = kw
                    break
            
            if found_keyword:
                try:
                    # Формируем ссылку
                    chat = await event.get_chat()
                    if hasattr(chat, 'username') and chat.username:
                        link = f"https://t.me/{chat.username}/{event.id}"
                    else:
                        link = f"https://t.me/c/{current_clean_id}/{event.id}"
                    
                    msg = (f"🚨 **НАЙДЕНО: {found_keyword.upper()}**\n"
                           f"📢 {chat.title if hasattr(chat, 'title') else 'Канал'}\n"
                           f"🔗 [Ссылка]({link})\n\n"
                           f"{full_text[:200]}...")
                    
                    # Отправляем уведомление КОНКРЕТНОМУ пользователю
                    await bot_client.send_message(user_id, msg, link_preview=False)
                    logger.info(f"🔔 ALERT SENT TO {user_id}")
                except Exception as e:
                    logger.error(f"Error sending alert to {user_id}: {e}")

# === ЗАПУСК ===
async def main():
    try:
        # Уведомляем всех разрешенных юзеров о рестарте (опционально)
        for uid in ALLOWED_USERS:
            try:
                await bot_client.send_message(uid, "✅ Бот перезапущен и готов!")
            except:
                pass
    except:
        pass

    await asyncio.gather(user_client.start(), bot_client.run_until_disconnected())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
