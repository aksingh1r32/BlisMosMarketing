import os
import asyncio
import requests
import pandas as pd
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from google import genai
from PIL import Image
import csv
import json
from datetime import datetime

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not APOLLO_API_KEY:
    raise ValueError("APOLLO_API_KEY not found in .env")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=GEMINI_API_KEY)

CSV_FILE = "processed_contacts.csv"

def load_processed_ids():

    if not os.path.exists(CSV_FILE):
        return set()

    df = pd.read_csv(CSV_FILE)

    if "apollo_id" not in df.columns:
        return set()

    return set(
        df["apollo_id"]
        .dropna()
        .astype(str)
        .tolist()
    )


def save_contact(contact, subject, body):

    organization = contact.get("organization", {}) or {}

    row = {
        "apollo_id": contact.get("id"),
        "first_name": contact.get("first_name"),
        "last_name": contact.get("last_name"),
        "title": contact.get("title"),
        "company_name": organization.get("name"),
        "email": contact.get("email"),
        "phone": contact.get("phone_numbers"),
        "stage": "Not Started",
        "linkedin_url": contact.get("linkedin_url"),
        "company_name_for_emails": organization.get("name"),
        "email_status": contact.get("email_status"),
        "email_confidence": contact.get("email_confidence"),
        "seniority": contact.get("seniority"),
        "industry": organization.get("industry"),
        "email_subject": subject,
        "email_body": body,
        "processed_date": datetime.now()
    }

    file_exists = os.path.exists(CSV_FILE)

    pd.DataFrame([row]).to_csv(
        CSV_FILE,
        mode="a",
        header=not file_exists,
        index=False
    )

# -----------------------------
# APOLLO SEARCH
# -----------------------------

def get_contacts():

    url = "https://api.apollo.io/api/v1/contacts/search"

    payload = {
        "per_page": 35,
        "page": 1
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": APOLLO_API_KEY
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers
    )

    response.raise_for_status()

    data = response.json()

    contacts = data.get("contacts", [])

    pd.DataFrame(contacts).to_csv(
        "apollo_contacts.csv",
        index=False
    )

    return contacts


# -----------------------------
# GEMINI SUMMARY
# -----------------------------

def summarize_image(image_path):

    image = Image.open(image_path)

    prompt = """
Analyze this LinkedIn profile screenshot.

Return ONLY valid JSON.

Example:

{
    "subject": "Improving operational efficiency with AI",
    "email": "Hi John,\n\n..."
}

Use the following email template as the base.

Hi [Name],

I hope you are doing well.

I am reaching out to introduce Blismos Solutions, a Data and AI company helping organizations move from AI discussions to practical, business-ready AI implementations.

Many companies today are exploring AI, but the real value comes when AI is applied to the right business processes — where it can reduce manual effort, improve decision-making, accelerate operations, and create measurable cost or productivity benefits.

At Blismos, we help businesses identify and implement AI solutions across areas such as:

• Intelligent workflow automation
• Customer support and service automation
• Sales and marketing intelligence
• Finance, HR, and operations use cases
• Custom AI agents and GenAI solutions
• Data modernization to make AI adoption scalable and reliable

Our approach is practical and implementation-focused.

We work with existing systems, existing teams, and existing business processes to deliver AI solutions without unnecessary disruption.

We would be happy to explore whether there are any areas in your organization where AI can improve efficiency, reduce operational effort, or create measurable business impact.

Would you be open to a short discussion next week?

Regards,
Aditya
Marketing Specialist
Blismos Solutions Pvt Ltd
https://blismos.com/

Replace [Name] with the actual person's name if visible.
Keep the opener concise and personalized. And keep the email professional and engaging and short. Around 4 sentences where you introduce the company and the value proposition, you talk about a call to action, have a personalized opener and then ask for a time to meet for a short discussion. And dont repeat the name twice.
Make sure to break up sentences so it isnt all one massive paragraph.

Do not include markdown.
Do not include code fences.
Return JSON only.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            image
        ]
    )

    return response.text


# -----------------------------
# PLAYWRIGHT
# -----------------------------

async def screenshot_profile(url, filename):

    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            user_data_dir="./userdata",
            headless=False
        )

        page = await context.new_page()

        print(f"Opening: {url}")

        await page.goto(url)

        await page.wait_for_timeout(5000)

        await page.screenshot(
            path=filename,
            full_page=True
        )

        await context.close()


def load_processed_contacts():
    try:
        df = pd.read_csv("processed_contacts.csv")
        return set(df["linkedin_url"].dropna())
    except FileNotFoundError:
        return set()

# -----------------------------
# MAIN PROGRAM
# -----------------------------

async def main():

    contacts = get_contacts()

    if not contacts:
        print("No contacts found.")
        return

    processed_ids = load_processed_ids()

    new_contacts = [
        c for c in contacts
        if str(c.get("id")) not in processed_ids
    ]

    if not new_contacts:
        print("No new contacts found.")
        return

    os.makedirs("screenshots", exist_ok=True)

    for contact in new_contacts[:50]:

        try:

            apollo_id = contact.get("id")

            name = (
                contact.get("name")
                or f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
            )

            linkedin = contact.get("linkedin_url")

            print(f"\nProcessing: {name}")

            if not linkedin:
                print("No LinkedIn URL found.")
                continue

            screenshot_path = f"screenshots/{apollo_id}.png"

            await screenshot_profile(
                linkedin,
                screenshot_path
            )

            summary = summarize_image(screenshot_path)

            data = json.loads(summary)

            subject = data["subject"]
            body = data["email"]

            save_contact(
                contact,
                subject,
                body
            )

            print("Saved.")

        except Exception as e:

            print(
                f"Failed processing "
                f"{contact.get('name')}: {e}"
            )


if __name__ == "__main__":
    asyncio.run(main())