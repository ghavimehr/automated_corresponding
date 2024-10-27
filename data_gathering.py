# data_gathering.py

import os
import sqlite3
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
import json
import time
import random
from config import (
    SEARCH_DEPTH,
    SEARCH_STYLE,
    SERPAPI_API_KEY,
    ENTREZ_EMAIL,
    ORCID_CLIENT_ID,
    ORCID_CLIENT_SECRET
)
import datetime

# Import the libraries
from scholarly import scholarly
from serpapi import GoogleSearch
from Bio import Entrez
from habanero import Crossref

def main(db_file, table_name, project_directory, search_depth, professor_id=None):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Define supplementary columns
    supplementary_columns = [f"Supplementary{i}" for i in range(1, 11)]
    columns = ["ID", "Professor", "Webpage"] + supplementary_columns
    columns_str = ", ".join([f'"{col}"' for col in columns])

    # Fetch professor details
    if professor_id:
        cursor.execute(f"""
            SELECT {columns_str}
            FROM "{table_name}"
            WHERE "ID" = ?
        """, (professor_id,))
        professors = cursor.fetchall()
    else:
        cursor.execute(f"""
            SELECT {columns_str}
            FROM "{table_name}"
        """)
        professors = cursor.fetchall()

    for professor in professors:
        prof_data = dict(zip(columns, professor))
        prof_id = prof_data["ID"]
        professor_name = prof_data["Professor"]
        webpage_url = prof_data["Webpage"]
        supplementary_urls = [prof_data[f"Supplementary{i}"] for i in range(1, 11)]

        print(f"Gathering data for Professor ID {prof_id}: {professor_name}")

        # Create a directory for the professor
        safe_professor_name = ''.join(c if c.isalnum() else '_' for c in professor_name)
        professor_dir = os.path.join(project_directory, 'data', safe_professor_name)
        os.makedirs(professor_dir, exist_ok=True)

        # Initialize data dictionary
        professor_data = {
            'scholarly': {},
            'serpapi': {},
            'entrez': {},
            'crossref': {},
            'orcid': {}
        }

        saved_pages = set()  # To keep track of saved URLs

        # Fetch and save the professor's main webpage
    if webpage_url:
        try:
            response = requests.get(webpage_url)
            response.raise_for_status()
            main_page_content = response.text

            # Save the main page content with a consistent filename
            main_page_file = os.path.join(professor_dir, 'main_page.html')
            with open(main_page_file, 'w', encoding='utf-8') as f:
                f.write(main_page_content)
            print(f"Saved main webpage for {professor_name}")

            # Add the URL to saved_pages to avoid duplicates
            saved_pages.add(webpage_url)

            # Determine search style
            if SEARCH_STYLE == 1:
                # Breadth-First Search
                fetch_links_bfs(webpage_url, professor_dir, search_depth, saved_pages)
            elif SEARCH_STYLE == 2:
                # Depth-First Search
                fetch_links_dfs(webpage_url, professor_dir, search_depth, saved_pages)
            else:
                print(f"Invalid SEARCH_STYLE: {SEARCH_STYLE}")
        except requests.RequestException as e:
            print(f"Failed to fetch webpage for {professor_name}: {e}")
    else:
        print(f"No webpage URL provided for {professor_name}")

        # Download supplementary URLs
        for idx, url in enumerate(supplementary_urls, start=1):
            if url and url.strip():
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '').lower()

                    if 'application/pdf' in content_type:
                        # It's a PDF file
                        content = response.content
                        filename = f"supplementary{idx}.pdf"
                        filepath = os.path.join(professor_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        print(f"Saved supplementary PDF {idx}: {url}")
                    else:
                        # Assume it's an HTML page
                        content = response.text
                        filename = f"supplementary{idx}.html"
                        filepath = os.path.join(professor_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Saved supplementary page {idx}: {url}")
                except requests.RequestException as e:
                    print(f"Failed to fetch supplementary URL {url}: {e}")

        # Add a small delay to avoid overwhelming servers
        time.sleep(random.uniform(1, 3))

        # Gather additional data using the libraries
        try:
            # 1. Use scholarly to get author profile and publications
            search_query = scholarly.search_author(professor_name)
            author = next(search_query, None)
            if author and author['name'].lower() == professor_name.lower():
                author = scholarly.fill(author)
                professor_data['scholarly'] = author
                print(f"Retrieved scholarly data for {professor_name}")
            else:
                print(f"No exact match found in scholarly data for {professor_name}")
        except Exception as e:
            print(f"Error fetching scholarly data for {professor_name}: {e}")

        try:
            # 2. Use serpapi to perform a Google search
            params = {
                "api_key": SERPAPI_API_KEY,
                "engine": "google",
                "q": professor_name,
                "location": "United States"
            }
            search = GoogleSearch(params)
            results = search.get_dict()
            professor_data['serpapi'] = results
            print(f"Retrieved serpapi data for {professor_name}")
        except Exception as e:
            print(f"Error fetching serpapi data for {professor_name}: {e}")

        try:
            # 3. Use Entrez to search for publications in PubMed
            Entrez.email = ENTREZ_EMAIL  # Required by NCBI
            handle = Entrez.esearch(db="pubmed", term=f'"{professor_name}"[Author]', retmax=5)
            record = Entrez.read(handle)
            id_list = record["IdList"]
            publications = []
            for pubmed_id in id_list:
                handle = Entrez.efetch(db="pubmed", id=pubmed_id, rettype="abstract", retmode="text")
                abstract = handle.read()
                publications.append({'pubmed_id': pubmed_id, 'abstract': abstract})
            professor_data['entrez'] = publications
            print(f"Retrieved PubMed data for {professor_name}")
        except Exception as e:
            print(f"Error fetching Entrez data for {professor_name}: {e}")

        try:
            # 4. Use Crossref to search for publications
            cr = Crossref()
            works = cr.works(query_author=professor_name, limit=5)
            # Filter results to include only exact author name matches
            exact_works = []
            for item in works['message']['items']:
                authors = item.get('author', [])
                for author in authors:
                    author_name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                    if author_name.lower() == professor_name.lower():
                        exact_works.append(item)
                        break
            professor_data['crossref'] = exact_works
            print(f"Retrieved Crossref data for {professor_name}")
        except Exception as e:
            print(f"Error fetching Crossref data for {professor_name}: {e}")

        try:
            # 5. Use ORCID to fetch author data
            orcid_data = fetch_orcid_data(professor_name)
            if orcid_data:
                professor_data['orcid'] = orcid_data
                print(f"Retrieved ORCID data for {professor_name}")
            else:
                print(f"No ORCID data found for {professor_name}")
        except Exception as e:
            print(f"Error fetching ORCID data for {professor_name}: {e}")

        # Save the collected data to a JSON file
        data_file = os.path.join(professor_dir, 'professor_data.json')
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(professor_data, f, indent=4)
        print(f"Saved professor data to {data_file}")

    conn.close()


def fetch_orcid_data(professor_name):
    # ORCID API endpoint for searching
    search_url = 'https://pub.orcid.org/v3.0/search/'

    headers = {
        'Accept': 'application/json'
    }

    # Query to search for the exact name
    query = f'(given-names:"{professor_name}" OR family-name:"{professor_name}")'

    params = {
        'q': query
    }

    response = requests.get(search_url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        if 'result' in data:
            for item in data['result']:
                orcid_id = item['orcid-identifier']['path']
                # Fetch detailed profile data
                profile_url = f'https://pub.orcid.org/v3.0/{orcid_id}/record'
                profile_response = requests.get(profile_url, headers=headers)
                if profile_response.status_code == 200:
                    profile_data = profile_response.json()
                    # Verify exact name match
                    personal_details = profile_data.get('person', {}).get('name', {})
                    given_names = personal_details.get('given-names', {}).get('value', '').lower()
                    family_name = personal_details.get('family-name', {}).get('value', '').lower()
                    full_name = f"{given_names} {family_name}".strip()
                    if full_name == professor_name.lower():
                        return profile_data
        else:
            return None
    else:
        print(f"ORCID API request failed with status code {response.status_code}")
        return None

def fetch_links_bfs(base_url, professor_dir, max_depth, saved_pages):
    visited = set()
    queue = [(base_url, 0)]

    while queue:
        current_url, depth = queue.pop(0)
        if depth > max_depth or current_url in visited or current_url in saved_pages:
            continue

        visited.add(current_url)
        try:
            response = requests.get(current_url)
            response.raise_for_status()
            content = response.text

            # Save the page content
            filename = get_safe_filename(current_url)
            filepath = os.path.join(professor_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved page: {current_url}")

            # Add the URL to saved_pages to avoid duplicates
            saved_pages.add(current_url)

            if depth < max_depth:
                soup = BeautifulSoup(content, 'html.parser')
                links = soup.find_all('a', href=True)

                for link in links:
                    href = link['href']
                    href = urljoin(current_url, href)
                    parsed_href = urlparse(href)

                    # Check if the link is on the same domain
                    if parsed_href.netloc != urlparse(base_url).netloc:
                        continue

                    if href not in visited and href not in saved_pages:
                        queue.append((href, depth + 1))

            # Add a small delay
            time.sleep(random.uniform(0.5, 1.5))
        except requests.RequestException as e:
            print(f"Failed to fetch link {current_url}: {e}")

def fetch_links_dfs(base_url, professor_dir, max_depth, saved_pages, visited=None, depth=0):
    if depth > max_depth:
        return
    if visited is None:
        visited = set()

    if base_url in visited or base_url in saved_pages:
        return

    visited.add(base_url)
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        content = response.text

        # Save the page content
        filename = get_safe_filename(base_url)
        filepath = os.path.join(professor_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Saved page: {base_url}")

        # Add the URL to saved_pages to avoid duplicates
        saved_pages.add(base_url)

        if depth < max_depth:
            soup = BeautifulSoup(content, 'html.parser')
            links = soup.find_all('a', href=True)

            for link in links:
                href = link['href']
                href = urljoin(base_url, href)
                parsed_href = urlparse(href)

                # Check if the link is on the same domain
                if parsed_href.netloc != urlparse(base_url).netloc:
                    continue

                if href not in visited and href not in saved_pages:
                    fetch_links_dfs(href, professor_dir, max_depth, saved_pages, visited, depth + 1)

        # Add a small delay
        time.sleep(random.uniform(0.5, 1.5))
    except requests.RequestException as e:
        print(f"Failed to fetch link {base_url}: {e}")

def get_safe_filename(url):
    # Create a safe filename from the URL
    parsed_url = urlparse(url)
    path = parsed_url.path.strip('/')
    if not path:
        path = 'index'
    safe_path = re.sub(r'[^a-zA-Z0-9_\-]', '_', path)
    filename = f"{safe_path}.html"
    return filename
