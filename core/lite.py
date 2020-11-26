import os
import re
import sqlite3
from textwrap import dedent
from PIL import Image

import unidecode
import yaml
from bunch import Bunch
from datetime import datetime
from subprocess import DEVNULL, STDOUT, check_call
import tempfile
from urllib.request import urlretrieve
from .util import read

re_sp = re.compile(r"\s+")

sqlite3.register_converter("BOOLEAN", lambda x: int(x) > 0)
#sqlite3.register_converter("DATE", lambda x: datetime.strptime(str(x), "%Y-%m-%d").date())
sqlite3.enable_callback_tracebacks(True)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def bunch_factory(cursor, row):
    d = dict_factory(cursor, row)
    return Bunch(**d)

def one_factory(cursor, row):
    return row[0]

def ResultIter(cursor, size=1000):
    while True:
        results = cursor.fetchmany(size)
        if not results:
            break
        for result in results:
            yield result

def save(file, content):
    if file and content:
        content = dedent(content).strip()
        with open(file, "w") as f:
            f.write(content)


class CaseInsensitiveDict(dict):
    def __setitem__(self, key, value):
        dict.__setitem__(self, key.lower(), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, key.lower())

    def do_null(self):
        for k in self.keys():
            self[k]=None

    def rm_null(self):
        for k, v in list(self.items()):
            if v is None:
                del self[k]

class DBLite:
    def __init__(self, file, readonly=False, overwrite=False):
        self.file = file
        if overwrite and os.path.isfile(file):
            os.remove(file)
        self.readonly = readonly
        if self.readonly:
            file = "file:"+self.file+"?mode=ro"
            self.con = sqlite3.connect(
                file, detect_types=sqlite3.PARSE_DECLTYPES, uri=True)
        else:
            self.con = sqlite3.connect(
                self.file, detect_types=sqlite3.PARSE_DECLTYPES)
        self.tables = CaseInsensitiveDict()
        self.load_tables()
        self.inTransaction = False

    def openTransaction(self):
        if self.inTransaction:
            self.con.execute("END TRANSACTION")
        self.con.execute("BEGIN TRANSACTION")
        self.inTransaction = True

    def closeTransaction(self):
        if self.inTransaction:
            self.con.execute("END TRANSACTION")
            self.inTransaction = False

    def execute(self, sql, to_file=None):
        if os.path.isfile(sql):
            with open(sql, 'r') as schema:
                sql = schema.read()
        if sql.strip():
            save(to_file, sql)
            self.con.executescript(sql)
            self.con.commit()
            self.load_tables()

    def get_cols(self, sql):
        cursor = self.con.cursor()
        cursor.execute(sql)
        cols = tuple(col[0] for col in cursor.description)
        cursor.close()
        return cols


    def load_tables(self):
        self.tables.do_null()
        for t in self.to_list("SELECT name FROM sqlite_master WHERE type = 'table'"):
            try:
                self.tables[t] = self.get_cols("select * from "+t+" limit 0")
            except:
                pass
        self.tables.rm_null()

    def insert(self, table, insert_or=None, **kargv):
        sobra = {}
        ok_keys = self.tables[table]
        keys = []
        vals = []
        for k, v in kargv.items():
            if v is None or (isinstance(v, str) and len(v) == 0):
                continue
            _k = "_" + k
            if k not in ok_keys and _k in ok_keys and _k not in kargv:
                k = _k
            if k not in ok_keys:
                sobra[k] = v
                continue
            keys.append('"'+k+'"')
            vals.append(v)
        prm = ['?']*len(vals)
        sql = "insert or "+insert_or if insert_or else "insert"
        sql = sql+" into %s (%s) values (%s)" % (
            table, ', '.join(keys), ', '.join(prm))
        try:
            self.con.execute(sql, vals)
        except sqlite3.InterfaceError:
            print(sql)
            print(vals)
            raise
        return sobra

    def update(self, table, **kargv):
        sobra = {}
        ok_keys = self.tables[table]
        keys = []
        vals = []
        sql_set = []
        id = None
        for k, v in kargv.items():
            if v is None or (isinstance(v, str) and len(v) == 0):
                continue
            _k = "_" + k
            if k not in ok_keys and _k in ok_keys and _k not in kargv:
                k = _k
            if k not in ok_keys:
                sobra[k] = v
                continue
            if k.lower() == "id":
                id = v
                continue
            sql_set.append(k+' = ?')
            vals.append(v)
        vals.append(id)
        sql = "update %s set %s where id = ?" % (
            table, ', '.join(sql_set))
        self.con.execute(sql, vals)
        return sobra

    def _build_select(self, sql):
        sql = sql.strip()
        if not sql.lower().startswith("select"):
            field = "*"
            if "." in sql:
                sql, field = sql.rsplit(".", 1)
            sql = "select "+field+" from "+sql
        return sql

    def commit(self):
        self.con.commit()

    def close(self, vacuum=True):
        if self.readonly:
            self.con.close()
            return
        self.closeTransaction()
        self.con.commit()
        if vacuum:
            c = self.con.execute("pragma integrity_check")
            c = c.fetchone()
            print("integrity_check =", *c)
            self.con.execute("VACUUM")
        self.con.commit()
        self.con.close()

    def select(self, sql, *args, row_factory=None, **kargv):
        sql = self._build_select(sql)
        self.con.row_factory=row_factory
        cursor = self.con.cursor()
        if args:
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
        for r in ResultIter(cursor):
            yield r
        cursor.close()
        self.con.row_factory=None

    def to_list(self, *args, **kargv):
        r=[]
        flag=False
        for i in self.select(*args, **kargv):
            flag = flag or (isinstance(i, tuple) and len(i)==1)
            if flag:
                i = i[0]
            r.append(i)
        return r

    def one(self, sql, row_factory=None):
        sql = self._build_select(sql)
        self.con.row_factory=row_factory
        cursor = self.con.cursor()
        cursor.execute(sql)
        r = cursor.fetchone()
        cursor.close()
        self.con.row_factory=None
        if not r:
            return None
        if row_factory is None and len(r)==1:
            return r[0]
        return r

    def get_sql_table(self, table):
        sql = "SELECT sql FROM sqlite_master WHERE type='table' AND name=?"
        cursor = self.con.cursor()
        cursor.execute(sql, (table,))
        sql = cursor.fetchone()[0]
        cursor.close()
        return sql

    def size(self, file=None, suffix='B'):
        file = file or self.file
        num = os.path.getsize(file)
        for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
            if abs(num) < 1024.0:
                return ("%3.1f%s%s" % (num, unit, suffix))
            num /= 1024.0
        return ("%.1f%s%s" % (num, 'Yi', suffix))

    def zip(self, zip=None, file=None):
        if file is None:
            file = self.file
        if zip is None:
            zip = os.path.splitext(self.file)[0]+".7z"
        if os.path.isfile(zip):
            os.remove(zip)
        os.makedirs(os.path.dirname(zip), exist_ok=True)
        cmd = "7z a %s ./%s" % (zip, file)
        check_call(cmd.split(), stdout=DEVNULL, stderr=STDOUT)
        return self.size(zip)

    def find_cols(self, *cols):
        for t, cls in self.tables.items():
            for c in cols:
                if c in cls:
                    yield (t, c)
