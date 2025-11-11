from src.skills.email_skill import email, oauth_credential
from src.skills.interest import OpenQuestion
import streamlit as st
from src.skills.zettel import Zettel

st.title("Zettel Semantic Search")

search_query = st.text_input("Search zettels", placeholder="Enter your search query")

if search_query:
    search_results = Zettel.find_similar(search_query, limit=20)
    
    st.subheader("Search Results")
    st.code(search_query, language="text")
    
    for ztl, similarity in search_results:
        st.markdown(f"*Similarity score:* {similarity:.3f}")
        st.markdown(f"**{ztl.title}**")
        st.caption(f"UUID: {ztl.uuid} | Updated at: {ztl.updated_at}")
        st.write(ztl.content)
        st.divider()
