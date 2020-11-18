
CREATE VIEW _wp_posts
AS
SELECT
  CASE
    when type = 'post' then b.url || '/?p=' || i.ID
    when type = 'page' then b.url || '/?page_id=' || i.ID
    else b.url
  END _URL,
  'https://' || b.url || '/wp-admin/post.php?post=' || i.ID || '&action=edit' _ADMIN,
  'https://' || b.url || '?rest_route=/wp/v2/' || i.type || 's/' || i.ID URL_WPJSON,
  i.*
FROM
 sites b join wp_posts i on b.ID = i.site
;

CREATE VIEW _wp_media
AS
SELECT
  CASE
    when i.file is not null and b._files is null then b.url || '/files/' || i.file
    when i.file is not null and b._files is not null then b.url || b._files || '/' || i.file
    else b.url || '/?attachment_id=' || i.ID
  END _URL,
  'https://' || b.url || '/wp-admin/post.php?post=' || i.ID || '&action=edit' _ADMIN,
  'https://' || b.url || '?rest_route=/wp/v2/media/' || i.ID URL_WPJSON,
 i.*
FROM
 sites b join wp_media i on b.ID = i.site
;
