DROP VIEW IF EXISTS _posts;
DROP VIEW IF EXISTS _media;
DROP VIEW IF EXISTS objects;
DROP TABLE IF EXISTS ref;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS media;
DROP TABLE IF EXISTS urls;
DROP TABLE IF EXISTS blogs;

CREATE TABLE blogs (
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
  blog INTEGER REFERENCES blogs(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  content TEXT,
  title TEXT,
  name TEXT,
  author TEXT,
  url TEXT,
  _modified TEXT,
  _WPJSON INTEGER,
  _content TEXT,
  _parent INTEGER,
  PRIMARY KEY (blog, id)
);

CREATE TABLE media (
  blog INTEGER REFERENCES blogs(ID),
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
  PRIMARY KEY (blog, id)
);

CREATE TABLE tags (
  blog INTEGER REFERENCES posts(blog),
  post INTEGER REFERENCES posts(ID),
  tag TEXT,
  type INTEGER,
  PRIMARY KEY (blog, post, tag, type)
);

CREATE TABLE comments (
  ID INTEGER,
  blog INTEGER REFERENCES blogs(id),
  object INTEGER,
  content TEXT,
  date TEXT,
  author TEXT,
  parent INTEGER,
  _author_url TEXT,
  _author_email TEXT,
  _type TEXT,
  PRIMARY KEY (ID, blog, object)
);

CREATE TABLE ref (
  blog INTEGER REFERENCES blogs(ID),
  object INTEGER,
  in_blog INTEGER REFERENCES blogs(ID),
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
 blogs b join posts i on b.ID = i.blog
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
 blogs b join media i on b.ID = i.blog
;
CREATE VIEW objects
AS
SELECT ID, blog,
  type,
  date,
  author,
  url
FROM
  posts
UNION
SELECT ID, blog,
  'media' type,
  date,
  author,
  url
FROM
  media
UNION
SELECT ID, blog,
  'pmedia' type,
  date,
  author,
  page url
FROM
  media
where
  page != url and page is not null
;
