#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asynchronous blog application"""

import os
import asyncio
import logging; logging.basicConfig(level=logging.INFO)

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from async_web_framework import add_routes, add_static
from factorys_and_filters import logger_factory, data_factory, response_factory, datetime_filter, auth_factory


def init_jinja2(application, **kwargs):
    logging.info('[Jinja2]: Initiating...')
    configs = dict(
        autoescape=kwargs.get('autoescape', True),
        # 设置block的起始字符串
        block_start_string=kwargs.get('block_start_string', '{%'),
        block_end_string=kwargs.get('block_end_string', '%}'),
        variable_start_string=kwargs.get('variable_start_string', '{{'),
        variable_end_string=kwargs.get('variable_end_string', '}}'),
        auto_reload=kwargs.get('auto_reload', True)
    )
    # 设置templates的路径
    path = kwargs.get('path', None)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('[Jinja2]: set templates path to [%s]' % path)
    env = Environment(loader=FileSystemLoader(path), **configs)
    filters = kwargs.get('filters', None)
    if filters:
        for name, f in filters.items():
            # env.filters.update(name=f) ???? update 加不进去数据？？？ what happened
            env.filters[name] = f
    application['__template__'] = env


@asyncio.coroutine
def init_app(event_loop, host='127.0.0.1', port=8000):
    yield from orm.create_db_pool(
        loop=loop,
        user='blog-data',
        password=' ',
        db='blog')

    app = web.Application(
        loop=event_loop,
        middlewares=[logger_factory, data_factory, auth_factory, response_factory])

    init_jinja2(app, filters=dict(datetime=datetime_filter))

    add_routes(app, 'handlers')
    add_static(app)
    server = yield from loop.create_server(
        app.make_handler(),
        host=host,
        port=port
    )
    logging.info('[Server]server started at http://%s:%s...' % (host, port))
    return server


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_app(loop, host='0.0.0.0', port=8000))
    loop.run_forever()
