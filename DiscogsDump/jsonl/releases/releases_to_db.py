import json
import psycopg2
from psycopg2.extras import Json
from tqdm import tqdm
from dotenv import load_dotenv
import os
import argparse

load_dotenv()

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

RELEASES_FILE = 'releases.jsonl'
ERROR_LOG = 'release_import_errors.txt'

def connect_db():
    return psycopg2.connect(**DB_PARAMS)

def insert_release(cursor, release, log_file):
    try:
        release_id_raw = release.get('id')
        if not release_id_raw:
            raise ValueError("Release missing ID")

        release_id = int(release_id_raw)
        master_id_raw = release.get('master_id')
        master_id = int(master_id_raw['value']) if isinstance(master_id_raw, dict) and 'value' in master_id_raw else (
            int(master_id_raw) if isinstance(master_id_raw, str) else None
        )
        title = release.get('title')
        country = release.get('country')
        released_date = release.get('released')
        notes = release.get('notes')
        data_quality = release.get('data_quality')

        cursor.execute("""
            INSERT INTO "Releases" 
            (id, master_id, title, country, released_date, notes, data_quality, full_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, (release_id, master_id, title, country, released_date, notes, data_quality, Json(release)))

        # Primary artists
        artists_block = release.get('artists', {}).get('artist')
        if isinstance(artists_block, dict):
            artists_block = [artists_block]

        for artist in artists_block or []:
            artist_id_raw = artist.get('id')
            if artist_id_raw is not None:
                try:
                    artist_id = int(artist_id_raw)
                except (TypeError, ValueError):
                    continue

                role = artist.get('role', 'Primary')

                cursor.execute('SELECT 1 FROM "Artists" WHERE id = %s', (artist_id,))
                if cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO "ReleaseArtists" (release_id, artist_id, role)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (release_id, artist_id, role))

        # Extra artists
        extra_artists_block = release.get('extraartists')
        if extra_artists_block and 'artist' in extra_artists_block:
            extras = extra_artists_block['artist']
            if isinstance(extras, dict):
                extras = [extras]
            for artist in extras:
                artist_id_raw = artist.get('id')
                try:
                    artist_id = int(artist_id_raw) if artist_id_raw is not None else None
                except (TypeError, ValueError):
                    artist_id = None

                anv = artist.get('anv')
                role = artist.get('role')

                if artist_id is not None:
                    cursor.execute('SELECT 1 FROM "Artists" WHERE id = %s', (artist_id,))
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO "ReleaseExtraArtists" (release_id, artist_id, anv, role)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (release_id, artist_id, anv, role))

        # Formats
        formats_block = release.get('formats', {}).get('format')
        descriptions = []
        if isinstance(formats_block, list):
            for f in formats_block:
                desc = f.get('descriptions', {}).get('description')
                if isinstance(desc, list):
                    descriptions.extend(desc)
                elif isinstance(desc, str):
                    descriptions.append(desc)
        elif isinstance(formats_block, dict):
            desc = formats_block.get('descriptions', {}).get('description')
            if isinstance(desc, list):
                descriptions = desc
            elif isinstance(desc, str):
                descriptions = [desc]

        for desc in descriptions:
            cursor.execute("""
                INSERT INTO "ReleaseFormats" (release_id, format_desc)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (release_id, desc))

        # Videos
        videos_block = release.get('videos', {}).get('video')
        if isinstance(videos_block, dict):
            videos_block = [videos_block]
        for video in videos_block or []:
            title = video.get('title')
            description = video.get('description')
            cursor.execute("""
                INSERT INTO "ReleaseVideos" (release_id, title, description)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (release_id, title, description))

        # Tracklist and per-track extra artists
        tracks = release.get('tracklist', {}).get('track')
        if isinstance(tracks, dict):
            tracks = [tracks]
        for track in tracks or []:
            position = track.get('position')
            track_title = track.get('title')
            duration = track.get('duration')

            cursor.execute("""
                INSERT INTO "ReleaseTracklist" (release_id, position, title, duration)
                VALUES (%s, %s, %s, %s)
                RETURNING track_id;
            """, (release_id, position, track_title, duration))

            track_id = cursor.fetchone()[0]

            extraartists = track.get('extraartists')
            if extraartists and 'artist' in extraartists:
                ea_list = extraartists['artist']
                if isinstance(ea_list, dict):
                    ea_list = [ea_list]
                for ea in ea_list:
                    artist_id_raw = ea.get('id')
                    try:
                        artist_id = int(artist_id_raw) if artist_id_raw is not None else None
                    except (TypeError, ValueError):
                        artist_id = None
                    name = ea.get('name')
                    anv = ea.get('anv')
                    role = ea.get('role')

                    if artist_id is not None:
                        cursor.execute('SELECT 1 FROM "Artists" WHERE id = %s', (artist_id,))
                        if cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO "TrackExtraArtists" (release_id, track_id, artist_id, name, anv, role)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING;
                            """, (release_id, track_id, artist_id, name, anv, role))

        # Labels
        labels_block = release.get('labels', {}).get('label')
        if isinstance(labels_block, dict):
            labels_block = [labels_block]
        for label in labels_block or []:
            label_id = label.get('id')
            if label_id:
                cursor.execute("""
                    INSERT INTO "ReleaseLabels" (release_id, label_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (release_id, label_id))

        # Companies
        companies_block = release.get('companies', {}).get('company')
        if isinstance(companies_block, dict):
            companies_block = [companies_block]
        for company in companies_block or []:
            company_id = company.get('id')
            role = company.get('entity_type_name') or company.get('role')
            if company_id:
                cursor.execute("""
                    INSERT INTO "ReleaseCompanies" (release_id, company_id, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (release_id, company_id, role))

        # Identifiers
        identifiers_block = release.get('identifiers', {}).get('identifier')
        if isinstance(identifiers_block, dict):
            identifiers_block = [identifiers_block]
        for identifier in identifiers_block or []:
            id_type = identifier.get('type')
            value = identifier.get('value')
            if id_type or value:
                cursor.execute("""
                    INSERT INTO "ReleaseIdentifiers" (release_id, type, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (release_id, id_type, value))

    except Exception as e:
        log_file.write(f"Error processing release id {release.get('id')}: {e}\n")
        print(f"Error processing release id {release.get('id')}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Import Discogs releases into database")
    parser.add_argument('--start', type=int, default=0, help="Line number to start processing from (0-indexed)")
    args = parser.parse_args()

    conn = connect_db()
    cursor = conn.cursor()
    log_file = open(ERROR_LOG, 'a', encoding='utf-8')

    with open(RELEASES_FILE, 'r', encoding='utf-8') as file:
        for i, line in enumerate(tqdm(file, desc="Importing releases")):
            if i < args.start:
                continue
            try:
                data = json.loads(line)
                release = data.get('release')
                if not release:
                    continue
                if 'id' not in release and release.get('master_id'):
                    release['id'] = int(release['master_id'])

                insert_release(cursor, release, log_file)
                conn.commit()
            except Exception as e:
                log_file.write(f"General error on line {i}: {e}\n")
                print(f"General error on line {i}: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    log_file.close()
    print("✅ Release import complete.")

if __name__ == '__main__':
    main()
