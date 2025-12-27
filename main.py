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
MY_USER_ID = int(os.environ.get("MY_USER_ID", 0))

DB_FILE = "database.json"

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояние диалога (что бот ждет от пользователя прямо сейчас)
# Например: {12345: 'WAITING_CHANNEL_LINK'}
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

# --- ГЛАВНОЕ МЕНЮ (КНОПКИ) ---
async def send_main_menu(event, text="🤖 **Панель Управления**\nВыберите действие:"):
    buttons = [
        [Button.inline("➕ Добавить Канал", b"add_channel"), Button.inline("➖ Удалить Канал", b"del_channel")],
        [Button.inline("➕ Добавить Слово", b"add_word"), Button.inline("➖ Удалить Слово", b"del_word")],
        [Button.inline("📋 Показать настройки", b"list_all")]
    ]
    await event.respond(text, buttons=buttons)

# --- ОБРАБОТЧИК КОМАНД БОТА (/start) ---
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id != MY_USER_ID:
        return # Игнорируем чужих
    
    USER_STATE[event.sender_id] = None # Сброс состояния
    await send_main_menu(event)

# --- ОБРАБОТЧИК НАЖАТИЙ НА КНОПКИ ---
@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id != MY_USER_ID:
        return

    data = event.data.decode()
    sender_id = event.sender_id

    # Кнопка: Добавить канал
    if data == 'add_channel':
        USER_STATE[sender_id] = 'WAITING_CHANNEL_ADD'
        await event.respond("✍️ **Пришли мне юзернейм канала или ссылку.**\nНапример: `@durov` или `https://t.me/durov`", buttons=Button.inline("🔙 Отмена", b"cancel"))
    
    # Кнопка: Добавить слово
    elif data == 'add_word':
        USER_STATE[sender_id] = 'WAITING_WORD_ADD'
        await event.respond("✍️ **Пришли ключевое слово или фразу.**\nНапример: `маркетинг`", buttons=Button.inline("🔙 Отмена", b"cancel"))

    # Кнопка: Удалить канал (показываем список кнопок)
    elif data == 'del_channel':
        if not CONFIG['channels']:
            await event.answer("Список каналов пуст!", alert=True)
            return
        
        buttons = []
        for ch in CONFIG['channels']:
            # В callback_data кладем ID канала с префиксом del_ch_
            buttons.append([Button.inline(f"❌ {ch['name']}", f"del_ch_{ch['id']}")])
        
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 **Нажми на канал, чтобы удалить его:**", buttons=buttons)

    # Кнопка: Удалить слово (показываем список кнопок)
    elif data == 'del_word':
        if not CONFIG['keywords']:
            await event.answer("Список слов пуст!", alert=True)
            return
        
        buttons = []
        for i, word in enumerate(CONFIG['keywords']):
            # В callback_data кладем индекс слова
            buttons.append([Button.inline(f"❌ {word}", f"del_wd_{i}")])
            
        buttons.append([Button.inline("🔙 Назад", b"cancel")])
        await event.edit("👇 **Нажми на слово, чтобы удалить его:**", buttons=buttons)

    # Логика удаления конкретного канала
    elif data.startswith('del_ch_'):
        ch_id_to_del = int(data.split('_')[2])
        # Фильтруем список
        CONFIG['channels'] = [c for c in CONFIG['channels'] if c['id'] != ch_id_to_del]
        save_db(CONFIG)
        await event.answer("✅ Канал удален!")
        await send_main_menu(event, "Канал удален. Что дальше?")

    # Логика удаления конкретного слова
    elif data.startswith('del_wd_'):
        index = int(data.split('_')[2])
        try:
            removed_word = CONFIG['keywords'].pop(index)
            save_db(CONFIG)
            await event.answer(f"Слово '{removed_word}' удалено!")
        except:
            await event.answer("Ошибка удаления", alert=True)
        await send_main_menu(event, "Слово удалено. Что дальше?")

    # Кнопка: Список
    elif data == 'list_all':
        msg = "**📋 ТЕКУЩИЕ НАСТРОЙКИ:**\n\n**📢 Каналы:**\n"
        if not CONFIG['channels']: msg += "— Пусто —\n"
        for c in CONFIG['channels']: msg += f"• `{c['name']}`\n"
        
        msg += "\n**🔑 Слова:**\n"
        if not CONFIG['keywords']: msg += "— Пусто —\n"
        for k in CONFIG['keywords']: msg += f"• `{k}`\n"
        
        await event.edit(msg, buttons=Button.inline("🔙 Меню", b"cancel"))

    # Кнопка: Отмена / Назад
    elif data == 'cancel':
        USER_STATE[sender_id] = None
        await event.delete() # Удаляем старое меню
        await send_main_menu(event)

# --- ОБРАБОТЧИК ТЕКСТА (КОГДА ПОЛЬЗОВАТЕЛЬ ЧТО-ТО ПИШЕТ) ---
@bot_client.on(events.NewMessage())
async def input_handler(event):
    if event.sender_id != MY_USER_ID:
        return

    state = USER_STATE.get(event.sender_id)

    # Если ждем ссылку на канал
    if state == 'WAITING_CHANNEL_ADD':
        link = event.text.strip()
        msg = await event.respond("⏳ Проверяю канал...")
        
        try:
            # Используем user_client для поиска, так как бот может не видеть канал
            entity = await user_client.get_entity(link)
            chat_id = entity.id
            title = entity.title if hasattr(entity, 'title') else entity.username
            
            # Проверка дублей
            if any(c['id'] == chat_id for c in CONFIG['channels']):
                await msg.edit(f"⚠️ Канал **{title}** уже есть в списке.")
            else:
                CONFIG['channels'].append({"id": chat_id, "name": title})
                save_db(CONFIG)
                await msg.edit(f"✅ Канал **{title}** успешно добавлен!")
            
            USER_STATE[event.sender_id] = None
            await send_main_menu(event)
            
        except Exception as e:
            await msg.edit(f"❌ Не удалось найти канал.\nПроверь ссылку или юзернейм.\nОшибка: {str(e)}")
            # Не сбрасываем состояние, даем попробовать еще раз

    # Если ждем ключевое слово
    elif state == 'WAITING_WORD_ADD':
        word = event.text.strip().lower()
        if word in CONFIG['keywords']:
            await event.respond(f"⚠️ Слово **{word}** уже есть.")
        else:
            CONFIG['keywords'].append(word)
            save_db(CONFIG)
            await event.respond(f"✅ Слово **{word}** добавлено!")
        
        USER_STATE[event.sender_id] = None
        await send_main_menu(event)

# --- МОНИТОРИНГ (Работает фоном) ---
# --- МОНИТОРИНГ ---
@user_client.on(events.NewMessage())
async def monitor_handler(event):
    if event.out: return
    
    # Логируем все входящие сообщения для отладки (чтобы видеть ID)
    chat_id = event.chat_id
    logger.info(f"📩 Новое сообщение в чате ID: {chat_id}")
    
    # Получаем список ID, за которыми следим
    # Приводим всё к базовому виду (без префикса -100) для надежного сравнения
    watched_ids = []
    for c in CONFIG['channels']:
        cid = c['id']
        # Убираем префикс -100 если есть, чтобы получить "чистый" ID
        clean_id = int(str(cid).replace('-100', ''))
        watched_ids.append(clean_id)
    
    # ID текущего чата тоже чистим
    current_clean_id = int(str(chat_id).replace('-100', ''))
    
    if current_clean_id in watched_ids:
        text = (event.message.text or "") + (event.message.caption or "")
        
        found_word = None
        for kw in CONFIG['keywords']:
            if kw.lower() in text.lower():
                found_word = kw
                break
        
        if found_word:
            try:
                chat = await event.get_chat()
                if chat.username:
                    msg_link = f"https://t.me/{chat.username}/{event.id}"
                else:
                    msg_link = f"https://t.me/c/{clean_id}/{event.id}"

                alert_text = (
                    f"🚨 **НАЙДЕНО: {found_word.upper()}**\n\n"
                    f"📢 **Канал:** {chat.title}\n"
                    f"🔗 **Ссылка:** [Перейти к посту]({msg_link})\n\n"
                    f"📝 **Текст:**\n{text[:200]}..."
                )
                
                await bot_client.send_message(MY_USER_ID, alert_text, link_preview=False)
                logger.info(f"🔔 АЛЕРТ ОТПРАВЛЕН!")
                
            except Exception as e:
                logger.error(f"Ошибка алерта: {e}")
    else:
        # Если ID не совпал, пишем в лог, почему (для отладки)
        logger.info(f"⚠️ Чат {current_clean_id} не в списке {watched_ids}")
