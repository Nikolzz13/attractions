import logging
import requests
from math import radians, cos, sin, asin, sqrt
from telegram import (
    Update, Location,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TELEGRAM_TOKEN = "7629568178:AAFETrxM6q9uO0AAsh7uPpBbDI-IH4X1wOE"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

message_cache = set()

MOSCOW_LAT_MIN = 55.3
MOSCOW_LAT_MAX = 56.1
MOSCOW_LON_MIN = 36.8
MOSCOW_LON_MAX = 38.1

CATEGORY_TRANSLATIONS = {
    "museum": "Музей",
    "gallery": "Галерея",
    "attraction": "Достопримечательность",
    "artwork": "Арт-объект",
    "viewpoint": "Смотровая площадка",
    "theatre": "Театр",
    "park": "Парк"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    chat_id = update.message.chat_id
    cache_key = f"{chat_id}_{message_id}"
    if cache_key in message_cache:
        return
    message_cache.add(cache_key)
    if len(message_cache) > 100:
        message_cache.clear()

    reply_markup = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📍 Отправить геопозицию", request_location=True)],
            [KeyboardButton("💡 Инструкция")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "👋 Привет! Я найду достопримечательности рядом с тобой в Москве.\n\n"
        "Выбери действие ниже:",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    chat_id = update.message.chat_id
    text = update.message.text

    cache_key = f"{chat_id}_{message_id}"
    if cache_key in message_cache:
        return
    message_cache.add(cache_key)

    if text == "💡 Инструкция":
        await update.message.reply_text(
            "ℹ️ <b>Как пользоваться:</b>\n\n"
            "1. Нажмите <b>📍 Отправить геопозицию</b>\n"
            "2. Я найду ближайшие достопримечательности, покажу их название, категорию и ссылку на Яндекс.Карты\n"
            "3. Работает только в пределах Москвы",
            parse_mode="HTML"
        )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location: Location = update.message.location
    lat, lon = location.latitude, location.longitude

    message_id = update.message.message_id
    chat_id = update.message.chat_id
    cache_key = f"{chat_id}_{message_id}"
    if cache_key in message_cache:
        return
    message_cache.add(cache_key)
    if len(message_cache) > 100:
        message_cache.clear()

    if not is_in_moscow(lat, lon):
        await update.message.reply_text("⚠️ Бот работает только в пределах Москвы 📍")
        return

    await update.message.reply_text("🔍 Ищу достопримечательности рядом с вами...")

    places = get_nearby_places(lat, lon)
    if not places:
        await update.message.reply_text("Поблизости ничего не нашёл 😕")
    else:
        for place in places:
            name = place['name']
            category = translate_category(place.get('category'))
            plat = place['lat']
            plon = place['lon']
            distance = haversine(lat, lon, plat, plon)

            yandex_link = f"https://yandex.ru/maps/?rtext={lat}%2C{lon}~{plat}%2C{plon}&rtt=auto"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📍 Маршрут в Яндекс.Картах", url=yandex_link)]
            ])

            caption = (
                f"🏛 <b>{name}</b>\n"
                f"📏 Расстояние: {distance:.1f} м\n"
                f"📂 Категория: {category}"
            )

            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

def is_in_moscow(lat, lon):
    return (MOSCOW_LAT_MIN <= lat <= MOSCOW_LAT_MAX) and (MOSCOW_LON_MIN <= lon <= MOSCOW_LON_MAX)

def get_nearby_places(lat, lon):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["tourism"~"museum|gallery|attraction|artwork|viewpoint"](around:1500,{lat},{lon});
      node["amenity"="theatre"](around:1500,{lat},{lon});
      node["leisure"="park"](around:1500,{lat},{lon});
    );
    out center;
    """
    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=30)
        data = response.json()
        elements = data.get("elements", [])
        places = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name")
            if name:
                category = (
                    tags.get("tourism")
                    or tags.get("amenity")
                    or tags.get("leisure")
                    or "не указано"
                )
                places.append({
                    "name": name,
                    "lat": el.get("lat"),
                    "lon": el.get("lon"),
                    "category": category
                })
        return places[:5]
    except Exception as e:
        logger.error(f"Ошибка Overpass API: {e}")
        return []

def translate_category(category):
    return CATEGORY_TRANSLATIONS.get(category, "не указано")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    logger.info("Бот запущен")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()