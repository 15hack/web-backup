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

total = sum(len(i) for i in dict(scr.wp).values())

print("Creando sqlite 0%", end="\r")
db = SiteDBLite("sites.db", total=total)
db.execute('sql/schema.sql')

for site, meta in sorted(scr.wp.sites.items(), key=lambda x: tuple_url(x[0])):
    db.insert("sites", **meta)

for data in scr.wp.posts:
    db.insert("posts", **data)

for data in scr.wp.tags:
    db.insert("tags", insert_or="ignore", **data)

for data in scr.wp.comments:
    db.insert("comments", **data)

for data in scr.wp.media:
    if data["url"] in (None, "#") and data["page"] in (None, "#") and data["status"]!="publish" and not(data["_WPJSON"]):
        continue
    db.insert("media", **data)

for site, meta in sorted(scr.phpbb.sites.items(), key=lambda x: tuple_url(x[0])):
    db.insert("sites", **meta)

fnd.close()
db.execute("sql/update.sql")
db.commit()
db.close(vacuum=True)

print("Creando sqlite 100%")
print("Tamaño: "+db.size())
