#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, re, urllib3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from db import DBHandler
urllib3.disable_warnings()

# Logger Config
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

# DB Config
db = DBHandler("logger.sqlite")

# Temp media_type -> italian text dictionary
media_texts = {"voice"    : " messaggio vocale",
               "photo"    : "'immagine",
               "sticker"  : "o sticker",
               "audio"    : "a traccia",
               "document" : " file",
               "gif"      : "a GIF"}


def cmd_start(bot, update):
    logged = db.log(update.message)
    chat = update.message.chat
    if chat.type == "private":
        text = "*Oneplus Community Custom Care* ti dà il benvenuto!\n" \
               "Sei registrato per le notifiche!"
        db.started_set(update.message.from_user.id)
        db.log(bot.sendMessage(chat.id, text, parse_mode=ParseMode.MARKDOWN))


def msg_parse(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        chat_id = message.chat.id
        logged = db.log(message)
        if logged["welcome_msg"] or logged["goodbye_msg"]:
            if logged["welcome_msg"]:
                msg = logged["welcome_msg"]
            else:
                msg = logged["goodbye_msg"]
            msg = re.sub(r"%username%", logged["welcome_goodbye_name"], msg)
            msg = re.sub(r"%chat%", message.chat.title, msg)
            db.log(bot.sendMessage(chat_id, msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True))
        if not message.chat.type == "private":
            admins = db.update_admins(bot.getChatAdministrators(chat_id), chat_id)
            fwd_from = None
            if message.forward_from:
                fwd_from = message.forward_from.id
            if not fwd_from == bot.id:
                notify = db.notify(message)
                keyboard = [[InlineKeyboardButton("Vai al messaggio", callback_data="goto.%s" % (notify["msg_id"]))]]
                if notify["chat_username"]:
                    keyboard = [[InlineKeyboardButton("Vai al messaggio", url="https://t.me/%s/%s" % (notify["chat_username"], notify["msg_id"]))]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                if notify["tag_to_notify"]:
                    for chat_id in notify["tag_to_notify"]:
                        text = "%s ti ha nominato in *%s*\n\n_%s_" % (notify["from_user"], notify["chat_title"], notify["msg_text"])
                        db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup))
                if notify["reply_to_notify"]:
                    text = "%s ti ha risposto in *%s*" % (notify["from_user"], notify["chat_title"])
                    if notify["msg_text"]:
                        text += "\n\n_%s_" % notify["msg_text"]
                        reply_markup_reply = reply_markup
                    else:
                        media_text = media_texts[notify["media_type"]]
                        if notify["doc_type"] == "video/mp4" or notify["doc_type"] == "video/webm":
                            media_text = media_texts["gif"]
                        text += " con un%s" % media_text
                        keyboard_media = keyboard + [[InlineKeyboardButton("Visualizza qui media", callback_data="showmedia.%s" % notify["media_id"])]]
                        reply_markup_reply = InlineKeyboardMarkup(keyboard_media)
                    db.log(bot.sendMessage(notify["reply_to_notify"], text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup_reply))
                if notify["admin_to_notify"]:
                    for admin_id in notify["admin_to_notify"]:
                        text = "%s ha chiamato un amministratore in *%s*\n\n_%s_" % (notify["from_user"], notify["chat_title"], notify["msg_text"])
                        db.log(bot.sendMessage(admin_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup))


def cmd_pin(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        logged = db.log(message)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        error = False
        message_id = None
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.getChatAdministrators(chat_id), chat_id)
                    if message.from_user.id in admins["admins_id"]:
                        is_admin = True
                    if is_admin:
                        pinned = db.get_pinned_msg(chat_id)
                        if pinned["msg_id"]:
                            if pinned["from_id"] == bot.id:
                                message_id = pinned["msg_id"]
                            else:
                                text = "Posso modificare il messaggio fissato solo è stato inviato da me, per favore fissa un mio messaggio."
                                error = True
                    else:
                        text = "Solo gli amministratori possono usare questa funzione."
                        error = True
                else:
                    text = "Non puoi usare questa funzione in una conversazione privata."
                    error = True
            else:
                text = "È necessario un testo dopo il comando."
                error = True
            if not error:
                db.log(bot.editMessageText(text=text, message_id=message_id, chat_id=chat_id, parse_mode=ParseMode.MARKDOWN))
            else:
                db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def cmd_markdown(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        logged = db.log(message)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                not_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.getChatAdministrators(chat_id), chat_id)
                    if not message.from_user.id in admins["admins_id"]: # To-Do: Configurable if only admin or not
                        not_admin = True
                if not_admin:
                    text = "Solo gli amministratori possono usare questa funzione."
            else:
                text = "È necessario un testo dopo il comando."
            if update.edited_message:
                msg_original = db.get_msg(chat_id, msg_id=message.message_id)
                cmd_text = re.search(cmd_regex, msg_original["msg"][0]["text"])
                msg_original = msg_original["msg"][0]["text"][cmd_text.end():].strip()
                msg_original_bot = db.get_msg(chat_id, text=msg_original, from_id=bot.id)
                db.log(bot.editMessageText(text, chat_id, msg_original_bot["msg"][0]["msg_id"], parse_mode=ParseMode.MARKDOWN))
            else:
                db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def cmd_welcome(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        logged = db.log(message)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.getChatAdministrators(chat_id), chat_id)
                    if message.from_user.id in admins["admins_id"]:
                        is_admin = True
                    if is_admin:
                        db.welcome_goodbye(chat_id, welcome_msg=text)
                        text = "Messaggio di benvenuto impostato."
                    else:
                        text = "Solo gli amministratori possono usare questa funzione."
                else:
                    text = "Non puoi usare questa funzione in una conversazione privata."
            else:
                text = "È necessario un testo dopo il comando."
            db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def cmd_goodbye(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        logged = db.log(message)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.getChatAdministrators(chat_id), chat_id)
                    if message.from_user.id in admins["admins_id"]:
                        is_admin = True
                    if is_admin:
                        db.welcome_goodbye(chat_id, goodbye_msg=text)
                        text = "Messaggio di arrivederci impostato."
                    else:
                        text = "Solo gli amministratori possono usare questa funzione."
                else:
                    text = "Non puoi usare questa funzione in una conversazione privata."
            else:
                text = "È necessario un testo dopo il comando."
            db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def cmd_clear_welcome(bot, update):
    message = update.message
    logged = db.log(message)
    chat_id = message.chat.id
    if not message.chat.type == "private":
        db.welcome_goodbye(chat_id, welcome_msg="")
        text = "Messaggio di benvenuto rimosso."
    else:
        text = "Non puoi usare questa funzione in una conversazione privata."
    db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def cmd_clear_goodbye(bot, update):
    message = update.message
    logged = db.log(message)
    chat_id = message.chat.id
    if not message.chat.type == "private":
        db.welcome_goodbye(chat_id, goodbye_msg="")
        text = "Messaggio di arrivederci rimosso."
    else:
        text = "Non puoi usare questa funzione in una conversazione privata."
    db.log(bot.sendMessage(chat_id, text, parse_mode=ParseMode.MARKDOWN))


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    updater = Updater("INSERT TOKEN HERE")
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("md", cmd_markdown, allow_edited=True))
    dp.add_handler(CommandHandler("markdown", cmd_markdown, allow_edited=True))
    dp.add_handler(CommandHandler("pin", cmd_pin, allow_edited=True))
    dp.add_handler(CommandHandler("welcome", cmd_welcome))
    dp.add_handler(CommandHandler("goodbye", cmd_goodbye))
    dp.add_handler(CommandHandler("del_welcome", cmd_clear_welcome))
    dp.add_handler(CommandHandler("del_goodbye", cmd_clear_goodbye))
    dp.add_handler(MessageHandler(Filters.audio |
                                  Filters.command |
                                  Filters.contact |
                                  Filters.document |
                                  Filters.photo |
                                  Filters.sticker |
                                  Filters.text |
                                  Filters.video |
                                  Filters.voice |
                                  Filters.status_update, msg_parse, allow_edited=True))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
