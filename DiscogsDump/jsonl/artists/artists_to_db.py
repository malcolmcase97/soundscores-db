import json
import psycopg2
from psycopg2.extras import Json
from tqdm import tqdm
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# CONFIGURATION
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}
ARTISTS_FILE = 'artists.jsonl'

def normalize_to_list(value):
    """
    Ensures that the input is a list of strings.
    - If it's a string, wrap it in a list.
    - If it's a dict with 'value', use that.
    - If it's already a list, process each element.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [value.get('value')] if value.get('value') else []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                v = item.get('value')
                if v:
                    result.append(v)
            elif isinstance(item, str):
                result.append(item)
        return result
    return []

# Connect to PostgreSQL
def connect_db():
    return psycopg2.connect(**DB_PARAMS)

def insert_artist(cursor, artist):
    artist_id = artist.get('id')
    if artist_id is None:
        raise ValueError("Artist missing 'id'")
    artist_id = int(artist_id)

    # Insert into Artists
    cursor.execute("""
        INSERT INTO "Artists" (id, name, real_name, profile, data_quality, full_data)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        artist_id,
        artist.get('name'),
        artist.get('realname'),
        artist.get('profile'),
        artist.get('data_quality'),
        Json(artist)
    ))

    # ArtistUrls
    for url in normalize_to_list(artist.get('urls', {}).get('url')):
        cursor.execute("""
            INSERT INTO "ArtistUrls" (artist_id, url)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (artist_id, url))

    # ArtistAliases
    for alias in normalize_to_list(artist.get('aliases', {}).get('name')):
        cursor.execute("""
            INSERT INTO "ArtistAliases" (artist_id, alias_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (artist_id, alias))

    # ArtistNameVariations
    for var in normalize_to_list(artist.get('namevariations', {}).get('name')):
        cursor.execute("""
            INSERT INTO "ArtistNameVariations" (artist_id, variation)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (artist_id, var))

    # ArtistMembers
    for member in normalize_to_list(artist.get('members', {}).get('name')):
        cursor.execute("""
            INSERT INTO "ArtistMembers" (artist_id, member_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (artist_id, member))

    # ArtistGroups
    for group in normalize_to_list(artist.get('groups', {}).get('name')):
        cursor.execute("""
            INSERT INTO "ArtistGroups" (artist_id, group_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (artist_id, group))

def main():
    conn = connect_db()
    cursor = conn.cursor()

    with open(ARTISTS_FILE, 'r', encoding='utf-8') as file:
        for line in tqdm(file, desc="Importing artists"):
            try:
                data = json.loads(line)
                artist = data.get('artist')
                if not artist:
                    print("Warning: 'artist' key missing in line, skipping")
                    continue

                insert_artist(cursor, artist)
                conn.commit()
            except Exception as e:
                print(f"Error inserting line: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    print("✅ Import complete.")

if __name__ == '__main__':
    main()
