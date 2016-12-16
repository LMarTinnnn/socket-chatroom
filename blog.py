#!/usr/bin/env python3
# _*_ coding: utf-8 -*-

import os
import sqlite3
from flask import Flask, request, session, g,\
    redirect, url_for, abort, render_template, flash

app = Flask(__name__)

# get config from this module
app.config.from_object(__name__)
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'blog.db'),
    # The SECRET_KEY is needed to keep the client-side sessions secure
    SECRET_KEY='Designed By APPLE In California',
    USERNAME='admin',
    PASSWORD='admin'
))
app.config.from_envvar('BLOG_SETTINGS', silent=True)


def connect_db():
    """
    Connects to the specif database
    :return: a connection object
    """
    conn = sqlite3.connect(app.config['DATABASE'])
    # if using Row as the row_factory, the query will return data as dictionaries rather than tuple
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as file:
            db.cursor().executescript(file.read())
        db.commit()
        print('初始化完毕')


def get_db():
    """
    Open a new database connection in the current application context if not exists
    :return: a database connection object which is an attribute of 'g'
    """
    if not hasattr(g, 'sqlite_db'):
        # 'For now, all you have to know is that
        # you can store information safely on the g object.'
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
# Function within teardown_appcontext will be called every time the application tears down
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/')
def show_entries():
    db = get_db()
    # execute() method of connection object calls the execute() method of a created cursor object and return the cursor
    cur = db.execute('SELECT TITLE, TEXT FROM entries ORDER BY id DESC')
    entries = cur.fetchall()
    return render_template('show_entries.html', entries=entries)


@app.route('/add', methods=['POST'])
def add_entry():
    # This view lets the user add new entries if they are logged in.
    if not session.get('logged_in', False):
        flash(" YOU DON'T HAVE RIGHT TO ADD ARTICLE!")
        return redirect(url_for('show_entries'))
    data = (request.form['title'], request.form['text'])
    db = get_db()
    sql_add = 'INSERT INTO entries (title, text) VALUES (?, ?)'
    db.execute(sql_add, data)
    db.commit()
    flash('New entry is successfully posted')
    return redirect(url_for('show_entries'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # BY checking  if error is None to reuse the login template
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('Logged in successfully')
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    # pop(key[, default])
    # If key is in the dictionary, remove it and return its value,
    # else return default. If default is not given and key is not in the dictionary, a KeyError is raised.
    flash("You'v already logged out")
    return redirect(url_for('show_entries'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)