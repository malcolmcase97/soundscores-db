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

# Connect to PostgreSQL
def connect_db():
    return psycopg2.connect(**DB_PARAMS)

def insert_artist(cursor, artist):
    # Extract artist id and convert to int
    artist_id = artist.get('id')
    if artist_id is None:
        raise ValueError("Artist missing 'id'")
    artist_id = int(artist_id)

    # Insert into artists table
    cursor.execute("""
        INSERT INTO artists (id, name, real_name, profile, data_quality, full_data)
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

    # Insert URLs
    for url in artist.get('urls', {}).get('url', []):
        if url:
            cursor.execute("""
                INSERT INTO artist_urls (artist_id, url)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (artist_id, url))

    # Insert aliases
    for alias in artist.get('aliases', {}).get('name', []):
        if alias:
            cursor.execute("""
                INSERT INTO artist_aliases (artist_id, alias_name)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (artist_id, alias))

    # Insert name variations
    for var in artist.get('namevariations', {}).get('name', []):
        if var:
            cursor.execute("""
                INSERT INTO artist_name_variations (artist_id, variation)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (artist_id, var))

    # Insert members
    for member in artist.get('members', {}).get('name', []):
        if member:
            cursor.execute("""
                INSERT INTO artist_members (artist_id, member_name)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (artist_id, member))

    # Insert groups
    for group in artist.get('groups', {}).get('name', []):
        if group:
            cursor.execute("""
                INSERT INTO artist_groups (artist_id, group_name)
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
                # Extract actual artist dictionary inside the "artist" key
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