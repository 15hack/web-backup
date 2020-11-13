select distinct 
  concat(TT1.table_schema, '.', SUBSTR(phpbb_user, 1, length(phpbb_user)-5)) prefix
from (
  select table_schema, table_name phpbb_user from (
  	select table_schema, table_name, count(*) N 
  	from information_schema.COLUMNS 
  	where
  		column_name in ('user_type', 'group_id', 'username', 'username_clean') and 
  		table_name like '%user%'
  	group by table_schema, table_name
  ) T1 where T1.N=4
) TT1
JOIN
(
  select table_schema, table_name phpbb_user_group from (
  	select table_schema, table_name, count(*) N 
  	from information_schema.COLUMNS
  	where 
  		column_name in ('group_id', 'user_id', 'group_leader', 'user_pending') and 
  		table_name like '%user_group%' 
  	group by table_schema, table_name
  ) T2 where T2.N=4
) TT2
JOIN
(
  select table_schema, table_name phpbb_user_group from (
  	select table_schema, table_name, count(*) N 
  	from information_schema.COLUMNS
  	where 
  		column_name in ('config_name', 'config_value') and 
  		table_name like '%config%' 
  	group by table_schema, table_name
  ) T2 where T2.N=2
) TT3
ON 
	TT1.table_schema = TT2.table_schema and
	TT1.table_schema = TT3.table_schema	
order by
	concat(TT1.table_schema, '.', SUBSTR(phpbb_user, 1, length(phpbb_user)-5))
;

