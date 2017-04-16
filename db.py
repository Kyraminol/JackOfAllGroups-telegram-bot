#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, sqlite3, re
from datetime import datetime
from flags import Flags


class NotifyOptions(Flags):
    master = ("Interruttore generale",)
    tag = ("Menzioni",)
    reply = ("Risposte",)
    hashtag = ("Hashtag",)
    pin = ("Messaggi fissati",)
    silent = ("Notifiche silenziose",)



class DBHandler:
    def __init__(self, path):
        self._dbpath = path

    def log(self, message, link_chat_id=None, link_msg_id=None):
        start_time = time.time()
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        result = {"task_name"   : "log",
                  "welcome_msg" : None,
                  "goodbye_msg" : None}
        # Update User
        user_info = cursor.execute("SELECT * FROM users WHERE id=?", (message.from_user.id,)).fetchone()
        query_user = (message.from_user.first_name,
                      message.from_user.last_name,
                      message.from_user.username,
                      message.from_user.id)
        if user_info:
            cursor.execute("UPDATE users SET first_name=?,last_name=?,username=? WHERE id=?", query_user)
        else:
            query_user += (int(NotifyOptions.all_flags - NotifyOptions.silent),)
            cursor.execute("INSERT INTO users(first_name,last_name,username,id,options) VALUES(?,?,?,?,?)", query_user)
        # Update Chat
        chat_info = cursor.execute("SELECT * FROM chats WHERE id=?", (message.chat.id,)).fetchone()
        query_chat = (message.chat.title,
                      message.chat.type,
                      message.chat.id)
        if chat_info:
            cursor.execute("UPDATE chats SET title=?,type=? WHERE id=?", query_chat)
        else:
            cursor.execute("INSERT INTO chats(title,type,id) VALUES(?,?,?)", query_chat)
        # Insert Log
        fwd_from_chat = None
        fwd_from_user = None
        replyto_id = None
        pinned_id = None
        get_media = self._get_media(message)
        text = get_media["text"]
        media_id = get_media["media_id"]
        media_type = get_media["media_type"]
        doc_type = get_media["doc_type"]
        if message.forward_from:
            fwd_from_user = message.forward_from.id
        if message.forward_from_chat:
            fwd_from_chat = message.forward_from_chat.id
        if message.reply_to_message:
            replyto_id = message.reply_to_message.message_id
        if message.pinned_message:
            pinned_id = message.pinned_message.message_id
        query_log = (message.from_user.id,
                     message.chat.id,
                     message.message_id,
                     media_id,
                     media_type,
                     doc_type,
                     text,
                     fwd_from_chat,
                     fwd_from_user,
                     time.mktime(message.date.timetuple()),
                     replyto_id,
                     pinned_id,
                     link_chat_id,
                     link_msg_id)
        if text or media_type or pinned_id:
            cursor.execute("INSERT INTO logs(from_id,chat_id,msg_id,media_id,media_type,doc_type,text,fwd_from_chat,fwd_from_user,date,replyto_id,pinned_id, linked_chat_id, linked_msg_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", query_log)
        # User List
        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.from_user.id)).fetchone()
        if message.left_chat_member:
            cursor.execute("UPDATE users_chats SET leaved=1 WHERE chat_id=? AND user_id=?", (message.chat.id, message.left_chat_member.id))
            needs_goodbye = cursor.execute("SELECT goodbye_msg FROM chats WHERE id=?", (message.chat.id,)).fetchone()
            if needs_goodbye:
                result["goodbye_msg"] = needs_goodbye["goodbye_msg"]
                if message.left_chat_member.username:
                    result["welcome_goodbye_name"] = "@%s" % message.left_chat_member.username
                else:
                    result["welcome_goodbye_name"] = "%s" % message.left_chat_member.first_name
        if message.new_chat_member:
            user_chat_new_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.new_chat_member.id)).fetchone()
            if not user_chat_new_info:
                cursor.execute("INSERT INTO users_chats(user_id,chat_id,options) VALUES(?,?,?)", (message.new_chat_member.id, message.chat.id,int(NotifyOptions.all_flags - NotifyOptions.silent)))
            user_info_new = cursor.execute("SELECT * FROM users WHERE id=?", (message.new_chat_member.id,)).fetchone()
            if not user_info_new:
                query_user_new = (message.new_chat_member.id,
                                  message.new_chat_member.first_name,
                                  message.new_chat_member.last_name,
                                  message.new_chat_member.username,)
                cursor.execute("INSERT INTO users(id,first_name,last_name,username) VALUES(?,?,?,?)", query_user_new)
            needs_welcome = cursor.execute("SELECT welcome_msg FROM chats WHERE id=?", (message.chat.id,)).fetchone()
            if needs_welcome:
                result["welcome_msg"] = needs_welcome["welcome_msg"]
                if message.new_chat_member.username:
                    result["welcome_goodbye_name"] = "@%s" % message.new_chat_member.username
                else:
                    result["welcome_goodbye_name"] = "%s" % message.new_chat_member.first_name
        if not user_chat_info:
            query_user_chat = (message.from_user.id,
                               message.chat.id,
                               int(NotifyOptions.all_flags - NotifyOptions.silent),)
            cursor.execute("INSERT INTO users_chats(user_id,chat_id,options) VALUES(?,?,?)", query_user_chat)
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def update_admins(self, admins, chat):
        start_time = time.time()
        result = {"task_name": "admin_update"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        admins_id = ()
        admins_full = ()
        for admin in admins:
            admins_id += (admin.user.id,)
            admins_full += ({"first_name": admin.user.first_name,
                             "last_name" : admin.user.last_name,
                             "username"  : admin.user.username,
                             "id"        : admin.user.id,
                             "status"    : admin.status},)
            # User
            user_info = cursor.execute("SELECT * FROM users WHERE id=?", (admin.user.id,)).fetchone()
            query_user = (admin.user.first_name,
                          admin.user.last_name,
                          admin.user.username,
                          admin.user.id)
            if user_info:
                cursor.execute("UPDATE users SET first_name=?,last_name=?,username=? WHERE id=?", query_user)
            else:
                query_user += (int(NotifyOptions.all_flags - NotifyOptions.silent),)
                cursor.execute("INSERT INTO users(first_name,last_name,username,id,options) VALUES(?,?,?,?,?)", query_user)
            # User_chat
            user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=?", (admin.user.id, chat)).fetchone()
            query_user_chat_add = (admin.status,
                                   admin.user.id,
                                   chat,)
            if user_chat_info:
                cursor.execute("UPDATE users_chats SET status=? WHERE user_id=? AND chat_id=?", query_user_chat_add)
            else:
                query_user_chat_add += (int(NotifyOptions.all_flags - NotifyOptions.silent),)
                cursor.execute("INSERT INTO users_chats(status,user_id,chat_id,options) VALUES(?,?,?,?)", query_user_chat_add)
        # Remove old admins
        old_admins = cursor.execute("SELECT user_id FROM users_chats WHERE chat_id=? AND (status='creator' OR status='administrator')", (chat,)).fetchall()
        for admin in old_admins:
            if admin["user_id"] not in admins_id:
                cursor.execute("UPDATE users_chats SET status='member' WHERE user_id=? AND chat_id=?", (admin["user_id"], chat,))
        handle.commit()
        result["admins_id"] = admins_id
        result["admin_full"] = admins_full
        result["exec_time"] = time.time() - start_time
        return(result)

    def log_get(self, chat_id, datetime_from, datetime_to=datetime.utcnow()):
        start_time = time.time()
        result = {"task_name": "log_get"}
        query_result = {}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        query = (chat_id,
                (datetime_from - datetime(1970,1,1)).total_seconds(),
                (datetime_to   - datetime(1970,1,1)).total_seconds(),)
        msgs = cursor.execute("SELECT * FROM logs WHERE chat_id=? AND date>=? AND date<=?", query).fetchall()
        query_result["msg_count"] = len(msgs)
        for msg in msgs:
            print(msg)
        result["query_result"] = query_result
        result["exec_time"] = time.time() - start_time
        return(result)

    def started_set(self, user_id, reset=False):
        start_time = time.time()
        result = {"task_name": "set_started"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        cursor.execute("UPDATE users SET started=? WHERE id=?", (int(not reset), user_id,))
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def notify(self, message):
        start_time = time.time()
        result = {"task_name": "notify"}
        to_notify = {}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        chat_id = message.chat.id
        from_id = message.from_user.id
        if message.from_user.username:
            from_user = "@%s" % message.from_user.username
        else:
            from_user = message.from_user.first_name
        if message.pinned_message:
            get_media = self._get_media(message.pinned_message)
            text = get_media["text"]
            media_type = get_media["media_type"]
            doc_type = get_media["doc_type"]
            chat_id = message.pinned_message.chat.id
            users_db = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND leaved IS NULL", (chat_id,)).fetchall()
            for user_db in users_db:
                user_id = user_db["user_id"]
                user_options_global = self.get_user_options(user_id)
                user_options_global = user_options_global["options_true"]
                if "master" in user_options_global and "pin" in user_options_global:
                    user_options_chat = self.get_user_options(user_id, chat_id)
                    user_options_chat = user_options_chat["options_true"]
                    if "master" in user_options_chat and "pin" in user_options_chat:
                        user_info = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                        if user_info["started"] == 1 and not user_id == from_id:
                            if not user_id in to_notify:
                                to_notify[user_id] = {"type" : "pin"}
                                if "silent" in user_options_global or "silent" in user_options_chat:
                                    to_notify[user_id]["silent"] = True
        else:
            get_media = self._get_media(message)
            text = get_media["text"]
            media_type = get_media["media_type"]
            doc_type = get_media["doc_type"]
            if message.reply_to_message:
                user_id = message.reply_to_message.from_user.id
                user_options_global = self.get_user_options(user_id)
                user_options_global = user_options_global["options_true"]
                if "master" in user_options_global and "reply" in user_options_global:
                    user_options_chat = self.get_user_options(user_id, chat_id)
                    user_options_chat = user_options_chat["options_true"]
                    if "master" in user_options_chat and "reply" in user_options_chat:
                        user_info = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=? AND leaved IS NULL", (user_id, chat_id)).fetchone()
                        if user_info["started"] == 1 and user_chat_info and not user_id == from_id:
                            if not user_id in to_notify:
                                to_notify[user_id] = {"type" : "reply"}
                                if "silent" in user_options_global or "silent" in user_options_chat:
                                    to_notify[user_id]["silent"] = True
            if text:
                    regex_tag = r"@\w+"
                    regex_hashtag = r"#\w+"
                    tags = re.finditer(regex_tag, text, re.MULTILINE)
                    for tag in tags:
                        username = tag.group()
                        if username == "@admin":
                            admin_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND (status='creator' OR status='administrator') AND leaved IS NULL", (chat_id,)).fetchall()
                            for admin in admin_chat_info:
                                user_id = admin["user_id"]
                                if not user_id == from_id:
                                    if not user_id in to_notify:
                                        to_notify[user_id] = {"type" : "admin_call"}
                        else:
                            user_info = cursor.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (username[1:],)).fetchone()
                            if user_info:
                                user_id = user_info["id"]
                                user_options_global = self.get_user_options(user_id)
                                user_options_global = user_options_global["options_true"]
                                silent = False
                                if "master" in user_options_global and "tag" in user_options_global:
                                    user_options_chat = self.get_user_options(user_id, chat_id)
                                    user_options_chat = user_options_chat["options_true"]
                                    if "master" in user_options_chat and "tag" in user_options_chat:
                                        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=? AND leaved IS NULL", (user_id, chat_id)).fetchone()
                                        if user_info["started"] == 1 and user_chat_info and not user_id == from_id:
                                            if not user_id in to_notify:
                                                to_notify[user_id] = {"type" : "tag"}
                                                if "silent" in user_options_global or "silent" in user_options_chat:
                                                    to_notify[user_id]["silent"] = True
                    hashtags = re.finditer(regex_hashtag, text, re.MULTILINE)
                    for i_hashtag in hashtags:
                        hashtag = i_hashtag.group()
                        users_db = cursor.execute("SELECT * FROM users_hashtags WHERE hashtag=? AND (chat_id=0 OR chat_id=?)", (hashtag[1:], chat_id)).fetchall()
                        for user_db in users_db:
                            user_id = user_db["user_id"]
                            hashtag_db = user_db["hashtag"]

                            user_options_global = self.get_user_options(user_id)
                            user_options_global = user_options_global["options_true"]
                            silent = False
                            if "master" in user_options_global and "tag" in user_options_global:
                                user_options_chat = self.get_user_options(user_id, chat_id)
                                user_options_chat = user_options_chat["options_true"]
                                if "master" in user_options_chat and "tag" in user_options_chat:
                                    user_info = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                                    user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND user_id=? AND leaved IS NULL", (chat_id, user_id)).fetchone()
                                    if user_info["started"] == 1 and user_chat_info and not user_id == from_id:
                                        if user_id in to_notify:
                                            if "hashtag" in to_notify[user_id]:
                                                if not hashtag_db in to_notify[user_id]["hashtag"]:
                                                    to_notify[user_id]["hashtag"] += (hashtag_db,)
                                            else:
                                                to_notify[user_id]["hashtag"] = (hashtag_db,)
                                        else:
                                            to_notify[user_id] = {"hashtag": (hashtag_db,),
                                                                  "type": "hashtag"}
                                        if "silent" in user_options_global or "silent" in user_options_chat:
                                            to_notify[user_id]["silent"] = True
        result["media_type"] = media_type
        result["doc_type"] = doc_type
        result["text"] = text
        result["to_notify"] = to_notify
        result["chat_title"] = message.chat.title
        result["from_user"] = from_user
        result["msg_id"] = message.message_id
        result["chat_id"] = chat_id
        if message.chat.username:
            result["chat_username"] = message.chat.username
        result["exec_time"] = time.time() - start_time
        return(result)

    def hashtags(self, chat_id, user_id, hashtags=(), remove=False):
        start_time = time.time()
        result = {"task_name"            : "hashtags",
                  "hashtags_added"       : (),
                  "hashtags_not_added"   : (),
                  "hashtags_removed"     : (),
                  "hashtags_not_removed" : ()}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        hashtags_db = []
        hashtags_query = cursor.execute("SELECT * FROM users_hashtags WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchall()
        for hashtag in hashtags_query:
            hashtags_db += [hashtag["hashtag"],]
        if hashtags:
            for hashtag in hashtags:
                query_hashtag = (chat_id,
                                 user_id,
                                 hashtag)
                if not remove:
                    if hashtag not in hashtags_db:
                        cursor.execute("INSERT INTO users_hashtags(chat_id, user_id, hashtag) VALUES(?,?,?)", query_hashtag)
                        hashtags_db += [hashtag]
                        result["hashtags_added"] += (hashtag,)
                    else:
                        if not hashtag in result["hashtags_not_added"]:
                            result["hashtags_not_added"] += (hashtag,)
                else:
                    if hashtag in hashtags_db:
                        cursor.execute("DELETE FROM users_hashtags WHERE chat_id=? AND user_id=? AND hashtag=?", query_hashtag)
                        hashtags_db.remove(hashtag)
                        result["hashtags_removed"] += (hashtag,)
                    else:
                        if not hashtag in result["hashtags_not_removed"]:
                            result["hashtags_not_removed"] += (hashtag,)
            handle.commit()
        result["hashtags"] = tuple(hashtags_db)
        result["exec_time"] = time.time() - start_time
        return(result)

    def welcome_goodbye(self, chat_id, welcome_msg=None, goodbye_msg=None):
        start_time = time.time()
        result = {"task_name": "welcome_goodbye"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        if not welcome_msg == None or not goodbye_msg == None:
            if not welcome_msg == None:
                if welcome_msg == "":
                    query_welcome = (None,
                                     chat_id)
                else:
                    query_welcome = (welcome_msg,
                                     chat_id)
                cursor.execute("UPDATE chats SET welcome_msg=? WHERE id=?", query_welcome)
            if not goodbye_msg == None:
                if goodbye_msg == "":
                    query_goodbye = (None,
                                     chat_id)
                else:
                    query_goodbye = (goodbye_msg,
                                     chat_id)
                cursor.execute("UPDATE chats SET goodbye_msg=? WHERE id=?", query_goodbye)
            handle.commit()
        msgs = cursor.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
        result["goodbye"] = msgs["goodbye_msg"]
        result["welcome"] = msgs["welcome_msg"]
        result["exec_time"] = time.time() - start_time
        return(result)

    def _get_media(self, message):
        media_id = None
        media_type = None
        doc_type = None
        text = None
        if message.audio:
            media_id = message.audio.file_id
            media_type = "audio"
        elif message.document:
            media_id = message.document.file_id
            media_type = "document"
            doc_type = message.document.mime_type
        elif message.photo:
            media_id = message.photo[-1].file_id
            media_type = "photo"
        elif message.sticker:
            media_id = message.sticker.file_id
            media_type = "sticker"
        elif message.video:
            media_id = message.video.file_id
            media_type = "video"
        elif message.voice:
            media_id = message.voice.file_id
            media_type = "voice"
        if message.text:
            text = message.text
        if media_id:
            text = message.caption
        result = {"media_id"   : media_id,
                  "media_type" : media_type,
                  "doc_type"   : doc_type,
                  "text"       : text}
        return(result)

    def _strip_markdown(self, text):
        bold = re.findall(r"\*", text)
        italic = re.findall(r"_", text)
        if len(bold) % 2 == 0 and len(italic) % 2 == 0:
            text = re.sub(r"[\*_`]", "", re.sub(r"\[(.+)\]\(.+\)", "\g<1>", text)).strip()
        return(text)

    def get_pinned_msg(self, chat_id):
        start_time = time.time()
        result = {"task_name": "get_pinned_msg"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        from_id = None
        msg_id = None
        text = None
        pinned_db = cursor.execute("SELECT pinned_id FROM logs WHERE chat_id=? AND pinned_id NOT NULL ORDER BY msg_id DESC", (chat_id,)).fetchone()
        if pinned_db:
            pinned_msg_db = cursor.execute("SELECT * FROM logs WHERE chat_id=? AND msg_id=?", (chat_id, pinned_db["pinned_id"])).fetchone()
            if pinned_msg_db:
                from_id = pinned_msg_db["from_id"]
                msg_id = pinned_msg_db["msg_id"]
                text = pinned_msg_db["text"]
        result["from_id"] = from_id
        result["msg_id"] = msg_id
        result["text"] = text
        result["exec_time"] = time.time() - start_time
        return(result)

    def get_msg(self, chat_id, text=None, msg_id=None, full_match=False, case_sensitive=False, from_id=None, reply_to=None, linked_chat_id=None, linked_msg_id=None):
        start_time = time.time()
        result = {"task_name": "get_msg"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        result_msg = ()
        query = "SELECT * FROM logs WHERE chat_id=?"
        query_args = (chat_id,)
        query_args_retry = ()
        if text:
            if full_match:
                if case_sensitive:
                    query += " AND text=?"
                else:
                    query += " AND LOWER(text)=LOWER(?)"
            else:
                text_no_md = "%%%s%%" % self._strip_markdown(text)
                text = "%%%s%%" % text
                if case_sensitive:
                    query += " AND text LIKE (?)"
                else:
                    query += " AND LOWER(text) LIKE LOWER(?)"
                query_args_retry += (chat_id, text_no_md)
            query_args += (text,)
        if from_id:
            query += " AND from_id=%s" % from_id
        if reply_to:
            query += " AND replyto_id=%s" % reply_to
        if linked_chat_id:
            query += " AND linked_chat_id=%s" % linked_chat_id
        if linked_msg_id:
            query += " AND linked_msg_id=%s" % linked_msg_id
        if msg_id:
            query += " AND msg_id=%s" % msg_id
            query += " ORDER BY id DESC"
        else:
            query += " ORDER BY msg_id DESC"
        msg_db = cursor.execute(query, query_args).fetchall()
        if not msg_db and query_args_retry:
            query = "SELECT * FROM logs WHERE chat_id=? AND LOWER(text) LIKE LOWER(?)"
            if from_id:
                query += " AND from_id=%s" % from_id
            msg_db = cursor.execute(query, query_args_retry).fetchall()
        for msg in msg_db:
            pinned_msg_id = None
            if msg["pinned_id"]:
                get_pinned = self.get_msg(msg["chat_id"], msg_id=msg["pinned_id"])
                msg = get_pinned["msg"][0]
                pinned_msg_id = msg["msg_id"]
            result_msg += ({"msg_id"     : msg["msg_id"],
                            "text"       : msg["text"],
                            "chat_id"    : msg["chat_id"],
                            "from_id"    : msg["from_id"],
                            "media_id"   : msg["media_id"],
                            "media_type" : msg["media_type"],
                            "doc_type"   : msg["doc_type"],
                            "pinned_id"  : pinned_msg_id,
                            "timestamp"  : msg["date"]},)
        result["msg"] = result_msg
        result["exec_time"] = time.time() - start_time
        return(result)

    def set_bot_admin(self, admin_id):
        start_time = time.time()
        result = {"task_name": "set_bot_admin"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        admin_db = cursor.execute("SELECT id FROM users WHERE bot_admin NOT NULL").fetchone()
        if not admin_db:
            admin_lvl = 1
        else:
            admin_lvl = 2
        cursor.execute("UPDATE users SET bot_admin=? WHERE id=?", (admin_lvl, admin_id,))
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def remove_bot_admin(self, admin_id):
        start_time = time.time()
        result = {"task_name": "remove_bot_admin"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        cursor.execute("UPDATE users SET bot_admin=NULL WHERE id=?", (admin_id,))
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def get_bot_admin(self):
        start_time = time.time()
        result = {"task_name": "get_bot_admin",
                  "admins_id": ()}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        admin_db = cursor.execute("SELECT id FROM users WHERE bot_admin NOT NULL").fetchall()
        for admin in admin_db:
            result["admins_id"] += (admin["id"],)
        result["exec_time"] = time.time() - start_time
        return(result)

    def get_user(self, user_id):
        start_time = time.time()
        result = {"task_name": "get_user",
                  "user": {}}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        user = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if user:
            result["user"] = {"first_name" : user["first_name"],
                              "last_name"  : user["last_name"],
                              "username"   : user["username"],
                              "id"         : user["id"],
                              "started"    : user["started"],
                              "bot_admin"  : user["bot_admin"]}
        result["exec_time"] = time.time() - start_time
        return(result)

    def _markdown_escape(self, text):
        text = re.sub(r"([\*_`])", r"\\\g<1>", text)
        return(text)

    def get_user_groups(self, user_id):
        start_time = time.time()
        result = {"task_name": "get_user_groups",
                  "groups": (),}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        chats = cursor.execute("SELECT * FROM users_chats JOIN chats ON users_chats.chat_id=chats.id WHERE users_chats.user_id=? AND chats.type != 'private' AND users_chats.leaved IS NULL", (user_id,)).fetchall()
        if chats:
            for chat in chats:
                result["groups"] += ({"id"    : chat["chat_id"],
                                     "title" : chat["title"]},)
        result["exec_time"] = time.time() - start_time
        return(result)

    def get_user_options(self, user_id, chat_id=None):
        start_time = time.time()
        result = {"task_name"    : "get_user_options",
                  "options_all"  : (),
                  "options_true" : (),
                  "options_text" : {}}
        for option in NotifyOptions.all_flags:
            result["options_all"] += (option.name,)
            result["options_text"][option.name] = option.data
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        if chat_id:
            query = "SELECT options FROM users_chats WHERE user_id=? AND chat_id=?"
            query_args = (user_id, chat_id)
        else:
            query = "SELECT options FROM users WHERE id=?"
            query_args = (user_id,)
        options_db = cursor.execute(query, query_args).fetchone()
        if options_db:
            if not options_db["options"] == None:
                options = NotifyOptions(options_db["options"])
                for option in options:
                    result["options_true"] += (option.name,)
        result["exec_time"] = time.time() - start_time
        return(result)

    def toggle_user_option(self, user_id, option_name, chat_id=None):
        start_time = time.time()
        result = {"task_name"    : "toggle_user_options"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        if chat_id:
            query = "SELECT options FROM users_chats WHERE user_id=? AND chat_id=?"
            query_args = (user_id, chat_id)
            query_commit = "UPDATE users_chats SET options=? WHERE user_id=? AND chat_id=?"
        else:
            query = "SELECT options FROM users WHERE id=?"
            query_args = (user_id,)
            query_commit = "UPDATE users SET options=? WHERE id=?"
        options_db = cursor.execute(query, query_args).fetchone()
        if options_db:
            current_options = NotifyOptions(options_db["options"])
            to_toggle = NotifyOptions(option_name)
            new_options = to_toggle ^ current_options
            query_args = (int(new_options),) + query_args
            cursor.execute(query_commit, query_args)
            handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def feedback_add(self, from_id, msg_id):
        start_time = time.time()
        result = {"task_name"    : "feedback_add"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        cursor.execute("INSERT INTO feedback(from_id, message_id) VALUES (?,?)", (from_id, msg_id))
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def shortcut(self, chat_id, shortcut_name, shortcut_content=None, remove=False):
        start_time = time.time()
        result = {"task_name"    : "shortcut"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        action = ""
        query_data = (chat_id, shortcut_name)
        shortcut = cursor.execute("SELECT * FROM shortcuts WHERE chat_id=? AND shortcut_name=?", query_data).fetchone()
        if remove == True:
            if shortcut:
                cursor.execute("DELETE FROM shortcuts WHERE chat_id=? AND shortcut_name=?", query_data)
                action = "removed"
            else:
                action = "not_removed"
        elif shortcut_content:
            query_data = (shortcut_content,) + query_data
            if shortcut:
                cursor.execute("UPDATE shortcuts SET shortcut_content=? WHERE chat_id=? AND shortcut_name=?", query_data)
                action = "modified"
            else:
                cursor.execute("INSERT INTO shortcuts(shortcut_content, chat_id, shortcut_name) VALUES (?,?,?)", query_data)
                action = "added"
        else:
            action = "get"
            result["shortcut"] = {}
            if shortcut:
                result["shortcut"] = {"chat_id"          : shortcut["chat_id"],
                                      "shortcut_name"    : shortcut["shortcut_name"],
                                      "shortcut_content" : shortcut["shortcut_content"],
                                      "shortcut_extra"   : shortcut["shortcut_extra"]}
        result["action"] = action
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)
