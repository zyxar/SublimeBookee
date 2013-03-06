#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "0.1.2" # 2 for st2; 3 for st3
__author__ = "Markus Chou (chou.marcus@gmail.com)"
__copyright__ = "(c) 2013 Markus Chou"
__license__ = "MIT License"

from html.parser import HTMLParser
from urllib.parse import quote
from urllib.parse import urljoin
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from threading import Thread

import sublime, sublime_plugin
import subprocess
import re
import os

site_url = "http://www.ebookshare.net"
_tracker_ = "magnet:?xt=urn:btih:%s&dn=%s&tr=udp%%3A%%2F%%2Ftracker.publicbt.com%%3A80&tr=udp%%3A%%2F%%2Ftracker.openbittorrent.com%%3A80&tr=udp%%3A%%2F%%2Ftracker.ccc.de%%3A80"

class PostParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.mark = False
        self.store = []
        self.is_title = False
        self.is_meta = False
        self.is_href = False
        self.url = ""
        self.title = ""
        self.meta = ""

    def parse(self, content):
        self.feed(content.decode('utf-8'))

    def read(self):
        r = self.store
        self.store = []
        return r

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if attrs[0][0] == "class" and attrs[0][1] == "post":
                self.mark = True
        elif tag == 'h2':
            if len(attrs) > 0 and len(attrs[0]) == 2 and attrs[0][0] == "class" and attrs[0][1] == "posttitle":
                self.is_title = True
        elif tag == 'p':
            if attrs[0][0] == "class" and attrs[0][1] == "postmeta":
                self.is_meta = True
        elif tag == 'a':
            if self.is_title:
                self.is_href = True
                self.url = attrs[0][1]
        else:
            pass

    def handle_endtag(self, tag):
        if tag == 'div':
            self.mark = False
        elif tag == 'h2':
            self.is_title = False
        elif tag == 'p':
            self.is_meta = False
        elif tag == 'a':
            self.is_href = False
        else:
            pass
  
    def handle_data(self, text):
        if self.mark:
            if self.is_title:
                self.title = text
                if self.is_href:
                    self.url = site_url+self.url
            elif self.is_meta:
                try:
                    self.meta = re.compile(r'[0-9]+-[0-9]+-[0-9]+').search(text.strip()).group()
                except:
                    self.meta = text.strip()
                self.is_meta = False
                post = PostInfo({'title':self.title, 'link':self.url, 'pubDate':self.meta})
                self.store.append(post)
            else:
                pass

class PostInfo(dict):
    """Structure representing a post"""
    def __init__(self, dicts=None):
        if dicts is not None: self.update(dicts)
    
    def feed(self):
        try:
            cont = urlopen(Request(self['link'])).read().decode('utf-8')
            try:
                self['torrent_url'] = re.compile(r'/download.*id=[0-9]+').search(cont).group()
            except:
                self['torrent_url'] = ''
            try:
                self['info_hash'] = re.compile(r'\w{40,40}').search(cont).group()
            except:
                self['info_hash'] = ''
        except HTTPError:
            self['torrent_url'] = ''
            self['info_hash'] = ''

    def get_magnet(self):
        if self['info_hash'] is None or self['info_hash'] == '':
            return ''
        return  _tracker_ % (self['info_hash'], quote(self['title']))

def readPage(n=1):
    try:
        fd = urlopen(site_url+'/all-%d.html'%n, timeout=5)
        return fd.read()
    except:
        return None
    finally:
        # fd.close()
        pass

def readDays(days=1):
    n = 1
    done_date = []
    rr = []
    pp = PostParser()
    while len(done_date) <= int(days):#date is None or cont[-1]['pubDate'] == date:
        page = readPage(n)
        if page is not None:
            pp.parse(page)
            cont = pp.read()
            for post in cont:
                date = post['pubDate']
                if date not in done_date:
                    done_date.append(date)
                if len(done_date) <= int(days):
                    post.feed()
                    rr.append(post)
        print('Page %d done.' % n)
        n += 1
    print('Total: %d posts' % len(rr))
    return rr

def do_proxy():
    if 'http_proxy' in os.environ and os.environ['http_proxy'] != '':
        return
    http_proxy = sublime.load_settings('Bookee.sublime-settings').get('http_proxy')
    if http_proxy is not None and http_proxy != '':
        os.environ['http_proxy'] = http_proxy
        print('set http_proxy to \'%s\'' % http_proxy)

class BookeeFetch(sublime_plugin.TextCommand):
    """command: bookee_fetch"""

    def is_enable(self):
        return self.view.file_name() is None and self.view.is_read_only() == False

    def is_visible(self):
        return self.is_enable()

    def run(self, edit, download=False):

        def do_thread(args):
            days = args[0]
            download_on = args[1]
            do_proxy()
            posts = readDays(days)
            downs = [urljoin(site_url, post['torrent_url']) for post in posts]
            # self.view.erase(edit, sublime.Region(0, self.view.size()))
            # selv.view.insert(edit, 0, '\n'.join(['%s\tbt://%s' % (post['pubDate'], post['info_hash']) for post in posts]))
            # self.view.insert(edit, self.view.size(), '\n\n')
            # self.view.insert(edit, self.view.size(), '\n'.join(downs))
            print('\n'.join(['%s\tbt://%s' % (post['pubDate'], post['info_hash']) for post in posts]))
            print('\n')
            print('\n'.join(downs))
            if download_on:
                os.chdir(os.path.expanduser('~/Desktop'))
                for url in downs:
                    try:
                        subprocess.call(['curl', '-OJ', url])
                    except Exception as e:
                        print('Unable to download %s.\n%s' % (url, repr(e)))
                print('Download procedure ends.')
        
        def issue(days):
            t = Thread(target=do_thread, args=((days, download),))
            t.start()
            
        self.view.window().show_input_panel('How Many Days?', '1', issue, None, None)
        
