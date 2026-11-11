# ASC Neo Mitel MIR Exported Call Archive

A small HTML recording browser for Mitel conversation XML + MP3 exports.

## Windows quick start

Put your XML and MP3 files inside the Recordings folder beside Start_Call_Archive.bat. Double-click Start_Call_Archive.bat to start the local server and open your browser automatically. Requires Python 3.10+. Keep the server window open; press Ctrl+C to stop it.

Python Download https://www.python.org/downloads/

## Recommended: persistent archive (11 months)

Install Python 3.10 or later. No third-party packages are needed. Extract this entire ZIP to a writable folder, then run in a terminal:

Windows:

    py server.py "D:\Call Recordings"

Linux:

    python3 server.py "/srv/Call Recordings"

Open http://127.0.0.1:8765 in a browser. Keep the terminal running. The first scan traverses all subfolders, parses XML and builds an SQLite index beside server.py. MP3 data is streamed only for playback/download. Subsequent starts reuse unchanged XML metadata; Refresh index rescans for changes and removes deleted records. The directory is read only. Keep XML and MP3 exports together when possible; an audio filename elsewhere in the tree is matched only if unique. Invalid XML files are skipped and reported. A different root folder gets a separate index. Back up the recordings separately: the database is only a rebuildable index.

Use --port 8766 to change the listening port, or --db "D:\Indexes\calls.sqlite3" to choose an index path (parent directory must exist). Keep a separate database per archive. This local server binds to 127.0.0.1 only, with no remote user access. It is intended for a trusted local workstation. Shared/multi-user hosting requires a separate authenticated deployment with access controls.

## Browser-only use

Open dist/index.html in Chrome or Edge and choose the Call Recordings folder. This scans XML metadata in batches without loading MP3 audio contents. Subfolders are included. Select the folder again after refreshing. Folder selection does not upload anything. Large folder enumeration and metadata searches depend on browser memory: use server.py for the full archive. The hosted version has the same folder mode. “Try sample metadata” works on the hosted/local-server version and shows three fictional demo conversations without audio. In a file:// page, the sample preview may be blocked by browser fetch rules; folder selection still works.

## Search

All filters combine with AND: free text across XML content, caller, called/DID, participant extension, agent ID, direction, inclusive dates, minimum/maximum duration in seconds, and audio availability. Number fields support partial matching and ignore formatting. Extension and agent searches match each participant value separately. Results are paginated at 50 rows and sorted by start time. Export CSV includes every matching row, not only the current page. XML duration is interpreted as milliseconds. Dates/times are shown exactly as exported; the supplied timestamps have no timezone offset and are not converted. Search is metadata-only; audio is not transcribed.

## Files and privacy

- dist/index.html: complete standalone UI, no CDN or third-party scripts.
- dist/sample-metadata.json: three fictional demo conversation summaries (no MP3 content).
- server.py: incremental indexer, local API, CSV export and seekable MP3 streaming.
- archive-*.sqlite3: generated locally, contains sensitive searchable call metadata. Protect it like the recordings.

If a recording will not play, check that it is a valid MP3 or download it to play locally. Initial indexing time and disk usage depend on the actual call volume and storage speed. The archive has not been tested with your full 11-month dataset.

## MP3 filenames and existing indexes

This version uses MP3 recordings. Keep each XML and corresponding MP3 together, preferably with the same filename stem. If conversationFileName in the XML still ends in .wav, the viewer looks for the corresponding .mp3 automatically. With no conversationFileName, it uses the XML filename stem plus .mp3. Matching is case-insensitive, including .MP3 extensions. A same-folder/path match is preferred; a filename elsewhere in the archive is used only if unique.

After updating, restart the server using Start_Call_Archive.bat. Startup or Refresh index updates cached audio paths and download names for unchanged XML files; no database deletion is needed. The viewer does not convert audio: existing files must be actual MP3 recordings, not WAV files renamed to .mp3.
