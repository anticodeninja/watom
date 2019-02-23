#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the
# Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
# with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Copyright 2019 Artem Yamshanov, me [at] anticode.ninja

import argparse
import asyncio
from docutils.core import publish_parts
from markdown import markdown
import json
import os
import PIL.Image
import pystray
import sys
import mimetypes
import threading
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.platform.asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

HERE = os.path.abspath(os.path.dirname(__file__))
SUPPORTED_EXT = {
    '.rst': lambda data: publish_parts(writer_name='html5', source=data)['html_body'],
    '.md': lambda data: markdown(data, output_format='html5'),
}

pages = {}
loops = []


class Page:
    def __init__(self, name, target, basedir, ext):
        self.name = name or 'index'
        self.target = target
        self.basedir = basedir
        self.ext = ext
        self.watchers = []

    def generate(self):
        with open(self.target, 'r', encoding='utf8') as input_file:
            return self.ext(input_file.read())


class FileChangedHandler(FileSystemEventHandler):
    def __init__(self, page):
        self.page = page

    def on_modified(self, event):
        super().on_modified(event)

        info = json.dumps({
            'page': self.page.generate()
        })

        for watcher in self.page.watchers:
            watcher.write_message(info)


class PageHandler(tornado.web.RequestHandler):
    def get(self, page_id):
        page = pages.get(page_id, None)
        if page:
            self.render('bootstrap.html', init=json.dumps({
                'page_id': page_id,
                'page': page.generate()
            }))
            return

        page_id = page_id.split('/')
        if len(page_id) == 1:
            page = pages.get('', None)
        else:
            page = pages.get(page_id[0], None)
            del page_id[0]

        if page:
            path = os.path.realpath(os.path.join(page.basedir, *page_id))
            if not path.startswith(page.basedir):
                raise Exception('Incorrect path')

            if os.path.exists(path):
                mime_type, encoding = mimetypes.guess_type(path)
                if encoding == "gzip":
                    content_type = "application/gzip"
                elif encoding is not None:
                    content_type = "application/octet-stream"
                elif mime_type is not None:
                    content_type = mime_type
                else:
                    content_type = "application/octet-stream"
                self.set_header("Content-Type", content_type)

                with open(path, 'rb') as input_file:
                    self.write(input_file.read())
                    return

        self.set_status(404)
        self.write('Ooops, something went wrong')


class ApiHandler(tornado.websocket.WebSocketHandler):
    page_id = None

    def open(self, page_id):
        self.page_id = page_id
        pages[self.page_id].watchers.append(self)

    def on_close(self):
        pages[self.page_id].watchers.remove(self)


def add_to_pages(observer, target, page_id):
    if os.path.isdir(target):
        for filename in os.listdir(target):
            namepart, extpart = os.path.splitext(filename)
            ext = SUPPORTED_EXT.get(extpart, None)
            if namepart == 'index' and ext:
                target = os.path.join(target, filename)
                break
        else:
            raise Exception('Cannot found index file')
    else:
        namepart, extpart = os.path.splitext(target)
        ext = SUPPORTED_EXT.get(extpart, None)

    page = Page(page_id, target, os.path.dirname(target), ext)
    observer.schedule(FileChangedHandler(page), page.basedir, recursive=True)
    pages[page_id] = page


def tornado_loop():
    tornado_app = tornado.web.Application(
        [
            (r'/api/(.*)', ApiHandler),
            (r'/(.*)', PageHandler),
        ],
        debug = True,
        template_path = os.path.join(HERE, "views"),
        static_path = os.path.join(HERE, "static")
    )
    tornado_app.listen(8082)

    tornado_ioloop = tornado.ioloop.IOLoop.current()
    loops.append(tornado_ioloop)
    tornado_ioloop.start()

def stop_loops():
    for loop in loops:
        loop.stop()

def main():
    icon = pystray.Icon('Watom')
    icon.icon = PIL.Image.open(os.path.join(HERE, 'watom.png'))
    icon.menu = pystray.Menu(
        pystray.MenuItem('Exit watom', stop_loops)
    )
    loops.append(icon)

    asyncio.set_event_loop_policy(tornado.platform.asyncio.AnyThreadEventLoopPolicy())
    tornado_thread = threading.Thread(target=tornado_loop)
    tornado_thread.daemon = True
    tornado_thread.start()

    observer = Observer()
    loops.append(observer)
    observer.start()

    if len(sys.argv) > 0:
        add_to_pages(observer, os.path.realpath(sys.argv[1]), '')
        print('Target file: ', pages[''].target)
    else:
        raise Exception('Only preview is supported in PoC')

    icon.run()

if __name__ == "__main__":
    main()
