from decouple import config
import streamlit as st
# import pandas as pd
# from io import StringIO
# import plotly.express as px

from src.models import User
from src.skills.interest import OpenQuestion
from src.skills.email_skill import check_mailbox, send_next_message_if_bandwidth_available
from src.skills.readwise_discourse import fetch_and_discuss_latest_readwise
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import db_session
from src.skills.zettel.file_management_service import FileManagementService
from src.skills.zettel import LOCAL_DOCS_FOLDER

# Set page title
st.title('Triggering Events')

st.write("This is a page for triggering events")

st.write("You can trigger events by clicking the button below")

st.button("Trigger Event")



def current_user():
    try:
        user = db_session.query(User).filter_by(name=config('ME')).first()
        return user
    finally:
        db_session.remove()  # Important: clean up the session after use


if st.button("Check Mailbox"):
    try:
        check_mailbox()
    finally:
        db_session.remove()

if st.button("Send Next Message"):
    try:
        send_next_message_if_bandwidth_available()
    finally:
        db_session.remove()


def sync_local_docs():
    # with app.app_context():
    try:
        FileManagementService().sync_documents_from_folder(LOCAL_DOCS_FOLDER, current_user())
    finally:
        db_session.remove()


if st.button("Sync Local Docs"):
    sync_local_docs()

if st.button("Fetch and Discuss Latest Readwise"):
    fetch_and_discuss_latest_readwise()



def ponder_wittgenstein():
    try:
        PonderWittgensteinSkill.ponder_wittgenstein(current_user())
    finally:
        db_session.remove()

if st.button("Ponder Wittgenstein"):
    ponder_wittgenstein()


def ask_get_to_know_you():
    try:
        GetToKnowYouSkill.ask_get_to_know_you_latest_zettelkasten_notes(current_user())
    finally:
        db_session.remove()


if st.button("Ask Get to Know You"):
    ask_get_to_know_you()
