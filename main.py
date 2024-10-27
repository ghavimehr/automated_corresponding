#!/home/ehsan/anaconda3/bin/python3

# main.py

import argparse
import data_gathering
import data_filtering
import modifier
import database_utils
import send_email
import sqlite3
import random
import time
import os
import logging
import university_manager
import reminder
from config import (
    TABLE_NAME,
    SEARCH_DEPTH,
    PROJECT_DIRECTORY,
    DB_FILE,
    TEST_RUN,
    TEST_EMAIL,
    REMINDER_INTERVAL_1,
    REMINDER_INTERVAL_2,
    REMINDER_INTERVAL_3,
    SENDING_METHOD,
    SEARCH_STYLE,
    # Removed EMAIL_ACCOUNTS from config.py
    # Add other configurations as needed
)
import datetime

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Main script to orchestrate the project.')
    parser.add_argument('-i', '--input',
                        help='SQLite database file.')
    parser.add_argument('-t', '--table-name',
                        help='Name of the table in the database.')
    parser.add_argument('-d', '--search-depth', type=int,
                        help='Depth of the link search.')
    parser.add_argument('-p', '--project-directory',
                        help='Project directory for storing data.')
    parser.add_argument('-e', '--email-account',
                        help='Email account to use (from_email). If not specified, a random account will be used.')
    return parser.parse_args()

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )

    args = parse_arguments()

    # Use command-line arguments if provided; otherwise, use config.py values
    db_file = args.input if args.input else DB_FILE
    table_name = args.table_name if args.table_name else TABLE_NAME
    project_directory = args.project_directory if args.project_directory else PROJECT_DIRECTORY
    search_depth = args.search_depth if args.search_depth else SEARCH_DEPTH
    specified_email_account = args.email_account  # This can be None

    logging.info("Starting main script")
    logging.info(f"Database file: {db_file}")
    logging.info(f"Table name: {table_name}")
    logging.info(f"Project directory: {project_directory}")
    logging.info(f"Search depth: {search_depth}")
    logging.info(f"Specified email account: {specified_email_account}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create or update necessary tables
    database_utils.create_tables(conn, table_name)
    logging.info("Database tables ensured.")

    # Fetch email accounts from the database
    cursor.execute('''
        SELECT "ID", "from_email" FROM email_accounts
    ''')
    email_accounts = cursor.fetchall()

    if not email_accounts:
        logging.error("No email accounts found in the database. Please add email accounts to proceed.")
        return

    # Determine which email account to use
    if specified_email_account:
        # Find the email account with the specified from_email
        email_account = next((acc for acc in email_accounts if acc[1] == specified_email_account), None)
        if email_account:
            from_email = email_account[1]  # Corrected line
            email_account_id = email_account[0]  # Added to get email_account_id
            logging.info(f"Using specified email account: {from_email}")
        else:
            logging.error(f"Email account '{specified_email_account}' not found in the database.")
            return
    else:
        # Choose a random email account
        email_account = random.choice(email_accounts)
        from_email = email_account[1]  # Corrected line
        email_account_id = email_account[0]  # Added to get email_account_id
        logging.info(f"Using random email account: {from_email}")

    # Main loop to process professors
    chronology_table = f"{table_name}_chronology"

    # Fetch professors where email_sent is not 1
    cursor.execute(f'''
        SELECT p."ID", p."Professor", p."Email", p."Webpage", p."University", c."email_sent"
        FROM "{table_name}" p
        LEFT JOIN "{chronology_table}" c ON p."ID" = c."ID"
        WHERE c."email_sent" IS NULL OR c."email_sent" != 1
    ''')

    professors = cursor.fetchall()
    logging.info(f"Found {len(professors)} professors to process.")

    # Shuffle the list to process professors randomly
    random.shuffle(professors)

    for professor in professors:
        professor_id, professor_name, professor_email, webpage, university_name, email_sent = professor

        # Process each professor
        logging.info(f"Processing Professor ID {professor_id}: {professor_name}")

        try:
            # Check if data gathering has been completed
            cursor.execute(f'''
                SELECT "data_gathering_completed"
                FROM "{chronology_table}"
                WHERE "ID" = ?
            ''', (professor_id,))
            result = cursor.fetchone()
            data_gathering_completed = result[0] if result else False

            if not data_gathering_completed:
                # Call data_gathering module
                data_gathering.main(db_file, table_name, project_directory, search_depth, professor_id)
                # Update the chronology table
                cursor.execute(f'''
                    INSERT OR REPLACE INTO "{chronology_table}" (
                        "ID", "Email", "search_style", "search_depth", "search_date",
                        "data_gathering_completed", "reminder_interval_1", "reminder_interval_2", "reminder_interval_3"
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    professor_id,
                    professor_email,
                    SEARCH_STYLE,
                    search_depth,
                    int(datetime.datetime.now().timestamp()),
                    True,
                    REMINDER_INTERVAL_1,
                    REMINDER_INTERVAL_2,
                    REMINDER_INTERVAL_3
                ))
                conn.commit()
                logging.info(f"Data gathering completed for Professor ID {professor_id}")

            # Similarly, check and perform data filtering
            cursor.execute(f'''
                SELECT "data_filtering_completed"
                FROM "{chronology_table}"
                WHERE "ID" = ?
            ''', (professor_id,))
            result = cursor.fetchone()
            data_filtering_completed = result[0] if result else False

            if not data_filtering_completed:
                # Call data_filtering module
                data_filtering.filter_professor_data(professor_name, project_directory)
                # Update the chronology table
                cursor.execute(f'''
                    UPDATE "{chronology_table}"
                    SET "data_filtering_completed" = TRUE
                    WHERE "ID" = ?
                ''', (professor_id,))
                conn.commit()
                logging.info(f"Data filtering completed for Professor ID {professor_id}")

            # Similarly, check and perform modifier
            cursor.execute(f'''
                SELECT "html_generation_completed", "cv_generation_completed"
                FROM "{chronology_table}"
                WHERE "ID" = ?
            ''', (professor_id,))
            result = cursor.fetchone()
            html_generation_completed = result[0] if result else False
            cv_generation_completed = result[1] if result else False

            if not html_generation_completed or not cv_generation_completed:
                # Call modifier module
                modifier.modify_template(db_file, table_name, project_directory, professor_id, professor_name)
                # html_generation_completed and cv_generation_completed are updated within modifier.py
                logging.info(f"Template modification completed for Professor ID {professor_id}")

            # Now, prepare to send the email
            # Update the chronology table with from_email and sending_method
            cursor.execute(f'''
                UPDATE "{chronology_table}"
                SET "from_email" = ?, "sending_method" = ?
                WHERE "ID" = ?
            ''', (from_email, SENDING_METHOD, professor_id))
            conn.commit()

            # Prepare the email content and attachments
            # Load email1.html
            safe_professor_name = ''.join(c if c.isalnum() else '_' for c in professor_name)
            professor_dir = os.path.join(project_directory, 'data', safe_professor_name)
            email_html_path = os.path.join(professor_dir, 'email1.html')
            cv_path = os.path.join(professor_dir, 'Ehsan_Ghavimehr_CV.pdf')  # Adjust as per your CV format

            if not os.path.exists(email_html_path):
                logging.warning(f"Email HTML file not found for {professor_name}")
                continue
            if not os.path.exists(cv_path):
                logging.warning(f"CV file not found for {professor_name}")
                continue

            with open(email_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Prepare to send email
            to_email = professor_email
            subject = 'Prospective Ph.D. Student'

            # Handle TEST_RUN
            if TEST_RUN:
                to_email = TEST_EMAIL
                logging.info(f"TEST_RUN is enabled. Email will be sent to {TEST_EMAIL} instead of {professor_email}")

            # Send email
            email_sent_flag, message_id, from_email_used = send_email.send_email_smtp(
                db_file=db_file,
                email_account_id=email_account_id,  # Use the email_account_id
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                attachment_paths=[cv_path]
            )

            if email_sent_flag:
                # Update the chronology table
                cursor.execute(f'''
                    UPDATE "{chronology_table}"
                    SET "email_sent" = 1, "send_date" = ?, "from_email" = ?, "message_id0" = ?
                    WHERE "ID" = ?
                ''', (int(datetime.datetime.now().timestamp()), from_email_used, message_id, professor_id))
                conn.commit()
                logging.info(f"Email sent to {to_email} for Professor ID {professor_id}")
            else:
                logging.error(f"Failed to send email to {to_email} for Professor ID {professor_id}")

            # Wait for a random interval between emails
            time_interval = random.randint(60, 180)  # Wait between 1 and 3 minutes
            logging.info(f"Waiting for {time_interval} seconds before processing the next professor...")
            time.sleep(time_interval)
        except Exception as e:
            logging.exception(f"An error occurred while processing Professor ID {professor_id}")

    # **Moved the call to send_reminders outside the for loop**
    reminder.send_reminders(db_file, project_directory)

    conn.close()
    logging.info("Processing completed.")

if __name__ == '__main__':
    main()
