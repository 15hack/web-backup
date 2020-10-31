#!/usr/bin/env python3

import os
import re
import sys
from shutil import copyfile, move
from datetime import date

from core.lite import one_factory
from core.liteblog import BlogDBLite
from core.schemaspy import SchemasPy

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

if not os.path.isfile("wp.db"):
    sys.exit("Primero ha de generar la base de datos")

target = date.today().strftime("%Y.%m.%d")+"_wp.db"
copyfile("wp.db", target)

db = BlogDBLite(target)
print("Tamaño inicial: "+db.size())
db.minimize("sql/clean.sql")
db.print_links("out/links.txt")
db.print_info("out/README.md")
db.close(vacuum=True)
print("Tamaño reducido: "+db.size())
print("Tamaño comprimido: "+db.zip(zip="out/wp.7z"))
db.save_diagram("out/diagram.png")
os.remove(target)
