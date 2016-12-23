"""models"""

import time
import uuid
from orm import Model, StringField, BooleanField, FloatField, TextField


def create_id():
    return '%15d%s000' % (time.time(), uuid.uuid4().hex)


class User(Model):
    __table__ = 'users'

    id = StringField(column_type='varchar(50)', primary_key=True, default=create_id)
    email = StringField(column_type='varchar(50')
    name = StringField(column_type='varchar(50)')
    password = StringField(column_type='varchar(50)')
    avatar = StringField(column_type='varchar(500)')  # 头像
    admin = BooleanField()  # 默认不是管理员
    created_at = FloatField(default=time.time)


class Blog(Model):
    __table__ = 'blogs'

    id = StringField(column_type='varchar(50)', primary_key=True, default=create_id)
    user_id = StringField(column_type='varchar(50)')
    user_name = StringField(column_type='varchar(50)')
    user_avatar = StringField(column_type='varchar(500)')
    name = StringField(column_type='varchar(50)')
    summary = StringField(column_type='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=create_id, column_type='varchar(50)')
    blog_id = StringField(column_type='varchar(50)')
    user_id = StringField(column_type='varchar(50)')
    user_name = StringField(column_type='varchar(50)')
    user_avatar = StringField(column_type='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
