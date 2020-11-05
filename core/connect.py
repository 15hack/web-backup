import os
import re
import sqlite3
from socket import gaierror, gethostbyname
from subprocess import DEVNULL, STDOUT, check_call
from urllib.parse import urlparse

import MySQLdb
import yaml
from bunch import Bunch
from sshtunnel import SSHTunnelForwarder

re_select = re.compile(r"^\s*select\b")
ip_dom = {}


def get_ip(dom):
    if dom in ip_dom:
        return ip_dom[dom]
    try:
        ip = gethostbyname(dom)
    except gaierror as e:
        ip = -1
    ip_dom[dom] = ip
    return ip


def get_yml(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        return list(yaml.load_all(f, Loader=yaml.FullLoader))


def str_list(s):
    if s is None or len(s) == 0:
        return []
    if isinstance(s, str):
        return s.split()
    return s


def build_result(c, to_tuples=False, to_bunch=False):
    results = c.fetchall()
    if len(results) == 0:
        return results
    if isinstance(results[0], tuple) and len(results[0]) == 1:
        return [a[0] for a in results]
    if to_tuples:
        return results
    cols = [(i, col[0]) for i, col in enumerate(c.description)]
    n_results = []
    for r in results:
        d = {}
        for i, col in cols:
            d[col] = r[i]
        if to_bunch:
            d = Bunch(**d)
        n_results.append(d)
    return n_results


def flat(*args):
    arr = []
    for a in args:
        if isinstance(a, str):
            arr.append(a)
        else:
            for i in a:
                arr.append(i)
    return arr


class DB:
    def __init__(self, server, host, ssh_private_key_password, user, passwd, remote_bind_address='127.0.0.1', remote_bind_port=3306, **kargv):
        self.server = SSHTunnelForwarder(
            host,
            ssh_private_key_password=ssh_private_key_password,
            remote_bind_address=(remote_bind_address, remote_bind_port)
        )
        self.host = host
        self.user = user
        self.passwd = passwd
        self.db = None
        self.ip = get_ip(server)
        self.forze_ok = [tuple(i.split(":", 1)) for i in str_list(kargv.get("forze_ok"))]
        self.db_ban = str_list(kargv.get("db_ban"))
        self.url_ban = str_list(kargv.get("url_ban"))
        self.dom_ban = str_list(kargv.get("dom_ban"))

    def connect(self):
        self.server.start()
        self.db = MySQLdb.connect(
            host='127.0.0.1',
            port=self.server.local_bind_port,
            user=self.user,
            passwd=self.passwd,
            charset='utf8'
        )

    def close(self):
        self.db.close()
        self.server.stop()

    def isOk(self, url):
        for u in self.url_ban:
            if u in url:
                return False
        return True

    def isOkDom(self, dom):
        if dom.startswith("http"):
            dom = urlparse(dom).netloc
        if get_ip(dom) != self.ip:
            return False
        for d in self.dom_ban:
            if dom == d or dom.endswith("." + d):
                return False
        return True

    def execute(self, file):
        cursor = self.db.cursor()
        _sql = None
        with open(file, 'r') as myfile:
            _sql = myfile.read()
        cursor.execute(_sql)
        result = cursor.fetchall()
        cursor.close()
        return flat(result)

    def multi_execute(self, vals, i_sql, where=None, order=None, debug=None, to_tuples=False):
        cursor = self.db.cursor()
        i_sql = i_sql.strip()

        if isinstance(vals, dict):
            vals = [flat(k, v) for k, v in vals.items()]
        if isinstance(vals[0], str):
            vals = [[v] for v in vals]

        if len(vals) > 1 or where or order:
            sql = "select distinct * from ("
            for v in sorted(vals):
                sql = sql+"(\n"+i_sql.format(*v)+"\n) UNION "
            sql = sql[:-7]
            sql = sql + "\n) T"
        else:
            sql = re_select.sub("select distinct", i_sql)
            sql = sql.format(*vals[0])
        if where:
            sql = sql + " where "+where
        if order:
            sql = sql + " order by "+order

        if debug:
            with open("debug/"+self.host+"_"+debug+".sql", "w") as f:
                f.write(sql)

        cursor.execute(sql)
        #results = cursor.fetchall()
        results = build_result(cursor, to_tuples=to_tuples)
        cursor.close()

        return results
        # return flat(results)

    def read_debug(self, debug):
        file = "debug/"+self.host+"_"+debug+".sql"
        with open(file, "r") as f:
            return f.read()

me = os.path.realpath(__file__)
dr = os.path.dirname(me)

DBs = (
    DB(**config) for config in get_yml(dr+"/config.yml")
)
