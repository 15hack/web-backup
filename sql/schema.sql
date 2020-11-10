DROP VIEW IF EXISTS _posts;
DROP VIEW IF EXISTS _media;
DROP VIEW IF EXISTS objects;
DROP TABLE IF EXISTS ref;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS media;
DROP TABLE IF EXISTS urls;
DROP TABLE IF EXISTS sites;

CREATE TABLE sites (
  _DB TEXT,
  ID INTEGER,
  url TEXT,
  _unapproved INTEGER,
  _spam INTEGER,
  _last_use TEXT,
  _permalink TEXT,
  _files TEXT,
  PRIMARY KEY (ID)
);

CREATE TABLE posts (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  content TEXT,
  title TEXT,
  author TEXT,
  url TEXT,
  _modified TEXT,
  _WPJSON INTEGER,
  _content TEXT,
  _parent INTEGER,
  PRIMARY KEY (site, id)
);

CREATE TABLE media (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  author TEXT,
  file TEXT,
  url TEXT,
  page TEXT,
  _modified TEXT,
  _WPJSON INTEGER,
  _parent INTEGER,
  PRIMARY KEY (site, id)
);

CREATE TABLE tags (
  site INTEGER REFERENCES posts(site),
  post INTEGER REFERENCES posts(ID),
  tag TEXT,
  type INTEGER,
  PRIMARY KEY (site, post, tag, type)
);

CREATE TABLE comments (
  ID INTEGER,
  site INTEGER REFERENCES sites(id),
  object INTEGER,
  content TEXT,
  date TEXT,
  author TEXT,
  parent INTEGER,
  _author_url TEXT,
  _author_email TEXT,
  _type TEXT,
  PRIMARY KEY (ID, site, object)
);

CREATE TABLE ref (
  site INTEGER REFERENCES sites(ID),
  object INTEGER,
  in_blog INTEGER REFERENCES sites(ID),
  in_object INTEGER
);

CREATE VIEW _posts
AS
SELECT
  CASE
    when type = 'post' then b.url || '/?p=' || i.ID
    when type = 'page' then b.url || '/?page_id=' || i.ID
    else b.url
  END _URL,
  'https://' || b.url || '/wp-admin/post.php?post=' || i.ID || '&action=edit' _ADMIN,
  'https://' || b.url || '?rest_route=/wp/v2/' || i.type || 's/' || i.ID URL_WPJSON,
  i.*
FROM
 sites b join posts i on b.ID = i.site
;

CREATE VIEW _media
AS
SELECT
  CASE
    when i.file is not null and b._files is null then b.url || '/files/' || i.file
    when i.file is not null and b._files is not null then b.url || b._files || '/' || i.file
    else b.url || '/?attachment_id=' || i.ID
  END _URL,
  'https://' || b.url || '/wp-admin/post.php?post=' || i.ID || '&action=edit' _ADMIN,
  'https://' || b.url || '?rest_route=/wp/v2/media/' || i.ID URL_WPJSON,
 i.*
FROM
 sites b join media i on b.ID = i.site
;
CREATE VIEW objects
AS
SELECT ID, site,
  type,
  date,
  author,
  url
FROM
  posts
UNION
SELECT ID, site,
  'media' type,
  date,
  author,
  url
FROM
  media
UNION
SELECT ID, site,
  'pmedia' type,
  date,
  author,
  page url
FROM
  media
where
  page != url and page is not null
;
