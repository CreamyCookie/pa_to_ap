# pa_to_ap
Migrate data from Podcast Addict's to AntennaPod's database

## Steps

0. Install Python 3.8
1. Export OPML in Podcast Addict
2. Import that OPML file in AntennaPod
3. Make full backup in both apps (not OPML)
4. Put both in the same folder as this script
5. Run this script (AntennaPod db file will be **modified**!)
6. Copy the modified db file back to your phone
7. Create `/storage/emulated/0/Android/data/de.danoeh.antennapod/files/media/from_podcast_addict` 
8. Manually move (or copy) the folders **inside**
`/storage/emulated/0/Android/data/com.bambuna.podcastaddict/files/podcast/`
**to**
`/storage/emulated/0/Android/data/de.danoeh.antennapod/files/media/from_podcast_addict`
   as AntennaPod cannot access the files under the other app's directory (Consider making a backup of these files.)
9. Import the modified db in AntennaPod
10. Have fun!

Of course, you can change the location that you will manually copy/move the files to by modifying the `EPISODES_DIR_PATH` before running the script.

## Warning
Note that this is somewhat rough and will likely not handle a lot of edge cases.

For example, it won't even check if an episode is already in the Favorites table. It will simply add them again, if they're already there. It will also not take care of images.
