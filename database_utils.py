# database_utils.py

import sqlite3

def create_tables(conn, table_name):
    cursor = conn.cursor()

    # Create answer_status_dict table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_status_dict (
            "answer_status" INTEGER PRIMARY KEY,
            "description" TEXT
        )
    ''')
    # Populate answer_status_dict if empty
    cursor.execute('SELECT COUNT(*) FROM answer_status_dict')
    if cursor.fetchone()[0] == 0:
        answer_statuses = [
            (0, 'No Answer'),
            (1, 'Positive Response'),
            (2, 'Negative Response'),
            (3, 'Out of Office'),
            (4, 'Follow-up Needed')
        ]
        cursor.executemany('''
            INSERT INTO answer_status_dict ("answer_status", "description")
            VALUES (?, ?)
        ''', answer_statuses)

    # Create search_style_dict table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_style_dict (
            "search_style" INTEGER PRIMARY KEY,
            "description" TEXT
        )
    ''')
    # Populate search_style_dict if empty
    cursor.execute('SELECT COUNT(*) FROM search_style_dict')
    if cursor.fetchone()[0] == 0:
        search_styles = [
            (1, 'Breadth-First Search'),
            (2, 'Depth-First Search')
        ]
        cursor.executemany('''
            INSERT INTO search_style_dict ("search_style", "description")
            VALUES (?, ?)
        ''', search_styles)

    # Create email_accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_accounts (
            "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
            "from_email" TEXT UNIQUE,
            "username" TEXT,
            "password" TEXT,
            "smtp_host" TEXT,
            "smtp_port" INTEGER,
            "imap_host" TEXT,
            "imap_port" INTEGER,
            "ssl" BOOLEAN
        )
    ''')

    # Create {table_name} table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            "ID" INTEGER PRIMARY KEY,
            "University" TEXT,
            "Professor" TEXT,
            "Webpage" TEXT,
            "Email" TEXT,
            "Research Area" TEXT
        )
    ''')

    # Create the new university_table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS university_table (
            "ID_university" INTEGER PRIMARY KEY AUTOINCREMENT,
            "University" TEXT UNIQUE,
            "professor1" INTEGER,
            "professor2" INTEGER,
            "professor3" INTEGER,
            "professor4" INTEGER,
            "professor5" INTEGER,
            "professor6" INTEGER,
            "professor7" INTEGER,
            "professor8" INTEGER,
            "professor9" INTEGER,
            "professor10" INTEGER
        )
    ''')

    # Create {table_name}_chronology table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{table_name}_chronology" (
            "ID" INTEGER PRIMARY KEY,
            "Email" TEXT,
            "search_style" INTEGER,
            "search_depth" INTEGER,
            "search_date" INTEGER,
            "data_gathering_completed" BOOLEAN DEFAULT FALSE,
            "data_filtering_completed" BOOLEAN DEFAULT FALSE,
            "html_generation_completed" BOOLEAN DEFAULT FALSE,
            "cv_generation_completed" BOOLEAN DEFAULT FALSE,
            "email_sent" BOOLEAN DEFAULT FALSE,
            "send_date" INTEGER,
            "from_email" TEXT,
            "sending_method" TEXT,
            "answer_status" INTEGER DEFAULT 0,
            "reminder_interval_1" INTEGER,
            "reminder1" INTEGER,
            "reminder_interval_2" INTEGER,
            "reminder2" INTEGER,
            "reminder_interval_3" INTEGER,
            "reminder3" INTEGER,
            FOREIGN KEY("ID") REFERENCES "{table_name}"("ID"),
            FOREIGN KEY("Email") REFERENCES "{table_name}"("Email"),
            FOREIGN KEY("search_style") REFERENCES "search_style_dict"("search_style"),
            FOREIGN KEY("answer_status") REFERENCES "answer_status_dict"("answer_status"),
            FOREIGN KEY("from_email") REFERENCES "email_accounts"("from_email")
        )
    ''')

    conn.commit()
