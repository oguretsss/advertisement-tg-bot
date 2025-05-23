#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime

from telegram.constants import ParseMode, ChatMemberStatus
from telegram.helpers import escape_markdown, escape
from telegram.ext import Updater, MessageHandler, filters, ApplicationBuilder, CommandHandler, ContextTypes, \
    CallbackQueryHandler
from telegram import InputMediaPhoto, PhotoSize, InputMedia, InlineKeyboardButton, InlineKeyboardMarkup, Update

import messages
from advertisement_repository import AdvertisementRepository
import traceback

try:
    import bot_settings
except ImportError(bot_settings):
    logging.info("No bot_settings.py file found! Please refer to README on how to get the bot running!")
    exit(1)

BOT_TOKEN = bot_settings.BOT_TOKEN
CHANNEL_ID = bot_settings.CHANNEL_ID
LOG_FILENAME = datetime.now().strftime('logs/bot_log_%d%m%Y_%H%M%S.log')

logging.basicConfig(
    format='%(asctime)s : %(filename)s:%(lineno)d : %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=LOG_FILENAME
)
advertisement_repository = AdvertisementRepository()

lock = asyncio.Lock()


def build_menu(buttons, n_cols):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    return menu


async def handle_start(update, context):
    logging.info(f"Start command called by: {update.effective_user.id}")
    advertisement_repository.remove_advertisement(user_id=update.effective_user.id)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=messages.GREETING)


def generate_user_link(user):
    user_id = user.id
    nickname = user.username
    logging.info(f"Generating user link for user: {user_id}. Nick: {nickname}")
    
    res = messages.AUTHOR
    
    if nickname:
        res += f"@{nickname}"
    else:
        res += f"<a href='tg://user?id={user_id}'>link</a>"
    
    # Markdown
    # return f"Author: [link](tg://user?id={user_id})"
    # HTML
    return res


async def handle_user_message(update, context):
    message = update.message
    chat_id = update.effective_chat.id
    user = update.effective_user
    if user:
        user_id = update.effective_user.id
    else:
        logging.warning(f"No user found in chat: {chat_id}. Probably a message from the channel")
        await asyncio.sleep(0.01)
        return
    if not message:
        logging.warning(f"Message is None for user: {user_id}")
        await asyncio.sleep(0.01)
        return

    member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
    logging.info(f"User {user_id} status in {CHANNEL_ID} chat is: {member.status}")
    if member.status == ChatMemberStatus.BANNED:
        logging.info(f"User is kicked, message wont be published")
        await context.bot.send_message(chat_id=chat_id,
                                 text=messages.MSG_BANNED)
        return
    if member.status == ChatMemberStatus.LEFT:
        logging.info(f"User is not a member, message wont be published")
        await context.bot.send_message(chat_id=chat_id,
                                 text=messages.MSG_LEFT)
        return

    logging.info(f"Received message from user: {user_id}. Text: {message.text}, caption: {message.caption}")
    text = message.text or message.caption or ""
    photos = message.photo
    if photos:
        photo_file_id = photos[-1].file_id
    else:
        photo_file_id = None
    if user_id in advertisement_repository.active_advertisements:
        logging.info(f"User: {user_id} found among active advertisements. Appending media")
        if photo_file_id:
            advertisement_repository.active_advertisements[user_id].add_media(photo_file_id)
        if text:
            advertisement_repository.active_advertisements[user_id].add_text(escape(text))
    else:
        logging.info(f"Adding new advertisement for user: {user_id}")

        advertisement_repository.add_advertisement(user_id, escape(text))
        logging.info(f"Message text: {text}")
        if photo_file_id:
            advertisement_repository.active_advertisements[user_id].add_media(photo_file_id)
        button_list = [InlineKeyboardButton(messages.BTN_PREVIEW, callback_data="ACTION_PREVIEW")]
        reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
        await context.bot.send_message(chat_id=chat_id,
                                       text=messages.MSG_PREVIEW, reply_markup=reply_markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback_data = update.callback_query.data
    chat_id = update.effective_chat.id
    logging.info(f"Callback handler called with data {callback_data}")
    user_id = update.effective_user.id
    user = update.effective_user
    if callback_data == "ACTION_PUBLISH":
        logging.info(f"Publishing advertisement for user: {update.effective_user.id}")
        if user_id not in advertisement_repository.active_advertisements:
            await context.bot.send_message(chat_id=chat_id, text=messages.MSG_ERROR)
        else:
            caption = advertisement_repository.active_advertisements[user_id].caption
            author_text = generate_user_link(user)
            message_text = f"{caption}\n\n{author_text}"
            if advertisement_repository.active_advertisements[user_id].media:
                media = [InputMediaPhoto(file_id) for file_id in
                         advertisement_repository.active_advertisements[user_id].media]
                advertisement_repository.remove_advertisement(user_id)
                await context.bot.send_media_group(chat_id=CHANNEL_ID, caption=message_text, media=media,
                                                   parse_mode=ParseMode.HTML)
                await query.edit_message_text(text=messages.MSG_SUCCESS)
            else:
                advertisement_repository.remove_advertisement(user_id)
                await context.bot.send_message(chat_id=CHANNEL_ID, text=message_text, parse_mode=ParseMode.HTML)
                await query.edit_message_text(text=messages.MSG_SUCCESS)

    elif callback_data == "ACTION_DISCARD":
        logging.info(f"Discarding advertisement for user: {update.effective_user.id}")
        advertisement_repository.remove_advertisement(user_id)
        await query.edit_message_text(text=messages.MSG_ABORTED)

    elif callback_data == "ACTION_PREVIEW":
        logging.info(f"Publishing preview for user: {update.effective_user.id}")
        if user_id not in advertisement_repository.active_advertisements:
            await context.bot.send_message(chat_id=chat_id, text=messages.MSG_ERROR)
        else:
            caption = advertisement_repository.active_advertisements[user_id].caption
            author_text = generate_user_link(user)
            message_text = f"{caption}\n\n{author_text}"
            button_list = [InlineKeyboardButton(messages.BTN_PUBLISH, callback_data="ACTION_PUBLISH"),
                           InlineKeyboardButton(messages.BTN_DISCARD, callback_data="ACTION_DISCARD")]
            reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
            if advertisement_repository.active_advertisements[user_id].media:
                media = [InputMediaPhoto(file_id) for file_id in
                         advertisement_repository.active_advertisements[user_id].media]
                await context.bot.send_media_group(chat_id=chat_id, caption=message_text, media=media,
                                                   parse_mode=ParseMode.HTML)
            else:
                await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.HTML)
            await context.bot.send_message(chat_id=chat_id,
                                           text=messages.MSG_CONFIRM, reply_markup=reply_markup)


async def default_error_handler(update, context):
    logging.error(f"Error occurred and wasn't handled in code so triggered default error handler")
    logging.error(f"Error: {context.error}")

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logging.error(f"Traceback: {tb_string}")
    if update and update.effective_user:
        advertisement_repository.remove_advertisement(update.effective_user.id)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=messages.MSG_ERROR)

def main():
    application = ApplicationBuilder().token(bot_settings.BOT_TOKEN).build()

    message_handler = MessageHandler(filters.TEXT | filters.PHOTO, handle_user_message)
    start_handler = CommandHandler("start", handle_start)
    application.add_handler(start_handler)
    application.add_handler(message_handler)
    application.add_error_handler(default_error_handler)
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.run_polling(connect_timeout=10)


if __name__ == '__main__':
    main()
