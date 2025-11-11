import streamlit as st
from src.skills.email_skill import Email
from src.skills.zettel import Zettel
from src.skills.interest import OpenQuestion

@st.cache_data
def fetch_emails():
    return Email.query.all() # TODO: scope by user

emails = fetch_emails()

st.title("Emails")
st.divider()

for email in emails:
    st.write(f"**Subject:** {email.subject}")
    st.write(f"**From:** {email.from_email_address}")
    st.write(email.snippet)
    st.divider()
