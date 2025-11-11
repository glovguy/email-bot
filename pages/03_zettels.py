import streamlit as st
from src.skills.email_skill import Email
from src.skills.zettel import Zettel
from src.skills.interest import OpenQuestion

@st.cache_data
def fetch_zettels():
    return Zettel.query.all() # TODO: scope by user

zettels = fetch_zettels()

st.title("Zettels")
st.divider()

for ztl in zettels:
    st.markdown(f"**{ztl.title}**")
    st.caption(f"UUID: {ztl.uuid} | Updated at: {ztl.updated_at}")
    st.write(ztl.content)
    st.divider()
