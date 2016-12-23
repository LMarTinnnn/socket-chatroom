#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import inspect
import logging
import functools

from aiohttp import web

from apis import APIError


def get(path):
    """
    Define decorator @get('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper

    return decorator


def post(path):
    """
    Define decorator @get('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper

    return decorator


def has_named_kwargs(fn):
    """If function has any named keyword argument"""
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            found = True
    return found


def has_var_kwargs(fn):
    """If fn has any variable keyword arguments"""
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            found = True
    return found


def has_request_arg(fn):
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY
                      and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                'request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(params)))
    return found


def get_no_default_kwargs(fn):
    """get names of all keyword arguments without default value"""
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


def get_named_kwargs(fn):
    """get names of all keyword arguments"""
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._fn = fn
        self._has_request_arg = has_request_arg(self._fn)
        self._has_named_kwargs = has_named_kwargs(self._fn)
        self._has_var_kwargs = has_var_kwargs(self._fn)
        self._named_kw_args = get_named_kwargs(self._fn)
        self._no_default_kw_args = get_no_default_kwargs(self._fn)

    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        if self._has_var_kwargs or self._has_request_arg or self._has_named_kwargs:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content Type')
                content_type = request.content_type.lower()
                if 'application/json' in content_type or 'application/x-www-form-urlencoded' in content_type \
                        or 'multipart/form-data' in content_type:
                    kw = request.__data__
                else:
                    return web.HTTPBadRequest(text='Unsupported Content Type')

            elif request.method == 'GET':
                kw = request.__data__

        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kwargs and self._named_kw_args:
                # 如果不含可变关键字参数 但是有命名关键字参数 则把kw内的不是named keyword 的参数删除
                filtered_kw = dict()
                for name in self._named_kw_args:
                    if name in kw.keys():
                        filtered_kw[name] = kw[name]
                kw = filtered_kw

            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v

        if self._has_request_arg:
            # 函数是否需要传入requests
            kw['request'] = request

        if self._no_default_kw_args:
            # 是否所有不提供默认值的参数都有传入值
            for name in self._no_default_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)

        logging.info('[Framework]: Call function [ %s ] with args: [ %s ]' %
                     (self._fn.__name__, str(kw) if kw else 'No argument'))

        try:
            result = yield from self._fn(**kw)
            return result
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)  # raise API 错误的时候会返回一个dict
            # 通过response factory 生成json类型 返回给浏览器的js程序


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('[Framework] add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    method = fn.__method__
    route = fn.__route__
    if not (method or route):
        raise ValueError('[Framework] %s has not defined @get or @post' % fn.__name__)
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('[Framework] add route [%s %s] => [%s(%s)]'
                 % (method, route, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 因为给RequestHandler定义了call方法, 实现了在调用fn前处理
    # wsgi 服务器在调用app时会传入request参数 RequestHandler会对request参数进行处理以符合fn要求
    app.router.add_route(method, route, RequestHandler(app, fn))


def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)

    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if hasattr(fn, '__call__'):
            if getattr(fn, '__method__', None) and getattr(fn, '__route__', None):
                add_route(app, fn)
