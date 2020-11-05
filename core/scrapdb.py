import os
import re

from bunch import Bunch

from .data import FindUrl, tuple_dom, loadwpjson
from functools import lru_cache

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
        posts = []
        comments = []
        media = []
        tags = []
        site_meta = {}
        for db in self.dbs:
            print(title(db.host))
            db.connect()

            results = db.execute('sql/search-wp.sql')
            prefixes = sorted([r for r in results if r[0]
                               not in db.db_ban and r[1] not in db.db_ban])
            print("%s wordpress encontrados" % len(prefixes))

            results = db.multi_execute(prefixes, '''
                select
                    '{0}' prefix1,
                    '{1}' prefix2,
                    option_value siteurl
                from
                    {1}options
                where
                    option_name = 'siteurl'
        	''', order="siteurl", debug="sites", to_tuples=True)

            sites = {}
            for p1, p2, siteurl in results:
                site = clean_url(siteurl)
                key = (p2, site)
                if key not in db.forze_ok and (not db.isOkDom(siteurl) or not db.isOk(site)):
                    print("%s (%s) sera descartado" % (p2, site))
                    continue
                sites[site] = (p1, p2)
            # https://codex.wordpress.org/Option_Reference
            results = db.multi_execute(sites, '''
                select
                    '{0}' siteurl,
                    case
                        when option_name = 'fileupload_url' then 'files'
                        when option_name = 'permalink_structure' then 'permalink'
                        when option_name = 'permalink_structure' then 'permalink'
                        else option_name
                    end name
                    ,
                    option_value
                from
                    {2}options
                where
                    option_name in (
                        'fileupload_url',
                        'permalink_structure',
                        'rewrite_rules',
                        'upload_url_path',
                        'upload_path',
                        'uploads_use_yearmonth_folders'
                    )
        	''', order="siteurl", debug="metasite", to_tuples=True)

            for siteurl, name, value in results:
                if value.startswith("http"):
                    st = re_rem.sub("", siteurl)
                    value = re_rem.sub("", clean_url(value))
                    if value.startswith(st):
                        value = value[len(st):]
                meta = site_meta.get(siteurl, {"_DB": sites[siteurl][1]})
                meta[name] = value
                meta["url"] = siteurl
                site_meta[siteurl] = meta

            results = db.multi_execute(sites, '''
                select
                    '{0}' site,
                    comment_approved,
                    count(*) c
                from
                    {2}comments tp
                where
                    comment_approved in ('spam', '0')
                group by
                    comment_approved
            ''', debug="spam", to_tuples=True)
            for site, comment_approved, c in results:
                b = site_meta[site]
                if comment_approved == "spam":
                    b["spam"] = c
                elif comment_approved in ("0", 0):
                    b["unapproved"] = c

            results = db.multi_execute(sites, '''
        		select
                    '{0}' site,
                    t1.ID ID,
                    t1.post_type type,
                    t1.post_date date,
                    t1.post_modified modified,
                    if(t1.post_parent=0, null, t1.post_parent) _parent,
                    TRIM(t1.post_content) content,
                    TRIM(t1.post_title) title,
                    TRIM(t2.display_name) author,
                    TRIM(t1.post_name) name
        		from
                    {2}posts t1
                    left join {1}users t2 on t1.post_author = t2.ID
                    left join {2}posts t3 on t1.post_parent = t3.ID
        		where
            		(
                        t1.post_status = 'publish' or
                        (t1.post_status='inherit' and t3.post_status = 'publish')
                    ) and
            		t1.post_type in ('post', 'page')
        	''', debug="posts")
            posts.extend(results)

            results = db.multi_execute(sites, '''
                select
                    '{0}' site,
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
                    {2}comments
                where
                    comment_type not in ('pingback', 'trackback') and
                    comment_approved=1 and
                    comment_post_ID in (
                        select
                            t1.ID
                        from
                            {2}posts t1 left join {2}posts t3 on t1.post_parent = t3.ID
                		where
                    		(
                                 t1.post_status='publish' or
                                (t1.post_status='inherit' and t3.post_status='publish')
                            ) and
                            t1.post_type in ('post', 'page', 'attachment')
                    )
            ''', debug="comments")
            comments.extend(results)

            results = db.multi_execute(sites, '''
        		select
                    '{0}' site,
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
                    {2}posts t1
                    left join {1}users t2 on t1.post_author = t2.ID
                    left join {2}posts t3 on t1.post_parent = t3.ID
                    left join {2}postmeta pm on pm.post_id = t1.ID and pm.meta_key = '_wp_attached_file'
        		where
                    t1.post_type = 'attachment'
            		-- and (
                    --     t1.post_status = 'publish' or
                    --     (t1.post_status='inherit' and t3.post_status = 'publish')
                    -- )
        	''', debug="media")
            media.extend(results)

            results = db.multi_execute(sites, '''
                select
                    '{0}' site,
                    tp.ID post,
                    TRIM(tm.name) tag,
                    if(tt.taxonomy='category', 1 ,2) type
                from
                    {2}term_relationships tr inner join
                    {2}term_taxonomy tt on
                    tr.term_taxonomy_id = tt.term_taxonomy_id inner join
                    {2}terms tm
                    on tm.term_id=tt.term_id join
                    {2}posts tp
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
                            {2}posts t1
                            left join {1}users t2 on t1.post_author = t2.ID
                            left join {2}posts t3 on t1.post_parent = t3.ID
                		where
                    		(
                                t1.post_status = 'publish' or
                                (t1.post_status='inherit' and t3.post_status = 'publish')
                            ) and
                    		t1.post_type in ('post', 'page')
                    )
        	''', debug="tags")

            for data in results:
                name = data["tag"]
                if not re_tg1.match(name):
                    tags.append(data)
                    continue
                for i in set(re_tg2.findall(name)):
                    name = i[1:-1].strip()
                    if len(name) > 0:
                        n_data = dict(data)
                        n_data["tag"] = name
                        tags.append(n_data)

            db.close()
            print("")

        wp = Bunch(
            posts=posts,
            comments=comments,
            media=media,
            tags=tags,
            sites=site_meta,
        )

        totales = {
            "posts_pages": len(wp.posts),
            "comentarios": len(wp.comments),
            "tags_categories": len(wp.tags),
            "recursos": len(wp.media)
        }

        s_total = max(len(str(t)) for t in totales.values())
        s_total = "%"+str(s_total)+"s "

        print("%s wordpress serán guardados:" % len(wp.sites))
        for k, v in totales.items():
            k = k.replace("_", "/")
            s = s_total+k
            print(s % v)
        print("")

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
            data["_content"] = wp_data.get("html")
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
