Perfect! You're exactly where you need to be.

Now do this in **30 seconds**:

1. In the box that says **“Name your file…”** type this exactly (with the slash at the end if it’s not there already):  
   `bot.py`

   It should now show:  
   `Hotel-booking-bot/bot.py` in main

2. Click inside the big black area that says “Enter file contents here”

3. Paste **this entire code** below (copy everything from the first line to the last):

```python
import logging
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_calendar import SimpleCalendar, simple_cal_callback
import asyncio
import os
import asyncpg
import uuid

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
pool = None

ROOM_PRICES = {"single": 7900, "double": 12900, "suite": 29900}
ROOM_NAMES = {"single": "Single Room", "double": "Double Room", "suite": "Luxury Suite"}

async def init_db():
    global pool
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    username TEXT,
                    room_type TEXT,
                    check_in DATE,
                    check_out DATE,
                    nights INTEGER,
                    total_price INTEGER,
                    booking_id TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')

def room_keyboard():
    kb = [[InlineKeyboardButton(f"{ROOM_NAMES[r]} - ${ROOM_PRICES[r]//100}/night", callback_data=f"room_{r}") for r in ROOM_PRICES]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def confirm_keyboard(booking_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("Confirm & Pay", callback_data=f"pay_{booking_id}")]])

class BookingStates(StatesGroup):
    choosing_room = State()
    choosing_checkin = State()
    choosing_checkout = State()

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Welcome to LuxeHotel!\nChoose your room:", reply_markup=room_keyboard())

@dp.callback_query(lambda c: c.data.startswith("room_"))
async def select_room(callback: types.CallbackQuery, state: FSMContext):
    room = callback.data.split("_")[1]
    await state.update_data(room_type=room)
    await callback.message.edit_text(f"Selected: <b>{ROOM_NAMES[room]}</b>\nSelect check-in date:", 
                                   reply_markup=await SimpleCalendar().start_calendar(), parse_mode="HTML")
    await state.set_state(BookingStates.choosing_checkin)

@dp.callback_query(simple_cal_callback.filter(), BookingStates.choosing_checkin)
async def process_checkin(callback: types.CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date_obj = await SimpleCalendar().process_selection(callback, callback_data)
    if selected and date_obj:
        await state.update_data(check_in=date_obj.date())
        await callback.message.edit_text(f"Check-in: <b>{date_obj.strftime('%Y-%m-%d')}</b>\nSelect check-out:", 
                                       reply_markup=await SimpleCalendar().start_calendar(year=date_obj.year, month=date_obj.month), parse_mode="HTML")
        await state.set_state(BookingStates.choosing_checkout)

@dp.callback_query(simple_cal_callback.filter(), BookingStates.choosing_checkout)
async def process_checkout(callback: types.CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date_obj = await SimpleCalendar().process_selection(callback, callback_data)
    if selected and date_obj:
        data = await state.get_data()
        check_in = data["check_in"]
        check_out = date_obj.date()
        if check_out <= check_in:
            await callback.answer("Check-out must be after check-in!", show_alert=True)
            return
        nights = (check_out - check_in).days
        total = nights * ROOM_PRICES[data["room_type"]]
        booking_id = str(uuid.uuid4())[:8].upper()
        await state.update_data(booking_id=booking_id, nights=nights, total_price=total)

        text = f"Summary:\nRoom: {ROOM_NAMES[data['room_type']]}\nCheck-in: {check_in}\nCheck-out: {check_out}\nNights: {nights}\nTotal: <b>${total//100}</b>"
        await callback.message.edit_text(text, reply_markup=confirm_keyboard(booking_id), parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("pay_"))
async def process_pay(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    booking_id = data["booking_id"]
    if pool and DATABASE_URL:
        async with pool.acquire() as conn:
            await conn.execute("""INSERT INTO bookings(user_id, username, room_type, check_in, check_out, nights, total_price, booking_id)
                                VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
                               callback.from_user.id, callback.from_user.username or "", data["room_type"],
                               data["check_in"], data["check_out"], data["nights"], data["total_price"], booking_id)

    prices = [LabeledPrice("Hotel Booking", data["total_price"])]
    await bot.send_invoice(callback.from_user.id, title="LuxeHotel", description=f"{ROOM_NAMES[data['room_type']]} × {data['nights']} nights",
                          payload=booking_id, provider_token=PAYMENT_PROVIDER_TOKEN, currency="USD", prices=prices)

@dp.pre_checkout_query(lambda q: True)
async def pre_checkout(q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(lambda m: m.successful_payment)
async def success(m: types.Message):
    payload = m.successful_payment.invoice_payload
    await bot.send_message(ADMIN_ID, f"NEW PAID BOOKING!\nID: {payload}\nUser: @{m.from_user.username}")
    await m.answer("Payment successful! Your booking is confirmed!")

async def main():
    await init_db()
    logging.info("Hotel Booking Bot Started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

4. Scroll down → click the big green **“Commit changes”** button

That’s it!  
As soon as you click commit, Render will automatically start deploying again and this time it will go **LIVE**.

Just reply “committed” when you’re done and I’ll tell you the final 30-second step (adding the database).  
You’re 100% there now!
