UPDATE blogs SET _last_use=(
  select max(date) from posts where blog=blogs.id
);
DELETE from tags
where (blog, post) not in (select blog, id from posts);
