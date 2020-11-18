CREATE TABLE sites (
  _DB TEXT,
  ID INTEGER,
  url TEXT,
  type TEXT,
  page_size INTEGER,
  _unapproved INTEGER,
  _spam INTEGER,
  _last_use TEXT,
  _permalink TEXT,
  _files TEXT,
  PRIMARY KEY (ID)
);

CREATE TABLE wp_posts (
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

CREATE TABLE wp_media (
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

CREATE TABLE wp_tags (
  site INTEGER REFERENCES posts(site),
  post INTEGER REFERENCES posts(ID),
  tag TEXT,
  type INTEGER,
  PRIMARY KEY (site, post, tag, type)
);

CREATE TABLE wp_comments (
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

CREATE TABLE phpbb_topics (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  date TEXT,
  title TEXT,
  author TEXT,
  url TEXT,
  _parent INTEGER,
  PRIMARY KEY (site, id)
);

CREATE TABLE phpbb_posts (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  topic INTEGER REFERENCES phpbb_topics(ID),
  date TEXT,
  content TEXT,
  title TEXT,
  author TEXT,
  _modified TEXT,
  PRIMARY KEY (site, id, topic)
);

CREATE TABLE phpbb_media (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  post INTEGER REFERENCES phpbb_posts(ID),
  topic INTEGER REFERENCES phpbb_topics(ID),
  type TEXT,
  date TEXT,
  author TEXT,
  file TEXT,
  comment TEXT,
  url TEXT,
  PRIMARY KEY (site, id, topic, post)
);


CREATE TABLE wk_pages (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  namespace INTEGER,
  date TEXT,
  modified TEXT,
  content TEXT,
  title TEXT,
  url TEXT,
  _touched TEXT,
  _WKJSON INTEGER,
  _content TEXT,
  PRIMARY KEY (site, id)
);

CREATE VIEW _wp_posts
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
 sites b join wp_posts i on b.ID = i.site
;

CREATE VIEW _wp_media
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
 sites b join wp_media i on b.ID = i.site
;

CREATE VIEW objects
AS
SELECT ID, site,
  ('wp_' || type) type,
  date,
  url
FROM
  wp_posts
UNION
SELECT ID, site,
  'wp_media' type,
  date,
  url
FROM
  wp_media
UNION
SELECT ID, site,
  'wp_pmedia' type,
  date,
  page url
FROM
  wp_media
where
  page != url and page is not null
UNION
SELECT ID, site,
  'phpbb_topic' type,
  date,
  url
FROM
  phpbb_topics
UNION
SELECT ID, site,
  type,
  date,
  url
FROM
  phpbb_media
UNION
SELECT ID, site,
  'wk_page' type,
  date,
  url
FROM
  wk_pages
;
