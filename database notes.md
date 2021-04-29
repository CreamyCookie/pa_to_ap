podcast addict
--------------------------------------
both this and antennapod chapters start is in ms

`podcastId, episodeId, start, name from chapters`

content almost like description (but with html)

url for other stuff

size sometimes 0, favorite = 0, 1

downloaded_date=   1613031652000

IGNORE: downloaded_status (is always -1)

duration_ms = 9710000

`_id, name, podcast_id, url, download_url, favorite, seen_status, downloaded_date, size, short_description, content, 
local_file_name, duration_ms, playbackDate, chapters_extracted, is_virtual from episodes`

status must be 1

`_id, name, subscribed_status, feed_url, author, folderName, description, 
is_virtual, automaticRefresh from podcasts`

antenna pod
--------------------------------------
`id, title, start, feeditem from SimpleChapters`

`id, title, description, author, keep_updated from Feeds`

`id, title, read, description, feed from FeedItems`  read = 0,1

`id, feeditem, feed in Favorites`

playback_completion_date 1616529079679   downloaded = 0,1

filesize can probably be ignored (at least if != 0)

`id, file_url, downloaded, feeditem, played_duration, 
playback_completion_date, last_played_time from FeedMedia`
