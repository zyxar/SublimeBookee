#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "0.1.2" # 2 for st2; 3 for st3
__author__ = "Markus Chou (chou.marcus@gmail.com)"
__copyright__ = "(c) 2013 Markus Chou"
__license__ = "MIT License"

from sgmllib import SGMLParser
from urllib import quote
from urlparse import urljoin

import sublime, sublime_plugin
import subprocess
import urllib2, re

site_url = "http://www.ebookshare.net"
_tracker_ = "magnet:?xt=urn:btih:%s&dn=%s&tr=udp%%3A%%2F%%2Ftracker.publicbt.com%%3A80&tr=udp%%3A%%2F%%2Ftracker.openbittorrent.com%%3A80&tr=udp%%3A%%2F%%2Ftracker.ccc.de%%3A80"

class PostParser(SGMLParser):
    def __init__(self):
        SGMLParser.__init__(self)
        self.mark = False
        self.store = []
        self.is_title = False
        self.is_meta = False
        self.is_href = False
        self.url = ""
        self.title = ""
        self.meta = ""
    def parse(self, content):
        self.feed(content)
    def read(self):
        r = self.store
        self.store = []
        return r
    def start_div(self, attrs):
        if attrs[0][0] == "class" and attrs[0][1] == "post":
            self.mark = True
    def end_div(self):
        self.mark = False
    def start_h2(self, attrs):
        if len(attrs) > 0 and len(attrs[0]) == 2 and attrs[0][0] == "class" and attrs[0][1] == "posttitle":
            self.is_title = True
    def end_h2(self):
        self.is_title = False
    def start_p(self, attrs):
        if attrs[0][0] == "class" and attrs[0][1] == "postmeta":
            self.is_meta = True
    def end_p(self):
        self.is_meta = False
    def start_a(self, attrs):
        if self.is_title:
            self.is_href = True
            self.url = attrs[0][1]
    def end_a(self):
        self.is_href = False   
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
            cont = urllib2.urlopen(urllib2.Request(self['link'])).read()
            try:
                self['torrent_url'] = re.compile(r'/download.*id=[0-9]+').search(cont).group()
            except:
                self['torrent_url'] = ''
            try:
                self['info_hash'] = re.compile(r'\w{40,40}').search(cont).group()
            except:
                self['info_hash'] = ''
        except urllib2.HTTPError:
            self['torrent_url'] = ''
            self['info_hash'] = ''

    def get_magnet(self):
        if self['info_hash'] is None or self['info_hash'] == '':
            return ''
        return  _tracker_ % (self['info_hash'], quote(self['title']))

def readPage(n=1):
    try:
        fd = urllib2.urlopen(site_url+'/all-%d.html'%n, timeout=5)
        return fd.read()
    except:
        return None
    finally:
        fd.close()

def readOneDay():
    date = None
    n = 1
    rr = []
    pp = PostParser()
    while date is None or cont[-1]['pubDate'] == date:
        page = readPage(n)
        if page is not None:
            pp.parse(page)
            cont = pp.read()
            if date is None:
                date = cont[0]['pubDate']
            for post in cont:
                if post['pubDate'] == date:
                    post.feed()
                    rr.append(post)
        print('Page %d done.' % n)
        n += 1
    sublime.status_message('Total: %d posts' % len(rr))
    return rr

class BookeeFetch(sublime_plugin.TextCommand):
    """command: bookee_fetch"""

    def is_enable(self):
        return self.view.file_name() is None and self.view.is_read_only() == False

    def is_visible(self):
        return self.is_enable()

    def run(self, edit, download=False):
        posts = readOneDay()
        downs = [urljoin(site_url, post['torrent_url']) for post in posts]
        self.view.erase(edit, sublime.Region(0 ,self.view.size()))
        self.view.insert(edit, 0, '\n'.join(['%s\tbt://%s' % (post['pubDate'], post['info_hash']) for post in posts]))
        self.view.insert(edit, self.view.size(), '\n\n')
        self.view.insert(edit, self.view.size(), '\n'.join(downs))
        if download:
            for url in downs:
                try:
                    subprocess.call(['curl', '-OJ', url])
                except Exception as e:
                    sublime.status_message('Unable to download %s.\n%s' % (url, repr(e)))
        