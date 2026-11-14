# YouTube Data API v3 response fixtures

Response bodies in the documented v3 shape (`playlists.list`, `playlistItems.list`,
`videos.list`, and the standard error envelope), trimmed to the fields
`app/providers/youtube.py` reads. They drive the `respx` tests in
`tests/unit/providers/test_youtube_http.py` and the provider contract test.

They are hand-built against the API reference, not captured from live traffic.
`contracts/third_party/youtube/*.schema.json` lists the fields the provider relies on.
`tests/contract/test_third_party_recorded.py` holds these fixtures to those schemas on
every PR, and the nightly check (`tests/contract/thirdparty/`,
`.github/workflows/contracts-nightly.yml`) holds the real API to the same schemas. When
the nightly check fails, update the schema and these fixtures together.
