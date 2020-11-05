UPDATE sites SET _last_use=(
  select max(date) from posts where site=sites.id
);
DELETE from tags
where (site, post) not in (select site, id from posts);
