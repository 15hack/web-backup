#!/usr/bin/env python3

import os
import re
import sys
from shutil import copyfile, move
from datetime import date

from core.lite import one_factory
from core.sitedb import SiteDBLite
from core.schemaspy import SchemasPy

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

if not os.path.isfile("sites.db"):
    sys.exit("Primero ha de generar la base de datos")

target = date.today().strftime("%Y.%m.%d")+"_sites.db"
copyfile("sites.db", target)

db = SiteDBLite(target)
print("Tamaño inicial: "+db.size())
db.minimize("sql/clean.sql")
db.print_links("out/links.txt")
db.print_links("out/links.md")
db.print_info("out/README.md")
db.close(vacuum=True)
print("Tamaño reducido: "+db.size())
print("Tamaño comprimido: "+db.zip(zip="out/sites.7z"))
db.save_diagram("out/diagram.png")
os.remove(target)
