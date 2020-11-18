select distinct
  concat(TT1.table_schema, '.', SUBSTR(wiki_page, 1, length(wiki_page)-4)) prefix
from (
  select table_schema, table_name wiki_page from (
    select table_schema, table_name, count(*) N
    from information_schema.COLUMNS
    where
      column_name in ('page_id', 'page_title', 'page_latest', 'page_is_redirect') and
      table_name like '%page'
    group by table_schema, table_name
  ) T1 where T1.N=4
) TT1
JOIN (
  select table_schema, table_name wiki_text from (
    select table_schema, table_name, count(*) N
    from information_schema.COLUMNS
    where
      column_name in ('old_id', 'old_text', 'old_flags') and
      table_name like '%text'
    group by table_schema, table_name
  ) T2 where T2.N=3
) TT2
JOIN (
  select table_schema, table_name wiki_revision from (
    select table_schema, table_name, count(*) N
    from information_schema.COLUMNS
    where
      column_name in ('rev_id', 'rev_page', 'rev_text_id') and
      table_name like '%revision'
    group by table_schema, table_name
  ) T3 where T3.N=3
) TT3
ON
	TT1.table_schema = TT2.table_schema and
	TT1.table_schema = TT3.table_schema
order by
	concat(TT1.table_schema, '.', SUBSTR(wiki_page, 1, length(wiki_page)-4))
