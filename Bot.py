import os
import re
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from dotenv import load_dotenv

from database import db
from downloader import download_instagram_video

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Regex Instagram havolalarini topish uchun (guruh va lichka uchun)
INSTAGRAM_REGEX = r'(https?://(?:www\.)?instagram\.com/[p|reels|reel]+/[a-zA-Z0-9_\-]+)'


# FSM holatlari (Admin panel uchun)
class AdminStates(StatesGroup):
    waiting_for_reklama = State()
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()


# Majburiy obunani tekshirish funksiyasi
async def check_subscription(user_id: int) -> list:
    channels = db.get_channels()
    must_join = []
    for ch_id, link, is_mandatory in channels:
        if is_mandatory == 1:  # Faqat majburiylarni tekshiramiz
            try:
                member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    must_join.append(link)
            except Exception:
                # Agar bot kanalda admin bo'lmasa yoki xato bersa
                must_join.append(link)
    return must_join


# --- KLAVIATURALAR ---
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Reklama Yuborish", callback_data="admin_rek")],
        [InlineKeyboardButton(text="⛓ Kanallarni boshqarish", callback_data="admin_channels")],
    ])


def get_channels_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="❌ Kanal O'chirish", callback_data="del_channel")],
        [InlineKeyboardButton(text="📋 Kanallar Ro'yxati", callback_data="list_channels")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])


# --- FOYDALANUVChI QISMI ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    db.add_user(message.from_user.id)
    await message.answer(f"Salom {message.from_user.full_name}! Men Instagram-dan video yuklovchi botman.\n"
                         f"Menga video havolasini yuboring yoki meni guruhga qo'shing.")


# Instagram havolalarini qayta ishlash (Lichka va Guruhlar uchun)
@dp.message(F.text.regexp(INSTAGRAM_REGEX))
async def handle_instagram_links(message: types.Message):
    user_id = message.from_user.id
    db.add_user(user_id)  # Bazaga yozib qo'yamiz

    # Guruhda bo'lsa majburiy obunani tekshirmaydi (ixtiyoriy qilsa bo'ladi)
    if message.chat.type == 'private':
        unsubscribed = await check_subscription(user_id)
        if unsubscribed:
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Kanalga o'tish", url=link)] for link in unsubscribed
            ])
            await message.answer("Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=btn)
            return

    # Havolani ajratib olish
    match = re.search(INSTAGRAM_REGEX, message.text)
    url = match.group(1)

    # Foydalanuvchiga jarayon boshlanganini bildirish
    status_msg = await message.reply("⏳ Video yuklanmoqda, iltimos kuting...")

    # Yuklash (Asinxron tarzda, bot to'xtab qolmaydi)
    file_path = await download_instagram_video(url)

    if file_path and os.path.exists(file_path):
        try:
            video_file = FSInputFile(file_path)
            if message.chat.type in ['group', 'supergroup']:
                # Guruhda foydalanuvchining o'ziga forward (reply) qilib yuborish
                await message.reply_video(video=video_file, caption="👉 Sizning Videongiz")
            else:
                # Lichkada oddiy yuborish
                await message.answer_video(video=video_file, caption="👉 Sizning Videongiz")
        except Exception as e:
            await message.reply("❌ Videoni yuborishda xatolik yuz berdi.")
            print(f"Yuborishda xato: {e}")
        finally:
            # Har qanday holatda ham faylni serverdan o'chirish
            if os.path.exists(file_path):
                os.remove(file_path)
            await status_msg.delete()
    else:
        await status_msg.edit_text("❌ Videoni yuklab bo'lmadi. Havola noto'g'ri yoki video yopiq profildan olingan.")


# --- ADMIN PANEL QISMI ---

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Admin panelga xush kelibsiz:", reply_markup=get_admin_keyboard())


@dp.callback_query(F.data == "admin_back", F.from_user.id == ADMIN_ID)
async def admin_back(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 Admin panelga xush kelibsiz:", reply_markup=get_admin_keyboard())


@dp.callback_query(F.data == "admin_stats", F.from_user.id == ADMIN_ID)
async def admin_stats(call: types.CallbackQuery):
    stats = db.get_stats()
    text = (f"📊 **Bot Statistikasi:**\n\n"
            f"👤 Jami foydalanuvchilar: {stats['all']}\n"
            f"🚫 Bloklanganlar (taxminiy): {stats['blocked']}")
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
    ]))


# --- REKLAMA TIZIMI ---
@dp.callback_query(F.data == "admin_rek", F.from_user.id == ADMIN_ID)
async def start_reklama(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 Har qanday turdagi reklama xabarini yuboring (Rasm, Video, Matn, Fayl va h.k.):")
    await state.set_state(AdminStates.waiting_for_reklama)


@dp.message(AdminStates.waiting_for_reklama, F.from_user.id == ADMIN_ID)
async def send_reklama(message: types.Message, state: FSMContext):
    await state.clear()
    users = db.get_all_users()
    await message.answer(f"📢 Reklama {len(users)} ta foydalanuvchiga yuborilmoqda...")

    success = 0
    blocked = 0

    for user_id in users:
        try:
            # Har qanday formatdagi xabarni aynan o'zidek nusxalab yuboradi (copy_to)
            await message.copy_to(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.05)  # Telegram limitlaridan oshib ketmaslik uchun cheklov
        except Exception:
            blocked += 1
            db.set_user_status(user_id, "blocked")

    await message.answer(f"✅ Reklama yakunlandi!\n\n"
                         f"🟢 Muvaffaqiyatli: {success}\n"
                         f"🔴 Yetib bormadi (Bloklangan): {blocked}")


## --- KANALLARNI BOSHQARISH (To'liq va xatosiz variant) ---

@dp.callback_query(F.data == "admin_channels", F.from_user.id == ADMIN_ID)
async def manage_channels(call: types.CallbackQuery):
    await call.message.edit_text("⚙️ Kanallarni boshqarish bo'limi:", reply_markup=get_channels_keyboard())

@dp.callback_query(F.data == "list_channels", F.from_user.id == ADMIN_ID)
async def list_channels(call: types.CallbackQuery):
    channels = db.get_channels()
    if not channels:
        text = "Hozircha hech qanday kanal qo'shilmagan."
    else:
        text = "📋 **Kanallar ro'yxati:**\n\n"
        for ch_id, link, is_m in channels:
            tur = "Majburiy" if is_m == 1 else "Ixtiyoriy"
            text += f"ID: `{ch_id}`\nLink: {link}\nTuri: {tur}\n\n"

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_channels")]
    ]))

@dp.callback_query(F.data == "add_channel", F.from_user.id == ADMIN_ID)
async def add_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("1️⃣ Kanal ID sini yuboring (Masalan: `-100123456789` yoki `@kanal_yuz`):\n"
                                 "*Eslatma: Bot ushbu kanalda admin bo'lishi shart!*")
    await state.set_state(AdminStates.waiting_for_channel_id)

@dp.message(AdminStates.waiting_for_channel_id, F.from_user.id == ADMIN_ID)
async def add_channel_id(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("2️⃣ Kanalga taklif havolasini (Invite Link) yuboring:")
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(AdminStates.waiting_for_channel_link, F.from_user.id == ADMIN_ID)
async def add_channel_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ch_id = data['ch_id']
    link = message.text

    db.add_channel(channel_id=ch_id, invite_link=link, is_mandatory=1)
    await state.clear()
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi va majburiy obunaga sozlandi!", reply_markup=get_channels_keyboard())

# --- KANAL O'CHIRISH UCHUN YANGI HOLAT (FSM) ---
# Buning uchun AdminStates klassiga 'waiting_for_del_id' ni qo'shib qo'yish kerak yoki shundoq ishlataverasiz:
class AdminStates(StatesGroup):
    waiting_for_reklama = State()
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()
    waiting_for_del_id = State()  # O'chirish uchun yangi holat

@dp.callback_query(F.data == "del_channel", F.from_user.id == ADMIN_ID)
async def delete_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ O'chirmoqchi bo'lgan kanalingiz ID sini yuboring:")
    await state.set_state(AdminStates.waiting_for_del_id)

@dp.message(AdminStates.waiting_for_del_id, F.from_user.id == ADMIN_ID)
async def process_del(message: types.Message, state: FSMContext):
    db.remove_channel(message.text)
    await state.clear()
    await message.answer("🗑 Kanal muvaffaqiyatli o'chirildi!", reply_markup=get_channels_keyboard())

# Botni ishga tushirish
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())