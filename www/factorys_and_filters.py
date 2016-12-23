#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import asyncio
import logging
import datetime

from aiohttp import web
from urllib import parse

from handlers import cookie2user, COOKIE_NAME


@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        logging.info('[Logger Factory] Request: %s %s' % (request.method, request.path))
        return (yield from handler(request))
    return logger


@asyncio.coroutine
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        if request.method == 'POST':
            content_type = request.content_type.lower()
            if content_type.startswith('application/json'):
                request.__data__ = yield from request.json()
                if not isinstance(request.__data__, dict):
                    return web.HTTPBadRequest(text='JSON body must be object')
                logging.info('[Data Factory]: request json: %s' % str(request.__data__))
            elif content_type.startswith('application/x-www-form-urlencoded') \
                    or content_type.startswith('multipart/form-data'):
                request.__data__ = yield from request.post()
                logging.info('[Data Factory]: request form: %s' % str(request.__data__))
        elif request.method == 'GET':
            query_string = request.query_string
            query_data = {k: v for k, v in parse.parse_qs(query_string, True).items()}
            request.__data__ = query_data
        return (yield from handler(request))
    return parse_data


@asyncio.coroutine
def auth_factory(app, handler):
    @asyncio.coroutine
    def auth(request):
        logging.info('[Auth_Factory]: User cookie check')
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = yield from cookie2user(cookie_str)
            if user:
                logging.info('[Auth_Factory]: user[%s] signs in with cookie' % user.email)
                request.__user__ = user
                request.__admin__ = user.admin
            else:
                logging.info('[Auth_Factory]: user\'s cookie is invalid.')
        else:
            logging.info('[Auth_Factory]: No cookie')
        return (yield from handler(request))
    return auth


@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info('[Response_Factory] Response to: %s %s' % (request.method, request.path))
        raw_resp = yield from handler(request)
        if isinstance(raw_resp, web.StreamResponse):
            return raw_resp
        if isinstance(raw_resp, bytes):
            resp = web.Response(body=raw_resp)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(raw_resp, str):
            if raw_resp.startswith('redirect:'):
                # web.HTTPFound实现重定向
                return web.HTTPFound(raw_resp[9:])
            # response的body部分需要处理成bytes类型
            resp = web.Response(body=raw_resp.encode())
            resp.content_type = 'text/html; charset=utf-8'
            return resp
        if isinstance(raw_resp, int) and 100 <= raw_resp < 600:
            # 处理status code
            return web.Response(status=raw_resp, text=str(raw_resp))

        if isinstance(raw_resp, tuple):
            # 处理status code 和 错误信息
            return web.Response(status=raw_resp[0], text=raw_resp[1])

        if isinstance(raw_resp, dict):
            template = raw_resp.get('__template__')
            if template is None:
                resp = web.Response(
                    body=json.dumps(
                        raw_resp,
                        ensure_ascii=False,
                        default=lambda obj: obj.__dict__).encode()
                )
                resp.content_type = 'application/json; charset=utf-8'
                return resp
            else:
                # 如果这个dict数据需要通过模版渲染成页面
                resp = web.Response(
                    # 对数据进行渲染
                    body=app['__template__'].get_template(template).render(**raw_resp).encode()
                )
                resp.content_type = 'text/html; charset=utf-8'
                return resp
    return response


# --------------------------- Filters----------------------------------------------------------
def datetime_filter(time_stamp):
    past = time.time() - time_stamp
    if past < 60:
        return '一分钟前'
    if past < 3600:
        return '%s分钟前' % int(past // 60)
    if past < 86400:
        return '%s小时前' % int(past // 3600)
    if past < 604800:
        return '%s天前' % int(past // 86400)
    else:
        dt = datetime.datetime.fromtimestamp(time_stamp)
        return '%s年%s月%s日' % (dt.year, dt.month, dt.day)

