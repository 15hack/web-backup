import os
import re

from bunch import Bunch

from .data import FindUrl, loadwpjson
from functools import lru_cache
import requests


re_tg1 = re.compile(r'^(\s*"[^"]+?"\s*)+$')
re_tg2 = re.compile(r'"[^"]+?"')
re_rem = re.compile(r"^[^/]+")

def title(s, c='=', l=10):
    s = "{1} {0} {1}".format(s, c*(l-len(s)))
    if len(s) % 2 == 1:
        s = c + s
    return s

def clean_url(url):
    url = url.split("://", 1)[1]
    url = url.rstrip("/")
    return url

class ScrapDB:
    def __init__(self, fnd, *args, **kargv):
        self.fnd = fnd
        self.dbs = args

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
            print(title(db.host))
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
                key = (p2, site)
                if key not in db.forze_ok:
                    if p1 in db.db_ban or p2 in db.db_ban:
                        print("%s (%s) sera descartado" % (p2, site))
                        continue
                    if not db.isOkDom(siteurl) or not db.isOk(site):
                        print("%s (%s) sera descartado" % (p2, site))
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
                        'uploads_use_yearmonth_folders'
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
            print("")

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

        s_total = max(len(str(t)) for t in totales.values())
        s_total = "%"+str(s_total)+"s "

        print("%s %s serán guardados:" % (len(obj.sites), label))
        for k, v in totales.items():
            k = k.replace("_", "/")
            s = s_total+k
            print(s % v)
        print("")

    @property
    @lru_cache(maxsize=None)
    def phpbb(self):
        phpbb = Bunch(
            posts=[],
            comments=[],
            media=[],
            tags=[],
            sites={},
        )
        for db in self.dbs:
            print(title(db.host))
            db.connect()
            # https://wiki.phpbb.com/Tables

            results = db.execute('sql/search/phpbb.sql')
            print("%s phpbb encontrados" % len(results))

            results = db.multi_execute(results, '''
                select
                    '{prefix}' prefix,
                    config_name name,
                    config_value value
                from
                    {prefix}config
                where
                    config_name in (
                        'server_name',
                        'script_path',
                        'server_protocol',
                        'posts_per_page',
                        'upload_path'
                    )
        	''', debug="phpbb-sites")

            sites={}
            for o in results:
                site = o["server_name"] + o["script_path"]
                site = site.rstrip("/")
                del o["server_name"]
                del o["script_path"]
                o["_DB"] = o["prefix"]
                o["page_size"] = int(o["posts_per_page"])
                o["siteurl"] = site
                o["url"] = site
                o["purl"]= o["server_protocol"] + site
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
                print("")
                continue

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.post_id ID,
                    CASE
                        when t1.post_id = t2.topic_first_post_id then 'topic'
                        else 'post'
                    END type,
                    TRIM(t1.post_subject) title,
                    TRIM(t1.post_text) content,
                    from_unixtime(t1.post_time) date,
                    if(t1.post_edit_time=0, null, from_unixtime(t1.post_edit_time)) modified,
                    if(t1.post_id = t2.topic_first_post_id, null, t2.topic_first_post_id) _parent,
                    case
                        when t4.username is not null and TRIM(username)!='' then TRIM(t4.username)
                        else TRIM(t1.post_username)
                    end author
        		from
                    {prefix}posts t1
                    left join {prefix}topics t2 on t1.topic_id = t2.topic_id
                    left join {prefix}users t4  on t1.poster_id = t4.user_id
        		where
                    t1.{post_visibility} = 1 and
                    t2.{topic_visibility} = 1 and
                    t1.forum_id in {forums_ids}
        	''', debug="phpbb-posts")
            for r in results:
                if r["type"]=="topic":
                    phpbb.posts.append(results)
                else:
                    phpbb.comments.append(results)

            results = db.multi_execute(sites, '''
        		select
                    '{siteurl}' site,
                    t1.attach_id ID,
                    t1.mimetype type,
                    from_unixtime(t1.filetime) date,
                    t1.real_filename file,
                    TRIM(t4.username) author,
                    t1.post_msg_id _parent,
                    concat('{purl}/download/file.php?id=', t1.attach_id) url
        		from
                    {prefix}attachments t1
                    left join {prefix}users t4  on t1.poster_id = t4.user_id
        	''', debug="phpbb-media")
            phpbb.media.extend(results)

            db.close()
            phpbb.sites = {**phpbb.sites, **sites}
            print("")

        self.print_totales("phpbb", phpbb)
        return phpbb

if __name__ == "__main__":
    import json
    from .connect import DBs
    scr = ScrapDB(None, *DBs)
    print(json.dumps(scr.phpbb.sites, indent=4))
