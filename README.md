# 📌 Job Application Tracker

A **Streamlit-based web app** that automatically tracks job applications from your **Gmail inbox** using the **Gmail API**. The app extracts job-related emails, categorizes their status (Received, Interview, Offer, Rejected), and presents a summary dashboard.

## 🚀 Features
- **Automatic Job Tracking:** Fetches job application emails from Gmail.
- **Application Status Detection:** Categorizes emails as "Received," "Interview," "Offer," or "Rejected."
- **Data Visualization:** Displays applications in a sortable table.
- **Application Summary:** Shows total applications by status.
- **Export to CSV:** Save your applications for offline tracking.

---

## 🛠️ Setup & Installation
### **1️⃣ Enable Gmail API & Get Credentials**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project & enable the **Gmail API**.
3. Create OAuth 2.0 **Client ID credentials** and download `credentials.json`.
4. Enable the Gmail API's **Read-Only** permission.

### **2️⃣ Install Dependencies**
```bash
pip install streamlit google-auth google-auth-oauthlib google-auth-httplib2 googleapiclient pandas beautifulsoup4
```

### **3️⃣ Run the App**
```bash
streamlit run test.py
```

---

## 📝 Configuration
### **Modify Search Query (Optional)**
The app searches Gmail for job-related emails. You can customize the `search_emails()` function to adjust the search query:
```python
query = ('subject:(application OR interview OR rejection OR offer) '
         '-from:no-reply@ -from:noreply@ -from:notifications@ '
         '-from:do-not-reply@ newer_than:30d')
```

---

## 📊 How It Works
1. **Fetch Emails** → Retrieves job application emails using Gmail API.
2. **Extract & Parse Data** → Extracts **subject, sender, date, body** and detects status.
3. **Display in Streamlit** → Shows applications in an interactive table.
4. **Summarize Applications** → Generates a status summary chart.
5. **Export Data** → Allows CSV export for offline tracking.

---

## 🎯 Application Status Detection
- **Received** → Default status when an email is found.
- **Interview** → If "interview" appears in the subject/body.
- **Offer** → If "offer" or "congratulations" appears.
- **Rejected** → If rejection phrases like "not moving forward" appear.

---

## 🎉 Contributing
Pull requests are welcome! Feel free to suggest improvements or report issues.

---

## 🔗 References
- [Google API Python Client](https://developers.google.com/api-client-library/python/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [ChatGPT](chat.openai.com)

