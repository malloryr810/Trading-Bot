"""
Data persistence layer.

Handles reading and writing raw and processed data to disk
(data/raw/, data/processed/) and, optionally, to a database
configured via DATABASE_URL. Keeps fetchers decoupled from storage details.
"""
