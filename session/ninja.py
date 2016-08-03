#!/usr/bin/env python
# encoding: utf-8

import random

from werkzeug.wrappers import Request, Response
from werkzeug.contrib.sessions import SessionMiddleware, SessionStore
from werkzeug.contrib.cache import MemcachedCache
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException


class MemcachedSessionStore(SessionStore):
    """A session store that saves sessions with memcache.
    :param session_class: The session class to use.  Defaults to
                          :model:`Session`.
    :param servers: a list or tuple of server addresses or a compatible client.
                    Defaults to `['127.0.0.1:11211']`.
    :param default_timeout: the default timeout that is used if no timeout is specified.
                            A timeout of 0 indicates that the cache never expires.
    :param key_prefix: a prefix that is added before all keys.  This makes it
                       possible to use the same memcached server for different
                       applications.
    """

    def __init__(self, session_class=None, servers=None, default_timeout=600, key_prefix=None):
        SessionStore.__init__(self, session_class)
        self.mc = MemcachedCache(servers, default_timeout, key_prefix)

    def get(self, key):
        return self.mc.get(key)

    def set(self, key, value, timeout=None):
        self.mc.set(key, value, timeout)

    def get_session(self, sid):
        data = self.get(sid)
        if data is None:
            data = {}
        return self.session_class(dict(data), sid, False)


class App(object):
    COOKIE_NAME = "SGSID"
    LUCKY_NUM_KEY = "lucky_num"

    def __init__(self):
        self.url_map = Map([
            Rule('/', endpoint='index'),
        ])

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except HTTPException, e:
            return e

    def index(self, request):
        # werkzeug have a low level session support,
        # you need send session id to browser cookie manually
        sid = request.cookies.get(self.COOKIE_NAME)
        if sid is None:
            # don't have a session id, create new session
            request.session = session_store.new()
        else:
            request.session = session_store.get_session(sid)
        if self.LUCKY_NUM_KEY in request.session:
            lucky_num = request.session[self.LUCKY_NUM_KEY]
        else:
            # random a new lucky number,
            # then store it in session
            # when user access again, will use the same lucky number
            lucky_num = random.randint(1, 10)
            request.session[self.LUCKY_NUM_KEY] = lucky_num
        response = Response('Hello, your lucky number is: %s' % (lucky_num,))
        if sid is None:
            # if the user don't have a session id,
            # don't forgot send session id to cookie
            response.set_cookie(self.COOKIE_NAME, request.session.sid)
        # and you should save session manually
        if request.session.should_save:
            session_store.set(request.session.sid, dict(request.session))
        return response

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = App()
    # open the session support using SessionMiddleware
    global session_store
    session_store = MemcachedSessionStore(key_prefix='SGS_')
    app = SessionMiddleware(app, session_store)
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple

    app = create_app()
    run_simple('0.0.0.0', 8888, app, use_debugger=True)
