import os
import json
import re
import logging
from datetime import datetime
from collections import OrderedDict
import unidecode  # For normalizing Unicode text

def filter_professor_data(professor_name, project_directory):
    # Configure logging
    logger = logging.getLogger('data_filtering')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Remove existing handlers to prevent duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler for logging
    fh = logging.FileHandler('data_filtering.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Stream handler for console output
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    safe_professor_name = ''.join(c if c.isalnum() else '_' for c in professor_name)
    professor_dir = os.path.join(project_directory, 'data', safe_professor_name)

    if not os.path.exists(professor_dir):
        logger.error(f"Professor directory '{professor_dir}' does not exist.")
        return

    data_file = os.path.join(professor_dir, 'professor_data.json')
    if not os.path.exists(data_file):
        logger.error(f"Professor data file '{data_file}' does not exist.")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        professor_data = json.load(f)

    articles = []

    # Process 'scholarly' data
    try:
        scholarly_data = professor_data.get('scholarly', {})
        publications = scholarly_data.get('publications', [])
        for pub in publications:
            article = extract_article_from_scholarly(pub, professor_name, logger)
            if article:
                articles.append(article)
        logger.info(f"Processed scholarly data for {professor_name}")
    except Exception as e:
        logger.exception(f"Error processing scholarly data for {professor_name}: {e}")

    # Process 'entrez' data
    try:
        entrez_data = professor_data.get('entrez', [])
        for pub in entrez_data:
            article = extract_article_from_entrez(pub, professor_name, logger)
            if article:
                articles.append(article)
        logger.info(f"Processed Entrez data for {professor_name}")
    except Exception as e:
        logger.exception(f"Error processing Entrez data for {professor_name}: {e}")

    # Process 'crossref' data
    try:
        crossref_data = professor_data.get('crossref', [])
        for pub in crossref_data:
            article = extract_article_from_crossref(pub, professor_name, logger)
            if article:
                articles.append(article)
        logger.info(f"Processed Crossref data for {professor_name}")
    except Exception as e:
        logger.exception(f"Error processing Crossref data for {professor_name}: {e}")

    # Process 'orcid' data
    try:
        orcid_data = professor_data.get('orcid', {})
        works = orcid_data.get('activities-summary', {}).get('works', {}).get('group', [])
        for work_group in works:
            work_summaries = work_group.get('work-summary', [])
            for work_summary in work_summaries:
                article = extract_article_from_orcid(work_summary, professor_name, logger)
                if article:
                    articles.append(article)
        logger.info(f"Processed ORCID data for {professor_name}")
    except Exception as e:
        logger.exception(f"Error processing ORCID data for {professor_name}: {e}")

    # Remove duplicates
    articles_unique = {article['title']: article for article in articles}.values()

    # **Modified Filtering Criteria**
    # Include articles from the last 5 years (or more recent)
    current_year = datetime.now().year
    min_year = current_year - 5  # Last 5 years
    articles_filtered = [article for article in articles_unique if (article['year'] >= min_year) or (article['year'] == 0)]

    # If no articles are found, include the most recent articles regardless of year
    if not articles_filtered:
        articles_filtered = list(articles_unique)

    # Sort articles
    articles_sorted = sort_articles(articles_filtered, professor_name)

    # Save the filtered data to a JSON file
    filtered_data = {
        'articles': articles_sorted
    }

    data_filtered_file = os.path.join(professor_dir, 'professor_data_filtered.json')
    with open(data_filtered_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=4)
    logger.info(f"Filtered data saved to {data_filtered_file}")

def extract_article_from_scholarly(pub, professor_name, logger):
    try:
        title = pub.get('bib', {}).get('title', '').strip()
        authors_raw = pub.get('bib', {}).get('author', '')
        authors = [author.strip() for author in re.split(r' and |,', authors_raw) if author.strip()]
        pub_year_str = pub.get('bib', {}).get('pub_year', '').strip()

        # Handle missing or invalid publication year
        year = parse_year(pub_year_str, logger, title)

        abstract = pub.get('bib', {}).get('abstract', '').strip()
        first_author = authors[0] if authors else ''
        corresponding_author = authors[-1] if authors else ''

        # Allow articles even if professor's name is not matched in authors
        # professor_in_authors = is_professor_in_authors(professor_name, authors)
        # if not professor_in_authors:
        #     logger.debug(f"Professor '{professor_name}' not in authors for article '{title}'. Including anyway.")

        article = {
            'title': title,
            'authors': authors,
            'year': year,
            'abstract': abstract,
            'source': 'scholarly',
            'first_author': first_author,
            'corresponding_author': corresponding_author,
            'professor_is_first_author': is_name_match(professor_name, first_author),
            'professor_is_corresponding_author': is_name_match(professor_name, corresponding_author),
        }
        return article
    except Exception as e:
        logger.exception(f"Error extracting article from scholarly: {e}")
        return None

def extract_article_from_entrez(pub, professor_name, logger):
    # Implemented as needed, similar to the other extraction functions
    return None  # Placeholder

def extract_article_from_crossref(pub, professor_name, logger):
    try:
        title = pub.get('title', [''])[0].strip()
        authors_list = pub.get('author', [])
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_list]

        # Get publication year from various possible fields
        year = 0
        for date_field in ['published-print', 'published-online', 'issued']:
            if pub.get(date_field):
                date_parts = pub[date_field].get('date-parts', [[0]])
                year_candidate = date_parts[0][0]
                if isinstance(year_candidate, int) and year_candidate > 0:
                    year = year_candidate
                    break

        # If year is still zero, attempt to parse from 'created' field
        if year == 0 and pub.get('created'):
            date_parts = pub['created'].get('date-parts', [[0]])
            year_candidate = date_parts[0][0]
            if isinstance(year_candidate, int) and year_candidate > 0:
                year = year_candidate

        # Handle missing or invalid publication year
        if year == 0:
            logger.warning(f"No valid publication year for article '{title}'. Setting year to 0.")
            year = 0

        abstract = pub.get('abstract', '').strip()
        first_author = authors[0] if authors else ''
        corresponding_author = authors[-1] if authors else ''

        # Allow articles even if professor's name is not matched in authors
        # professor_in_authors = is_professor_in_authors(professor_name, authors)
        # if not professor_in_authors:
        #     logger.debug(f"Professor '{professor_name}' not in authors for article '{title}'. Including anyway.")

        article = {
            'title': title,
            'authors': authors,
            'year': year,
            'abstract': abstract,
            'source': 'crossref',
            'first_author': first_author,
            'corresponding_author': corresponding_author,
            'professor_is_first_author': is_name_match(professor_name, first_author),
            'professor_is_corresponding_author': is_name_match(professor_name, corresponding_author),
        }
        return article
    except Exception as e:
        logger.exception(f"Error extracting article from Crossref: {e}")
        return None

def extract_article_from_orcid(work_summary, professor_name, logger):
    try:
        title = work_summary.get('title', {}).get('title', {}).get('value', '').strip()
        # ORCID doesn't provide authors in the summary; assume the professor is an author
        pub_year_str = work_summary.get('publication-date', {}).get('year', {}).get('value', '').strip()

        # Handle missing or invalid publication year
        year = parse_year(pub_year_str, logger, title)

        abstract = ''  # ORCID summary may not include abstract
        authors = [professor_name]  # Assume only the professor is known
        first_author = professor_name
        corresponding_author = professor_name

        article = {
            'title': title,
            'authors': authors,
            'year': year,
            'abstract': abstract,
            'source': 'orcid',
            'first_author': first_author,
            'corresponding_author': corresponding_author,
            'professor_is_first_author': True,  # Assume true in absence of data
            'professor_is_corresponding_author': True,  # Assume true in absence of data
        }
        return article
    except Exception as e:
        logger.exception(f"Error extracting article from ORCID: {e}")
        return None

def sort_articles(articles, professor_name):
    # Sort articles by year descending
    articles_sorted = sorted(articles, key=lambda x: x['year'], reverse=True)
    return articles_sorted

def is_professor_in_authors(professor_name, authors):
    for author in authors:
        if is_name_match(professor_name, author):
            return True
    return False

def is_name_match(professor_name, author_name):
    # Normalize names by removing accents and converting to lowercase
    professor_name_norm = unidecode.unidecode(professor_name.lower())
    author_name_norm = unidecode.unidecode(author_name.lower())

    # Remove punctuation and extra whitespace
    professor_name_norm = re.sub(r'[^\w\s]', '', professor_name_norm).strip()
    author_name_norm = re.sub(r'[^\w\s]', '', author_name_norm).strip()

    # Split names into parts
    professor_name_parts = professor_name_norm.split()
    author_name_parts = author_name_norm.split()

    # Match based on last names
    if len(professor_name_parts) >= 1 and len(author_name_parts) >= 1:
        prof_last = professor_name_parts[-1]
        auth_last = author_name_parts[-1]
        if prof_last == auth_last:
            return True

    # Exact match
    if professor_name_norm == author_name_norm:
        return True

    return False

def parse_year(year_str, logger, title):
    # Attempt to parse the year from the string
    year = 0
    if year_str:
        try:
            # Remove non-digit characters
            year_digits = re.findall(r'\d{4}', year_str)
            if year_digits:
                year = int(year_digits[0])
            else:
                logger.warning(f"Year not found in '{year_str}' for article '{title}'. Setting year to 0.")
        except ValueError:
            logger.warning(f"Invalid publication year '{year_str}' for article '{title}'. Setting year to 0.")
    else:
        logger.warning(f"No publication year provided for article '{title}'. Setting year to 0.")
    return year
