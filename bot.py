import os
import base64
import hashlib
import httpx
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

# Initialize bot and dispatcher
TOKEN = "YOUR_BOT_TOKEN"  # Replace with your bot token
API_KEY = "REMINI_API_KEY"  # Replace with your Remini API Key
CONTENT_TYPE = "image/jpeg"
_TIMEOUT = 60
_BASE_URL = "https://developer.remini.ai/api"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()  # Using routers (Recommended in Aiogram 3.x)


def _get_image_md5_content(file_path: str) -> tuple[str, bytes]:
    with open(file_path, "rb") as fp:
        content = fp.read()
        image_md5 = base64.b64encode(hashlib.md5(content).digest()).decode("utf-8")
    return image_md5, content


async def enhance_photo_and_send_link(file_path: str, chat_id: int):
    """Enhances a photo using the Remini API and sends the result URL."""
    image_md5, content = _get_image_md5_content(file_path)

    async with httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
    ) as client:
        try:
            # Step 1: Create a Task
            response = await client.post(
                "/tasks",
                json={
                    "tools": [
                        {"type": "face_enhance", "mode": "beautify"},
                        {"type": "background_enhance", "mode": "base"},
                    ],
                    "image_md5": image_md5,
                    "image_content_type": CONTENT_TYPE,
                },
            )
            response.raise_for_status()
            body = response.json()
            task_id = body["task_id"]

            # Step 2: Upload the Image
            upload_response = await client.put(
                body["upload_url"],
                headers=body["upload_headers"],
                content=content,
                timeout=_TIMEOUT,
            )
            upload_response.raise_for_status()

            # Step 3: Process the Image
            process_response = await client.post(f"/tasks/{task_id}/process")
            process_response.raise_for_status()

            # Step 4: Poll for Completion
            for _ in range(50):
                status_response = await client.get(f"/tasks/{task_id}")
                status_response.raise_for_status()
                if status_response.json()["status"] == "completed":
                    break
                await asyncio.sleep(2)

            # Step 5: Send Enhanced Photo Link
            output_url = status_response.json()["result"]["output_url"]
            await bot.send_message(chat_id, f"<b>Enhanced photo:</b> {output_url}", parse_mode=ParseMode.HTML)

        except httpx.HTTPError as e:
            await bot.send_message(chat_id, f"<b>Error enhancing the photo:</b> {e}", parse_mode=ParseMode.HTML)

        finally:
            os.remove(file_path)  # Ensure file cleanup


@router.message(Command("start"))
async def start_command(message: types.Message):
    """Handles the /start command."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dev 👨‍💻", url="https://t.me/TheSmartBisnu")],
        [InlineKeyboardButton(text="Update ✅", url="https://t.me/PremiumNetworkTeam")]
    ])

    await message.answer(
        "<b>Welcome! I am a Smart Enhancer BOT.\n\nPlease send me a photo to enhance.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


@router.message(lambda msg: msg.photo)
async def handle_photo(message: types.Message):
    """Handles incoming photo messages."""
    photo = message.photo[-1]
    file_path = os.path.join(os.getcwd(), f"{photo.file_unique_id}.jpg")
    await message.answer("<b>Enhancing your photo...</b>", parse_mode=ParseMode.HTML)

    try:
        await message.photo[-1].download(file_path)
        await enhance_photo_and_send_link(file_path, message.chat.id)
    except Exception as e:
        await message.answer(f"<b>Error:</b> {e}", parse_mode=ParseMode.HTML)


@router.message()
async def handle_invalid_message(message: types.Message):
    """Handles invalid messages (e.g., text, stickers)."""
    await message.answer(
        "<b>I only process photos.\n\nPlease send an image for enhancement.</b>",
        parse_mode=ParseMode.HTML,
    )


async def main():
    """Starts the bot."""
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())  # Correct way to run async code in Aiogram 3.x

