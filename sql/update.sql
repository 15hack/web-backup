UPDATE sites SET _last_use=(
  select max(d) from (
    select date d from wp_posts where site=sites.id
    union
    select date d from phpbb_posts where site=sites.id
    union
    select modified d from wk_pages where site=sites.id
    union
    select last_mail d from mailman_lists where site=sites.id
  ) where d is not null
);

DELETE from wp_tags
where (site, post) not in (select site, id from wp_posts);
