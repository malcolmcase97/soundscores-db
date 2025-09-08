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

LABELS_FILE = 'labels.jsonl'
ERROR_LOG = 'labels_errors.txt'

def connect_db():
    return psycopg2.connect(**DB_PARAMS)

def insert_label(cursor, label, log_file):
    label_id = int(label.get('id'))
    name = label.get('name')
    contact_info = label.get('contactinfo')
    profile = label.get('profile')
    data_quality = label.get('data_quality')
    is_full_entry = False  # default
    original_name = None

    # Handle parent label
    parent_id = None
    if label.get('parentLabel'):
        try:
            parent_id = int(label['parentLabel'].get('id'))
            # check if parent exists
            cursor.execute('SELECT 1 FROM "Labels" WHERE id = %s', (parent_id,))
            if not cursor.fetchone():
                message = f"⚠️ Parent label_id={parent_id} missing for label_id={label_id}, setting parent_id=None"
                print(message)
                log_file.write(message + "\n")
                parent_id = None
        except Exception as e:
            print(f"Error parsing parentLabel for label {label_id}: {e}")
            log_file.write(f"Error parsing parentLabel for label {label_id}: {e}\n")
            parent_id = None

    # Insert into Labels
    cursor.execute("""
        INSERT INTO "Labels" (id, name, contact_info, profile, data_quality, is_full_entry, original_name, parent_id, full_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        label_id, name, contact_info, profile, data_quality, is_full_entry, original_name, parent_id, Json(label)
    ))

    # Insert URLs
    urls_block = label.get('urls')
    urls = urls_block.get('url') if urls_block else []
    if isinstance(urls, str):
        urls = [urls]
    for url in urls or []:
        cursor.execute("""
            INSERT INTO "LabelUrls" (label_id, url)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (label_id, url))

def main(start_line=0):
    conn = connect_db()
    cursor = conn.cursor()
    log_file = open(ERROR_LOG, 'a', encoding='utf-8')

    with open(LABELS_FILE, 'r', encoding='utf-8') as file:
        # Skip ahead to start_line if needed
        for _ in range(start_line):
            next(file, None)

        for line_num, line in enumerate(tqdm(file, desc=f"Importing labels from line {start_line}"), start=start_line):
            try:
                data = json.loads(line)
                label = data.get('label')
                if not label:
                    print(f"Warning (line {line_num}): 'label' key missing, skipping")
                    continue

                insert_label(cursor, label, log_file)
                conn.commit()
            except Exception as e:
                print(f"Error inserting label on line {line_num}: {e}")
                log_file.write(f"Error inserting label on line {line_num}: {e}\n")
                conn.rollback()

    cursor.close()
    conn.close()
    log_file.close()
    print("✅ Label import complete.")

if __name__ == '__main__':
    main()
