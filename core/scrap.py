import os
import re

from bunch import Bunch

from .data import FindUrl, tuple_url, loadwpjson, loadpageswkjson, loadimageswkjson, requests_json, getphpbbhtml
from .util import find_value, get_yml
from .connect import DB, SSHFile, SSHCmd
from functools import lru_cache
import json
from datetime import datetime
import requests

me = os.path.realpath(__file__)
dr = os.path.dirname(me)

re_tg1 = re.compile(r'^(\s*"[^"]+?"\s*)+$')
re_tg2 = re.compile(r'"[^"]+?"')
re_rem = re.compile(r"^[^/]+")

flag_frm_title=False

def frm_title(s, c='=', l=10):
    global flag_frm_title
    s = "{1} {0} {1}".format(s, c*(l-len(s)))
    if len(s) % 2 == 1:
        s = c + s
    if flag_frm_title:
        s = "\n" + s
    flag_frm_title = True
    return s

def clean_url(url):
    if "://" in url:
        url = url.split("://", 1)[1]
    url = url.rstrip("/")
    return url

class SetDom(set):
    def add(self, a, www=True):
        super().add(a)
        a = clean_url(a)
        super().add(a)
        if "/" in a:
            super().add(a.split("/", 1)[0])
        if www:
            if a.startswith("www."):
                a = a[4:]
                self.add(a, www=False)
            else:
                self.add("www." + a, www=False)

class Scrap:
    def __init__(self, **kargv):
        self.fnd = FindUrl("out/error.md")
        self.config = get_yml(dr+"/config.yml")
        self.dbs = tuple(
            DB(**c) for c in self.config if c.get("db_user")
        )
        self.files = tuple(
            SSHFile(**c, debug="debug/") for c in self.config if c.get("file")
        )
        self.cmd = tuple(
            SSHCmd(**c, debug="debug/") for c in self.config if c.get("cmd")
        )
        self.done=SetDom()

    def close(self):
        self.fnd.close()

    @property
    def sites(self):
        for key, val in {
            "wp":self.wp,
            "phpbb":self.phpbb,
            "wiki":self.wiki,
            "mailman":self.mailman,
            "apache":self.apache
        }.items():
            val = val.sites
            if isinstance(val, dict):
                val = val.values()
            for meta in sorted(val, key=lambda x: tuple_url(x["url"])):
                meta["type"]=key
                yield meta

    @property
    def rows(self):
        rows = 0
        for d in (self.wp, self.phpbb, self.wiki, self.mailman, self.apache):
            rows = rows + sum((len(i) for i in dict(d).values()), 0)
        return rows

    @property
    @lru_cache(maxsize=None)
    def wp(self):
        wp = Bunch(
            posts=[],
            comments=[],
            media=[],
            tags=[],
            sites={},
        )
        for db in self.dbs:
            print(frm_title(db.host))
            db.connect()
            # https://codex.wordpress.org/Option_Reference

            results = db.execute('sql/search/wp.sql')
            print("%s wordpress encontrados" % len(results))

            results = db.multi_execute(results, '''
                select
                    '{prefix1}' prefix1,
                    '{prefix2}' prefix2,
                    option_value siteurl
                from
                    {prefix2}options
                where
                    option_name = 'siteurl'
        	''', order="siteurl", debug="wp-sites")

            sites = {}
            for r in results:
                p1 = r["prefix1"]
                p2 = r["prefix2"]
                siteurl = r["siteurl"]
                site = clean_url(siteurl)
                self.done.add(site)
                key = (p2, site)
                if p1 in db.db_ban or p2 in db.db_ban:
                    print("%s (%s) sera descartado" % key)
                    continue
                if not db.isOkDom(siteurl) or not db.isOk(site):
                    print("%s (%s) sera descartado" % key)
                    continue
                r["siteurl"] = site
                r["url"] = site
                r["_DB"] = r["prefix2"]
                sites[site] = r

            results = db.multi_execute(sites, '''
                select
                    '{siteurl}' siteurl,
                    case
                        when option_name = 'fileupload_url' then 'files'
                        when option_name = 'permalink_structure' then 'permalink'
                        when option_name = 'comments_per_page' then 'page_size'
                        when option_name = 'blogname' then 'title'
                        else option_name
                    end name,
                    option_value value
                from
                    {prefix2}options
                where
                    option_name in (
                        'fileupload_url',
                        'permalink_structure',
                        'rewrite_rules',
                        'upload_url_path',
                        'upload_path',
                        'uploads_use_yearmonth_folders',
                        'comments_per_page',
                        'blogname'
                    )
        	''', order="siteurl", debug="wp-metasite", to_tuples=True)

            for siteurl, name, value in results:
                if value.startswith("http"):
                    st = re_rem.sub("", siteurl)
                    value = re_rem.sub("", clean_url(value))
                    if value.startswith(st):
                        value = value[len(st):]
                sites[siteurl][name]=value

            results = db.multi_execute(sites, '''
                select
                    '{siteurl}' site,
                    comment_approved,
                    count(*) c
                from
                    {prefix2}comments tp
                where
                    comment_approved in ('spam', '0')
                group by
                    comment_approved
            ''', debug="wp-spam", to_tuples=True)
            for site, comment_approved, c in results:
                b = sites[site]
                if comment_approved == "spam":
                    b["spam"] = c
                elif comment_approved in ("0", 0):
                    b["unapproved"] = c

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.ID ID,
                    t1.post_type type,
                    t1.post_date date,
                    t1.post_modified modified,
                    if(t1.post_parent=0, null, t1.post_parent) _parent,
                    TRIM(t1.post_content) _content,
                    TRIM(t1.post_title) title,
                    TRIM(t2.display_name) author
        		from
                    {prefix2}posts t1
                    left join {prefix1}users t2 on t1.post_author = t2.ID
                    left join {prefix2}posts t3 on t1.post_parent = t3.ID
        		where
            		(
                        t1.post_status = 'publish' or
                        (t1.post_status='inherit' and t3.post_status = 'publish')
                    ) and
            		t1.post_type in ('post', 'page')
        	''', debug="wp-posts")
            wp.posts.extend(results)

            results = db.multi_execute(sites, '''
                select
                    '{siteurl}' site,
                    comment_ID ID,
                    comment_post_ID object,
                    comment_author author,
                    comment_date date,
                    comment_content content,
                    if(comment_parent=0, NULL, comment_parent) parent,
                    comment_author_url author_url,
                    comment_author_email author_email,
                    comment_type type
                from
                    {prefix2}comments
                where
                    comment_type not in ('pingback', 'trackback') and
                    comment_approved=1 and
                    comment_post_ID in (
                        select
                            t1.ID
                        from
                            {prefix2}posts t1 left join {prefix2}posts t3 on t1.post_parent = t3.ID
                		where
                    		(
                                 t1.post_status='publish' or
                                (t1.post_status='inherit' and t3.post_status='publish')
                            ) and
                            t1.post_type in ('post', 'page', 'attachment')
                    )
            ''', debug="wp-comments")
            wp.comments.extend(results)

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.ID ID,
                    t1.post_mime_type type,
                    t1.post_date date,
                    t1.post_modified modified,
                    if(t1.post_parent=0, null, t1.post_parent) _parent,
                    pm.meta_value file,
                    TRIM(t2.display_name) author,
                    t1.guid,
                    CASE
                        when t1.post_status='publish' then 'publish'
                        when t1.post_status='inherit' and t3.post_status='publish' then 'publish'
                        else NULL
                    END status
        		from
                    {prefix2}posts t1
                    left join {prefix1}users t2 on t1.post_author = t2.ID
                    left join {prefix2}posts t3 on t1.post_parent = t3.ID
                    left join {prefix2}postmeta pm on pm.post_id = t1.ID and pm.meta_key = '_wp_attached_file'
        		where
                    t1.post_type = 'attachment'
            		-- and (
                    --     t1.post_status = 'publish' or
                    --     (t1.post_status='inherit' and t3.post_status = 'publish')
                    -- )
        	''', debug="wp-media")
            wp.media.extend(results)

            results = db.multi_execute(sites, '''
                select
                    '{siteurl}' site,
                    tp.ID post,
                    TRIM(tm.name) tag,
                    if(tt.taxonomy='category', 1 ,2) type
                from
                    {prefix2}term_relationships tr inner join
                    {prefix2}term_taxonomy tt on
                    tr.term_taxonomy_id = tt.term_taxonomy_id inner join
                    {prefix2}terms tm
                    on tm.term_id=tt.term_id join
                    {prefix2}posts tp
                    on tr.object_id=tp.ID
                where
                    tt.taxonomy in ('post_tag', 'category') and
                    tm.slug not like 'sin-categoria%' and
                    tm.slug not like 'uncategorized%' and
                    lower(TRIM(tm.name)) not like 'sin categoría%' and
                    tp.ID in (
                		select
                            t1.ID ID
                		from
                            {prefix2}posts t1
                            left join {prefix1}users t2 on t1.post_author = t2.ID
                            left join {prefix2}posts t3 on t1.post_parent = t3.ID
                		where
                    		(
                                t1.post_status = 'publish' or
                                (t1.post_status='inherit' and t3.post_status = 'publish')
                            ) and
                    		t1.post_type in ('post', 'page')
                    )
        	''', debug="wp-tags")

            for data in results:
                name = data["tag"]
                if not re_tg1.match(name):
                    wp.tags.append(data)
                    continue
                for i in set(re_tg2.findall(name)):
                    name = i[1:-1].strip()
                    if len(name) > 0:
                        n_data = dict(data)
                        n_data["tag"] = name
                        wp.tags.append(n_data)

            db.close()
            wp.sites = {**wp.sites, **sites}

        self.print_totales("wordpress", wp)

        objects = wp.posts + wp.media
        print("Recuperando información de api wp-json (si existe) ...", end="\r")
        for site, meta in wp.sites.items():
            _objs = {}
            for i in objects:
                if i["site"] == site:
                    _objs[i["ID"]] = i
            meta["wpjson"] = loadwpjson(site, _objs)
        print("Recuperando información de api wp-json (si existe) 100%")

        for data in wp.posts:
            site = wp.sites[data["site"]]
            wp_data = site["wpjson"].get(data["ID"], {})
            data["_WPJSON"] = bool(wp_data)
            data["content"] = wp_data.get("html")
            data["url"] = wp_data.get("link")
            if data["url"] in (None, "#"):
                data["url"] = self.fnd.get(site, data)

        media = []
        for i, data in reversed(list(enumerate(wp.media))):
            site = wp.sites[data["site"]]
            wp_data = site["wpjson"].get(data["ID"], {})
            data["_WPJSON"] = bool(wp_data)
            data["page"] = wp_data.get("link")
            data["url"] = wp_data.get("source_url", wp_data.get("link"))
            if not data.get("file", None) and "/files/" in data.get("guid", ""):
                data["file"] = "/" + data["guid"].split("/files/", 1)[-1]
            if data["url"] in (None, "#"):
                data["url"] = self.fnd.get(site, data)
            if data["page"] in (None, "#") and data["status"]=="publish":
                data["page"] = self.fnd.get(site, data, attachment_id=True)
            if data["url"] in (None, "#") and data["page"] in (None, "#") and data["status"]!="publish" and not(data["_WPJSON"]):
                del wp.media[i]

        return wp

    def print_totales(self, label, obj):
        totales = {
            k:len(v) for k, v in dict(obj).items() if k!="sites"
        }
        val = obj.sites
        if isinstance(val, dict):
            val = val.values()
        for s in val:
            self.done.add(s['url'])
        if not totales:
            print("%s %s serán guardados" % (len(obj.sites), label))
            return

        s_total = max(len(str(t)) for t in totales.values())
        s_total = "%"+str(s_total)+"s "

        print("%s %s serán guardados:" % (len(obj.sites), label))
        for k, v in totales.items():
            k = k.replace("_", "/")
            s = s_total+k
            print(s % v)

    @property
    @lru_cache(maxsize=None)
    def phpbb(self):
        phpbb = Bunch(
            topics=[],
            posts=[],
            media=[],
            sites={},
        )
        for db in self.dbs:
            print(frm_title(db.host))
            db.connect()
            # https://wiki.phpbb.com/Tables

            results = db.execute('sql/search/phpbb.sql')
            print("%s phpbb encontrados" % len(results))

            results = db.multi_execute(results, '''
                select
                    '{prefix}' prefix,
                    case
                        when config_name = 'upload_path' then 'files'
                        when config_name = 'posts_per_page' then 'page_size'
                        when config_name = 'sitename' then 'title'
                        else config_name
                    end name,
                    config_value value
                from
                    {prefix}config
                where
                    config_name in (
                        'server_name',
                        'script_path',
                        'server_protocol',
                        'posts_per_page',
                        'upload_path',
                        'sitename'
                    )
        	''', debug="phpbb-sites")

            sites={}
            for o in results:
                site = o["server_name"] + o["script_path"]
                site = site.rstrip("/")
                del o["server_name"]
                del o["script_path"]
                o["_DB"] = o["prefix"]
                o["siteurl"] = site
                o["url"] = site
                o["purl"]= o["server_protocol"] + site
                key = (o["prefix"], site)
                if o["prefix"] in db.db_ban:
                    print("%s (%s) sera descartado" % key)
                    continue
                if not db.isOkDom(o["purl"]) or not db.isOk(site):
                    print("%s (%s) sera descartado" % key)
                    continue
                if db.one("select count(*) from "+o["_DB"]+"posts") == 0:
                    print("%s (%s) sera descartado (0 posts)" % (o["prefix"], site))
                    continue
                fake_id = db.one("select min(forum_id)-1 from "+o["_DB"]+"forums")
                if fake_id is None:
                    print("%s (%s) sera descartado (0 forums)" % (o["prefix"], site))
                    continue
                o["post_visibility"] = db.find_col(o["_DB"]+"posts", "post_visibility", "post_approved")
                o["topic_visibility"] = db.find_col(o["_DB"]+"topics", "topic_visibility", "topic_approved")
                fake_id = min(-1, fake_id)
                forums_ids=[]
                viewforum = o["server_protocol"] + site + "/viewforum.php?f="
                sql='''
                    select
                        forum_id
                    from
                        {prefix}forums
                    where
                        (forum_password is null or trim(forum_password)='') and
                        forum_id in (select forum_id from {prefix}posts where {post_visibility} = 1)
                '''.format(**o)
                for id in db.select(sql):
                    r = requests.get(viewforum+str(id), verify=False)
                    if re.search(r'<a\s+href\s*=\s*"[^"]*/viewforum\.php\?f='+str(id)+r'["&]', r.text):
                        forums_ids.append(id)
                if len(forums_ids)==0:
                    print("%s (%s) sera descartado (0 forums visibles)" % (o["prefix"], site))
                    continue
                if len(forums_ids)==1:
                    forums_ids.append(fake_id)
                o["forums_ids"]=tuple(sorted(forums_ids))
                sites[site]=o

            if not sites:
                db.close()
                continue

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t2.topic_id ID,
                    TRIM(t2.topic_title) title,
                    from_unixtime(t2.topic_time) date,
                    TRIM(t4.username) author,
                    concat('{purl}/viewtopic.php?f=', t2.forum_id, '&t=', t2.topic_id) url,
                    t2.forum_id parent
        		from
                    {prefix}topics t2
                    left join {prefix}users t4 on t2.topic_poster = t4.user_id
        		where
                    t2.{topic_visibility} = 1 and
                    t2.forum_id in {forums_ids}
        	''', debug="phpbb-topics")
            phpbb.topics.extend(results)

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.post_id ID,
                    t1.topic_id topic,
                    TRIM(t1.post_subject) title,
                    TRIM(t1.post_text) _content,
                    from_unixtime(t1.post_time) date,
                    if(t1.post_edit_time=0, null, from_unixtime(t1.post_edit_time)) modified,
                    case
                        when t4.username is not null and TRIM(username)!='' then TRIM(t4.username)
                        else TRIM(t1.post_username)
                    end author,
                    concat('{purl}/viewtopic.php?p=', t1.post_id) url
        		from
                    {prefix}posts t1
                    left join {prefix}topics t2 on t1.topic_id = t2.topic_id
                    left join {prefix}users t4 on t1.poster_id = t4.user_id
        		where
                    t1.{post_visibility} = 1 and
                    t2.{topic_visibility} = 1 and
                    t1.forum_id in {forums_ids}
        	''', debug="phpbb-posts")
            phpbb.posts.extend(results)

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.attach_id ID,
                    t1.mimetype type,
                    from_unixtime(t1.filetime) date,
                    t1.real_filename file,
                    TRIM(t4.username) author,
                    t1.post_msg_id post,
                    t1.topic_id topic,
                    attach_comment comment,
                    concat('{purl}/download/file.php?id=', t1.attach_id) url
        		from
                    {prefix}attachments t1
                    left join {prefix}users t4  on t1.poster_id = t4.user_id
                where
                    is_orphan!=1 and
                    t1.post_msg_id in (
                        select
                            t1.post_id ID
                        from
                            {prefix}posts t1
                            left join {prefix}topics t2 on t1.topic_id = t2.topic_id
                            left join {prefix}users t4  on t1.poster_id = t4.user_id
                        where
                            t1.{post_visibility} = 1 and
                            t2.{topic_visibility} = 1 and
                            t1.forum_id in {forums_ids}
                    )
        	''', debug="phpbb-media")
            phpbb.media.extend(results)

            db.close()
            phpbb.sites = {**phpbb.sites, **sites}

        self.print_totales("phpbb", phpbb)
        print("\nRecuperando html de los posts...", end="\r")
        htmls={}
        for p in phpbb.posts:
            if p['url'] not in htmls:
                htmls = {**htmls, **getphpbbhtml(p['url'])}
            p['content'] = htmls[p['url']]
        print("Recuperando html de los posts 100%")
        return phpbb

    @property
    @lru_cache(maxsize=None)
    def wiki(self):
        wiki = Bunch(
            pages=[],
            media=[],
            sites={},
        )
        for db in self.dbs:
            print(frm_title(db.host))
            db.connect()
            # https://www.mediawiki.org/wiki/Manual:Database_layout

            results = db.execute('sql/search/wiki.sql')
            print("%s wikis encontrados" % len(results))

            sites={}
            for o in results:
                data = db.db_meta.get(o["prefix"])
                if data is None:
                    print("%s sera descartado (no aparece en db_meta)" % o["prefix"])
                    continue
                o = {**o, **data}
                o["_DB"] = o["prefix"]
                o["url"] = o["site"]
                o["siteurl"] = o["site"]
                key = (o["prefix"], o["site"])
                if o["prefix"] in db.db_ban:
                    print("%s (%s) sera descartado" % key)
                    continue
                if not db.isOkDom(o["purl"]) or not db.isOk(o["site"]):
                    print("%s (%s) sera descartado" % key)
                    continue
                o["title"] = requests_json(o["api"]+"query&meta=siteinfo", "query", "general", "sitename")
                sites[o["site"]]=o

            if not sites:
                db.close()
                continue

            # https://gerrit.wikimedia.org/g/mediawiki/core/+/HEAD/includes/Defines.php#64
            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    p.page_id ID,
                    p.page_namespace namespace,
                    CONVERT(p.page_title USING utf8) title,
                    CONVERT(t.old_text USING utf8) _content,
                    TIMESTAMP(rA.rev_timestamp) date,
                    TIMESTAMP(rZ.rev_timestamp) modified,
                    TIMESTAMP(p.page_touched) touched,
                    CONCAT('{api}', 'parse&prop=text&formatversion=2&pageid=', p.page_id) _parse
                from
                    {prefix}page p
                    INNER JOIN
                    {prefix}revision rZ ON p.page_latest = rZ.rev_id
                    INNER JOIN
                    {prefix}revision rA ON p.page_id = rA.rev_page
                    INNER JOIN
                    {prefix}text t ON rZ.rev_text_id = t.old_id
                where
                    rZ.rev_deleted = 0 and
                    rA.rev_parent_id = 0 and
                    p.page_is_redirect = 0
        	''', debug="wiki-pages", order="site, ID")
            wiki.pages.extend(results)

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    CONVERT(p.img_name USING utf8) ID,
                    CONCAT(p.img_major_mime, '/', p.img_minor_mime) type,
                    TIMESTAMP(p.img_timestamp) date
                from
                    {prefix}image p
        	''', debug="wiki-media", order="site, ID")
            wiki.media.extend(results)

            db.close()
            wiki.sites = {**wiki.sites, **sites}

        print("\nRecuperando información de api wk-json ...", end="\r")
        for site, meta in wiki.sites.items():
            _objs = {}
            for i in wiki.pages:
                if i["site"] == site:
                    _objs[i["ID"]] = i
            meta["wkpagesjson"] = loadpageswkjson(meta['api'], site, _objs)
            _objs = {}
            for i in wiki.media:
                if i["site"] == site:
                    _objs[i["ID"]] = i
            meta["wkimagesjson"] = loadimageswkjson(meta['api'], site, _objs)
        print("Recuperando información de api wk-json) 100%")

        for data in wiki.pages:
            site = wiki.sites[data["site"]]
            wk_data = site["wkpagesjson"].get(data["ID"], {})
            data["_WKJSON"] = bool(wk_data)
            data["content"] = wk_data.get("text")
            title = (wk_data.get("title") or "").strip()
            if len(title)>0:
                data["title"]=title
            data["url"] = find_value(wk_data, "canonicalurl", "fullurl", avoid="#")
            if data["url"] and "error" in wk_data:
                self.fnd.check(data["url"])

        for data in wiki.media:
            site = wiki.sites[data["site"]]
            wk_data = site["wkimagesjson"].get(data["ID"], {})
            data["_WKJSON"] = bool(wk_data)
            data["url"] = find_value(wk_data, "url", avoid="#")

        self.print_totales("wiki", wiki)
        return wiki

    @property
    @lru_cache(maxsize=None)
    def mailman(self):
        mailman = Bunch(
            sites=[],
            lists=[],
            archive=[]
        )
        for sshfile in self.files:
            if not sshfile.file.get("mailman"):
                continue
            print(frm_title(sshfile.host))
            sites = []
            fdate = None
            for site, lsts in sshfile.file['mailman'].items():
                if site.startswith("__"):
                    if site == "__timestamp__":
                        fdate = datetime.fromtimestamp(lsts)
                    continue
                if not sshfile.isOkDom(site) or not sshfile.isOk(site):
                    print("%s sera descartado" % site)
                    continue
                r = self.fnd.check(site)
                if int(r.code/100) in (4, 5, 9):
                    print("%s sera descartado (%s)" % (site, r.code))
                    continue
                sites.append(site)

            if fdate:
                print("%s mailman encontrados (%s)" % (len(sites), fdate.strftime("%Y-%m-%d %H:%M")))
            else:
                print("%s mailman encontrados" % len(sites))

            for site in sites:
                lsts = sshfile.file['mailman'][site]
                site = site.split("://", 1)[-1]
                mailman.sites.append({
                    "url": site,
                })
                for l in lsts:
                    ls = {
                        "site": site,
                        "ID": l["mail"],
                        "first_mail": l["archive"]["first_date"],
                        "last_mail": l["archive"]["last_date"],
                        "date": l["created_at"],
                        "url": l["url"]["listinfo"],
                        "owner": l["users"]["owner"],
                        "moderator": l["users"]["moderator"],
                        "members": l["users"]["members"],
                        "total_users": l["users"]["total"],
                        "mails": l["archive"]["mails"],
                        "archiving": l["archive"]["archive"],
                        "exists_archive": l["archive"]["__exists__"],
                        "description": l["description"]
                    }
                    ls = {**l['visibility'], **ls}
                    for k, v in list(ls.items()):
                        if v is not None and isinstance(v, list):
                            ls[k]=len(v)
                    #if ls["last_mail"] is None or ls["last_mail"]<l["last_post_time"]:
                    #    ls["last_mail"] = l["last_post_time"]
                    for k in "date last_mail first_mail".split():
                        if ls[k] is not None:
                            ls[k]=datetime.fromtimestamp(ls[k])
                    mailman.lists.append(ls)
                    if l["url"]["archive"]:
                        mailman.archive.append({
                            "site": site,
                            "list": l["mail"],
                            "type": "archive",
                            "url": l["url"]["archive"]
                        })
                    for url in l["archive"]["urls"]:
                        mailman.archive.append({
                            "site": site,
                            "list": l["mail"],
                            "type": "mail",
                            "url": url
                        })
        self.print_totales("mailman", mailman)
        return mailman

    @property
    @lru_cache(maxsize=None)
    def apache(self):
        apache = Bunch(
            sites=[],
        )
        for sshcmd in self.cmd:
            if not sshcmd.cmd.get("apache"):
                continue
            print(frm_title(sshcmd.host))
            sites=set()
            for site in sshcmd.cmd['apache']:
                if site.startswith("#"):
                    continue
                site = site.split(None, 1)[-1]
                if site[0] in ("*", "$"):
                    continue
                if site in self.done:
                    continue
                sites.add(site)
            print("%s sitios apache encontrados" % len(sites))
            for site in sorted(sites, key=lambda x: tuple_url(x)):
                if not sshcmd.isOkDom(site) or not sshcmd.isOk(site):
                    print("%s sera descartado" % site)
                    continue
                r = self.fnd.check(site)
                if int(r.code/100) in (4, 5, 9):
                    print("%s sera descartado (%s)" % (site, r.code))
                    continue
                apache.sites.append({
                    "url": site
                })
        self.print_totales("apache", apache)
        return apache

if __name__ == "__main__":
    scr = Scrap()
    print(json.dumps(scr.apache.sites, indent=2))
    scr.close()
