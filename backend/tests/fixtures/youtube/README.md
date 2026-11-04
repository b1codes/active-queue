# YouTube Data API v3 response fixtures

Response bodies in the documented v3 shape (`playlists.list`, `playlistItems.list`,
`videos.list`, and the standard error envelope), trimmed to the fields
`app/providers/youtube.py` reads. They drive the `respx` tests in
`tests/unit/providers/test_youtube_http.py` and the provider contract test.

They are hand-built against the API reference, not captured from live traffic.
The nightly third-party contract check (`tests/contract/thirdparty/`) asserts that
real responses still contain every field these fixtures rely on. Update both
together.
