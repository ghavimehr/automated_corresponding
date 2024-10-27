# **Academic Outreach Automation Tool**

This project is a Python-based automation tool designed to streamline the outreach process for academic applications. The tool gathers, processes, and customizes content for professors based on publicly available data from various sources, then generates personalized emails and application materials tailored to the professor’s research focus and interests.

## **Table of Contents**
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Acknowledgments](#acknowledgments)

---

## **Features**
1. **Automated Data Gathering**:
   - Collects data from online sources including Google Scholar, PubMed, and ORCID, and captures both main and supplementary URLs for each professor.

2. **Content Extraction**:
   - Extracts and processes pure text content from HTML and PDF files while excluding irrelevant elements like headers, footers, and sidebars.

3. **Summarization**:
   - Summarizes extracted content using OpenAI’s API, focusing on recent research topics and skills relevant to the professor's lab.

4. **Customized Templates**:
   - Generates personalized email and CV content based on extracted notes and academic data.

5. **Automated Email Sending**:
   - Composes and sends personalized emails to professors using SMTP settings from a database.

---

## **Installation**

### **Prerequisites**
- Python 3.8+
- Recommended package manager: `pip`
- API keys for SerpAPI, ORCID, and OpenAI
- SMTP credentials for email accounts

### **Setup**
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Ehsangha/Automated_Corresponding.git
   cd academic-outreach-automation
   ```

2. **Install Required Libraries**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**: Set up the configuration file `config.py` as described below.

---

## **Usage**

### **Step 1: Configure Database and Settings**
Make sure the `config.py` file is properly set with your API keys, SMTP settings, and project settings. Additionally, initialize your SQLite database to store professor data and email logs.

### **Step 2: Run the Main Script**
To run the main application, use:
```bash
python main.py
```
### **Step 3: Review Generated Output**
- **Emails** and **CVs** for each professor are saved in the `data/{professor_name}` directories.
- Logs are created to track actions, errors, and data-gathering progress.

---

## **Configuration**

### **Configuration File (`config.py`)**

#### **Sample Configuration**
```python
# API keys
SERPAPI_API_KEY = 'your-serpapi-key'
OPENAI_API_KEY = 'your-openai-key'
ORCID_CLIENT_ID = 'your-orcid-client-id'
ORCID_CLIENT_SECRET = 'your-orcid-client-secret'
ENTREZ_EMAIL = 'your-entrez-email@example.com'

# Database and Project Settings
DB_FILE = 'database.db'
PROJECT_DIRECTORY = '/path/to/project/directory'
TABLE_NAME = 'professors'
SEARCH_DEPTH = 2
SEARCH_STYLE = 1  # 1 for BFS, 2 for DFS

# SMTP Settings
SENDING_METHOD = 'SMTP'
REMINDER_INTERVAL_1 = 7
REMINDER_INTERVAL_2 = 14
REMINDER_INTERVAL_3 = 30
TEST_RUN = False  # Set to True to send emails to TEST_EMAIL
TEST_EMAIL = 'test-email@example.com'
```

---

## **Project Structure**

```
├── config.py                 # Configuration file with API keys and settings
├── main.py                   # Main script to run the automation tool
├── data_gathering.py         # Module for gathering data from online sources
├── data_filtering.py         # Module for filtering and refining gathered data
├── modifier.py               # Module for generating templates and modifying content
├── send_email.py             # Module for sending emails using SMTP
├── templates/
│   └── template.html         # HTML template for personalized emails
├── requirements.txt          # Required Python libraries
└── README.md                 # Project documentation
```

---

## **Acknowledgments**

This project’s development has been assisted by **ChatGPT-o1-preview** (OpenAI), which supported the production of script modifications, code optimizations, and solution troubleshooting.

For any issues or questions, please feel free to open an issue on GitHub or contact the project maintainer.

