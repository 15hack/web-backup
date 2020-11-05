BEGIN TRANSACTION;

DELETE from tags where (site, post) in (select site, id from posts where url is null);

DROP view _posts;
DROP view _media;

ALTER TABLE sites RENAME TO temp_sites;

CREATE TABLE sites (
  ID INTEGER,
  url TEXT,
  PRIMARY KEY (ID)
);

INSERT INTO sites
    (ID, url)
SELECT
    ID, url
FROM
    temp_sites
where url is not null;

DROP TABLE temp_sites;

ALTER TABLE posts RENAME TO temp_posts;

CREATE TABLE posts (
  site INTEGER REFERENCES sites(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  content TEXT,
  title TEXT,
  name TEXT,
  author TEXT,
  url TEXT,
  PRIMARY KEY (site, id)
);

INSERT INTO posts
    (site, ID, type, date, content, title, name, author, url)
SELECT
    site, ID, type, date, _content, title, name, author, url
FROM
    temp_posts
where url is not null;

DROP TABLE temp_posts;

ALTER TABLE media RENAME TO temp_media;

CREATE TABLE media (
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

INSERT INTO media
    (site, ID, type, date, author, file, url, page)
SELECT
    site, ID, type, date, author, file, url, page
FROM
    temp_media
where url is not null;

DROP TABLE temp_media;

ALTER TABLE comments RENAME TO temp_comments;

CREATE TABLE comments (
  ID INTEGER,
  site INTEGER REFERENCES sites(id),
  object INTEGER,
  content TEXT,
  date TEXT,
  author TEXT,
  parent INTEGER,
  PRIMARY KEY (ID, site, object)
);

INSERT INTO comments
    (ID, site, object, content, date, author, parent)
SELECT
    ID, site, object, content, date, author, parent
FROM
    temp_comments;

DROP TABLE temp_comments;

COMMIT;