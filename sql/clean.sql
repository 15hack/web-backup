BEGIN TRANSACTION;

DELETE from tags where (blog, post) in (select blog, id from posts where url is null);

DROP view _posts;
DROP view _media;

ALTER TABLE blogs RENAME TO temp_blogs;

CREATE TABLE blogs (
  ID INTEGER,
  url TEXT,
  PRIMARY KEY (ID)
);

INSERT INTO blogs
    (ID, url)
SELECT
    ID, url
FROM
    temp_blogs
where url is not null;

DROP TABLE temp_blogs;

ALTER TABLE posts RENAME TO temp_posts;

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
  PRIMARY KEY (blog, id)
);

INSERT INTO posts
    (blog, ID, type, date, content, title, name, author, url)
SELECT
    blog, ID, type, date, _content, title, name, author, url
FROM
    temp_posts
where url is not null;

DROP TABLE temp_posts;

ALTER TABLE media RENAME TO temp_media;

CREATE TABLE media (
  blog INTEGER REFERENCES blogs(ID),
  ID INTEGER,
  type TEXT,
  date TEXT,
  author TEXT,
  file TEXT,
  url TEXT,
  page TEXT,
  PRIMARY KEY (blog, id)
);

INSERT INTO media
    (blog, ID, type, date, author, file, url, page)
SELECT
    blog, ID, type, date, author, file, url, page
FROM
    temp_media
where url is not null;

DROP TABLE temp_media;

ALTER TABLE comments RENAME TO temp_comments;

CREATE TABLE comments (
  ID INTEGER,
  blog INTEGER REFERENCES blogs(id),
  object INTEGER,
  content TEXT,
  date TEXT,
  author TEXT,
  parent INTEGER,
  PRIMARY KEY (ID, blog, object)
);

INSERT INTO comments
    (ID, blog, object, content, date, author, parent)
SELECT
    ID, blog, object, content, date, author, parent
FROM
    temp_comments;

DROP TABLE temp_comments;

COMMIT;