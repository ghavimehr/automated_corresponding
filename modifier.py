# modifier.py

import os
import sys
import json
import subprocess
import openai
from openai import OpenAI
from bs4 import BeautifulSoup
import pdfplumber  # For PDF text extraction
import logging
import sqlite3
import time
from config import OPENAI_API_KEY

# Set OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

def read_simplified_cv(cv_file_path):
    with open(cv_file_path, 'r', encoding='utf-8') as f:
        cv_content = f.read()
    return cv_content

def modify_template(db_file, table_name, project_directory, professor_id, professor_name):
    # Configure logging
    logger = logging.getLogger('modifier')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Remove any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler for logging
    fh = logging.FileHandler('modifier.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Stream handler for console output
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Connect to the database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Fetch professor details
    cursor.execute(f"""
        SELECT "Professor", "University"
        FROM "{table_name}"
        WHERE "ID" = ?
    """, (professor_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"No professor found with ID {professor_id}")
        conn.close()
        return
    professor_name, university = result

    # Close the database connection for now
    conn.close()

    # Define paths
    safe_professor_name = ''.join(c if c.isalnum() else '_' for c in professor_name)
    professor_dir = os.path.join(project_directory, 'data', safe_professor_name)
    data_file = os.path.join(professor_dir, 'professor_data_filtered.json')
    cv_file = os.path.join(project_directory, 'Ehsan_Ghavimehr_CV.tex')  
    cv_simplified_file = os.path.join(project_directory, 'CV_simplified.txt')

    # Ensure the professor directory exists
    if not os.path.exists(professor_dir):
        logger.error(f"Professor directory '{professor_dir}' does not exist.")
        return

    # Read professor_data_filtered.json
    if not os.path.exists(data_file):
        logger.error(f"Filtered data file '{data_file}' does not exist.")
        return
    with open(data_file, 'r', encoding='utf-8') as f:
        professor_data_filtered = json.load(f)

    if not os.path.exists(cv_simplified_file):
        logger.error(f"Simplified CV file '{cv_simplified_file}' does not exist.")
        return
    simplified_cv_content = read_simplified_cv(cv_simplified_file)

    # Step 1: Extract and summarize PDFs
    summarize_pdfs(professor_dir, professor_name, logger)

    # Step 2: Extract and summarize HTMLs
    summarize_htmls(professor_dir, professor_name, logger)

    # Step 3: Combine summarized texts to create 'extracted_notes.txt'
    combined_summaries = combine_summaries(professor_dir, professor_name, logger)

    # Save the combined summaries into 'extracted_notes.txt'
    notes_file = os.path.join(professor_dir, 'extracted_notes.txt')
    with open(notes_file, 'w', encoding='utf-8') as f:
        f.write(combined_summaries)
    logger.info(f"Extracted notes saved to {notes_file}")

    # Step 4: Use 'extracted_notes' and 'professor_data_filtered' as inputs to generate_prompt functions

    # Generate the prompt for personalized paragraph
    prompt_paragraph = generate_prompt_paragraph(
        professor_name, professor_data_filtered, combined_summaries, simplified_cv_content
    )

    # Generate the personalized paragraph
    personalized_paragraph = generate_personalized_paragraph(prompt_paragraph, logger, model='gpt-4')

    # Read the email template
    template_file = os.path.join(project_directory, 'template.html')
    if not os.path.exists(template_file):
        logger.error(f"Template file '{template_file}' does not exist.")
        return
    with open(template_file, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # Replace placeholders
    placeholders = {
        '{{ProfessorName}}': professor_name,
        '{{University}}': university,
        '{{PersonalizedParagraph}}': personalized_paragraph,
    }
    modified_content = template_content
    for placeholder, value in placeholders.items():
        modified_content = modified_content.replace(placeholder, value)

    # Save the modified HTML in the professor's folder
    os.makedirs(professor_dir, exist_ok=True)
    output_file = os.path.join(professor_dir, 'email1.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    logger.info(f"Modified email saved to {output_file}")

    # Generate the prompt for CV keywords
    prompt_keywords = generate_prompt_keywords(
        professor_name, professor_data_filtered, combined_summaries, simplified_cv_content
    )

    # Define the default keywords in case of API failure
    DEFAULT_KEYWORDS = "Emotions in Decision Making & Brain Evo-Devo & Personalized Neuropsychiatry \\\\ Moral and Aesthetic Psychology & Autism & rTMS"

    # Generate the new Research Interest section
    new_research_interest = generate_personalized_paragraph(
        prompt_keywords, logger, max_tokens=250, model='gpt-4', default_value=DEFAULT_KEYWORDS
    )

    # Modify your CV
    modify_cv(cv_file, new_research_interest, professor_dir, logger)

    # Update the database to set html_generation and cv_generation to TRUE
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    chronology_table = f"{table_name}_chronology"
    cursor.execute(f'''
        UPDATE "{chronology_table}"
        SET "html_generation_completed" = TRUE, "cv_generation_completed" = TRUE
        WHERE "ID" = ?
    ''', (professor_id,))
    conn.commit()
    conn.close()

def summarize_pdfs(professor_dir, professor_name, logger):
    # Extract text from PDF files and summarize
    for filename in os.listdir(professor_dir):
        if filename.endswith('.pdf'):
            pdf_filepath = os.path.join(professor_dir, filename)
            txt_filename = f"{filename}.txt"
            txt_filepath = os.path.join(professor_dir, txt_filename)
            summarized_filename = f"{filename}.summarized.txt"
            summarized_filepath = os.path.join(professor_dir, summarized_filename)

            # Extract text from PDF and save as .txt
            try:
                with pdfplumber.open(pdf_filepath) as pdf:
                    text = ''
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + '\n'
                with open(txt_filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                logger.info(f"Extracted text from {filename} and saved to {txt_filename}")
            except Exception as e:
                logger.error(f"Error extracting text from {filename}: {e}")
                continue

            # Summarize the extracted text and save as .summarized.txt
            summarized_text = progressive_summarization(txt_filepath, professor_name, logger)
            with open(summarized_filepath, 'w', encoding='utf-8') as f:
                f.write(summarized_text)
            logger.info(f"Summarized text from {txt_filename} and saved to {summarized_filename}")

def summarize_htmls(professor_dir, professor_name, logger):
    # Extract text from HTML files and save as .txt
    html_texts = []
    for filename in os.listdir(professor_dir):
        if filename.endswith('.html'):
            html_filepath = os.path.join(professor_dir, filename)
            txt_filename = f"{filename}.txt"
            txt_filepath = os.path.join(professor_dir, txt_filename)

            # Extract text from HTML and save as .txt
            try:
                with open(html_filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    # Remove unwanted elements
                    for element in soup(["script", "style", "header", "footer", "nav", "aside", "form", "noscript"]):
                        element.extract()
                    text = soup.get_text(separator=' ', strip=True)
                with open(txt_filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                logger.info(f"Extracted text from {filename} and saved to {txt_filename}")
                html_texts.append(text)
            except Exception as e:
                logger.error(f"Error extracting text from {filename}: {e}")
                continue

    # Combine all HTML texts
    combined_html_text = '\n'.join(html_texts)

    # Summarize the combined HTML text and save as 'html.summarized.txt'
    summarized_text = progressive_summarization_text(combined_html_text, professor_name, logger)
    summarized_filepath = os.path.join(professor_dir, 'html.summarized.txt')
    with open(summarized_filepath, 'w', encoding='utf-8') as f:
        f.write(summarized_text)
    logger.info(f"Summarized HTML texts and saved to html.summarized.txt")

def combine_summaries(professor_dir, professor_name, logger):
    # Collect all *.summarized.txt files
    summarized_texts = []
    for filename in os.listdir(professor_dir):
        if filename.endswith('.summarized.txt'):
            filepath = os.path.join(professor_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                summarized_texts.append(f.read())

    # Combine all summaries
    combined_text = '\n'.join(summarized_texts)

    # Final summarization using API
    final_summary = progressive_summarization_text(combined_text, professor_name, logger)

    return final_summary

def progressive_summarization(file_path, professor_name, logger):
    # Read the text from file and summarize progressively
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Break the text into chunks
    max_chunk_size = 2000  # Adjust based on model's context length
    text_chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]

    summary = ''  # Initialize summary
    for idx, chunk in enumerate(text_chunks):
        prompt = f"""
Please summarize the following text focusing on the recent research focus and current lab research of {professor_name}
write three paragraphs.
What soft and hard skills are needed in {professor_name}'s lab?

Previous Summary:
{summary}

New Text:
{chunk}

Revised Summary:
"""
        role_description = f"You are {professor_name}."
        summary = call_openai_api(prompt, max_tokens=2500, model='gpt-3.5-turbo', role_description=role_description, temperature=0.3, logger=logger)
        if summary is None:
            logger.warning(f"Failed to summarize chunk {idx+1}.")
            continue
        time.sleep(1)  # Add a small delay between API calls

    return summary

def progressive_summarization_text(text, professor_name, logger):
    # Similar to progressive_summarization but works with text instead of file
    # Break the text into chunks
    max_chunk_size = 2000  # Adjust based on model's context length
    text_chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]

    summary = ''  # Initialize summary
    for idx, chunk in enumerate(text_chunks):
        prompt = f"""
Please summarize the following text focusing on the recent research focus and current lab research of {professor_name} 
write three paragraphs.
What soft and hard skills are needed in {professor_name}'s lab?

Previous Summary:
{summary}

New Text:
{chunk}

Revised Summary:
"""
        role_description = f"You are {professor_name}."
        summary = call_openai_api(prompt, max_tokens=2500, model='gpt-3.5-turbo', role_description=role_description, temperature=0.3, logger=logger)
        if summary is None:
            logger.warning(f"Failed to summarize chunk {idx+1}.")
            continue
        time.sleep(1)  # Add a small delay between API calls

    return summary

def generate_prompt_paragraph(professor_name, professor_data_filtered, extracted_notes, simplified_cv_content):
    # Create a concise prompt using the simplified CV content
    # Use 'extracted_notes' and 'professor_data_filtered' as inputs

    articles = professor_data_filtered.get('articles', [])
    articles_text = ''
    for article in articles:
        title = article.get('title', '')
        articles_text += f"Title: {title}\n"

    prompt = f"""
I am {professor_name}. In 3 simple sentences, explain how your skills and background align with my research interests.
Don't exaggerate your skills. Refer to your works and skills and my papers.
Write neutrally and humanized. Mention that you are eager to learn skills you don't yet possess. Keep it very very short.
Don't mention either your name or my name. Don't write either an opening (like Hello) or closing (like sincerely).
Write humanized.

My recent research titles:
{articles_text}

My summarized webpages:
{extracted_notes}

Your CV:
{simplified_cv_content}
"""
    return prompt

def generate_prompt_keywords(professor_name, professor_data_filtered, extracted_notes, simplified_cv_content):
    # Include 'professor_data_filtered' and 'extracted_notes' in the prompt
    articles = professor_data_filtered.get('articles', [])
    articles_text = ''
    for article in articles:
        title = article.get('title', '')
        articles_text += f"Title: {title}\n"

    prompt = f"""
Find 6 overlapping research topics between your background and {professor_name}'s recent research articles.
Keep keywords short.

{professor_name}'s recent research titles:
{articles_text}

Summarized {professor_name}'s webpages:
{extracted_notes}

Your CV:
{simplified_cv_content}

As the output is going to go inside a LaTeX table, separate the 6 research topics like this format:
A & B & C \\\\ D & E & F
(Don't include the capital letters in the output)
Don't explain anything.
If you couldn't find any research interest overlap, please use these:
Emotions in Decision Making & Brain Evo-Devo & Personalized Neuropsychiatry \\\\ Moral and Aesthetic Psychology & Autism & rTMS
"""
    return prompt

def generate_personalized_paragraph(prompt, logger, max_tokens=250, model='gpt-4', default_value=None):
    # Use the OpenAI API to generate the paragraph with retry mechanism
    response_text = call_openai_api(prompt, max_tokens=max_tokens, model=model, role_description="You are Ehsan Ghavimehr, M.D., who is applying for a Ph.D. You write simply and concisely.", temperature=0.7, logger=logger)
    if response_text is None:
        if default_value is not None:
            logger.warning("Failed to generate personalized paragraph after retries. Using default value.")
            return default_value
        else:
            logger.warning("Failed to generate personalized paragraph after retries. Leaving the paragraph empty.")
            return ""
    else:
        return response_text

def call_openai_api(prompt, max_tokens=200, model='gpt-3.5-turbo', role_description="You are an assistant.", temperature=0.5, logger=None):
    retries = 5
    delay = 60  # Start with 60 seconds
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": role_description},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                n=1,
                stop=None,
                temperature=temperature
            )
            generated_text = response.choices[0].message.content.strip()
            return generated_text
        except openai.error.RateLimitError as e:
            if logger:
                logger.warning(f"Rate limit exceeded: {e}. Retrying in {delay} seconds...")
            else:
                print(f"Rate limit exceeded: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        except Exception as e:
            if logger:
                logger.error(f"OpenAI API error: {e}")
            else:
                print(f"OpenAI API error: {e}")
            return None
    if logger:
        logger.error("Failed to get a response from OpenAI API after multiple retries.")
    else:
        print("Failed to get a response from OpenAI API after multiple retries.")
    return None

def modify_cv(cv_file, new_research_interest, professor_dir, logger):
    # Read the CV content
    with open(cv_file, 'r', encoding='utf-8') as f:
        cv_content = f.read()

    # Replace the old Research Interest section with the new one
    start_marker = '%BEGIN_RESEARCH_INTEREST%'
    end_marker = '%END_RESEARCH_INTEREST%'
    if start_marker in cv_content and end_marker in cv_content:
        before = cv_content.split(start_marker)[0] + start_marker + '\n'
        after = '\n' + end_marker + cv_content.split(end_marker)[1]
        cv_content = before + new_research_interest + after
    else:
        logger.warning("Markers for Research Interest section not found in CV.")
        return

    # Save the modified CV in the professor's directory
    modified_cv_file = os.path.join(professor_dir, 'Ehsan_Ghavimehr_CV.tex')
    with open(modified_cv_file, 'w', encoding='utf-8') as f:
        f.write(cv_content)
    logger.info(f"Modified CV saved to {modified_cv_file}")

    # Compile the modified CV using XeLaTeX
    compile_cv(modified_cv_file, logger)

def compile_cv(tex_file, logger):
    # Compile the TeX file using XeLaTeX
    try:
        subprocess.run(['xelatex', '-interaction=nonstopmode', tex_file], cwd=os.path.dirname(tex_file), check=True)
        logger.info(f"Compiled CV saved in {os.path.dirname(tex_file)}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error compiling CV: {e}")
