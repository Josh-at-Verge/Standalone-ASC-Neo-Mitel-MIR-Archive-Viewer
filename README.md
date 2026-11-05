# Call Archive

A small HTML recording browser for Mitel conversation XML + WAV exports.

## Windows quick start

Put your XML and WAV files inside the Recordings folder beside Start_Call_Archive.bat. Double-click Start_Call_Archive.bat to start the local server and open your browser automatically. Requires Python 3.10+. Keep the server window open; press Ctrl+C to stop it.

## Recommended: persistent archive (11 months)

Install Python 3.10 or later. No third-party packages are needed. Extract this entire ZIP to a writable folder, then run in a terminal:

Windows:

    py server.py "D:\Call Recordings"

Linux:

    python3 server.py "/srv/Call Recordings"

Open http://127.0.0.1:8765 in a browser. Keep the terminal running. The first scan traverses all subfolders, parses XML and builds an SQLite index beside server.py. WAV data is streamed only for playback/download. Subsequent starts reuse unchanged XML metadata; Refresh index rescans for changes and removes deleted records. The directory is read only. Keep XML and WAV exports together when possible; an audio filename elsewhere in the tree is matched only if unique. Invalid XML files are skipped and reported. A different root folder gets a separate index. Back up the recordings separately: the database is only a rebuildable index.

Use --port 8766 to change the listening port, or --db "D:\Indexes\calls.sqlite3" to choose an index path (parent directory must exist). Keep a separate database per archive. This local server binds to 127.0.0.1 only, with no remote user access. It is intended for a trusted local workstation. Shared/multi-user hosting requires a separate authenticated deployment with access controls.

## Browser-only use

Open dist/index.html in Chrome or Edge and choose the Call Recordings folder. This scans XML metadata in batches without loading WAV audio contents. Subfolders are included. Select the folder again after refreshing. Folder selection does not upload anything. Large folder enumeration and metadata searches depend on browser memory: use server.py for the full archive. The hosted version has the same folder mode. “Try sample metadata” works on the hosted/local-server version and shows three supplied sample conversations without audio. In a file:// page, the sample preview may be blocked by browser fetch rules; folder selection still works.

## Search

All filters combine with AND: free text across XML content, caller, called/DID, participant extension, agent ID, direction, inclusive dates, minimum/maximum duration in seconds, and audio availability. Number fields support partial matching and ignore formatting. Extension and agent searches match each participant value separately. Results are paginated at 50 rows and sorted by start time. Export CSV includes every matching row, not only the current page. XML duration is interpreted as milliseconds. Dates/times are shown exactly as exported; the supplied timestamps have no timezone offset and are not converted. Search is metadata-only; audio is not transcribed.

## Files and privacy

- dist/index.html: complete standalone UI, no CDN or third-party scripts.
- dist/sample-metadata.json: three sample conversation summaries (no WAV content).
- server.py: incremental indexer, local API, CSV export and seekable WAV streaming.
- archive-*.sqlite3: generated locally, contains sensitive searchable call metadata. Protect it like the recordings.

Some WAV codecs cannot play in every browser; download the original recording if playback is unsupported. Initial indexing time and disk usage depend on the actual call volume and storage speed. The archive has not been tested with your full 11-month dataset.
