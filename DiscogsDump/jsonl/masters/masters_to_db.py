import json
import psycopg2
from psycopg2.extras import Json
from tqdm import tqdm
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

MASTERS_FILE = 'masters.jsonl'
ERROR_LOG = 'master_artists_errors.txt'

def connect_db():
    return psycopg2.connect(**DB_PARAMS)

def insert_master(cursor, master, log_file):
    master_id = master.get('id')
    if master_id is None:
        raise ValueError("Master missing 'id'")
    master_id = int(master_id)

    title = master.get('title')
    year = int(master.get('year')) if master.get('year') else None
    main_release = int(master.get('main_release')) if master.get('main_release') else None
    data_quality = master.get('data_quality')

    # Insert into Masters
    cursor.execute("""
        INSERT INTO "Masters" (id, title, year, main_release, data_quality, full_data)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        master_id, title, year, main_release, data_quality, Json(master)
    ))

    # Insert into MasterArtists
    artist_block = master.get('artists', {}).get('artist')
    if isinstance(artist_block, dict):
        artist_block = [artist_block]

    for artist in artist_block or []:
        try:
            artist_id = int(artist['id'])
            join_phrase = artist.get('join')
            anv = artist.get('anv')

            # Check if artist exists in Artists table
            cursor.execute('SELECT 1 FROM "Artists" WHERE id = %s', (artist_id,))
            if cursor.fetchone():
                cursor.execute("""
                    INSERT INTO "MasterArtists" (master_id, artist_id, join_phrase, anv)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (master_id, artist_id, join_phrase, anv))
            else:
                message = f"⚠️ Skipping missing artist_id={artist_id} for master_id={master_id}"
                print(message)
                log_file.write(message + "\n")
        except Exception as e:
            print(f"Skipping artist for master {master_id}: {e}")
            log_file.write(f"⚠️ Error with artist block on master {master_id}: {e}\n")

    # Insert into MasterGenres
    genres = master.get('genres', {}).get('genre')
    if isinstance(genres, str):
        genres = [genres]

    for genre in genres or []:
        cursor.execute("""
            INSERT INTO "MasterGenres" (master_id, genre)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (master_id, genre))

    # Insert into MasterStyles
    styles = master.get('styles', {}).get('style')
    if isinstance(styles, str):
        styles = [styles]

    for style in styles or []:
        cursor.execute("""
            INSERT INTO "MasterStyles" (master_id, style)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (master_id, style))

    # Insert into MasterVideos
    videos = master.get('videos', {}).get('video')
    if isinstance(videos, dict):
        videos = [videos]

    for video in videos or []:
        video_title = video.get('title')
        description = video.get('description')
        cursor.execute("""
            INSERT INTO "MasterVideos" (master_id, title, description)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (master_id, video_title, description))

def main():
    conn = connect_db()
    cursor = conn.cursor()
    log_file = open(ERROR_LOG, 'a', encoding='utf-8')

    with open(MASTERS_FILE, 'r', encoding='utf-8') as file:
        for line in tqdm(file, desc="Importing masters"):
            try:
                data = json.loads(line)
                master = data.get('master')
                if not master:
                    print("Warning: 'master' key missing in line, skipping")
                    continue

                # Ensure master has ID (sometimes not explicitly set)
                if 'id' not in master and master.get('main_release'):
                    master['id'] = int(master.get('main_release'))

                insert_master(cursor, master, log_file)
                conn.commit()
            except Exception as e:
                print(f"Error inserting master: {e}")
                log_file.write(f"Error inserting master: {e}\n")
                conn.rollback()

    cursor.close()
    conn.close()
    log_file.close()
    print("✅ Master import complete.")

if __name__ == '__main__':
    main()
