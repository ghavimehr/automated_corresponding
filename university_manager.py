# university_manager.py

import sqlite3
import datetime
import logging
import config  # Import your config.py to access TABLE_NAME

def setup_logger():
    # Configure logging
    logger = logging.getLogger('university_manager')
    logger.setLevel(logging.DEBUG)  # Set to DEBUG level for rich logging

    # Remove existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler for logging
    fh = logging.FileHandler('university_manager.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Stream handler for console output
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def add_professor_to_university(conn, university_name, professor_id, professor_name, table_name):
    logger = logging.getLogger('university_manager')
    cursor = conn.cursor()

    university_table = f"{table_name}_university"
    chronology_table = f"{table_name}_chronology"

    logger.debug(f"Attempting to add Professor '{professor_name}' (ID {professor_id}) to university '{university_name}' in table '{university_table}'.")

    # Ensure the university table exists
    create_university_table(conn, university_table)

    # Check if the university exists
    cursor.execute(f'''
        SELECT *
        FROM "{university_table}"
        WHERE University = ?
    ''', (university_name,))
    result = cursor.fetchone()

    if result:
        # University exists
        ID_university = result[0]
        columns = [description[0] for description in cursor.description]
        professor_columns = [col for col in columns if col.startswith('professor')]
        professor_values = result[columns.index(professor_columns[0]):]

        logger.debug(f"University '{university_name}' exists with ID {ID_university}.")

        # Find the next available professor slot
        for idx, (col_name, prof_id) in enumerate(zip(professor_columns, professor_values)):
            if prof_id is None:
                cursor.execute(f'''
                    UPDATE "{university_table}"
                    SET "{col_name}" = ?
                    WHERE ID_university = ?
                ''', (professor_id, ID_university))
                conn.commit()
                logger.info(f"Added Professor '{professor_name}' (ID {professor_id}) to university '{university_name}' in column '{col_name}'.")
                return True

        # All existing slots are full, add a new column
        next_index = len(professor_columns) + 1
        new_column_name = f'professor{next_index}'
        logger.warning(f"All existing professor slots are full for university '{university_name}'. Adding new column '{new_column_name}'.")

        # Alter the table to add the new column
        cursor.execute(f'''
            ALTER TABLE "{university_table}"
            ADD COLUMN "{new_column_name}" INTEGER
        ''')
        conn.commit()

        # Add the professor to the new column
        cursor.execute(f'''
            UPDATE "{university_table}"
            SET "{new_column_name}" = ?
            WHERE ID_university = ?
        ''', (professor_id, ID_university))
        conn.commit()
        logger.info(f"Added Professor '{professor_name}' (ID {professor_id}) to university '{university_name}' in new column '{new_column_name}'.")
        return True
    else:
        # University does not exist, create it and add the professor
        cursor.execute(f'''
            INSERT INTO "{university_table}" (University, professor1)
            VALUES (?, ?)
        ''', (university_name, professor_id))
        conn.commit()
        logger.info(f"Created university '{university_name}' and added Professor '{professor_name}' (ID {professor_id}) to 'professor1'.")
        return True

def can_select_new_professor(conn, university_name, table_name):
    logger = logging.getLogger('university_manager')
    cursor = conn.cursor()

    university_table = f"{table_name}_university"
    chronology_table = f"{table_name}_chronology"

    logger.debug(f"Checking if we can select a new professor from university '{university_name}' in table '{university_table}'.")

    # Ensure the university table exists
    create_university_table(conn, university_table)

    # Check if the university exists
    cursor.execute(f'''
        SELECT *
        FROM "{university_table}"
        WHERE University = ?
    ''', (university_name,))
    result = cursor.fetchone()

    if not result:
        # University does not exist, so we can select a professor
        logger.info(f"University '{university_name}' does not exist in '{university_table}'. Can select a new professor.")
        return True

    # University exists
    columns = [description[0] for description in cursor.description]
    professor_columns = [col for col in columns if col.startswith('professor')]
    professor_ids = [result[columns.index(col)] for col in professor_columns if result[columns.index(col)] is not None]

    logger.debug(f"University '{university_name}' has professors: {professor_ids}")

    if not professor_ids:
        # No professors associated with the university yet
        logger.info(f"No professors associated with university '{university_name}' in '{university_table}'. Can select a new professor.")
        return True

    # Get the latest professor (assuming the highest index is the latest)
    latest_professor_id = professor_ids[-1]  # Get the last professor in the list

    # Fetch professor's name for logging
    cursor.execute(f'''
        SELECT "Professor"
        FROM "{table_name}"
        WHERE "ID" = ?
    ''', (latest_professor_id,))
    res_name = cursor.fetchone()
    latest_professor_name = res_name[0] if res_name else 'Unknown'

    logger.debug(f"Latest professor for university '{university_name}' is '{latest_professor_name}' (ID {latest_professor_id}).")

    # Get the answer_status and send_date for the latest professor
    cursor.execute(f'''
        SELECT "answer_status", "send_date"
        FROM "{chronology_table}"
        WHERE "ID" = ?
    ''', (latest_professor_id,))
    res = cursor.fetchone()
    if res:
        answer_status, send_date = res
        days_since_sent = (datetime.datetime.now() - datetime.datetime.fromtimestamp(send_date)).days if send_date else None

        logger.debug(f"Latest professor '{latest_professor_name}' (ID {latest_professor_id}) has answer_status {answer_status} and days_since_sent {days_since_sent}.")

        if answer_status == 0:
            # Professor has not replied yet
            if days_since_sent is not None and days_since_sent < 7:
                # It's been less than 7 days since the email was sent
                logger.info(f"Cannot select new professor from university '{university_name}' because the latest professor '{latest_professor_name}' (ID {latest_professor_id}) has not replied and it's been less than 7 days since email was sent.")
                return False
            else:
                # It's been more than 7 days since the email was sent
                # Optionally, mark this professor with answer_status=20
                cursor.execute(f'''
                    UPDATE "{chronology_table}"
                    SET "answer_status" = 20
                    WHERE "ID" = ?
                ''', (latest_professor_id,))
                conn.commit()
                logger.info(f"Marked Professor '{latest_professor_name}' (ID {latest_professor_id}) with answer_status=20 due to no response after 7 days.")
        elif answer_status not in [1, 2, 3, 4, 10]:
            # Professor's answer_status is not in the allowed statuses
            logger.info(f"Cannot select new professor from university '{university_name}' because the latest professor '{latest_professor_name}' (ID {latest_professor_id}) has answer_status {answer_status} which is not allowed.")
            return False
    else:
        # No entry in chronology_table; treat as not allowed
        logger.warning(f"No entry in '{chronology_table}' for Professor '{latest_professor_name}' (ID {latest_professor_id}). Cannot select new professor.")
        return False

    # All conditions met, can select a new professor
    logger.info(f"Can select a new professor from university '{university_name}'.")
    return True

def create_university_table(conn, university_table):
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{university_table}" (
            "ID_university" INTEGER PRIMARY KEY AUTOINCREMENT,
            "University" TEXT NOT NULL,
            "professor1" INTEGER
        )
    ''')
    conn.commit()
