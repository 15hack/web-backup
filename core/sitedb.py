from .lite import DBLite, one_factory
from .writer import MDWriter
import sqlite3
from bunch import Bunch
from functools import lru_cache
from textwrap import dedent
from .schemaspy import SchemasPy
import re

re_blank = re.compile(r'^\s*$\n', re.MULTILINE)

def get_dom(url):
    if url is None:
        return None
    slp = url.split("://", 1)
    if len(slp)!=2 and slp[0].lower() not in ("http", "https"):
        return None
    dom = slp[1]
    dom = dom.split("/", 1)[0]
    return dom

def build_tr(md_row, space=" "):
    md_row = md_row.strip()
    md_row = (i.strip() for i in md_row.split("\n"))
    md_row = (space+"|"+space).join(md_row)
    md_row = "|"+space+md_row+space+"|"
    return md_row

def write(f, sql, *args, end=None):
    if end is None:
        end = ";\n\n"
    if len(args) > 0:
        sql = sql.format(*args)
    sql = re_blank.sub("", sql)
    sql = dedent(sql).strip()
    f.write(sql+end)

class SiteDBLite(DBLite):
    def __init__(self, *args, total=None, **kargv):
        super().__init__(*args, **kargv)
        self.con.create_function("get_dom", 1, get_dom)
        self.id_sites={}
        self.total = total
        self.count = 0

    def get_site_id(self, site):
        if site not in self.id_sites:
            self.id_sites[site] = self.one("select ID from sites where url = '" + site + "'")
        if site not in self.id_sites or self.id_sites[site] is None:
            raise Exception("No se ha encontrado el ID del site "+site)
        return self.id_sites[site]

    def insert(self, table, **kargv):
        if table == "sites":
            if kargv.get("ID") is None:
                id = self.one("select max(ID) from sites")
                kargv["ID"] = (id or 0)+1
            if "url" in kargv:
                self.id_sites[kargv["url"]] = kargv["ID"]
        else:
            for k in ("site", "in_site"):
                if k in kargv and isinstance(kargv[k], str):
                    kargv[k] = self.get_site_id(kargv[k])
        super().insert(table, **kargv)
        if self.total is not None:
            self.count = self.count + 1
            print("Creando sqlite {0:.0f}%".format(
                self.count*100/self.total), end="\r")

    @property
    @lru_cache(maxsize=None)
    def links(self):
        links = self.select('''
            select
                distinct url
            from
                objects
            where
                url is not null and
                url!='#' and (
                    type!='wp_pmedia' or
                    (site, ID) in (select site, object from wp_comments)
                )
            order by
                site, ID
        ''', row_factory=one_factory)
        links = list(links)
        pages = self.select('''
            select distinct
            	t.url, p.posts, s.page_size
            from
            	sites s join
            (
            	select
            		p.site,
            		p.topic,
            		count(*) posts
            	from
            		phpbb_posts p
            	group by
            		p.site,
            		p.topic
            ) p
            on s.ID=p.site
            join phpbb_topics t
            on t.site=p.site and t.ID=p.topic
            where p.posts>s.page_size
            order by p.site, p.topic
        ''')
        for url, posts, size in pages:
            for p in range(size, posts, size):
                links.append(url+"&start="+str(p))
        return links

    def print_links(self, file):
        with open(file, "w") as f:
            for l in self.links:
                f.write(l+"\n")

    def get_info(self, site=None):
        where = ""
        if site is not None:
            where = " where site = "+str(site)
        fch = []
        for t, c in self.find_cols("date", "modified"):
            if site is not None and "site" not in self.tables[t]:
                continue
            if t == "wp_comments":
                continue
            fch.append("select substr({0}, 1, 10) d from {1}".format(c, t)+where)
        fch = '''
        select
            min(d) ini,
            max(d) fin
        from (
            {0}
        ) t
        where
            d>='2011-05-17' and
            d<=date('now')
        '''.format(" union \n".join(fch))
        ini, fin = self.one(fch)
        r = Bunch(
            ini=ini,
            fin=fin,
            counts={}
        )
        tables = tuple('''
            posts
            media
            comments
            tags
            pages
            topics
        '''.strip().split())
        if site is None:
            r.counts['sites']={
                '_total_':self.one("select count(*) from sites")
            }
            for tp, c in self.select("select type, count(*) c from sites group by type order by count(*) desc"):
                r.counts['sites'][tp]=c
        for t in sorted(self.tables):
            if t not in tables and t.split("_", 1)[-1] not in tables:
                continue
            r.counts[t]=self.one("select count(*) from "+t+where)
        return r

    def print_info(self, file, table_link=True):
        md=MDWriter(file)
        r = self.get_info()
        md.write(dedent('''
            Se han escaneado {t_sites} `sites`, con datos desde el {ini} al {fin},
            repartidos en:
        ''').format(t_sites=r.counts['sites']['_total_'], **dict(r)), end="\n\n")
        del r.counts['sites']['_total_']
        for t, c in r.counts['sites'].items():
            s = "" if c == 1 else "s"
            md.write("* {rows} sitio{s} `{type}`".format(type=t, rows=c, s=s))
        del r.counts['sites']
        for t, c in r.counts.items():
            md.write("* {rows} registros en `{table}`".format(table=t, rows=c))
        if "url" in self.tables["sites"]:
            def _sort_sites(x):
                id, url = x[:2]
                r = re.split(r"[/\?]", url, maxsplit=1)
                r[0]=tuple(reversed(r[0].split(".")))
                if len(r)==1:
                    r.append("")
                r.append(id)
                return tuple(r+list(x[2:]))

            md.write("")
            md.write("Lo que supone {urls} urls.".format(urls=len(self.links)))
            sites = self.select("select id, url from sites where type='wp'")
            sites = sorted(sites, key=_sort_sites)
            max_site = max(len(x[1]) for x in sites)
            md.write(dedent('''
                # Wordpress

                | SITE | post/page | Comentarios | Último uso | 1º uso | Último comentario |
                |:-----|----------:|------------:|-----------:|-------:|------------------:|
            ''').strip())
            for id, url in sites:
                info = self.get_info(id)
                row = dict(info.counts)
                row["ini"] = info.ini
                row["fin"] = info.fin
                row["site"] = url
                row["admin"] = "https://{}/wp-admin/".format(url)
                row["ult_comment"] = self.one("select IFNULL(substr(max(date), 1, 10), '') from wp_comments where site="+str(id))
                if row["ult_comment"] is None:
                    row["ult_comment"] = ""
                if table_link:
                    md_row = build_tr('''
                        [{site}](https://{site})
                        [{wp_posts}]({admin}edit.php?orderby=date&order=desc)
                        [{wp_comments}]({admin}edit-comments.php?comment_type=comment&orderby=comment_date&order=desc)
                        {fin}
                        {ini}
                        {ult_comment}
                    ''', space="")
                else:
                    md_row = build_tr('''
                        {site:<%s}
                        {wp_posts:>6}
                        {wp_comments:>6}
                        {fin}
                        {ini}
                        {ult_comment}
                    ''' % max_site)
                md.write(md_row.format(**row).strip())
            md.write("")
            sites = self.select("select id, url from sites where type='phpbb'")
            sites = sorted(sites, key=_sort_sites)
            max_site = max(len(x[1]) for x in sites)
            md.write(dedent('''
                # phpBB

                | SITE | topics | posts | Último uso | 1º uso |
                |:-----|-------:|------:|-----------:|-------:|
            ''').strip())
            for id, url in sites:
                info = self.get_info(id)
                row = dict(info.counts)
                row["ini"] = info.ini
                row["fin"] = info.fin
                row["site"] = url
                if table_link:
                    md_row = build_tr('''
                        [{site}](http://{site})
                        {phpbb_topics}
                        {phpbb_posts}
                        {fin}
                        {ini}
                    ''', space="")
                else:
                    md_row = build_tr('''
                        {site:<%s}
                        {phpbb_topics:>6}
                        {phpbb_posts:>6}
                        {fin}
                        {ini}
                    ''' % max_site)
                md.write(md_row.format(**row).strip())
            md.write("")
            sites = self.select("select id, url from sites where type='wiki'")
            sites = sorted(sites, key=_sort_sites)
            max_site = max(len(x[1]) for x in sites)
            md.write(dedent('''
                # MediaWiki

                | SITE | pages | Último uso | 1º uso |
                |:-----|------:|-----------:|-------:|
            ''').strip())
            for id, url in sites:
                info = self.get_info(id)
                row = dict(info.counts)
                row["ini"] = info.ini
                row["fin"] = info.fin
                row["site"] = url
                if table_link:
                    md_row = build_tr('''
                        [{site}](http://{site})
                        {wk_pages}
                        {fin}
                        {ini}
                    ''', space="")
                else:
                    md_row = build_tr('''
                        {site:<%s}
                        {wk_pages:>6}
                        {fin}
                        {ini}
                    ''' % max_site)
                md.write(md_row.format(**row).strip())
            md.write("")
            if table_link:
                md.write(dedent('''
                    Para reordenar la tabla puede usar las extensiones
                    [`Tampermonkey`](https://chrome.google.com/webstore/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo?hl=es)
                    o [`Greasemonkey`](https://addons.mozilla.org/es/firefox/addon/greasemonkey/)
                    con [`Github Sort Content`](https://greasyfork.org/en/scripts/21373-github-sort-content)
                '''))
        md.close

    def minimize(self, file):
        re_rem = re.compile(r"^\s*_.*$", re.MULTILINE)
        with open(file, "w") as f:
            write(f, "BEGIN TRANSACTION")
            write(f, "DELETE from wp_tags where (site, post) in (select site, id from wp_posts where url is null);")
            write(f, "DELETE from wk_media where url is null;")
            sql = "SELECT type, name FROM sqlite_master WHERE type in ('view', 'table') and name like '^_%' ESCAPE '^'"
            for r in self.select(sql):
                write(f, "DROP {0} {1}", *r, end=";\n")
            write(f, "", end="\n")
            tables = [i for i in self.tables.items() if not i[0].startswith("_")]
            flag = False
            for t, cs in tables:
                if "_delete" in cs:
                    write(f, "DELETE from {0} where _delete=1", t, end=";\n")
                    flag = True
            if flag:
                f.write("\n")
            for t, cs in tables:
                ok = []
                ko = []
                for c in cs:
                    if c.startswith("_"):
                        ko.append(c)
                    else:
                        ok.append(c)
                if len(ko) > 0:
                    write(f, "ALTER TABLE {0} RENAME TO temp_{0}", t)
                    sql = self.get_sql_table(t)
                    sql = re_rem.sub("", sql)
                    write(f, sql)
                    end = None
                    if "url" in ok:
                        end = "\nwhere url is not null;\n\n"
                    write(f, '''
                        INSERT INTO {0}
                            ({1})
                        SELECT
                            {2}
                        FROM
                            temp_{0}
                    ''', t, ", ".join(ok), ", ".join(ok), end=end)
                    write(f, "DROP TABLE temp_{0}", t)
            write(f, "COMMIT", end=";")

        self.execute(file)

    def save_diagram(self, file, *args, **kargv):
        sch = SchemasPy()
        sch.save_diagram(self.file, file, "-noviews", *args, **kargv)

if __name__ == "__main__":
    import sys
    from glob import glob
    from .util import unzip
    from shutil import copyfile, move
    from os.path import dirname, isfile, basename, isdir
    from os import makedirs, remove
    for db in sys.argv[1:]:
        pre = db.split("/")
        pre = pre[-1]
        pre = pre.split(".")
        pre = pre[0]
        pre_dt = pre[:10].replace("-", ".")
        print(db,"->", end=" ")
        db = unzip(db, get="*.db")
        print(db)
        tg = dirname(db)+"/{pre_dt}_wp.db".format(pre_dt=pre_dt)
        if not isfile(tg):
            print(db, "->", tg)
            move(db, tg)
        db.close(vacuum=True)
        target = "data/archive/{pre}/wp.7z".format(pre=pre)
        db.zip(target, file=tg)
        print(tg,"->", target)
        remove(tg)
    for zip in sorted(glob("data/archive/*/*.7z")):
        print(zip,"->", end=" ")
        target = dirname(zip) + "/"
        tg = unzip(zip, get="*.db")
        print(basename(tg))
        db = SiteDBLite(tg, readonly=True)
        db.print_links(target+"links.txt")
        db.print_info(target+"README.md", table_link=False)
        db.save_diagram(target+"diagram.png")
        db.close()
        remove(tg)
