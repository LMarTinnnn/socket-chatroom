#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import json
import base64
import logging
import hashlib
import asyncio
from aiohttp import web

import markdown2

from conf.config import configs
from async_web_framework import get, post
from model import User, Blog, Comment, create_id
from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError


# -------------------------------cookie 处理函数------------------------------------
COOKIE_NAME = 'LM_blog_cookie'
_COOKIE_KEY = configs['session']['secret']


def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))   # time.time()'s value is float
    key = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    sha1_key = hashlib.sha1(key.encode()).hexdigest()
    cookie = '-'.join([user.id, expires, sha1_key])
    return cookie


@asyncio.coroutine
def cookie2user(cookie_str):
    if not cookie_str:
        return None
    else:
        try:
            user_id, expires, sha1_key = cookie_str.split('-')
        except ValueError:  # If cookie was not built with three parts divided by dash line
            return None

        if int(expires) < time.time():
            return None

        user = yield from User.find_by_primary_key(user_id)
        if not user:
            return None

        db_key = '%s-%s-%s-%s' % (user_id, user.password, expires, _COOKIE_KEY)
        if sha1_key != hashlib.sha1(db_key.encode()).hexdigest():
            logging.info('[Cookie Checker]: Cookie with invalid sha1')
            return None
        else:
            user.password = '********'
            return user


# ------------------------------ Helper --------------------------------------
def check_admin(request):
    if not request.__admin__:
        raise APIPermissionError('No authority')


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


# ------------------------------ url handler --------------------------------------
@get('/')
@asyncio.coroutine
def index(request):
    summary = '我是简介哈哈哈哈'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 6049801212)
    ]
    blogs = yield from Blog.find_all()
    return dict(
        __template__='index.html',
        blogs=blogs,
        __user__=request.__user__
    )


@get('/signup')
def signup():
    return {
        '__template__': 'signup.html'
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@get('/manage/blogs/create')
def crete_blog(request):
    return {
        '__template__': 'blog_edit.html',
        'id': '',
        'action': '/api/blogs',
        '__user__': request.__user__
    }


@get('/blog/{blog_id}')
@asyncio.coroutine
def read_blog(blog_id, request):
    blog = yield from Blog.find_by_primary_key(blog_id)
    print(blog)
    if not blog:
        raise APIResourceNotFoundError('blog', '似乎来到了没有知识的荒原')
    comments = yield from Comment.find_all(where='blog_id=?', args=[blog_id], order_by='created_at DESC')

    # escape
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        '__user__': request.__user__,
        'blog': blog,
        'comments': comments
    }


# ---------------------------------- API -----------------------------------
_RE_EMAIL = re.compile(r'^[a-z0-9.\-_]+@[a-z0-9\-_]+(\.[a-z0-9\-_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@post('/api/signup')
@asyncio.coroutine
def api_signup(*, email, name, password):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not re.match(_RE_EMAIL, email):
        raise APIValueError('email')
    if not password or not re.match(_RE_SHA1, password):   # js 传过来的是经过一次sha1加密的密码
        raise APIValueError('password')

    user = yield from User.find_all(where='email=?', args=[email])
    if user:
        raise APIError('register:failed', 'email', 'already exist')
    uid = create_id()
    # 又加密一次
    sha1_password = hashlib.sha1(('%s:%s' % (uid, password)).encode()).hexdigest()
    user = User(id=uid, email=email, name=name, password=sha1_password, avatar='/static/pics/default_avatar.png')
    yield from user.save()

    # set cookie
    resp = web.Response(content_type='application/json')
    cookie = user2cookie(user, max_age=86400)
    user.password = '********'
    resp.set_cookie(COOKIE_NAME, cookie, max_age=86400, httponly=True)
    resp.body = json.dumps(user, ensure_ascii=False).encode()
    return resp


@post('/api/signin')
@asyncio.coroutine
def api_signin(*, email, password):
    if not email:
        raise APIValueError('email', '邮箱不能为空')
    if not password:
        raise APIValueError('password', '密码不能为空')

    user_list = yield from User.find_all(where='email=?', args=[email])
    if not user_list:
        raise APIError('signin:failed', 'email', '邮箱不存在')
    else:
        user = user_list[0]

    db_sha1 = user.password
    sign_in_key = '%s:%s' % (user.id, password)

    if db_sha1 != hashlib.sha1(sign_in_key.encode()).hexdigest():
        raise APIValueError('password', '密码错误')

    resp = web.Response(content_type='application/json')
    resp.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '********'
    resp.body = json.dumps(user, ensure_ascii=False).encode()
    return resp


@get('/api/signout')
def signout(request):
    referer = request.get('Referer')
    resp = web.HTTPFound(referer or '/')
    resp.set_cookie(COOKIE_NAME, '-delete-', max_age=0, httponly=True)
    logging.info('User signed out')
    return resp


@post('/api/blogs')
@asyncio.coroutine
def post_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError(name, message='标题不能为空')
    if not summary or not summary.strip():
        raise APIValueError(summary, message='简介不能为空')
    if not content or not content.strip():
        raise APIValueError(content, message='内容不能为空')

    user = request.__user__
    blog = Blog(
        user_id=user.id,
        user_name=user.name,
        user_avatar=user.avatar,
        name=name,
        summary=summary,
        content=content
    )

    yield from blog.save()
    return blog   # blog是dict的子类 在response_factory 会处理成json对象

