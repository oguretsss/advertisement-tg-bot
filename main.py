#!/usr/bin/env python3
import asyncio
import html
import logging
import traceback
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.types import (
    Message, CallbackQuery, InputMediaPhoto,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ErrorEvent,
)

import messages
from advertisement_repository import AdvertisementRepository

import os

try:
    import bot_settings
    BOT_TOKEN = bot_settings.BOT_TOKEN
    CHANNEL_ID = bot_settings.CHANNEL_ID
except ImportError:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    CHANNEL_ID = os.environ.get("CHANNEL_ID")
    if not BOT_TOKEN or not CHANNEL_ID:
        logging.error("No bot_settings.py and no BOT_TOKEN/CHANNEL_ID env vars set.")
        exit(1)

DB_PATH = os.environ.get("DB_PATH", "advertisements.db")
LOG_FILENAME = datetime.now().strftime('logs/bot_log_%Y%m%d_%H%M%S.log')

logging.basicConfig(
    format='%(asctime)s : %(filename)s:%(lineno)d : %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=LOG_FILENAME
)
advertisement_repository = AdvertisementRepository(DB_PATH)

bot = Bot(token=BOT_TOKEN)
router = Router()


def build_menu(buttons, n_cols):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    return menu


def generate_user_link(user):
    user_id = user.id
    nickname = user.username
    logging.info(f"Generating user link for user: {user_id}. Nick: {nickname}")

    res = messages.AUTHOR

    if nickname:
        res += f"@{nickname}"
    else:
        res += f"<a href='tg://user?id={user_id}'>link</a>"

    return res


@router.message(F.text == "/start")
async def handle_start(message: Message):
    logging.info(f"Start command called by: {message.from_user.id}")
    advertisement_repository.remove_draft(user_id=message.from_user.id)
    await message.answer(text=messages.GREETING)


@router.message(F.text | F.photo)
async def handle_user_message(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        logging.warning(f"No user found in chat: {chat_id}. Probably a message from the channel")
        return
    user_id = user.id
    if not message:
        logging.warning(f"Message is None for user: {user_id}")
        return

    member = await bot.get_chat_member(CHANNEL_ID, user_id)
    logging.info(f"User {user_id} status in {CHANNEL_ID} chat is: {member.status}")
    if member.status == ChatMemberStatus.KICKED:
        logging.info(f"User is kicked, message wont be published")
        await message.answer(text=messages.MSG_BANNED)
        return
    if member.status == ChatMemberStatus.LEFT:
        logging.info(f"User is not a member, message wont be published")
        await message.answer(text=messages.MSG_LEFT)
        return

    logging.info(f"Received message from user: {user_id}. Text: {message.text}, caption: {message.caption}")
    text = message.text or message.caption or ""
    photos = message.photo
    if photos:
        photo_file_id = photos[-1].file_id
    else:
        photo_file_id = None
    draft = advertisement_repository.get_draft(user_id)
    if draft:
        logging.info(f"User: {user_id} found among active advertisements. Appending media")
        if photo_file_id:
            advertisement_repository.add_media(draft["id"], photo_file_id)
        if text:
            advertisement_repository.append_text(draft["id"], html.escape(text))
    else:
        logging.info(f"Adding new advertisement for user: {user_id}")
        ad_id = advertisement_repository.create_draft(user_id, html.escape(text))
        logging.info(f"Message text: {text}")
        if photo_file_id:
            advertisement_repository.add_media(ad_id, photo_file_id)
        button_list = [InlineKeyboardButton(text=messages.BTN_PREVIEW, callback_data="ACTION_PREVIEW")]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=build_menu(button_list, n_cols=2))
        await message.answer(text=messages.MSG_PREVIEW, reply_markup=reply_markup)


@router.callback_query(F.data == "ACTION_PUBLISH")
async def handle_publish(query: CallbackQuery):
    chat_id = query.message.chat.id
    user = query.from_user
    user_id = user.id
    logging.info(f"Publishing advertisement for user: {user_id}")
    draft = advertisement_repository.get_draft(user_id)
    if not draft:
        await bot.send_message(chat_id=chat_id, text=messages.MSG_ERROR)
    else:
        caption = draft["caption"]
        author_text = generate_user_link(user)
        message_text = f"{caption}\n\n{author_text}"
        repost_button = InlineKeyboardButton(text=messages.BTN_REPOST, callback_data=f"ACTION_REPOST_{draft['id']}")
        repost_markup = InlineKeyboardMarkup(inline_keyboard=[[repost_button]])
        if draft["media"]:
            media = [InputMediaPhoto(media=file_id) for file_id in draft["media"]]
            media[0].caption = message_text
            media[0].parse_mode = ParseMode.HTML
            advertisement_repository.publish(draft["id"])
            await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
            await query.message.edit_text(text=messages.MSG_SUCCESS, reply_markup=repost_markup)
        else:
            advertisement_repository.publish(draft["id"])
            await bot.send_message(chat_id=CHANNEL_ID, text=message_text, parse_mode=ParseMode.HTML)
            await query.message.edit_text(text=messages.MSG_SUCCESS, reply_markup=repost_markup)
    await query.answer()


@router.callback_query(F.data == "ACTION_DISCARD")
async def handle_discard(query: CallbackQuery):
    user_id = query.from_user.id
    logging.info(f"Discarding advertisement for user: {user_id}")
    draft = advertisement_repository.get_draft(user_id)
    if draft:
        advertisement_repository.discard(draft["id"])
    await query.message.edit_text(text=messages.MSG_ABORTED)
    await query.answer()


@router.callback_query(F.data == "ACTION_PREVIEW")
async def handle_preview(query: CallbackQuery):
    user = query.from_user
    user_id = user.id
    chat_id = query.message.chat.id
    logging.info(f"Publishing preview for user: {user_id}")
    draft = advertisement_repository.get_draft(user_id)
    if not draft:
        await bot.send_message(chat_id=chat_id, text=messages.MSG_ERROR)
    else:
        caption = draft["caption"]
        author_text = generate_user_link(user)
        message_text = f"{caption}\n\n{author_text}"
        button_list = [InlineKeyboardButton(text=messages.BTN_PUBLISH, callback_data="ACTION_PUBLISH"),
                       InlineKeyboardButton(text=messages.BTN_DISCARD, callback_data="ACTION_DISCARD")]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=build_menu(button_list, n_cols=2))
        if draft["media"]:
            media = [InputMediaPhoto(media=file_id) for file_id in draft["media"]]
            media[0].caption = message_text
            media[0].parse_mode = ParseMode.HTML
            await bot.send_media_group(chat_id=chat_id, media=media)
        else:
            await bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.HTML)
        await bot.send_message(chat_id=chat_id, text=messages.MSG_CONFIRM, reply_markup=reply_markup)
    await query.answer()


@router.callback_query(F.data.startswith("ACTION_REPOST_"))
async def handle_repost(query: CallbackQuery):
    user_id = query.from_user.id
    ad_id = int(query.data.split("_")[-1])
    new_draft_id = advertisement_repository.repost(ad_id, user_id)
    if new_draft_id is None:
        await query.message.edit_text(text=messages.MSG_REPOST_NOT_FOUND)
    else:
        button_list = [InlineKeyboardButton(text=messages.BTN_PREVIEW, callback_data="ACTION_PREVIEW")]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=build_menu(button_list, n_cols=2))
        await query.message.edit_text(text=messages.MSG_REPOST_SUCCESS, reply_markup=reply_markup)
    await query.answer()


@router.error()
async def default_error_handler(event: ErrorEvent):
    logging.error(f"Error occurred and wasn't handled in code so triggered default error handler")
    logging.error(f"Error: {event.exception}")

    tb_list = traceback.format_exception(None, event.exception, event.exception.__traceback__)
    tb_string = "".join(tb_list)
    logging.error(f"Traceback: {tb_string}")

    update = event.update
    if update and hasattr(update, 'message') and update.message and update.message.from_user:
        advertisement_repository.remove_draft(update.message.from_user.id)
        await bot.send_message(chat_id=update.message.chat.id, text=messages.MSG_ERROR)
    elif update and hasattr(update, 'callback_query') and update.callback_query and update.callback_query.from_user:
        advertisement_repository.remove_draft(update.callback_query.from_user.id)
        await bot.send_message(chat_id=update.callback_query.message.chat.id, text=messages.MSG_ERROR)


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
