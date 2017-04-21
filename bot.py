#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, re, urllib3, mistune
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Unauthorized, BadRequest
from db import DBHandler
from time import time
from simple_renderer import SimplestRenderer
from pprint import pprint
urllib3.disable_warnings()

# Logger Config
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

# DB Config
db = DBHandler("logger.sqlite")

# Mistune markdown handler
renderer = SimplestRenderer()
markdown = mistune.Markdown(renderer=renderer)

# Temp media_type -> italian text dictionary
media_texts = {"voice"    : " messaggio vocale",
               "photo"    : "'immagine",
               "sticker"  : "o sticker",
               "audio"    : "a traccia",
               "document" : " file",
               "gif"      : "a GIF"}

# Temp option -> italian info dictionary, will remove this and above dictionary when translating process will begin
options_info = {"master"  : "Questo comodo interruttore ti permette di disattivare qualsiasi tipo di notifica da questo gruppo (o globalmente, nella relativa sezione) senza andare a intaccare le altre impostazioni!",
                "tag"     : "Questo interruttore, se attivato, ti permette di ricevere una notifica qualora vieni nominato (taggato) nel gruppo (o globalmente, nella relativa sezione) con il tuo @username.",
                "reply"   : "Questo interruttore, se attivato, ti permette di ricevere una notifica qualora qualcuno risponda ad un tuo messaggio in questo gruppo (o globalmente, nella relativa sezione)!",
                "hashtag" : "Con questo interruttore, quando attivo, ti invierò una notifica quando qualcuno utilizza un hashtag che tu hai aggiunto ai tuoi interessi di questo gruppo (o globalmente, nella relativa sezione.\nNella sezione precedente troverai \"Impostazioni Hashtag\", usalo per gestire gli hashtag di tuo interesse!",
                "pin"     : "Grazie a questo interruttore, quando attivo, riceverai una notifica quando un messaggio viene fissato su un gruppo (o globalmente, nella relativa sezione).",
                "silent"  : "Quando questo interruttore è attivo, le notifiche relative a questo gruppo (o globali, nell'apposita sezione), non produrranno suono di notifica, ma saranno sempre qui in questa chat ad aspettarti!"}


# Global variables for tracking user actions through inline menu
user_actions = {}
hashtag_set = {}
hashtag_remove = {}
feedback_leaving = []

def list_group(lst, n):
    result = ()
    temp = ()
    x = 1
    for i, item in enumerate(lst):
        temp += (item,)
        if x % n == 0:
            x = 1
            result += (temp,)
            temp = ()
        else:
            x += 1
        if i == len(lst) - 1 and temp:
            result += (temp,)
    return(result)


def markdown_escape(text):
    text = re.sub(r"([\*_`])", r"\\\g<1>", text)
    return(text)


def markdown_to_html(text):
    escape_newlines = re.sub(r"\n", "%%%%NEWLINE%%%%", text)
    escape_html = renderer.escape(text=escape_newlines)
    html = markdown(escape_html)
    restore_newlines = re.sub(r"%%%%NEWLINE%%%%", "\n", html)
    return(restore_newlines)


def send_media(bot, chat_id, media_type, media_id, text, reply_to_id=None):
    if media_type == "audio":
        bot.send_audio(chat_id=chat_id, audio=media_id, reply_to_message_id=reply_to_id)
    elif media_type == "document":
        bot.send_document(chat_id=chat_id, document=media_id, caption=text, reply_to_message_id=reply_to_id)
    elif media_type == "photo":
        bot.send_photo(chat_id=chat_id, photo=media_id, caption=text, reply_to_message_id=reply_to_id)
    elif media_type == "sticker":
        bot.send_sticker(chat_id=chat_id, sticker=media_id, reply_to_message_id=reply_to_id)
    elif media_type == "video":
        bot.send_video(chat_id=chat_id, video=media_id, caption=text, reply_to_message_id=reply_to_id)
    elif media_type == "voice":
        bot.send_voice(chat_id=chat_id, voice=media_id, reply_to_message_id=reply_to_id)


def cmd_start(bot, update):
    msg_parse(bot, update)
    chat = update.message.chat
    if chat.type == "private":
        text = "*Oneplus Community Custom Care* ti dà il benvenuto!\n" \
               "Sei registrato per le notifiche!\n" \
               "Usa /settings per aprire il pannello impostazioni, troverai anche un aiuto su come usare al meglio il bot!."
        db.started_set(update.message.from_user.id)
        db.log(bot.send_message(chat.id, markdown_to_html(text), parse_mode=ParseMode.HTML))


def msg_parse(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        chat_id = message.chat.id
        from_id = message.from_user.id
        msg_id = message.message_id
        logged = db.log(message)
        if message.new_chat_member:
            if message.new_chat_member.id == bot.id:
                bot_admins = db.get_bot_admin()
                if bot_admins["admins_id"] and not message.from_user.id in bot_admins["admins_id"]:
                    text = "Non sei uno dei miei amministratori, per favore contatta uno di loro per potermi aggiungere."
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML))
                    bot.leave_chat(chat_id)
                    return
        if logged["welcome_msg"] or logged["goodbye_msg"]:
            if logged["welcome_msg"]:
                msg = logged["welcome_msg"]
            else:
                msg = logged["goodbye_msg"]
            msg = re.sub(r"%username%", markdown_escape(logged["welcome_goodbye_name"]), msg)
            msg = re.sub(r"%chat%", markdown_escape(message.chat.title), msg)
            db.log(bot.send_message(chat_id, markdown_to_html(msg), parse_mode=ParseMode.HTML, disable_web_page_preview=True))
        if not message.chat.type == "private":
            admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
            fwd_from = None
            if message.forward_from:
                fwd_from = message.forward_from.id
            if not fwd_from == bot.id:
                to_notify = db.notify(message)
                keyboard = [[InlineKeyboardButton("Vai al messaggio", callback_data="goto.%s.%s" % (to_notify["chat_id"] ,to_notify["msg_id"]))]]
                if "chat_username" in to_notify:
                    keyboard = [[InlineKeyboardButton("Vai al messaggio", url="https://t.me/%s/%s" % (to_notify["chat_username"], to_notify["msg_id"]))]]
                for user_id,notify in to_notify["to_notify"].items():
                    keyboard_temp = []
                    text = "%s" % markdown_escape(to_notify["from_user"])
                    if notify["type"] == "reply":
                        text += " ti ha risposto"
                    elif notify["type"] == "tag":
                        text += " ti ha nominato"
                    elif notify["type"] == "admin_call":
                        text += " ha chiamato un admin"
                    elif notify["type"] == "pin":
                        text += " ha fissato"
                        if not to_notify["media_type"]:
                            text += " un messaggio"
                    text +=  " in *%s*" % to_notify["chat_title"]
                    if to_notify["media_type"]:
                        media_text = media_texts[to_notify["media_type"]]
                        if to_notify["doc_type"] == "video/mp4" or to_notify["doc_type"] == "video/webm":
                            media_text = media_texts["gif"]
                        if not notify["type"] == "pin":
                            text += " con"
                        text += " un%s" % media_text
                        keyboard_temp += [[InlineKeyboardButton("Visualizza qui media", callback_data="showmedia.%s.%s" % (chat_id, msg_id))]]
                    if "hashtag" in notify:
                        if not notify["type"] == "hashtag":
                            text += " ed"
                        if len(notify["hashtag"]) > 1:
                            text += " ha utilizzato degli hashtag di tuo interesse _(#%s)_" % (", #".join(notify["hashtag"]))
                        else:
                            text += " ha utlizzato un hashtag di tuo interesse _(#%s)_" % (", #".join(notify["hashtag"]))
                    if to_notify["text"]:
                        text += "\n\n"
                        if to_notify["media_type"]:
                            text += "Didascalia: "
                        text += "_%s_" % to_notify["text"]
                    reply_markup = InlineKeyboardMarkup(keyboard + keyboard_temp)
                    disable_notification = False
                    if "silent" in notify:
                        disable_notification = notify["silent"]
                    if edited:
                        original_msg = db.get_msg(user_id, linked_chat_id=to_notify["chat_id"], linked_msg_id=to_notify["msg_id"])
                        original_msg = original_msg["msg"][0]
                        db.log(bot.edit_message_text(markdown_to_html(text), user_id, original_msg["msg_id"], parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_notification=disable_notification))
                    else:
                        try:
                            db.log(bot.send_message(user_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_notification=disable_notification), link_chat_id=chat_id, link_msg_id=msg_id)
                        except Unauthorized:
                            db.started_set(user_id, reset=True)
                regex_shortcut = r"^!\w+$"
                if re.search(regex_shortcut, message.text):
                    if message.text[:1] == "!":
                        shortcut_name = message.text[1:]
                    else:
                        shortcut_name = message.text
                    shortcut = db.shortcut(chat_id, name=shortcut_name)
                    if shortcut["shortcut"]:
                        shortcut = shortcut["shortcut"]
                        if message.reply_to_message:
                            reply_to_id = message.reply_to_message.message_id
                        else:
                            reply_to_id = message.message_id
                        text = shortcut["text"]
                        if shortcut["media_id"]:
                            send_media(bot, chat_id, shortcut["media_type"], shortcut["media_id"], text, reply_to_id)
                        else:
                            if edited:
                                msg_original_bot = db.get_msg(chat_id, reply_to=reply_to_id, from_id=bot.id)
                                if msg_original_bot["msg"]:
                                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_original_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML, disable_web_page_preview=True))
                                else:
                                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_id, disable_web_page_preview=True))
                            else:
                                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_id, disable_web_page_preview=True))
        else:
            text = ""
            keyboard = []
            if from_id in hashtag_set or from_id in hashtag_remove:
                regex_hashtag = r"#\w+"
                msg_hashtags = re.finditer(regex_hashtag, message.text, re.MULTILINE)
                tags = ()
                for msg_hashtag in msg_hashtags:
                    tag = msg_hashtag.group()[1:]
                    tags += (tag,)
                hashtag_chat_id = None
                if from_id in hashtag_set:
                    hashtag_chat_id = hashtag_set[from_id]
                    hashtags = db.hashtags(chat_id=hashtag_chat_id, user_id=from_id, hashtags=tags)
                elif from_id in hashtag_remove:
                    hashtag_chat_id = hashtag_remove[from_id]
                    hashtags = db.hashtags(chat_id=hashtag_chat_id, user_id=from_id, hashtags=tags, remove=True)
                if hashtags:
                    if hashtags["hashtags_added"]:
                        text += "\n\nI seguenti hashtag sono stati aggiunti:\n_#%s_" % ", #".join(hashtags["hashtags_added"])
                    if hashtags["hashtags_not_added"]:
                        text += "\n\nI seguenti hashtag erano già presenti e pertanto non sono stati aggiunti:\n_#%s_" % ", #".join(hashtags["hashtags_not_added"])
                    if hashtags["hashtags_removed"]:
                        text += "\n\nI seguenti hashtag sono stati rimossi:\n_#%s_" % ", #".join(hashtags["hashtags_removed"])
                    if hashtags["hashtags_not_removed"]:
                        text += "\n\nI seguenti hashtag non erano presenti e pertanto non sono stati rimossi:\n_#%s_" % ", #".join(hashtags["hashtags_not_removed"])
                    if hashtags["hashtags_added"] or hashtags["hashtags_not_added"]:
                        text += "\n\nMandami altri hashtag da aggiungere o usa il bottone qui sotto per tornare indietro!"
                    if hashtags["hashtags_removed"] or hashtags["hashtags_not_removed"]:
                        text += "\n\nMandami altri hashtag da rimuovere o usa il bottone qui sotto per tornare indietro!"
                    keyboard += [[InlineKeyboardButton("Indietro", callback_data="settings.hashtags.%s" % hashtag_chat_id)]]
            elif from_id in feedback_leaving:
                db.feedback_add(from_id, msg_id)
                feedback_leaving.remove(from_id)
                text = "Inviato! Grazie per il tuo supporto!"
                keyboard += [[InlineKeyboardButton("Indietro", callback_data="main")]]
            if text:
                reply_markup = InlineKeyboardMarkup(keyboard)
                db.log(bot.send_message(from_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_markup=reply_markup))


def cmd_pin(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
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
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
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
                db.log(bot.edit_message_text(text=markdown_to_html(text), message_id=message_id, chat_id=chat_id, parse_mode=ParseMode.HTML))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML))


def cmd_markdown(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                not_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
                    if not message.from_user.id in admins["admins_id"]: # To-Do: Configurable if only admin or not
                        not_admin = True
                if not_admin:
                    text = "Solo gli amministratori possono usare questa funzione."
            else:
                text = "È necessario un testo dopo il comando."
            if message.reply_to_message:
                reply_to_id = message.reply_to_message.message_id
            else:
                reply_to_id = message.message_id
            if edited:
                msg_original_bot = db.get_msg(chat_id, reply_to=reply_to_id, from_id=bot.id)
                if msg_original_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_original_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML, disable_web_page_preview=True))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_id, disable_web_page_preview=True))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_id, disable_web_page_preview=True))


def cmd_welcome(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
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
            if edited:
                msg_bot = db.get_msg(chat_id, from_id=bot.id, reply_to=message.message_id)
                if msg_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))


def cmd_goodbye(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
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
            if edited:
                msg_bot = db.get_msg(chat_id, from_id=bot.id, reply_to=message.message_id)
                if msg_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))


def cmd_clear_welcome(bot, update):
    message = update.message
    msg_parse(bot, update)
    chat_id = message.chat.id
    if not message.chat.type == "private":
        db.welcome_goodbye(chat_id, welcome_msg="")
        text = "Messaggio di benvenuto rimosso."
    else:
        text = "Non puoi usare questa funzione in una conversazione privata."
    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML))


def cmd_clear_goodbye(bot, update):
    message = update.message
    msg_parse(bot, update)
    chat_id = message.chat.id
    if not message.chat.type == "private":
        db.welcome_goodbye(chat_id, goodbye_msg="")
        text = "Messaggio di arrivederci rimosso."
    else:
        text = "Non puoi usare questa funzione in una conversazione privata."
    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML))


def cmd_set_bot_admin(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        bot_admins = db.get_bot_admin()
        from_id = message.from_user.id
        text = ""
        if not bot_admins["admins_id"]:
            db.set_bot_admin(from_id)
            text = "Ti sei impostato come creatore del bot."
        else:
            if message.reply_to_message:
                reply_to_id = message.reply_to_message.from_user.id
                if not reply_to_id == bot.id and not reply_to_id == from_id and not reply_to_id in bot_admins["admins_id"]:
                    user_info = db.get_user(message.from_user.id)
                    if user_info["user"]:
                        if user_info["user"]["bot_admin"] == 1:
                            db.set_bot_admin(reply_to_id)
                            text = "Utente impostato come amministratore del bot."
                        else:
                            text = "Non hai il permesso di farlo."
        if text:
            bot.send_message(message.chat.id, markdown_to_html(text), reply_to_message_id=message.message_id, parse_mode=ParseMode.HTML)


def cmd_remove_bot_admin(bot, update):
    if update.message:
        message = update.message
    elif update.edited_message:
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        bot_admins = db.get_bot_admin()
        bot_admins_id = bot_admins["admins_id"]
        from_id = message.from_user.id
        text = ""
        if bot_admins_id:
            if message.reply_to_message:
                reply_to_id = message.reply_to_message.from_user.id
                if not reply_to_id == bot.id and not reply_to_id == from_id:
                    user_info = db.get_user(from_id)
                    if user_info["user"]["bot_admin"] == 1:
                        if reply_to_id in bot_admins_id:
                            db.remove_bot_admin(reply_to_id)
                            text = "Utente rimosso da amministratore del bot."
                    else:
                        text = "Non hai il permesso di farlo."
        if text:
            bot.send_message(message.chat.id, markdown_to_html(text), reply_to_message_id=message.message_id, parse_mode=ParseMode.HTML)


def cmd_shortcut_set(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        error_msg = "È necessario indicare dopo il comando il nome della scorciatoia e il testo della scorciatoia, oppure rispondere ad un messaggio con solo il nome della scorciatoia.\n\n_Esempio: /shortcut !GuidaScorciatoia Questo è il testo che verrà mostrato quando si invocherà !GuidaScorciatoia_"
        if cmd_text:
            text = message.text[cmd_text.end():].strip().split(maxsplit=1)
            if (len(text) >= 2) or (len(text) >= 1 and message.reply_to_message):
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
                    if message.from_user.id in admins["admins_id"]:
                        is_admin = True
                    if is_admin:
                        shortcut = None
                        if text[0][:1] == "!":
                            shortcut_name = text[0][1:]
                        else:
                            shortcut_name = text[0]
                        if message.reply_to_message:
                            media_info = db._get_media(message.reply_to_message)
                            if media_info["media_id"]:
                                shortcut = db.shortcut(chat_id, name=shortcut_name, content=media_info)
                            else:
                                shortcut = db.shortcut(chat_id, name=shortcut_name, content=media_info["text"])
                        elif len(text) >= 2:
                            shortcut = db.shortcut(chat_id, name=shortcut_name, content=text[1])
                        else:
                            text = error_msg
                        if shortcut:
                            if shortcut["action"] == "added":
                                text = "Scorciatoia impostata."
                            elif shortcut["action"] == "modified":
                                text = "Scorciatoia modificata."
                            else:
                                text = "Comportamento anomalo, contattare il mio sviluppatore!"
                    else:
                        text = "Solo gli amministratori possono usare questa funzione."
                else:
                    text = "Non puoi usare questa funzione in una conversazione privata."
            else:
                text = error_msg
            if edited:
                msg_bot = db.get_msg(chat_id, from_id=bot.id, reply_to=message.message_id)
                if msg_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))


def cmd_shortcut_del(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if text:
                is_admin = False
                if not chat_type == "private":
                    admins = db.update_admins(bot.get_chat_administrators(chat_id), chat_id)
                    if message.from_user.id in admins["admins_id"]:
                        is_admin = True
                    if is_admin:
                        if text[0][:1] == "!":
                            shortcut_name = text[1:]
                        else:
                            shortcut_name = text
                        shortcut = db.shortcut(chat_id, name=shortcut_name, remove=True)
                        if shortcut["action"] == "removed":
                            text = "Scorciatoia rimossa."
                        elif shortcut["action"] == "not_removed":
                            text = "La scorciatoia indicata non esiste."
                        else:
                            text = "Comportamento anomalo, contattare il mio sviluppatore!"
                    else:
                        text = "Solo gli amministratori possono usare questa funzione."
                else:
                    text = "Non puoi usare questa funzione in una conversazione privata."
            else:
                text = "È necessario indicare dopo il comando il nome della scorciatoia da rimuovere."
            if edited:
                msg_bot = db.get_msg(chat_id, from_id=bot.id, reply_to=message.message_id)
                if msg_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))


def cmd_shortcut_getall(bot, update):
    edited = False
    if update.message:
        message = update.message
    elif update.edited_message:
        edited = True
        message = update.edited_message
    else:
        message = None
    if message:
        msg_parse(bot, update)
        chat_id = message.chat.id
        chat_type = message.chat.type
        cmd_regex = r"^/\w+"
        cmd_text = re.search(cmd_regex, message.text)
        if cmd_text:
            text = message.text[cmd_text.end():].strip()
            if not chat_type == "private":
                shortcuts_db = db.shortcut(chat_id)
                if shortcuts_db["action"] == "get_all" and isinstance(shortcuts_db["shortcut"], tuple):
                    if shortcuts_db["shortcut"]:
                        shortcuts = ()
                        for shortcut in shortcuts_db["shortcut"]:
                            print(shortcut["name"])
                            shortcuts += (shortcut["name"],)
                        text = "Scorciatoie impostate per questa chat:\n\n*!%s*" % (", !".join(shortcuts))
                    else:
                        text = "Non ci sono scorciatoie impostate per questa chat."
            else:
                text = "Non puoi usare questa funzione in una conversazione privata."
            if edited:
                msg_bot = db.get_msg(chat_id, from_id=bot.id, reply_to=message.message_id)
                if msg_bot:
                    db.log(bot.edit_message_text(markdown_to_html(text), chat_id, msg_bot["msg"][0]["msg_id"], parse_mode=ParseMode.HTML))
                else:
                    db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))
            else:
                db.log(bot.send_message(chat_id, markdown_to_html(text), parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id))



def cmd_settings(bot, update):
    message = update.message
    msg_parse(bot, update)
    text = ""
    keyboard = []
    if message.chat.type == "private":
        text = "Cosa vuoi impostare?"
        keyboard += [[InlineKeyboardButton("Impostazioni globali", callback_data="settings.set.0"),
                      InlineKeyboardButton("Impostazioni per gruppo", callback_data="settings.groups")]]
        keyboard += [[InlineKeyboardButton("Aiuto", callback_data="help.main")]]
        keyboard += [[InlineKeyboardButton("Lascia un suggerimento", callback_data="feedback.leave"),
                      InlineKeyboardButton("Informazioni sviluppatore", callback_data="dev.info")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(message.chat.id, markdown_to_html(text), reply_to_message_id=message.message_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


def inline_button_callback(bot, update):
    max_button_lenght = 25
    button_per_line = 3
    max_button_lines = 6
    query = update.callback_query
    query_id = query.id
    answer_text = ""
    from_user = query.from_user
    from_id = from_user.id
    if from_id in hashtag_set:
        del hashtag_set[from_id]
    if from_id in hashtag_remove:
        del hashtag_remove[from_id]
    if from_id in feedback_leaving:
        feedback_leaving.remove(from_id)
    text = ""
    keyboard = []
    new_msg = False
    media_type = None
    media_id = None
    chat_id = query.message.chat_id
    query_data = query.data.split(".")
    if query_data[0] == "settings":
        if query_data[1] == "groups":
            groups = db.get_user_groups(from_id)
            if groups["groups"]:
                text = "Quale dei gruppi vuoi impostare?"
                pages = list_group(groups["groups"], button_per_line)
                pages = list_group(pages, max_button_lines)
                page = 1
                if len(pages) > 1 and len(query_data) > 2:
                    page = int(query_data[2])
                for groups in pages[page - 1]:
                    temp = []
                    for group in groups:
                        if len(group["title"]) > max_button_lenght:
                            button_text = "%s [...]" % (group["title"][:max_button_lenght].strip())
                        else:
                            button_text = "%s" % (group["title"][:max_button_lenght].strip())
                        temp += [InlineKeyboardButton(button_text, callback_data="settings.set.%s" % group["id"])]
                    keyboard += [temp]
                if len(pages) > 1:
                    temp = []
                    if page > 1:
                        temp += [InlineKeyboardButton("Pagina precedente", callback_data="settings.groups.%s" % (page - 1))]
                    if not page == len(pages):
                        temp += [InlineKeyboardButton("Pagina successiva", callback_data="settings.groups.%s" % (page + 1))]
                    keyboard += [temp]
            else:
                text = "Non hai nessun gruppo da impostare."
            keyboard += [[InlineKeyboardButton("Indietro", callback_data="main")]]
        elif query_data[1] == "set":
            text = "Cosa vuoi impostare?"
            if len(query_data) > 3:
                if query_data[2] == "0":
                    db.toggle_user_option(from_id, query_data[3])
                else:
                    db.toggle_user_option(from_id, query_data[3], query_data[2])
            if query_data[2] == "0":
                options = db.get_user_options(from_id)
            else:
                options = db.get_user_options(from_id, query_data[2])
            for option in options["options_all"]:
                if option in options["options_true"]:
                    flag = "✅"
                else:
                    flag = "❌"
                keyboard += [[InlineKeyboardButton("%s %s" % (flag, options["options_text"][option]), callback_data="settings.set.%s.%s" % (query_data[2], option)),
                              InlineKeyboardButton("Aiuto %s" % (options["options_text"][option]), callback_data="info.%s.%s" % (option, query_data[2]))]]
            keyboard += [[InlineKeyboardButton("Impostazioni hashtag", callback_data="settings.hashtags.%s" % query_data[2])]]
            if query_data[2] == "0":
                keyboard += [[InlineKeyboardButton("Torna indietro", callback_data="main")]]
            else:
                keyboard += [[InlineKeyboardButton("Torna indietro", callback_data="settings.groups")]]
        elif query_data[1] == "hashtags":
            if len(query_data) > 3:
                if query_data[3] == "add":
                    hashtag_set[from_id] = query_data[2]
                    text = "Bene, inviami l'hashtag o gli hashtag che *vuoi seguire*, separati da uno spazio.\n\n_Esempio: #telegram #android #calcio_"
                elif query_data[3] == "remove":
                    hashtag_remove[from_id] = query_data[2]
                    text = "Bene, inviami l'hashtag o gli hashtag che *non vuoi più seguire*, separati da uno spazio.\n\n_Esempio: #whatsapp #iphone #calcio_"
                keyboard += [[InlineKeyboardButton("Indietro", callback_data="settings.hashtags.%s" % query_data[2])]]
            else:
                hashtags = db.hashtags(chat_id=query_data[2], user_id=from_id)
                temp = [InlineKeyboardButton("Aggiungi hashtag", callback_data="settings.hashtags.%s.add" % query_data[2])]
                if hashtags["hashtags"]:
                    text = "Ecco gli hashtag che hai impostasto per questa chat:\n_#%s_" % ", #".join(hashtags["hashtags"])
                    temp += [InlineKeyboardButton("Rimuovi hashtag", callback_data="settings.hashtags.%s.remove" % query_data[2])]
                else:
                    text = "Non hai ancora impostato nessun hashtag, usa il bottone qui sotto per impostarne qualcuno."
                keyboard += [temp]
                keyboard += [[InlineKeyboardButton("Indietro", callback_data="settings.set.%s" % query_data[2])]]
    elif query_data[0] == "main":
        text = "Cosa vuoi impostare?"
        keyboard += [[InlineKeyboardButton("Impostazioni globali", callback_data="settings.set.0"),
                      InlineKeyboardButton("Impostazioni per gruppo", callback_data="settings.groups")]]
        keyboard += [[InlineKeyboardButton("Aiuto", callback_data="help.main")]]
        keyboard += [[InlineKeyboardButton("Lascia un suggerimento", callback_data="feedback.leave"),
                      InlineKeyboardButton("Informazioni sviluppatore", callback_data="dev.info")]]
    elif query_data[0] == "info":
        text = options_info[query_data[1]]
        keyboard += [[InlineKeyboardButton("Indietro", callback_data="settings.set.%s" % query_data[2])]]
    elif query_data[0] == "feedback":
        if query_data[1] == "leave":
            feedback_leaving.append(from_id)
            text = "Vuoi lasciare un suggerimento, riportare un errore, o semplicemente scrivere qualcosa? Invialo nel messaggio successivo!\nOppure torna indietro..."
            keyboard += [[InlineKeyboardButton("Indietro", callback_data="main")]]
    elif query_data[0] == "dev":
        if query_data[1] == "info":
            text += "Bot sviluppato interamente da @Kyraminol.\n" \
                    "Puro cuore Phytonico, con un pizzico di SQLite.\n" \
                    "Ringrazio @jh0ker per il fantastico wrapper.\n\n" \
                    "*Questo bot è totalmente open source*, non come una certa nicchia che si professa \"open\" e di open non ha niente.\n" \
                    "[Premi qui per andare alla pagina del progetto](https://github.com/Kyraminol/JackOfAllGroups-telegram-bot)."
            keyboard += [[InlineKeyboardButton("Indietro", callback_data="main")]]
    elif query_data[0] == "showmedia":
        new_msg = True
        msg = db.get_msg(chat_id=query_data[1], msg_id=query_data[2])
        msg = msg["msg"][0]
        print(msg)
        media_id = msg["media_id"]
        media_type = msg["media_type"]
        text = msg["text"]
    elif query_data[0] == "help":
        if query_data[1] == "main":
            text = "Ecco una piccola guida su come impostarmi, è tutto molto semplice!\n\n" \
                   "Nella sezione *Impostazioni per gruppo* troverai una lista di tutti i gruppi in cui sei presente, " \
                   "qui puoi impostare che tipo di notifiche vuoi ricevere gruppo per gruppo, così da non sovraccaricarti" \
                   "di notiche che non ti interessano! La descrizione su cosa attiva o disattiva un bottone si trova di" \
                   "fianco al bottone stesso, facci un salto!\n\n" \
                   "Nella sezione *Impostazioni globali* troverai un modo comodo per attivare o disattivare qualche impostazione " \
                   "per tutti i gruppi in cui sei presente, e queste impostazioni *avranno la precedenza* di quelle _per gruppo_, " \
                   "ad esempio disattivando qui l'_interruttore principale_, *non riceverai più notifiche*, oppure disattivando " \
                   "l'interruttore _menzioni_, nessuna menzione, nessun \"@tag\" ti verrà notificato!\n\n" \
                   "Se vuoi lasciare un suggerimento, qualsiasi cosa, ti invito ad usare il bottone nel menù principale. " \
                   "Ogni consiglio è sempre ben accetto e serve a far crescere questo bot!"
            keyboard += [[InlineKeyboardButton("Indietro", callback_data="main")]]
    elif query_data[0] == "goto":
        msg = db.get_msg(chat_id=query_data[1], msg_id=query_data[2])
        if time() - msg["msg"][0]["timestamp"] < 20:
            answer_text = "Il messaggio è stato inviato da poco, controlla il gruppo!"
        else:
            if from_user.username:
                name = "@%s" % from_user.username
            else:
                name = from_user.first_name
            goto_text = "%s ecco il tuo messaggio!\n#id%s" % (name, from_id)
            try:
                bot.send_message(text=goto_text, chat_id=query_data[1], reply_to_message_id=query_data[2])
                new_msg = True
                text = "Vai nel gruppo, c'è un mio messaggio che ti attende!\nPremi qui sotto per trovarlo più in fretta!\n-> #id%s <-" % from_id
            except BadRequest:
                answer_text = "Il messaggio originale è stato eliminato!"
    reply_markup = InlineKeyboardMarkup(keyboard)
    if text or media_type:
        if new_msg:
            if media_type:
                send_media(bot, chat_id, media_type, media_id, text, query.message.message_id)
            else:
                bot.send_message(text=markdown_to_html(text), chat_id=chat_id, message_id=query.message.message_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview="true")
        else:
            if query.message:
                bot.edit_message_text(text=markdown_to_html(text), chat_id=chat_id, message_id=query.message.message_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview="true")
            else:
                bot.edit_message_text(text=markdown_to_html(text), inline_message_id=query.inline_message_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview="true")
    bot.answer_callback_query(callback_query_id=query.id, text=answer_text)


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    updater = Updater("INSERT TOKEN HERE")
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("md", cmd_markdown, allow_edited=True))
    dp.add_handler(CommandHandler("markdown", cmd_markdown, allow_edited=True))
    dp.add_handler(CommandHandler("pin", cmd_pin, allow_edited=True))
    dp.add_handler(CommandHandler("welcome", cmd_welcome, allow_edited=True))
    dp.add_handler(CommandHandler("goodbye", cmd_goodbye, allow_edited=True))
    dp.add_handler(CommandHandler("del_welcome", cmd_clear_welcome))
    dp.add_handler(CommandHandler("del_goodbye", cmd_clear_goodbye))
    dp.add_handler(CommandHandler("set_bot_admin", cmd_set_bot_admin, allow_edited=True))
    dp.add_handler(CommandHandler("remove_bot_admin", cmd_remove_bot_admin, allow_edited=True))
    dp.add_handler(CommandHandler("settings", cmd_settings))
    dp.add_handler(CommandHandler("shortcut", cmd_shortcut_set, allow_edited=True))
    dp.add_handler(CommandHandler("del_shortcut", cmd_shortcut_del, allow_edited=True))
    dp.add_handler(CommandHandler("shortcuts", cmd_shortcut_getall, allow_edited=True))
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
    dp.add_handler(CallbackQueryHandler(inline_button_callback))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
