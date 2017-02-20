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
        result = {"task_name": "log"}
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
        media_id = None
        media_type = None
        fwd_from_chat = None
        fwd_from_user = None
        replyto_id = None
        pinned_id = None
        if message.audio:
            media_id = message.audio.file_id
            media_type = "audio"
        elif message.document:
            media_id = message.document.file_id
            media_type = "document"
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
        text = message.text
        if media_id:
            text = message.caption
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
                     text,
                     fwd_from_chat,
                     fwd_from_user,
                     (message.date - datetime(1970, 1, 1)).total_seconds(),
                     replyto_id,
                     pinned_id,)
        if text or media_type:
            cursor.execute("INSERT INTO logs(from_id,chat_id,msg_id,media_id,media_type,text,fwd_from_chat,fwd_from_user,date,replyto_id,pinned_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", query_log)
        # User List
        user_chat_info = cursor.execute("SELECT * FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.from_user.id)).fetchone()
        if message.left_chat_member:
            cursor.execute("DELETE FROM users_chats WHERE chat_id=? AND user_id=?", (message.chat.id, message.left_chat_member.id))
            needs_goodbye = cursor.execute("SELECT welcome_msg FROM chats WHERE id=?", (message.chat.id,)).fetchone()
            if needs_goodbye:
                result["goodbye_msg"] = needs_goodbye["goodbye_msg"]
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
        if message.text:
            text = message.text
        elif message.caption:
            text = message.caption
        else:
            text = None
        if text:
            result["msg_text"] = text
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
                if tag_to_notify:
                    if user_id not in tag_to_notify:
                        reply_to_notify = user_id
                else:
                    reply_to_notify = user_id
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
