#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
import aiomysql
logging.basicConfig()


def log(sql, args=()):
    logging.info('[SQL]: %s, Args: %s' % (sql, args or 'None'))

__pool = None


@asyncio.coroutine
def create_db_pool(loop, user, password, db, **kwargs):
    """
    Create a global database pool

    :param loop: event loop of the web application
    :param user: username of the database
    :param password:
    :param db: database name
    :param kwargs:
    :return: No return
    """
    logging.info('[DB]: Create database connecting pool')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kwargs.get('host', 'localhost'),
        # 3306 is the default mysql port
        port=kwargs.get('port', 3306),  # port is an integer
        charset=kwargs.get('charset', 'utf8'),  # 尼玛为什么是utf8 No dash line ？？？
        maxsize=kwargs.get('maxsize', 10),
        minsize=kwargs.get('minsize', 1),
        autocommit=kwargs.get('autocommit', True),
        user=user,
        password=password,
        db=db,
        loop=loop
    )


@asyncio.coroutine
def destroy_pool():  # 销毁连接池
    global __pool
    if __pool is not None:
        __pool.close()
        yield from __pool.wait_closed()


@asyncio.coroutine
def select(sql, args=(), number=None):
    log(sql, args)
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args)
        res = yield from cur.fetchall()
    print()
    res = res[:number] if number else res
    logging.info('[SQL]: %s row returned' % len(res))
    return res

@asyncio.coroutine
def execute(sql, args=()):
    log(sql, args)
    with (yield from __pool) as conn:
        cur = yield from conn.cursor()
        try:
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
        except:
            conn.rollback()
            raise
    return affected


class Field(object):
    # Abstract Class
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return 'Field Type: %s; Value Type: %s' % (self.__class__.__name__, self.column_type)


class StringField(Field):
    def __init__(self, name=None, column_type='varchar(100)', primary_key=False, default=None):
        super(StringField, self).__init__(name, column_type, primary_key, default)


class TextField(Field):
    # This field will never be primary_key, so don't need to add primary_key parameter into __init__
    def __init__(self, name=None, default=None):
        super(TextField, self).__init__(name, 'text', False, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super(BooleanField, self).__init__(name, 'boolean', False, default)


class IntField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super(IntField, self).__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super(FloatField, self).__init__(name, 'real', primary_key, default)


def create_args_string(number):
    s = []
    for i in range(number):
        s.append('?')
    return ', '.join(s)


class MetaModel(type):

    def __new__(mcs, future_class_name, future_class_parents, future_class_attributes):
        """

        :param future_class_name: the name of the future class whose metaclass is MetaModel
        :param future_class_parents: the parents of future class
        :param future_class_attributes: attributes of the future class.
                not the attributes of instance.
        :return:  重写过attributes的 __new__()
        """
        if future_class_name == 'Model':
            # 不对Model类做处理
            return type.__new__(mcs, future_class_name, future_class_parents, future_class_attributes)

        # get table name from the future class. If not set, use the class name.
        table_name = future_class_attributes.get('__table__', None) or future_class_name
        logging.info('[ORM]: Found model: %s [table name: %s]' % (future_class_name, table_name))

        mappings = {}
        # fields contains all fields except primary key field
        fields = []
        found_primary_key = False
        for key, value in future_class_attributes.items():
            if isinstance(value, Field):
                # e.g  key = 'email'; value = StringField(column_type='varchar(50)')
                logging.info('[ORM]: Found mapping %s => %s' % (key, value))
                mappings[key] = value
                if value.primary_key:
                    if found_primary_key:
                        raise RuntimeError('[ORM]: Duplicated primary key.')
                    found_primary_key = key
                else:
                    fields.append(key)
        if not found_primary_key:
            raise RuntimeError('[ORM]: Did not found primary key.')

        for field_name in mappings:
            # 把attr里面的field项都清理掉 包括primary_key
            future_class_attributes.pop(field_name)

        # 重写类的attributes
        primary_key = found_primary_key
        # 不知道是干嘛的。。。 详细看了mysql的sql语句应该就明白了 暂时掠过
        # Maybe to defence SQL injection attack
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))

        # sql statements
        sql_select = 'SELECT `%s`, %s from `%s`' % (primary_key, ', '.join(escaped_fields), table_name)
        sql_insert = 'INSERT INTO `%s` (`%s`, %s) values (%s)' % \
                     (table_name, primary_key, ', '.join(escaped_fields), create_args_string(len(escaped_fields) + 1))
        sql_delete = 'DELETE FROM `%s` WHERE `%s`=?' % (table_name, primary_key)

        # 貌似用不到Field示例的name属性 所以我就不按着这个写了
        # sql_update = 'update `%s` set %s where `%s`=?' % \(table_name,
        # ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primary_key)

        sql_update = 'UPDATE `%s` SET %s WHERE `%s`=?' % \
                     (table_name, ', '.join(list(map(lambda escaped_field: '%s=?' % escaped_field, escaped_fields))),
                      primary_key)
        # e.g 'UPDATE `%s` SET `email`=?, `name`=? (...省略) WHERE `id`=?'

        future_class_attributes.update(
            __mappings__=mappings,
            __table__=table_name,
            __primary_key__=primary_key,
            __fields__=fields,
            __select__=sql_select,
            __insert__=sql_insert,
            __delete__=sql_delete,
            __update__=sql_update
        )

        return type.__new__(mcs, future_class_name, future_class_parents, future_class_attributes)


class Model(dict, metaclass=MetaModel):
    """Abstract class"""
    def __getattr__(self, key):
        # 只有在访问该类实例拥有的方法时调用
        try:
            return self[key]
        except KeyError:
            raise AttributeError('[ORM]: The model don\'t have %s attribute' % key)

    def __setattr__(self, key, value):
        self[key] = value

    def get_value_or_default(self, field_name):
        value = self.get(field_name, None)
        # 如果实例并没有写这个field的值 则用default处理
        if value is None:
            # 实例没有的attribute 会去类里面找
            field = self.__mappings__[field_name]
            if field.default is not None:  # ... Admin的默认值设置的是False
                value = field.default() if callable(field.default) else field.default
                logging.info('Using default value. [%s:%s]' % (field_name, value))
                self[field_name] = value
        return value

    @classmethod
    @asyncio.coroutine
    def find_all(cls, args=None, where=None, **kwargs):
        """
        Find objects by where clause

        :return a list of object
        """
        sql = [cls.__select__]
        if where:
            sql.append('WHERE')
            sql.append(where)

        if not args:
            # sql的args必须传入iterable object， 且默认参数不要设置为mutable object
            # 因此有这一步
            args = []

        order_by = kwargs.get('order_by', None)
        if order_by:
            sql.append('ORDER BY')
            sql.append(order_by)

        limit = kwargs.get('limit', None)
        if limit:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple):
                if len(limit) == 2:
                    sql.append('?, ?')
                    args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        result = yield from select(' '.join(sql), args)
        # 返回结果result 是字典变量 传关键字参数进去构造当前类的实例！ 好巧妙
        return [cls(**r) for r in result]

    @classmethod
    @asyncio.coroutine
    def count_rows(cls, select_field='*', where=None, args=None):
        """ find number by select and where. """
        sql = ['select count(%s) _num_ from `%s`' % (select_field, cls.__table__)]
        if where:
            sql.append('where %s' % where)
        results = yield from select(' '.join(sql), args, 1)  # size = 1
        if not results:
            return 0
        return results[0].get('_num_', 0)

    @classmethod
    @asyncio.coroutine
    def find_by_primary_key(cls, primary_key):
        result = yield from select('%s WHERE `%s`=?' % (cls.__select__, cls.__primary_key__), [primary_key], 1)
        if len(result) == 0:
            return None
        return cls(**result[0])

    @asyncio.coroutine
    def save(self):
        args = [self.get_value_or_default(self.__primary_key__)]
        args.extend(list(map(self.get_value_or_default, self.__fields__)))
        row_affected = yield from execute(self.__insert__, args)
        if row_affected != 1:
            logging.warning('Failed to save record, row affected: %s' % row_affected)

    @asyncio.coroutine
    def update_data(self):
        # ... update 的 sql 主键在最后 ，insert , select 我都把主键放在最后了。。。 还是廖老师技高一筹啊
        # UPDATE `users` SET `admin`=?, `created_at`=?, `password`=?, `name`=?, `avatar`=?, `email`=? WHERE `id`=?
        args = list(map(self.get_value_or_default, self.__fields__))
        args.append(self.get_value_or_default(self.__primary_key__))
        row_affected = yield from execute(self.__update__, args)
        if row_affected != 1:
            logging.warning('Failed to update, row affected: %s' % row_affected)

    @asyncio.coroutine
    def delete(self):
        args = [self.get_value_or_default(self.__primary_key__)]
        row_affected = yield from execute(self.__delete__, args)
        if row_affected != 1:
            logging.warning('Failed to delete, row affected: %s' % row_affected)
