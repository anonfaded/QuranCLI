http client/server for asyncio
==============================

.. image:: https://raw.github.com/KeepSafe/aiohttp/master/docs/aiohttp-icon.png
  :height: 64px
  :width: 64px
  :alt: aiohttp logo

.. image:: https://secure.travis-ci.org/KeepSafe/aiohttp.png
  :target:  https://secure.travis-ci.org/KeepSafe/aiohttp
  :align: right


Requirements
------------

- Python >= 3.3
- asyncio https://pypi.python.org/pypi/asyncio


License
-------

``aiohttp`` is offered under the Apache 2 license.


Documentation
-------------

http://aiohttp.readthedocs.org/


Getting started
---------------

Client
^^^^^^

To retrieve something from the web::

  import aiohttp

  def get_body(url):
      response = yield from aiohttp.request('GET', url)
      return (yield from response.read())

You can use the get command like this anywhere in your ``asyncio``
powered program::

  response = yield from aiohttp.request('GET', 'http://python.org')
  body = yield from response.read()
  print(body)

If you want to use timeouts for aiohttp client side please use standard
asyncio approach::

   yield from asyncio.wait_for(request('GET', url), 10)

Server
^^^^^^

In aiohttp 0.12 we've added highlevel API for web HTTP server.

There is simple usage example::

    import asyncio
    from aiohttp import web


    @asyncio.coroutine
    def handle(request):
        name = request.match_info.get('name', "Anonymous")
        text = "Hello, " + name
        return web.Response(body=text.encode('utf-8'))


    @asyncio.coroutine
    def init(loop):
        app = web.Application(loop=loop)
        app.router.add_route('GET', '/{name}', handle)

        srv = yield from loop.create_server(app.make_handler(),
                                            '127.0.0.1', 8080)
        print("Server started at http://127.0.0.1:8080")
        return srv

    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()

CHANGES
=======

0.13.1 (12-31-2014)
--------------------

- Add `aiohttp.web.StreamResponse.started` property #213

- Html escape traceback text in `ServerHttpProtocol.handle_error`

- Mention handler and middlewares in `aiohttp.web.RequestHandler.handle_request`
  on error (#218)


0.13.0 (12-29-2014)
-------------------

- `StreamResponse.charset` converts value to lower-case on assigning.

- Chain exceptions when raise `ClientRequestError`.

- Support custom regexps in route variables #204

- Fixed graceful shutdown, disable keep-alive on connection closing.

- Decode http message with `utf-8` encoding, some servers send headers in utf-8 encoding #207

- Support `aiohtt.web` middlewares #209

- Add ssl_context to TCPConnector #206


0.12.0 (12-12-2014)
-------------------

- Deep refactoring of `aiohttp.web` in backward-incompatible manner.
  Sorry, we have to do this.

- Automatically force aiohttp.web handlers to coroutines in
  `UrlDispatcher.add_route()` #186

- Rename `Request.POST()` function to `Request.post()`

- Added POST attribute

- Response processing refactoring: constructor does't accept Request instance anymore.

- Pass application instance to finish callback

- Exceptions refactoring

- Do not unquote query string in `aiohttp.web.Request`

- Fix concurrent access to payload in `RequestHandle.handle_request()`

- Add access logging to `aiohttp.web`

- Gunicorn worker for `aiohttp.web`

- Removed deprecated `AsyncGunicornWorker`

- Removed deprecated HttpClient


0.11.0 (11-29-2014)
-------------------

- Support named routes in `aiohttp.web.UrlDispatcher` #179

- Make websocket subprotocols conform to spec #181


0.10.2 (11-19-2014)
-------------------

- Don't unquote `environ['PATH_INFO']` in wsgi.py #177


0.10.1 (11-17-2014)
-------------------

- aiohttp.web.HTTPException and descendants now files response body
  with string like `404: NotFound`

- Fix multidict `__iter__`, the method should iterate over keys, not (key, value) pairs.


0.10.0 (11-13-2014)
-------------------

- Add aiohttp.web subpackage for highlevel http server support.

- Add *reason* optional parameter to aiohttp.protocol.Response ctor.

- Fix aiohttp.client bug for sending file without content-type.

- Change error text for connection closed between server responses
  from 'Can not read status line' to explicit 'Connection closed by
  server'

- Drop closed connections from connector #173

- Set server.transport to None on .closing() #172

