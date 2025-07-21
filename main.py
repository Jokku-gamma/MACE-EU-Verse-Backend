import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
from github import Github, InputGitTreeElement, UnknownObjectException
from dotenv import load_dotenv
from flask_cors import CORS
from bs4 import BeautifulSoup

# Load environment variables from .env for local development
load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes by default

# --- GitHub Configuration ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")
GITHUB_FILE_PATH_PREFIX = "daily-verses"

# Initialize GitHub API client
g = None
repo = None
if GITHUB_TOKEN and GITHUB_REPO_OWNER and GITHUB_REPO_NAME:
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user(GITHUB_REPO_OWNER).get_repo(GITHUB_REPO_NAME)
        print(f"Successfully connected to GitHub repo: {repo.full_name}")
    except Exception as e:
        print(f"Error connecting to GitHub repository during initialization: {e}")
        print("Please ensure GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME are set correctly and the token has 'repo' scope.")
else:
    print("GitHub API client not initialized due to missing environment variables.")

# Regex to extract date from filename like 'bible_verse_YYYY-MM-DD.html'
FILE_DATE_PATTERN = re.compile(r"bible_verse_(\d{4}-\d{2}-\d{2})\.html")

# --- HTML Template (Your existing template) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Bible Verse from MACE EU - {display_date}</title>
    <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
    <style>
        /* Base Styling & Variables */
        :root {{
            font-size: 16px; /* Base for rem units */
            --primary-green: #4CAF50;
            --dark-green: #28a745;
            --light-gray-bg: #f0f4f8;
            --card-bg: #ffffff;
            --text-dark: #333;
            --text-medium: #555;
            --text-light: #777;
            --shadow-subtle: rgba(0, 0, 0, 0.1);
            --shadow-strong: rgba(0, 0, 0, 0.15);
        }}

        body {{
            margin: 0;
            padding: 0;
            font-family: 'Open Sans', sans-serif;
            background-color: var(--light-gray-bg);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
            line-height: 1.6;
            color: var(--text-dark);
            overflow-x: hidden; /* Prevent horizontal scroll */
        }}

        /* Main Container Card */
        .verse-card-container {{
            background: var(--card-bg);
            border-radius: 20px; /* Rounded corners for the card */
            box-shadow: 0 10px 30px var(--shadow-subtle); /* Soft shadow */
            max-width: 650px;
            width: 90%; /* Responsive width */
            padding: 2.5rem; /* 40px */
            text-align: center;
            position: relative;
            overflow: hidden;
            animation: fadeInScale 1s ease-out forwards; /* Initial animation */
            margin: 20px 0; /* Margin for spacing on small screens */
            border: 1px solid #eee; /* Subtle border */
        }}

        /* Header Section for the Page */
        .verse-card-header {{
            margin-bottom: 2rem; /* 32px */
            position: relative;
            z-index: 1; /* Ensure header is above any background graphics */
        }}

        .verse-card-header h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 2.8rem; /* Large heading for prominence */
            color: var(--primary-green);
            margin-bottom: 0.5rem; /* 8px */
            text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.05);
            line-height: 1.2;
        }}

        .verse-card-header p.date {{
            font-size: 1.1rem; /* Date text */
            color: var(--text-medium);
            margin-top: 0;
            opacity: 0.8;
        }}

        /* Bible Verse Section */
        .bible-verse-block {{
            background-color: #f7fcf7; /* Lighter background for verse */
            border-left: 6px solid var(--dark-green); /* Accent bar */
            border-radius: 12px;
            padding: 1.875rem; /* 30px */
            margin: 2rem auto; /* 32px */
            max-width: 90%; /* Constraint within card */
            box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.05); /* Inner shadow */
            text-align: left;
            position: relative;
            z-index: 1;
        }}

        .bible-verse-block blockquote {{
            font-family: 'Playfair Display', serif; /* Elegant font for the verse */
            font-size: 1.4rem; /* Prominent verse text */
            font-style: italic;
            color: var(--text-dark);
            margin: 0;
            padding: 0;
            quotes: "“" "”" "‘" "’"; /* Custom quotes */
            position: relative;
            padding-left: 1.5rem; /* Space for large quote mark */
        }}
        .bible-verse-block blockquote::before {{
            content: "“";
            font-size: 4em; /* Large opening quote */
            color: rgba(40, 167, 69, 0.2); /* Semi-transparent green */
            position: absolute;
            left: 0;
            top: -0.5em; /* Adjust position */
            line-height: 1;
            font-family: serif; /* Ensure it's a clear quote mark */
        }}

        .bible-verse-block cite {{
            display: block;
            margin-top: 1rem; /* 16px */
            font-size: 0.95rem;
            color: var(--text-light);
            text-align: right;
            font-style: normal; /* Override italic from blockquote */
        }}

        /* Message/Reflection Section */
        .message-section {{
            margin-top: 2rem; /* 32px */
            padding: 0 1rem; /* Some internal padding */
            text-align: left;
            position: relative;
            z-index: 1;
        }}

        .message-section h3 {{
            font-family: 'Playfair Display', serif;
            font-size: 1.6rem; /* Sub-heading for message */
            color: var(--dark-green);
            margin-bottom: 1rem; /* 16px */
            position: relative;
            padding-bottom: 0.5rem;
        }}

        .message-section h3::after {{ /* Small underline for message heading */
            content: '';
            display: block;
            width: 4rem; /* 64px */
            height: 3px;
            background-color: var(--primary-green);
            margin-top: 0.5rem;
            border-radius: 2px;
        }}

        .message-section p {{
            font-size: 1rem;
            color: var(--text-medium);
            line-height: 1.7;
            margin-bottom: 1rem;
        }}

        /* Sender Info Footer */
        .sender-info {{
            margin-top: 3rem; /* 48px */
            font-size: 0.9rem;
            color: var(--text-light);
            line-height: 1.5;
            text-align: center;
            position: relative;
            z-index: 1;
            padding-top: 1rem;
            border-top: 1px dashed #e0e0e0; /* Subtle separator */
        }}

        .sender-info strong {{
            color: var(--text-dark);
        }}

        /* Animations */
        @keyframes fadeInScale {{
            from {{ opacity: 0; transform: scale(0.95); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}

        /* Responsive Adjustments (using rem for scaling) */
        @media (max-width: 650px) {{
            :root {{
                font-size: 15px; /* Slightly reduce base font size */
            }}
            .verse-card-container {{
                padding: 1.5rem; /* 24px */
                border-radius: 0; /* Remove border-radius on small screens */
                width: 100%;
                box-shadow: none; /* Remove shadow for full-width look */
                margin: 0; /* No margin needed */
            }}
            body {{
                align-items: flex-start; /* Align to top on small screens */
                min-height: auto; /* Remove min-height to prevent empty space */
            }}
            .verse-card-header h1 {{
                font-size: 2rem; /* Smaller heading */
            }}
            .verse-card-header p.date {{
                font-size: 0.9rem;
            }}
            .bible-verse-block {{
                padding: 1.25rem; /* 20px */
                margin: 1.5rem auto; /* 24px */
            }}
            .bible-verse-block blockquote {{
                font-size: 1.2rem;
            }}
            .bible-verse-block blockquote::before {{
                font-size: 3em;
                top: -0.2em;
            }}
            .message-section h3 {{
                font-size: 1.3rem;
            }}
            .message-section p {{
                font-size: 0.95rem;
            }}
            .sender-info {{
                margin-top: 2rem; /* 32px */
            }}
        }}

        @media (max-width: 450px) {{
            :root {{
                font-size: 14px; /* Further reduce base font size */
            }}
            .verse-card-container {{
                padding: 1rem; /* 16px */
            }}
            .verse-card-header h1 {{
                font-size: 1.8rem;
            }}
            .verse-card-header p.date {{
                font-size: 0.85rem;
            }}
            .bible-verse-block {{
                padding: 1rem; /* 16px */
                margin: 1rem auto; /* 16px */
            }}
            .bible-verse-block blockquote {{
                font-size: 1.1rem;
            }}
            .bible-verse-block blockquote::before {{
                font-size: 2.5em;
                top: -0.1em;
            }}
            .message-section h3 {{
                font-size: 1.1rem;
            }}
            .message-section p {{
                font-size: 0.875rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="verse-card-container">
        <div class="verse-card-header">
            <h1>Your Daily Bible Verse!</h1>
            <p class="date">{display_date}</p>
        </div>

        <div class="bible-verse-block">
            <blockquote>
                {malayalam_verse}
            </blockquote>
            <cite>—{malayalam_ref}</cite>
            <blockquote>
                "{english_verse}"
            </blockquote>
            <cite>— {english_ref}</cite>
        </div>

        <div class="message-section">
            <h3>{message_title}:</h3>
            <p>
                {message_paragraph1}
            </p>
            <p>
                {message_paragraph2}
            </p>
        </div>

        <div class="sender-info">
            Blessings,<br>
            The Team at <strong>MACE Evangelical Union</strong><br>
            <a href="https://jokku-gamma.github.io/MACE-EU/" style="color: #4CAF50; text-decoration: none;">Visit our Website</a>
        </div>
    </div>
</body>
</html>
"""

# --- Flask Route for generating and uploading verse ---
@app.route('/generate_and_upload_verse', methods=['POST'])
def generate_and_upload_verse():
    if repo is None:
        return jsonify({"success": False, "message": "Backend not connected to GitHub repository. Check environment variables."}), 500

    data = request.get_json()

    manual_date_str = data.get('date')
    malayalam_verse = data.get('malayalam_verse')
    malayalam_ref = data.get('malayalam_ref')
    english_verse = data.get('english_verse')
    english_ref = data.get('english_ref')
    message_title = data.get('message_title')
    message_paragraph1 = data.get('message_paragraph1')
    message_paragraph2 = data.get('message_paragraph2')

    if not all([manual_date_str, malayalam_verse, malayalam_ref, english_verse,
                english_ref, message_title, message_paragraph1, message_paragraph2]):
        return jsonify({"success": False, "message": "Missing required fields in request data."}), 400

    try:
        date_obj = datetime.strptime(manual_date_str, "%B %d, %Y")
    except ValueError:
        return jsonify({"success": False, "message": f"Invalid date format: {manual_date_str}. Expected 'Month DD, YYYY'."}), 400

    display_date = date_obj.strftime("%B %d, %Y")
    file_date_format = date_obj.strftime("%Y-%m-%d")
    github_file_path = f"{GITHUB_FILE_PATH_PREFIX}/bible_verse_{file_date_format}.html"

    try:
        # --- Duplicate Prevention Logic ---
        try:
            repo.get_contents(github_file_path, ref="main")
            return jsonify({
                "success": False,
                "message": f"A daily verse for {display_date} already exists. Please choose another date."
            }), 409
        except UnknownObjectException:
            pass
        except Exception as e:
            print(f"GitHub API Error checking file existence: {e}")
            raise e

        html_content = HTML_TEMPLATE.format(
            display_date=display_date,
            malayalam_verse=malayalam_verse,
            malayalam_ref=malayalam_ref,
            english_verse=english_verse,
            english_ref=english_ref,
            message_title=message_title,
            message_paragraph1=message_paragraph1,
            message_paragraph2=message_paragraph2
        )

        repo.create_file(
            path=github_file_path,
            message=f"Add daily verse for {display_date} via API",
            content=html_content,
            branch="main"
        )
        print(f"Successfully created file: {github_file_path} in {repo.full_name}")
        return jsonify({
            "success": True,
            "message": f"Verse for {display_date} successfully created and pushed to GitHub."
        }), 200

    except Exception as e:
        print(f"GitHub API Error: {e}")
        return jsonify({"success": False, "message": f"Failed to push to GitHub: {str(e)}"}), 500

# --- NEW ENDPOINT: Get existing verse dates ---
@app.route('/get_existing_verse_dates', methods=['GET'])
def get_existing_verse_dates():
    if repo is None:
        return jsonify({"success": False, "message": "Backend not connected to GitHub repository. Check environment variables."}), 500

    existing_dates = []
    try:
        contents = repo.get_contents(GITHUB_FILE_PATH_PREFIX, ref="main")
        for content in contents:
            if content.type == 'file' and content.name.endswith('.html'):
                match = FILE_DATE_PATTERN.match(content.name)
                if match:
                    iso_date = match.group(1)
                    try:
                        formatted_date = datetime.strptime(iso_date, "%Y-%m-%d").strftime("%B %d, %Y")
                        existing_dates.append(formatted_date)
                    except ValueError:
                        print(f"Warning: Could not parse date from filename: {content.name}")
        return jsonify({"success": True, "dates": existing_dates}), 200

    except UnknownObjectException:
        return jsonify({"success": True, "dates": []}), 200
    except Exception as e:
        print(f"GitHub API Error when fetching existing dates: {e}")
        return jsonify({"success": False, "message": f"Failed to fetch existing dates from GitHub: {str(e)}"}), 500

# --- NEW ENDPOINT: Get verse content by date ---
@app.route('/get_verse_content_by_date', methods=['GET'])
def get_verse_content_by_date():
    if repo is None:
        return jsonify({"success": False, "message": "Backend not connected to GitHub repository. Check environment variables."}), 500

    date_str_frontend = request.args.get('date')
    if not date_str_frontend:
        return jsonify({"success": False, "message": "Date parameter is required"}), 400

    try:
        date_obj = datetime.strptime(date_str_frontend, "%B %d, %Y")
        file_date_format = date_obj.strftime("%Y-%m-%d")
        github_file_path = f"{GITHUB_FILE_PATH_PREFIX}/bible_verse_{file_date_format}.html"
    except ValueError:
        return jsonify({"success": False, "message": f"Invalid date format: {date_str_frontend}. Expected 'Month DD, YYYY'."}), 400

    try:
        file_content_obj = repo.get_contents(github_file_path, ref="main")
        html_content = file_content_obj.decoded_content.decode('utf-8')

        soup = BeautifulSoup(html_content, 'html.parser')

        malayalam_verse_elem = soup.find('div', class_='bible-verse-block').find_all('blockquote')[0]
        malayalam_verse = malayalam_verse_elem.get_text(strip=True) if malayalam_verse_elem else ""

        malayalam_ref_elem = soup.find('div', class_='bible-verse-block').find_all('cite')[0]
        malayalam_ref = malayalam_ref_elem.get_text(strip=True).replace('—', '') if malayalam_ref_elem else ""

        english_verse_elem = soup.find('div', class_='bible-verse-block').find_all('blockquote')[1]
        english_verse = english_verse_elem.get_text(strip=True).strip('"') if english_verse_elem else "" # Remove quotes

        english_ref_elem = soup.find('div', class_='bible-verse-block').find_all('cite')[1]
        english_ref = english_ref_elem.get_text(strip=True).replace('—', '') if english_ref_elem else ""

        message_title_elem = soup.find('div', class_='message-section').find('h3')
        message_title = message_title_elem.get_text(strip=True).replace(':', '') if message_title_elem else ""

        paragraphs = soup.find('div', class_='message-section').find_all('p')
        message_paragraph1 = paragraphs[0].get_text(strip=True) if len(paragraphs) > 0 else ""
        message_paragraph2 = paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else ""

        verse_data = {
            "date": date_str_frontend,
            "malayalam_verse": malayalam_verse,
            "malayalam_ref": malayalam_ref,
            "english_verse": english_verse,
            "english_ref": english_ref,
            "message_title": message_title,
            "message_paragraph1": message_paragraph1,
            "message_paragraph2": message_paragraph2,
        }

        return jsonify({"success": True, "verse": verse_data}), 200

    except UnknownObjectException:
        return jsonify({"success": False, "message": f"No verse found for {date_str_frontend}"}), 404
    except Exception as e:
        print(f"Error fetching or parsing verse content for {date_str_frontend}: {e}")
        return jsonify({"success": False, "message": f"Failed to retrieve verse content: {str(e)}"}), 500

# --- NEW ENDPOINT: Get the latest date a verse was added ---
@app.route('/get_latest_verse_date', methods=['GET'])
def get_latest_verse_date():
    if repo is None:
        return jsonify({"success": False, "message": "Backend not connected to GitHub repository. Check environment variables."}), 500

    latest_date_obj = None
    try:
        contents = repo.get_contents(GITHUB_FILE_PATH_PREFIX, ref="main")
        for content in contents:
            if content.type == 'file' and content.name.endswith('.html'):
                match = FILE_DATE_PATTERN.match(content.name)
                if match:
                    iso_date_str = match.group(1)
                    try:
                        current_date_obj = datetime.strptime(iso_date_str, "%Y-%m-%d")
                        if latest_date_obj is None or current_date_obj > latest_date_obj:
                            latest_date_obj = current_date_obj
                    except ValueError:
                        print(f"Warning: Could not parse date from filename: {content.name}")
        
        if latest_date_obj:
            formatted_latest_date = latest_date_obj.strftime("%B %d, %Y")
            return jsonify({"success": True, "latest_date": formatted_latest_date}), 200
        else:
            return jsonify({"success": True, "latest_date": None, "message": "No verses found yet."}), 200

    except UnknownObjectException:
        # Directory does not exist yet, so no verses
        return jsonify({"success": True, "latest_date": None, "message": "No verses found yet."}), 200
    except Exception as e:
        print(f"GitHub API Error when fetching latest date: {e}")
        return jsonify({"success": False, "message": f"Failed to fetch latest verse date: {str(e)}"}), 500


# --- Health Check Endpoint ---
@app.route('/')
def health_check():
    if repo:
        try:
            repo.get_branch("main")
            return jsonify({"status": "MACE EU Verse Generator Backend is running and connected to GitHub."}), 200
        except Exception as e:
            return jsonify({"status": f"MACE EU Verse Generator Backend is running, but GitHub connection failed: {e}"}), 500
    else:
        return jsonify({"status": "MACE EU Verse Generator Backend is running, but GitHub client not initialized (check env vars)."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
