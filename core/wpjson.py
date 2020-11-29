from functools import lru_cache

import requests
from bunch import Bunch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlencode
import simplejson


def get_targets(url, html):
    if html and html.strip():
        soup = BeautifulSoup(html, 'html.parser')
        for n in soup.findAll(["img", "iframe", "a"]):
            attr = "href" if n.name == "a" else "src"
            href = n.attrs.get(attr)
            if href and not href.startswith("#"):
                yield urljoin(url, href)

def get_dom(url):
    p = urlparse(url)
    dom = p.netloc
    if dom.startswith("www."):
        dom=dom[4:]
    return dom

def secureWP(dom, http="http", **kargv):
    if not dom.startswith("http"):
        dom = http + "://" + dom
    try:
        return WP(dom, **kargv)
    except Exception as e:
        pass
    try:
        return WP("www."+dom, **kargv)
    except Exception as e:
        pass
    if http != "https":
        return secureWP(dom, http="https", **kargv)
    return None

class WP:
    def __init__(self, url, progress=None):
        self.last_url = None
        self.url = url.rstrip("/")
        self.id = self.url.split("://", 1)[1]
        self.rest_route = self.url + "/?rest_route="
        self.info = Bunch(**self.get("/"))
        self.progress = progress
        self.dom = get_dom(self.last_url or self.url)
        self.exclude = None
        self.include = None

    def get(self, path):
        url = self.rest_route+path
        try:
            r = requests.get(url, verify=False)
            self.last_url = r.url
            js = r.json()
            return js
        except requests.exceptions.ConnectionError:
            print(url)
            raise
        except simplejson.errors.JSONDecodeError:
            print(url)
            raise

    def get_object(self, tp, size=100, page=1, **kargv):
        url = "/wp/v2/{}/&per_page={}&page={}".format(tp, size, page)
        if kargv:
            url = url + "&" + urlencode(kargv, doseq=True)
        return self.get(url)

    def get_all_objects(self, tp, size=100, **kargv):
        if tp in ("pages", "posts", "media"):
            if self.exclude:
                key = "exclude" if len(self.exclude)==1 else "exclude[]"
                kargv[key]=self.exclude
            if self.include:
                key = "include" if len(self.include)==1 else "include[]"
                kargv[key]=self.include
        rs = []
        page = 0
        while True:
            page = page + 1
            r = self.get_object(tp, size=size, page=page, **kargv)
            if isinstance(r, list) and len(r) > 0:
                rs.extend(r)
                if self.progress:
                    print(self.progress.format(tp, len(rs)), end="\r")
            else:
                return sorted(rs, key=lambda x: x["id"])

    @property
    @lru_cache(maxsize=None)
    def targets(self):
        targets=set()
        for p in self.posts + self.pages:
            for target in get_targets(p["link"], p["content"]["rendered"]):
                targets.add(target)
        return sorted(targets)

    @property
    @lru_cache(maxsize=None)
    def dom_targets(self):
        doms=set()
        for t in self.targets:
            doms.add(get_dom(t))
        return sorted(doms)

    @property
    @lru_cache(maxsize=None)
    def error(self):
        js = self.get_object("posts", size=1)
        if "code" in js:
            return js["code"] + " " + self.last_url
        return None

    @property
    @lru_cache(maxsize=None)
    def posts(self):
        return self.get_all_objects("posts")

    @property
    @lru_cache(maxsize=None)
    def pages(self):
        return self.get_all_objects("pages")

    @property
    @lru_cache(maxsize=None)
    def media(self):
        return self.get_all_objects("media")

    @property
    @lru_cache(maxsize=None)
    def comments(self):
        return self.get_all_objects("comments")

    @property
    @lru_cache(maxsize=None)
    def users(self):
        return self.get_all_objects("users")

    @property
    @lru_cache(maxsize=None)
    def tags(self):
        return self.get_all_objects("tags")

    @property
    @lru_cache(maxsize=None)
    def categories(self):
        return self.get_all_objects("categories")
