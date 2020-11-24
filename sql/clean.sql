BEGIN TRANSACTION;
DELETE from wp_tags where (site, post) in (select site, id from wp_posts where url is null);
DELETE from wk_media where url is null;

ALTER TABLE sites RENAME TO temp_sites;

CREATE TABLE sites (
  ID INTEGER,
  url TEXT,
  type TEXT,
  page_size INTEGER,
  PRIMARY KEY (ID)
);

INSERT INTO sites
    (ID, url, type, page_size)
SELECT
    ID, url, type, page_size
FROM
    temp_sites
where url is not null;

DROP TABLE temp_sites;

ALTER TABLE wp_posts RENAME TO temp_wp_posts;

CREATE TABLE wp_posts (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  content TEXT,
  title TEXT,
  author TEXT,
  url TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO wp_posts
    (site, ID, type, date, content, title, author, url)
SELECT
    site, ID, type, date, content, title, author, url
FROM
    temp_wp_posts
where url is not null;

DROP TABLE temp_wp_posts;

ALTER TABLE wp_media RENAME TO temp_wp_media;

CREATE TABLE wp_media (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  author TEXT,
  file TEXT,
  url TEXT,
  page TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO wp_media
    (site, ID, type, date, author, file, url, page)
SELECT
    site, ID, type, date, author, file, url, page
FROM
    temp_wp_media
where url is not null;

DROP TABLE temp_wp_media;

ALTER TABLE wp_comments RENAME TO temp_wp_comments;

CREATE TABLE wp_comments (
  ID INTEGER,
  site INTEGER REFERENCES sites(id),
  object INTEGER,
  content TEXT,
  date TEXT,
  author TEXT,
  parent INTEGER,
  PRIMARY KEY (ID, site, object)
);

INSERT INTO wp_comments
    (ID, site, object, content, date, author, parent)
SELECT
    ID, site, object, content, date, author, parent
FROM
    temp_wp_comments;

DROP TABLE temp_wp_comments;

ALTER TABLE phpbb_topics RENAME TO temp_phpbb_topics;

CREATE TABLE phpbb_topics (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  date TEXT,
  title TEXT,
  author TEXT,
  url TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO phpbb_topics
    (site, ID, date, title, author, url)
SELECT
    site, ID, date, title, author, url
FROM
    temp_phpbb_topics
where url is not null;

DROP TABLE temp_phpbb_topics;

ALTER TABLE phpbb_posts RENAME TO temp_phpbb_posts;

CREATE TABLE phpbb_posts (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  topic INTEGER REFERENCES phpbb_topics(ID),
  date TEXT,
  content TEXT,
  title TEXT,
  author TEXT,
  PRIMARY KEY (site, id, topic)
);

INSERT INTO phpbb_posts
    (site, ID, topic, date, content, title, author)
SELECT
    site, ID, topic, date, content, title, author
FROM
    temp_phpbb_posts;

DROP TABLE temp_phpbb_posts;

ALTER TABLE wk_pages RENAME TO temp_wk_pages;

CREATE TABLE wk_pages (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  namespace INTEGER,
  date TEXT,
  modified TEXT,
  content TEXT,
  title TEXT,
  url TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO wk_pages
    (site, ID, namespace, date, modified, content, title, url)
SELECT
    site, ID, namespace, date, modified, content, title, url
FROM
    temp_wk_pages
where url is not null;

DROP TABLE temp_wk_pages;

ALTER TABLE mailman_lists RENAME TO temp_mailman_lists;

CREATE TABLE mailman_lists (
  site INTEGER REFERENCES sites(ID),
  ID TEXT,
  date TEXT,
  first_mail TEXT,
  last_mail TEXT,
  mails INTEGER,
  url TEXT,
  archive TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO mailman_lists
    (site, ID, date, first_mail, last_mail, mails, url, archive)
SELECT
    site, ID, date, first_mail, last_mail, mails, url, archive
FROM
    temp_mailman_lists
where url is not null;

DROP TABLE temp_mailman_lists;

COMMIT;