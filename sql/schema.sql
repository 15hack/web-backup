CREATE TABLE sites (
  _DB TEXT,
  ID INTEGER,
  title TEXT,
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
  _content TEXT,
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
  _parse TEXT,
  PRIMARY KEY (site, id)
);

CREATE TABLE wk_media (
  site INTEGER REFERENCES sites(ID),
  ID TEXT,
  type TEXT,
  date TEXT,
  url TEXT,
  PRIMARY KEY (site, id)
);

CREATE TABLE mailman_lists (
  site INTEGER REFERENCES sites(ID),
  ID TEXT,
  description TEXT,
  date TEXT,
  first_mail TEXT,
  last_mail TEXT,
  mails INTEGER,
  url TEXT,
  _owner INTEGER,
  _moderator INTEGER,
  _members INTEGER,
  _total_users INTEGER,
  _private_roster INTEGER,
  _archiving INTEGER,
  _exists_archive INTEGER,
  _archive_private INTEGER,
  _advertised INTEGER,
  PRIMARY KEY (site, id)
);

CREATE TABLE mailman_archive (
  site INTEGER REFERENCES sites(ID),
  list TEXT REFERENCES mailman_lists(ID),
  type TEXT,
  url TEXT
);

CREATE VIEW objects
AS
SELECT 0 ID, ID site,
  type,
  null date,
  url
FROM
  sites
UNION
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
UNION
SELECT ID, site,
  type,
  date,
  url
FROM
  wk_media
UNION
SELECT ID, site,
  'mailman_lists' type,
  date,
  url
FROM
  mailman_lists
UNION
SELECT list ID, site,
  ('mailman_' || type) type,
  null date,
  url
FROM
  mailman_archive
;
