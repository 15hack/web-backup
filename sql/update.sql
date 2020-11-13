UPDATE sites SET _last_use=(
  select max(d) from (
    select date d from wp_posts where site=sites.id
    union
    select date d from phpbb_posts where site=sites.id
  )
);
DELETE from wp_tags
where (site, post) not in (select site, id from wp_posts);
