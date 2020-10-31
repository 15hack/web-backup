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

class DBLite:
    def __init__(self, file, readonly=False, schemaspy=None):
        self.file = file
        self.readonly = readonly
        if self.readonly:
            file = "file:"+self.file+"?mode=ro"
            self.con = sqlite3.connect(
                file, detect_types=sqlite3.PARSE_DECLTYPES, uri=True)
        else:
            self.con = sqlite3.connect(
                self.file, detect_types=sqlite3.PARSE_DECLTYPES)
        self.tables = None
        self.load_tables()
        self.inTransaction = False
        self._schemaspy=Bunch(
            driver="https://github.com/xerial/sqlite-jdbc/releases/download/3.32.3.2/sqlite-jdbc-3.32.3.2.jar",
            jar="https://github.com/schemaspy/schemaspy/releases/download/v6.1.0/schemaspy-6.1.0.jar",
            home=schemaspy
        )
        if self._schemaspy.home is None and os.path.isdir("schemaspy"):
            self._schemaspy.home = "schemaspy"

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

    def get_objects(self, *tp):
        if len(tp)==1:
            sql = "SELECT name FROM sqlite_master WHERE type = '%s'" % tp[0]
        else:
            if not tp:
                tp = ('table', 'view')
            sql = "SELECT name FROM sqlite_master WHERE type in " + str(tp)
        return list(self.select(sql, row_factory=one_factory))

    def load_tables(self):
        self.tables = CaseInsensitiveDict()
        for t in self.get_objects():
            try:
                self.tables[t] = self.get_cols("select * from "+t+" limit 0")
            except:
                pass

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
        self.con.execute(sql, vals)
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
        if len(r)==1:
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
        cls = None
        for t in self.get_objects('table'):
            try:
                cls = self.get_cols("select * from "+t+" limit 0")
            except:
                continue
            for t, cls in self.tables.items():
                for c in cols:
                    if c in cls:
                        yield (t, c)

    def schemaspy(self, out=None):
        # https://github.com/schemaspy/schemaspy/issues/524#issuecomment-496010502
        if self._schemaspy.home is None:
            self._schemaspy.home = tempfile.mkdtemp()
        if not os.path.isdir(self._schemaspy.home):
            os.makedirs(self._schemaspy.home, exist_ok=True)
        if out is None:
            out = tempfile.mkdtemp()
        root = os.path.realpath(self._schemaspy.home)+"/"
        reload = False
        for k, url in list(self._schemaspy.items()):
            if k not in ("driver", "jar"):
                continue
            name = os.path.basename(url)
            self._schemaspy["_"+k] = name
            if not os.path.isfile(root+name):
                reload = True
                print("wget", url)
                urlretrieve(url, root+name)
        target = root+"sqlite.properties"
        if reload or not os.path.isfile(target):
            with open(target, "w") as f:
                f.write(dedent('''
                    driver=org.sqlite.JDBC
                    description=SQLite
                    driverPath={driver}
                    connectionSpec=jdbc:sqlite:<db>
                ''').format(driver=self._schemaspy._driver).strip())

        target = root+"schemaspy.properties"
        if reload or not os.path.isfile(target):
            with open(root+"schemaspy.properties", "w") as f:
                f.write(dedent('''
                    schemaspy.t=sqlite
                    schemaspy.sso=true
                ''').strip())
        name = os.path.basename(self.file)
        name = name.rsplit(".", 1)[0]
        cmd = "java -jar {root}{schemaspy} -dp {root} -db {db} -o {out} -cat {name} -s {name} -u {name}".format(
            schemaspy=self._schemaspy._jar,
            root=root,
            db=os.path.realpath(self.file),
            out=os.path.realpath(out),
            name=name,
        )
        current_dir = os.getcwd()
        os.chdir(root)
        print(cmd)
        check_call(cmd.split(), stdout=DEVNULL, stderr=STDOUT)
        os.chdir(current_dir)
        return out

    def save_diagram(self, file):
        out = self.schemaspy()
        im = Image.open(out+"/diagrams/summary/relationships.real.compact.png")
        box = im.getbbox()
        box = list(box)
        box[3] = box[3] - 45
        gr = im.crop(tuple(box))
        gr.save(file)
        gr.close()
        im.close()
