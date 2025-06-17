-- This SQL script is for reference of the structure of the artists table and related tables in the soundscapes database.

-- Main artists table
CREATE TABLE artists (
    id INTEGER PRIMARY KEY,
    name TEXT,
    real_name TEXT,
    profile TEXT,
    data_quality TEXT,
    full_data JSONB
);

-- Related URLs
CREATE TABLE artist_urls (
    artist_id INTEGER REFERENCES artists(id),
    url TEXT
);

-- Aliases
CREATE TABLE artist_aliases (
    artist_id INTEGER REFERENCES artists(id),
    alias_name TEXT
);

-- Name variations (ANVs)
CREATE TABLE artist_name_variations (
    artist_id INTEGER REFERENCES artists(id),
    variation TEXT
);

-- Group members (for groups that contain individuals)
CREATE TABLE artist_members (
    artist_id INTEGER REFERENCES artists(id),
    member_name TEXT
);

-- Artist groups (for individuals that are part of groups)
CREATE TABLE artist_groups (
    artist_id INTEGER REFERENCES artists(id),
    group_name TEXT
);
