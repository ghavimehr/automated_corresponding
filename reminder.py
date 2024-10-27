#!/home/ehsan/anaconda3/bin/python3
# reminder.py

import sqlite3
import datetime
import send_email  # Assuming send_email.py is in the same directory
import logging
import os
from email.utils import formataddr, format_datetime
import email
from email import policy
import imaplib
import config  # Import your config.py

def send_reminders(db_file, project_directory):
    # Configure logging
    logger = logging.getLogger('reminder')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Remove any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler for logging
    fh = logging.FileHandler('reminder.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Stream handler for console output
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    table_name = config.TABLE_NAME
    chronology_table = f"{table_name}_chronology"

    # Fetch all professors who have been emailed and have answer_status in (0, 20)
    cursor.execute(f'''
        SELECT c."ID", c."email_sent", c."send_date",
               c."reminder1", c."reminder_interval_1",
               c."reminder2", c."reminder_interval_2",
               c."reminder3", c."reminder_interval_3",
               c."answer_status", c."from_email",
               p."Professor", p."Email", p."University"
        FROM "{chronology_table}" c
        JOIN "{table_name}" p ON c."ID" = p."ID"
        WHERE c."email_sent" = 1
          AND c."answer_status" IN (0, 20)
    ''')
    rows = cursor.fetchall()

    logger.info(f"Processing {len(rows)} professors for reminders.")

    current_timestamp = int(datetime.datetime.now().timestamp())

    for row in rows:
        (professor_id, email_sent, send_date,
         reminder1, reminder_interval_1,
         reminder2, reminder_interval_2,
         reminder3, reminder_interval_3,
         answer_status, from_email,
         professor_name, professor_email, university_name) = row

        logger.info(f"Processing Professor ID {professor_id}: {professor_name}")

        # Initialize variables
        reminder_number = None
        previous_send_timestamp = None
        previous_interval = None
        previous_email_filename = None
        email_sent = False  # Initialize email_sent as False

        try:
            # Determine which reminder to send
            if reminder1 != 1:
                # Check if it's time to send reminder1
                previous_send_timestamp = send_date
                days_since_email_sent = (current_timestamp - previous_send_timestamp) / 86400  # Convert seconds to days
                if days_since_email_sent >= config.REMINDER_INTERVAL_1:
                    # Time to send reminder1
                    reminder_number = 1
                    previous_email_filename = 'email1.html'
                    logger.info(f"It's time to send reminder1 to Professor ID {professor_id}")
                else:
                    # Not time yet, set reminder1 to 0
                    cursor.execute(f'''
                        UPDATE "{chronology_table}"
                        SET "reminder1" = 0
                        WHERE "ID" = ?
                    ''', (professor_id,))
                    conn.commit()
                    logger.info(f"Not time to send reminder1 to Professor ID {professor_id}. Set reminder1 to 0.")
                    continue
            elif reminder2 != 1:
                # Check if it's time to send reminder2
                if reminder_interval_1 is not None:
                    previous_send_timestamp = send_date + (reminder_interval_1 * 86400)
                    days_since_reminder1 = (current_timestamp - previous_send_timestamp) / 86400
                    if days_since_reminder1 >= config.REMINDER_INTERVAL_2:
                        # Time to send reminder2
                        reminder_number = 2
                        previous_email_filename = 'email2.html'
                        logger.info(f"It's time to send reminder2 to Professor ID {professor_id}")
                    else:
                        # Not time yet, set reminder2 to 0
                        cursor.execute(f'''
                            UPDATE "{chronology_table}"
                            SET "reminder2" = 0
                            WHERE "ID" = ?
                        ''', (professor_id,))
                        conn.commit()
                        logger.info(f"Not time to send reminder2 to Professor ID {professor_id}. Set reminder2 to 0.")
                        continue
                else:
                    logger.warning(f"Reminder1 interval is missing for Professor ID {professor_id}. Cannot send reminder2.")
                    continue
            elif reminder3 != 1:
                # Check if it's time to send reminder3
                if reminder_interval_1 is not None and reminder_interval_2 is not None:
                    previous_send_timestamp = send_date + ((reminder_interval_1 + reminder_interval_2) * 86400)
                    days_since_reminder2 = (current_timestamp - previous_send_timestamp) / 86400
                    if days_since_reminder2 >= config.REMINDER_INTERVAL_3:
                        # Time to send reminder3
                        reminder_number = 3
                        previous_email_filename = 'email3.html'
                        logger.info(f"It's time to send reminder3 to Professor ID {professor_id}")
                    else:
                        # Not time yet, set reminder3 to 0
                        cursor.execute(f'''
                            UPDATE "{chronology_table}"
                            SET "reminder3" = 0
                            WHERE "ID" = ?
                        ''', (professor_id,))
                        conn.commit()
                        logger.info(f"Not time to send reminder3 to Professor ID {professor_id}. Set reminder3 to 0.")
                        continue
                else:
                    logger.warning(f"Reminder intervals are missing for Professor ID {professor_id}. Cannot send reminder3.")
                    continue
            else:
                # All reminders have been sent
                logger.info(f"All reminders have been sent to Professor ID {professor_id}")
                continue

            # Fetch email account details using from_email
            cursor.execute('''
                SELECT "ID", "from_email", "username", "password", "smtp_host", "smtp_port", "imap_host", "imap_port", "ssl"
                FROM email_accounts
                WHERE "from_email" = ?
            ''', (from_email,))
            email_account = cursor.fetchone()
            if not email_account:
                logger.error(f"No email account found for from_email {from_email}")
                continue  # Skip this professor

            email_account_id, from_email, username, password, smtp_host, smtp_port, imap_host, imap_port, ssl_flag = email_account

            # Fetch message IDs from the database
            message_id_columns = ['message_id0', 'message_id1', 'message_id2', 'message_id3']
            cursor.execute(f'''
                SELECT {', '.join(f'"{col}"' for col in message_id_columns)}
                FROM "{chronology_table}"
                WHERE "ID" = ?
            ''', (professor_id,))
            message_id_row = cursor.fetchone()
            message_ids = []
            if message_id_row:
                for msg_id in message_id_row:
                    if msg_id:
                        message_ids.append(msg_id)
                    else:
                        message_ids.append(None)
            else:
                message_ids = [None] * 4  # Initialize with None

            # Determine the previous message ID
            previous_message_id = message_ids[reminder_number - 1]  # Indexing starts from 0
            in_reply_to = None
            references = None

            if previous_message_id:
                # Use the message ID from the database
                in_reply_to = previous_message_id
                references = ' '.join(filter(None, message_ids[:reminder_number]))
                logger.info(f"Using message IDs from database for threading: {references}")
            else:
                # Try to fetch the message ID via IMAP
                logger.info(f"Message-ID not found in database for reminder {reminder_number}. Attempting to fetch via IMAP.")
                fetched_message_id, thread_id, _ = fetch_original_message_id(
                    imap_host, imap_port, username, password, professor_email, ssl_flag,
                    previous_email_filename, project_directory, professor_name, from_email, logger
                )
                if fetched_message_id:
                    in_reply_to = fetched_message_id
                    references = fetched_message_id
                    # Save the fetched message ID into the database
                    message_id_column = f'message_id{reminder_number - 1}'
                    cursor.execute(f'''
                        UPDATE "{chronology_table}"
                        SET "{message_id_column}" = ?
                        WHERE "ID" = ?
                    ''', (fetched_message_id, professor_id))
                    conn.commit()
                    logger.info(f"Fetched and saved Message-ID '{fetched_message_id}' for Professor ID {professor_id}")
                else:
                    logger.warning(f"Could not fetch Message-ID via IMAP for Professor ID {professor_id}")
                    # Proceed without message ID, construct email to look like a reply using local emails

            # Generate reminder email content
            reminder_html_filename = f"reminder{reminder_number}.html"
            reminder_html_path = os.path.join(project_directory, reminder_html_filename)

            if not os.path.exists(reminder_html_path):
                logger.warning(f"Reminder HTML file not found: {reminder_html_path}")
                continue
            else:
                logger.info(f"Reminder HTML file found: {reminder_html_path}")

            with open(reminder_html_path, 'r', encoding='utf-8') as f:
                reminder_html_content = f.read()

            # Replace placeholders
            reminder_html_content = reminder_html_content.replace('{{ProfessorName}}', professor_name)
            reminder_html_content = reminder_html_content.replace('{{University}}', university_name)

            # Prepare to send email
            to_email = professor_email
            subject = f'Re: Prospective Ph.D. Student'

            # Handle TEST_RUN
            if config.TEST_RUN:
                to_email = config.TEST_EMAIL
                logger.info(f"TEST_RUN is enabled. Email will be sent to {config.TEST_EMAIL} instead of {professor_email}")

            # Prepare attachment paths
            # Attach the CV from the professor's folder
            safe_professor_name = ''.join(c if c.isalnum() else '_' for c in professor_name)
            professor_folder = os.path.join(project_directory, 'data', safe_professor_name)
            cv_path = os.path.join(professor_folder, 'Ehsan_Ghavimehr_CV.pdf')
            attachment_paths = []
            if os.path.exists(cv_path):
                attachment_paths.append(cv_path)
            else:
                logger.warning(f"CV file not found at {cv_path}. Proceeding without attachment.")

            # Concatenate previous email(s) if necessary
            if not in_reply_to:
                # No message ID available, construct email to look like a reply
                logger.info("No Message-ID available. Using local emails to create a reply-like email.")

                # Load previous email(s) from local files and concatenate
                email_chain = ''
                for i in range(reminder_number, 0, -1):
                    email_html_filename = f'email{i}.html'
                    email_html_path = os.path.join(professor_folder, email_html_filename)
                    if os.path.exists(email_html_path):
                        with open(email_html_path, 'r', encoding='utf-8') as f:
                            email_content = f.read()
                        # Simulate email reply format
                        email_date = format_datetime(datetime.datetime.fromtimestamp(send_date))
                        email_sender = formataddr((from_email, from_email))
                        email_recipient = formataddr((professor_name, to_email))
                        reply_header = f'<br><br>On {email_date}, {email_sender} wrote:<br><br>'
                        email_chain += reply_header + email_content
                    else:
                        logger.warning(f"Local email file not found: {email_html_path}")
                # Combine the reminder content with the email chain
                html_content = reminder_html_content + email_chain
            else:
                # Message-ID available, proceed normally
                html_content = reminder_html_content

            # Send reminder email
            email_sent, new_message_id = send_email.send_email_smtp(
                db_file=db_file,
                email_account_id=email_account_id,
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                attachment_paths=attachment_paths,
                in_reply_to=in_reply_to,
                references=references
            )

            if email_sent:
                # Save the sent email content into the professor's folder
                email_html_filename = f'email{reminder_number + 1}.html'  # email2.html, email3.html, etc.
                email_html_path = os.path.join(professor_folder, email_html_filename)
                with open(email_html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Saved sent email content to {email_html_path}")

                # Update the chronology table
                current_timestamp = int(datetime.datetime.now().timestamp())

                # Save the new message_id in the database
                message_id_column = f'message_id{reminder_number}'
                # Calculate actual interval since previous email
                if reminder_number == 1:
                    previous_timestamp = send_date
                elif reminder_number == 2:
                    previous_timestamp = send_date + (reminder_interval_1 * 86400)
                elif reminder_number == 3:
                    previous_timestamp = send_date + ((reminder_interval_1 + reminder_interval_2) * 86400)
                else:
                    previous_timestamp = current_timestamp  # Default to current time

                actual_interval = (current_timestamp - previous_timestamp) // 86400  # Convert seconds to days

                cursor.execute(f'''
                    UPDATE "{chronology_table}"
                    SET "reminder{reminder_number}" = 1,
                        "reminder_interval_{reminder_number}" = ?,
                        "{message_id_column}" = ?
                    WHERE "ID" = ?
                ''', (actual_interval, new_message_id, professor_id))
                conn.commit()
                logger.info(f"Reminder {reminder_number} sent to {to_email} for Professor ID {professor_id}")
            else:
                logger.error(f"Failed to send reminder {reminder_number} to {to_email} for Professor ID {professor_id}")
                # Do not update reminderX; proceed to next professor

        except Exception as e:
            logger.exception(f"An error occurred while processing Professor ID {professor_id}: {e}")
            # Do not update reminderX; proceed to next professor

    conn.close()

def fetch_original_message_id(imap_host, imap_port, username, password, to_email, ssl_flag, previous_email_filename, project_directory, professor_name, from_email, logger):
    try:
        if ssl_flag:
            imap = imaplib.IMAP4_SSL(imap_host, int(imap_port))
        else:
            imap = imaplib.IMAP4(imap_host, int(imap_port))
        imap.login(username, password)

        # Select the 'Sent' folder
        if 'gmail' in from_email.lower():
            folder_name = '"[Gmail]/Sent Mail"'
        elif 'hostinger' in imap_host.lower():
            folder_name = 'INBOX.Sent'  # Adjusted folder name
        else:
            folder_name = 'INBOX.Sent'  # Adjusted folder name for other providers

        # Try selecting the folder
        status, messages = imap.select(folder_name)
        if status != 'OK':
            logger.warning(f"Could not select folder '{folder_name}'. Status: {status}")
            # List available mailboxes to help debug
            status, mailboxes = imap.list()
            if status == 'OK':
                logger.info("Available mailboxes:")
                for mailbox in mailboxes:
                    logger.info(mailbox.decode())
            else:
                logger.warning("Failed to list mailboxes.")
            imap.logout()
            logger.warning(f"Proceeding without threading. Using local {previous_email_filename}.")
            return None, None, None

        # Search for the sent email to the professor
        status, data = imap.search(None, f'(TO "{to_email}")')
        if status != 'OK':
            logger.warning(f"IMAP search failed for {to_email}")
            imap.logout()
            logger.warning(f"Proceeding without threading. Using local {previous_email_filename}.")
            return None, None, None

        email_ids = data[0].split()
        if not email_ids:
            logger.warning(f"No sent emails found to {to_email}")
            imap.logout()
            logger.warning(f"Proceeding without threading. Using local {previous_email_filename}.")
            return None, None, None

        # Fetch the latest email
        latest_email_id = email_ids[-1]
        status, msg_data = imap.fetch(latest_email_id, '(RFC822)')
        if status != 'OK':
            logger.warning(f"Failed to fetch email with ID {latest_email_id}")
            imap.logout()
            logger.warning(f"Proceeding without threading. Using local {previous_email_filename}.")
            return None, None, None

        raw_email = msg_data[0][1]
        email_message = email.message_from_bytes(raw_email, policy=policy.default)

        message_id = email_message.get('Message-ID')
        references = email_message.get('References') or message_id

        imap.logout()

        return message_id, references, None  # We don't need the content here

    except Exception as e:
        logger.exception(f"Error fetching original message ID: {e}")
        logger.warning(f"Proceeding without threading. Using local {previous_email_filename}.")
        return None, None, None
