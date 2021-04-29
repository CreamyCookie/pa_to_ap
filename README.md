# pa_to_ap
Migrate data from Podcast Addict's to AntennaPod's database

## Takes care of
* chapters
* favorites
* played status, duration played and playback date
* file locations (so you don't have to download episodes in AntennaPod that were downloaded by Podcast Addict)
* feed: keep updated status

This does not use any IDs for matching feeds and episodes from one db to another, as those tend to be very unreliable. (They're supposed to stay the same, but often they don't.) Instead, we match them by their name and, in some cases, other attributes. This will work even if the name changed. For example, when using the script one episode's name changed from something like `123. Great Title` to just `Great Title`, but they were still matched.

## Steps

0. Install Python 3.8 or later
1. Export OPML in Podcast Addict
2. Import that OPML file in AntennaPod
3. Make full backup in both apps (not OPML)
4. Put both in the same folder as this script
5. Run the [`pa_to_ap.py`](pa_to_ap.py) script (AntennaPod db file will be **modified**!) in a terminal
6. Confirm that matches are correct (if they aren't you may need to increase `min_similarity`)
7. Copy the modified db file back to your phone
8. Create `/storage/emulated/0/Android/data/de.danoeh.antennapod/files/media/from_podcast_addict` 
9. Manually move (or copy) the folders **inside**
`/storage/emulated/0/Android/data/com.bambuna.podcastaddict/files/podcast/`
**to**
`/storage/emulated/0/Android/data/de.danoeh.antennapod/files/media/from_podcast_addict`
   as AntennaPod cannot access the files under the other app's directory (Consider making a backup of these files.)
10. Import the modified db in AntennaPod

Enjoy!

Of course, you can change the location (to which you have to manually copy/move the files to) by modifying the `EPISODES_DIR_PATH` before running the script.

## Warning
Note that this is somewhat rough and will likely not handle a lot of edge cases.

For example, it won't check if an episode is already in the Favorites table. It will simply add them again, if they're already there. It will also not take care of images or the queue.

As a result, this works best with a fresh AntennaPod install. Without commenting out the relevant (`INSERT INTO`) lines, this script should not be rerun again on the same database.
