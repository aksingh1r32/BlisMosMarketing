import requests
import pandas as pd
from dotenv import load_dotenv
import os
import streamlit as st

page_title = st.title("Apollo Contact Search")
title = st.text_input("Enter a title for your contact list")
industry = st.text_input("Enter an industry to search for contacts")

if st.button("Search"):
    st.write(f"Searching for contacts in the {industry} industry with the title '{title}'...")

load_dotenv()

url = "https://api.apollo.io/api/v1/contacts/search"

payload = {
    "per_page":25,
    "page": 1
}

headers = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "accept": "application/json",
    "x-api-key": os.getenv("APOLLO_API_KEY")
}

response = requests.post(url, json=payload, headers=headers)

data = response.json()

contacts = data.get("contacts", [])

cleaned = []

for c in contacts:
    org = c.get("organization", {})

    email = c.get("email")

    cleaned.append({
        "name": c.get("name"),
        "first_name": c.get("first_name"),
        "last_name": c.get("last_name"),
        "title": c.get("title"),
        "email": email,
        "linkedin": c.get("linkedin_url"),
        "city": c.get("city"),
        "state": c.get("state"),
        "country": c.get("country"),

        "company": org.get("name"),
        "website": org.get("website_url"),
        "domain": org.get("primary_domain"),
        "company_linkedin": org.get("linkedin_url"),
        "company_phone": org.get("phone"),
    })

filtered = []

for c in cleaned:
    if c["title"] == title and c["industry"] == industry:
        filtered.append(c)

df = pd.DataFrame(filtered)
df.to_csv('output.csv', index=False)

results = st.text(f"Found ({len(filtered)}) contacts matching the criteria. Results saved to output.csv!")

print(response.text)

