import json
import math
import os
import time
from glob import glob
from urllib.parse import urljoin
from datetime import datetime
from .lite import dict_factory
from .wpjson import WP, secureWP
from bunch import Bunch
from urllib.parse import urlparse
from textwrap import dedent
import requests
from bs4 import BeautifulSoup

cache_responses={}
cache_protocol={}

txt_dict = "data/dict.txt"
now = time.time()


def get_arr_json(file):
    if os.path.isfile(file):
        with open(file, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    return []


def tuple_dom(dom):
    dom = tuple(reversed(dom.split(".")))
    return dom


def reader(name):
    if os.path.isfile(name):
        with open(name, "r") as f:
            for l in f.readlines():
                l = l.strip()
                if l and not l.startswith("#"):
                    yield l


def get_dict(name=txt_dict):
    urls = {}
    site = None
    for l in reader(name):
        if " " not in l:
            site = l
            urls[site] = {}
            continue
        id, v = l.split()
        urls[site][int(id)] = v
    return urls


def set_dict(links_dict, name=txt_dict):
    with open(name, "w") as f:
        for site, urls in sorted(links_dict.items(), key=lambda x: tuple_dom(x[0])):
            if len(urls) == 0:
                continue
            f.write(site+"\n")
            m_id = max(len(str(id)) for id in urls.keys())
            line = "%"+str(m_id)+"s %s\n"
            for id, url in sorted(urls.items()):
                if url != "#":
                    f.write(line % (id, url))

def get_protocol(site):
    if site not in cache_protocol:
        try:
            r = requests.head("http://"+site, allow_redirects=False, verify=False)
            if r.status_code == 200:
                p = r.url.split("://")[0]
                cache_protocol[site] = p
                return p
        except:
            pass
    cache_protocol["site"] = "https"
    return "https"

def save_wpjson(site, data):
    if isinstance(data, dict):
        data = data.values()
    data = sorted(data, key=lambda x: (x["date_gmt"], x["id"]), reverse=True)
    file = "data/wp-json/%s.json" % site.replace("/", "_")
    with open(file, "w") as f:
        json.dump(data, f, indent=4)
    file = "data/wp-json/%s.txt" % site.replace("/", "_")
    width = max((len(str(d["id"])) for d in data), default=3)
    line = "%"+str(width)+"s %s\n"
    with open(file, "w") as f:
        for d in data:
            url = d.get("source_url", d["link"])
            if url != "#":
                url = url.split("://", 1)[-1]
                f.write(line % (d["id"], url))


def loadwpjson(site, db_objs):
    file = "data/wp-json/%s.json" % site.replace("/", "_")
    o_data = get_arr_json(file)
    o_data = [d for d in o_data if d["id"] in db_objs]
    save_wpjson(site, o_data)
    exclude=set()
    if site == "tomalaplaza.net":
        exclude.add(484)
    for i in o_data:
        idb = db_objs.get(i["id"])
        i_date = datetime.strptime(i["date"], '%Y-%m-%dT%H:%M:%S')
        i_modi = datetime.strptime(i["modified"], '%Y-%m-%dT%H:%M:%S')
        if i_date == idb["date"] and i_modi == idb["modified"]:
            exclude.add(i["id"])
    exclude = sorted(exclude)
    if len(exclude) == len(db_objs):
        data = o_data
    else:
        include=[i for i in db_objs.keys() if i not in exclude]
        site_url = get_protocol(site)+"://"+site
        wp = WP(site_url, progress="  {}: {}")
        if exclude and len(exclude)<len(include):
            wp.exclude = exclude
        if include and len(include)<len(exclude):
            wp.include = include
        data = {d["id"]:d for d in o_data}
        for d in wp.posts + wp.pages + wp.media:
            data[d["id"]] = d
        save_wpjson(site, data)

    if isinstance(data, list):
        data = {d["id"]:d for d in data}

    for d in data.values():
        html = d.get("content", {}).get("rendered", "").strip()
        d["html"] = html
        d["out_links"] = set()
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for n in soup.findAll(["img", "a"]):
                attr = "href" if n.name == "a" else "src"
                href = n.attrs.get(attr, None)
                if href is not None and not href.startswith("#"):
                    href = urljoin(d["link"], href)
                    slp = href.split("://", 1)
                    if len(slp)==2 and slp[0].lower() in ("http", "https"):
                        d["out_links"].add(slp[1])
        d["out_links"] = sorted(d["out_links"])

    return data

def get_response(url, default=None):
    if url in cache_responses:
        return cache_responses[url]
    try:
        rsp = requests.get(url, allow_redirects=False, verify=False)
        r = Bunch(code=rsp.status_code, url=url)
        if rsp.headers and rsp.headers.get('location', None):
            r.url = rsp.headers['location']
        cache_responses[url] = r
    except requests.exceptions.TooManyRedirects:
        return Bunch(code=998, url=url)
    r.o_dom = urlparse(url).netloc
    r.n_dom = urlparse(r.url).netloc
    if r.o_dom != r.n_dom and "wp-signup.php?new=" in r.url:
        r.code = 999
    return r

def text_link(url):
    if not url:
        return None
    url = url.rstrip("/")
    slp = url.split('://', 1)
    if len(slp) == 2 and slp[0].lower() in ("http", "https"):
        url = slp[1]
    if url.startswith("www."):
        url = url[4:]
    return url

class Blog(Bunch):
    def __init__(self, *args, **kargv):
        super().__init__(*args, **kargv)
        self.__http = None
        if "files" not in self:
            self.files = None

    @property
    def http(self):
        if self.__http is None:
            self.__http = get_protocol(self.url)
        return self.__http

    def findurl(self, obj, attachment_id=False):
        url = "{0}://{1}".format(self.http, self.url)
        if obj.type == "page":
            url = url + "/?page_id=" + str(obj.ID)
        elif obj.type == "post":
            url = url + "/?p=" + str(obj.ID)
        elif attachment_id:
            url = url + "/?attachment_id=" + str(abs(obj.ID))
        else:
            url = "/".join((
                url,
                (self.files or "files").strip("/"),
                obj.file.lstrip("/")
            ))
        r = get_response(url)
        r.textlink = text_link(r.url)
        return r

class FindUrl:
    def __init__(self, log):
        self.link_cache = get_dict()
        self.log = open(log, "w")
        self.log.write(dedent('''
        * `998`: `requests.exceptions.TooManyRedirects`
        * `999`: blog wordpress inexistente
        * `4XX` o `5XX`: `status code` de la petición `http`
        ''').strip()+"\n\n")
        self.log_lines=[]

    def writeln(self, line, *args, end="  \n"):
        if args:
            line = line.format(*args)
        line.rstrip()
        if line in self.log_lines:
            return
        self.log_lines.append(line)
        self.log.write(line+end)
        self.log.flush()

    def get(self, blog, obj, attachment_id=False):
        blog=Blog(blog)
        obj=Bunch(obj)
        if obj.url == "#":
            return "{}://{}".format(blog.http, blog.url)
        if attachment_id:
            obj.ID = -obj.ID
        url = self.link_cache.get(blog.url, {}).get(obj.ID)
        if url:
            slp = url.split("://", 1)
            ptc = slp[0].lower() if len(slp)==2 else None
            if ptc in ("http", "https") and ptc!=blog.http:
                url = "{}://{}".format(blog.http, slp[1])
                self.link_cache[blog.url][obj.ID]=url
            return url

        r = blog.findurl(obj, attachment_id=attachment_id)

        if int(r.code/100) in (4, 5, 9):
            self.writeln("`{0}` [{2}]({1})", r.code, r.url, r.textlink)
            return None

        if r.code == 999:
            self.writeln("`999` [{1}]({0}{1})", blog.http, r.o_dom)
            return None

        if blog.url not in self.link_cache:
            self.link_cache[blog.url] = {}
        self.link_cache[blog.url][obj.ID]=r.url

        return r.url

    def close(self):
        self.log.close()
        set_dict(self.link_cache)
