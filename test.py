import streamlit as st
import pandas as pd
import os
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
from datetime import datetime
from bs4 import BeautifulSoup

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = "token.json"

# List of ATS providers to ignore in domain extraction
ATS_PROVIDERS = ["myworkday", "successfactors", "icims", "taleo", "greenhouse", "avature", "smartrecruiters", "talent.icims"]

# Common non-company email prefixes to ignore
GENERIC_PREFIXES = ["careers", "recruitment", "jobs", "hr", "noreply", "notification"]

# Authenticate Gmail API
def authenticate_gmail():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    
    return creds

# Search for job application emails
def search_emails(service):
    """
    Fetch job application-related emails, handling pagination to get all results.
    Ensures we only fetch each email thread once.
    """
    query = (
        'subject:(application OR interview OR applying) '
        '-from:no-reply@ -from:noreply@ -from:notifications@ -from:jobs-noreply@ '
        '-from:do-not-reply@ newer_than:30d'
    )

    job_application_emails_lst = []
    seen_thread_ids = set()  # Track seen threads to prevent duplicates
    next_page_token = None

    while True:
        results = service.users().messages().list(userId="me", q=query, pageToken=next_page_token).execute()
        
        for msg in results.get("messages", []):
            msg_id = msg["id"]
            thread_id = msg.get("threadId")  # Ensure we don’t process the same thread multiple times
            
            if thread_id not in seen_thread_ids:
                seen_thread_ids.add(thread_id)  # Track processed threads
                job_application_emails_lst.append(msg)

        # Handle pagination
        next_page_token = results.get("nextPageToken")
        if not next_page_token:
            break  # No more pages, exit loop

    return job_application_emails_lst


# Extract company name from email sender (fix for Workday issue)
def extract_company_from_email(sender_email):
    match = re.search(r"([\w\d\-_]+)@([\w\d\-_]+)\.(com|net|org|io)", sender_email)
    if match:
        prefix, domain = match.group(1), match.group(2)
        
        # If domain is an ATS provider, use the prefix (e.g., "pwc@myworkday.com" -> "pwc")
        if domain in ATS_PROVIDERS and prefix.lower() not in GENERIC_PREFIXES:
            return prefix.lower()
        elif domain not in ATS_PROVIDERS:
            return domain.lower()
    
    return "Unknown"
            

# Extract company name from email body
def extract_company_from_body(text):
    if extract_company_from_email(text) == "Unknown":
        patterns = [
            r"Thank you for applying to ([\w\s\-&]+)",  # Example: "Thank you for applying to Google"
            r"Your application at ([\w\s\-&]+) has been received",  # Example: "Your application at Microsoft has been received."
            r"We appreciate your interest in ([\w\s\-&]+)",  # Example: "We appreciate your interest in KPMG."
            r"at ([\w\s\-&]+)", # example: "Your Application for Advanced Analytics, Associate - LinkedIn Marketing Solutions at LinkedIn"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            else:
                return None

def extract_email_body(payload):
    """
    Extracts the full text body from a Gmail email payload, ensuring we handle multipart emails properly.
    """
    if "parts" in payload:
        body_text = ""

        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")

            if body_data:
                decoded_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

                if mime_type == "text/plain":  
                    return decoded_text  # ✅ Return immediately if plain text is found
                elif mime_type == "text/html":
                    body_text = decoded_text  # Store HTML version as fallback

            # **🔍 Recursive call for nested parts (Gmail stores deep MIME parts sometimes)**
            if "parts" in part:
                nested_body = extract_email_body(part)
                if nested_body:
                    return nested_body  # ✅ Return if found in nested parts

        return body_text  # ✅ Return HTML text if no plain text was found

    else:  
        body_data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore") if body_data else ""




# Extract email details (including body content)
def extract_email_details(service, message_id):
    """
    Extracts subject, sender, date, company, and ensures the correct email body is extracted.
    Handles multi-part emails properly.
    """
    email_data = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = email_data.get("payload", {}).get("headers", [])
    subject = sender = date_str = email_body = None

    # Extract Subject, Sender, and Date
    for header in headers:
        if header["name"] == "Subject":
            subject = header["value"]
        elif header["name"] == "From":
            sender = header["value"]
        elif header["name"] == "Date":
            date_str = header["value"]  # Original raw date


    # ✅ Extract email body correctly
    email_body = extract_email_body(email_data["payload"])
    email_body = BeautifulSoup(email_body, "html.parser").get_text()  # ✅ Remove HTML tags
    # ✅ Convert Email Date to Standard Format
    date = None  # Default if parsing fails
    if date_str:
        try:
            # 🔹 Remove the timezone abbreviation (e.g., "(PST)", "(UTC)")
            date_str_clean = re.sub(r"\s\([A-Z]{3,4}\)$", "", date_str)

            # 🔹 Try parsing with timezone offset (-0800, +0000)
            date = datetime.strptime(date_str_clean, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                # 🔹 Try parsing without timezone (if no offset is present)
                date = datetime.strptime(date_str_clean, "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                print(f"❌ Date Parsing Error: {date_str}")  # Debugging print

        if date:
            date = date.strftime("%Y-%m-%d %H:%M:%S")  # Convert to standard format


    # Normalize email body for keyword detection
    email_body = " ".join(email_body.split()).lower()

    # Extract company name from sender email
    company = extract_company_from_email(sender)

    # If sender email is from an ATS, fallback to extracting from email body
    if company == "Unknown" and email_body:
        company_from_body = extract_company_from_body(email_body)
        if company_from_body:
            company = company_from_body
        elif subject:
            company_from_subject = extract_company_from_body(subject)
            if company_from_subject:
                company = company_from_subject

    return subject, sender, date, company, email_body



# Fetch job application data
def get_job_applications():
    creds = authenticate_gmail()
    service = build("gmail", "v1", credentials=creds)
    
    messages = search_emails(service)
    # print(messages)
    rejection_keywords = ["reject", "rejected", "decline", "declined", "not moving forward", "after careful review", "we will not be moving forward", "not be moving forward","regret", "unfortunately", "other candidates"]
    job_data = []
    for msg in messages:
        # print(msg)
        msg_id = msg["id"]
        subject, sender, date, company, email_body = extract_email_details(service, msg_id)

        # Determine job application status
        status = "Received"
        # if company == "pwc":
        #     print('pwc')
        #     print(email_body)
        #     print('-------------------')
        #     print("interview" in email_body.lower())
        #     print("interview" in subject.lower())
        #     print("offer" in subject.lower())
        #     print("congratulations" in subject.lower())
        #     print("congratulations" in email_body.lower())
        #     print("reject" in email_body.lower())
        #     print(any(keyword in email_body.lower() for keyword in rejection_keywords))
        if "update" in subject.lower() or "status" in subject.lower():
            if "interview" in subject.lower():
                status = "Interview"
            elif "offer" in subject.lower() or "congratulations" in subject.lower() or "congratulations" in email_body.lower():
                status = "Offer"
            elif "reject" in email_body.lower() or any(keyword in email_body.lower() for keyword in rejection_keywords):
                status = "Rejected"
        job_data.append([company, subject, status, date])
    
    df = pd.DataFrame(job_data, columns=["Company", "Subject", "Status", "Date"])
    return df.sort_values(by="Date", ascending=False)

# Streamlit UI
st.set_page_config(page_title="Job Application Tracker", layout="wide")

st.title("📋 Job Application Tracker")
st.write("Gmail API integration to track job applications and their status.")

# Button to fetch applications
if st.button("Fetch Applications"):
    df = get_job_applications()
    df.sort_values(by="Date", ascending=False, inplace=True)
    if df.empty:
        st.warning("No job applications found in the last 30 days.")
    else:
        st.success(f"Found {len(df)} job applications!")
        
        # Display full applications DataFrame with auto-width
        st.dataframe(df, use_container_width=True)
        df.to_csv("job_applications.csv", index=False)

        # Application status summary
        if "df" in locals():
            status_counts = df["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            status_counts.loc[len(status_counts.index)] = ["Total", status_counts["Count"].sum()]  # Add Total row
            
            # Display summary in a properly formatted table
            with st.container():
                st.write("## 📊 Application Status Summary")
                st.write(status_counts)
