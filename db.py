#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, sqlite3, re
from datetime import datetime


class DBHandler:
    def __init__(self, path):
        self._dbpath = path

    def log(self, message):
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
            cursor.execute("INSERT INTO users(first_name,last_name,username,id) VALUES(?,?,?,?)", query_user)
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
                     (message.date - datetime(1970, 1, 1)).total_seconds(),
                     replyto_id,
                     pinned_id,)
        if text or media_type or pinned_id:
            cursor.execute("INSERT INTO logs(from_id,chat_id,msg_id,media_id,media_type,doc_type,text,fwd_from_chat,fwd_from_user,date,replyto_id,pinned_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", query_log)
        # User List
        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.from_user.id)).fetchone()
        if message.left_chat_member:
            cursor.execute("DELETE FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.left_chat_member.id))
            needs_goodbye = cursor.execute("SELECT goodbye_msg FROM chats WHERE id=?", (message.chat.id,)).fetchone()
            if needs_goodbye:
                result["goodbye_msg"] = needs_goodbye["goodbye_msg"]
                if message.left_chat_member.username:
                    result["welcome_goodbye_name"] = "@%s" % message.left_chat_member.username
                else:
                    result["welcome_goodbye_name"] = "%s" % message.left_chat_member.first_name
        if message.new_chat_member:
            cursor.execute("INSERT INTO users_chats(user_id,chat_id) VALUES(?,?)", (message.new_chat_member.id, message.chat.id))
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
        query_user_chat = (message.from_user.id,
                           message.chat.id,)
        if not user_chat_info:
            cursor.execute("INSERT INTO users_chats(user_id,chat_id) VALUES(?,?)", query_user_chat)
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
                cursor.execute("INSERT INTO users(first_name,last_name,username,id) VALUES(?,?,?,?)", query_user)
            # User_chat
            user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=?", (admin.user.id, chat)).fetchone()
            query_user_chat_add = (admin.status,
                               admin.user.id,
                               chat,)
            if user_chat_info:
                cursor.execute("UPDATE users_chats SET status=? WHERE user_id=? AND chat_id=?", query_user_chat_add)
            else:
                cursor.execute("INSERT INTO users_chats(status,user_id,chat_id) VALUES(?,?,?)", query_user_chat_add)
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

    def started_set(self, user_id):
        start_time = time.time()
        result = {"task_name": "set_started"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        cursor.execute("UPDATE users SET started=1 WHERE id=?", (user_id,))
        handle.commit()
        result["exec_time"] = time.time() - start_time
        return(result)

    def notify(self, message):
        start_time = time.time()
        result = {"task_name": "notify"}
        tag_to_notify = ()
        reply_to_notify = None
        admin_to_notify = ()
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        chat_id = message.chat.id
        from_id = message.from_user.id
        if message.from_user.username:
            from_user = "@%s" % message.from_user.username
        else:
            from_user = message.from_user.first_name
        regex_tag = r"@\w+"
        get_media = self._get_media(message)
        text = get_media["text"]
        media_id = get_media["media_id"]
        media_type = get_media["media_type"]
        doc_type = get_media["doc_type"]
        if text:
            tags = re.finditer(regex_tag, text, re.MULTILINE)
            for tag in tags:
                username = tag.group()
                if username == "@admin":
                    admin_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND (status='creator' OR status='administrator')", (chat_id,)).fetchall()
                    for admin in admin_chat_info:
                        if not admin["user_id"] == from_id:
                            admin_to_notify += (admin["user_id"],)
                else:
                    user_info = cursor.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (username[1:],)).fetchone()
                    if user_info:
                        user_id = user_info["id"]
                        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=?", (user_id, chat_id)).fetchone()
                        if user_info["started"] == 1 and user_id not in tag_to_notify and user_chat_info and not user_id == from_id:
                            tag_to_notify += (user_id,)
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            user_info = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE user_id=? AND chat_id=?", (user_id, chat_id)).fetchone()
            if user_info["started"] == 1 and user_chat_info and not user_id == from_id:
                reply_to_notify = user_id
                if tag_to_notify:
                    if user_id in tag_to_notify:
                        reply_to_notify = None
        if reply_to_notify and not text and media_type:
            result["media_type"] = media_type
            result["media_id"] = media_id
        result["msg_text"] = text
        result["admin_to_notify"] = admin_to_notify
        result["reply_to_notify"] = reply_to_notify
        result["tag_to_notify"] = tag_to_notify
        result["chat_title"] = message.chat.title
        result["from_user"] = from_user
        result["msg_id"] = message.message_id
        if message.chat.username:
            result["chat_username"] = message.chat.username
        result["exec_time"] = time.time() - start_time
        return(result)

    def hashtags(self, chat_id, user_id, hashtags=(), remove=False):
        start_time = time.time()
        result = {"task_name": "hashtag_set"}
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
                else:
                    if hashtag in hashtags_db:
                        cursor.execute("DELETE FROM users_hashtags WHERE chat_id=? AND user_id=? AND hashtag=?", query_hashtag)
                        hashtags_db.remove(hashtag)
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
            print(pinned_db)
            print(pinned_msg_db)
            if pinned_msg_db:
                from_id = pinned_msg_db["from_id"]
                msg_id = pinned_msg_db["msg_id"]
                text = pinned_msg_db["text"]
        result["from_id"] = from_id
        result["msg_id"] = msg_id
        result["text"] = text
        result["exec_time"] = time.time() - start_time
        return(result)

    def get_msg(self, chat_id, text=None, msg_id=None, full_match=False, case_sensitive=False, from_id=None):
        start_time = time.time()
        result = {"task_name": "get_msg"}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        result_msg = ()
        if text:
            if full_match:
                if case_sensitive:
                    query = "SELECT * FROM logs WHERE chat=? AND text=?"
                else:
                    query = "SELECT * FROM logs WHERE chat=? AND LOWER(text)=LOWER(?)"
            else:
                text_no_md = "%%%s%%" % self._strip_markdown(text)
                text = "%%%s%%" % text
                if case_sensitive:
                    query = "SELECT * FROM logs WHERE chat_id=? AND text LIKE (?)"
                else:
                    query = "SELECT * FROM logs WHERE chat_id=? AND LOWER(text) LIKE LOWER(?)"
            if from_id:
                query += " AND from_id=%s" % from_id
            query_args = (chat_id, text)
            query_args_retry = (chat_id, text_no_md)
        elif msg_id:
            query = "SELECT * FROM logs WHERE chat_id=? AND msg_id=?"
            query_args = (chat_id, msg_id)
        else:
            query = None
        if query:
            query += " ORDER BY msg_id DESC"
            msg_db = cursor.execute(query, query_args).fetchall()
            if not msg_db and query_args_retry:
                query = "SELECT * FROM logs WHERE chat_id=? AND LOWER(text) LIKE LOWER(?)"
                if from_id:
                    query += " AND from_id=%s" % from_id
                msg_db = cursor.execute(query, query_args_retry).fetchall()
            for msg in msg_db:
                result_msg += ({"msg_id"     : msg["msg_id"],
                                "text"       : msg["text"],
                                "chat_id"    : msg["chat_id"],
                                "from_id"    : msg["from_id"],
                                "media_id"   : msg["media_id"],
                                "media_type" : msg["media_type"],
                                "doc_type"   : msg["doc_type"]},)
        result["msg"] = result_msg
        result["exec_time"] = time.time() - start_time
        return(result)

    def bound(self, bind_to_id=None):
        start_time = time.time()
        result = {"task_name": "bound",
                  "bound_ids": ()}
        handle = sqlite3.connect(self._dbpath)
        handle.row_factory = sqlite3.Row
        cursor = handle.cursor()
        if bind_to_id:
            bind_db = cursor.execute("SELECT id FROM users WHERE bound NOT NULL").fetchone()
            if bind_db:
                bind_lvl = 1
            else:
                bind_lvl = 2
            cursor.execute("UPDATE users SET bound=? WHERE id=?", (bind_lvl, bind_to_id,))
            handle.commit()
        bind_db = cursor.execute("SELECT id FROM users WHERE bound NOT NULL").fetchall()
        for bind in bind_db:
            result["bound_ids"] += (bind["id"],)
        result["exec_time"] = time.time() - start_time
        return(result)
