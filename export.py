#!/usr/bin/env python3
import os
import re

from bunch import Bunch

from core.connect import DBs
from core.sitedb import SiteDBLite
from core.data import FindUrl, tuple_url, loadwpjson
from core.scrapdb import ScrapDB

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

fnd = FindUrl("log/error.md")
scr = ScrapDB(fnd, *DBs)

db = SiteDBLite("sites.db", total=scr.rows, overwrite=True)
print("Creando sqlite 0%", end="\r")
db.execute('sql/schema.sql')

for meta in scr.sites:
    db.insert("sites", **meta)

for data in scr.wp.posts:
    db.insert("wp_posts", **data)

for data in scr.wp.tags:
    db.insert("wp_tags", insert_or="ignore", **data)

for data in scr.wp.comments:
    db.insert("wp_comments", **data)

for data in scr.wp.media:
    if data["url"] in (None, "#") and data["page"] in (None, "#") and data["status"]!="publish" and not(data["_WPJSON"]):
        continue
    db.insert("wp_media", **data)

for data in scr.phpbb.topics:
    db.insert("phpbb_topics", **data)

for data in scr.phpbb.posts:
    db.insert("phpbb_posts", **data)

for data in scr.phpbb.media:
    db.insert("phpbb_media", **data)

for data in scr.wiki.pages:
    db.insert("wk_pages", **data)

for data in scr.wiki.media:
    db.insert("wk_media", **data)

fnd.close()
db.execute("sql/update.sql")
db.commit()
db.close(vacuum=True)

print("Creando sqlite 100%")
print("Tamaño: "+db.size())
