import streamlit as st
from src.models import *
from src.skills.persona import Persona
from src.skills.email_skill import *
from src.skills.zettel import *
from src.skills.interest import *

st.title("Chat")
st.divider()

# Initialize session state for the active conversation
if 'conversation' not in st.session_state:
    st.session_state.conversation = None

# Get all available personas
personas = Persona.query.all()

def chat():
    # Persona/conversation selection
    selected_persona_index = st.sidebar.selectbox(
        "Select a persona:",
        range(len(personas)),
        format_func=lambda i: personas[i].name
    )
    selected_persona = personas[selected_persona_index]
    
    # Initialize or reset conversation
    if st.sidebar.button("New Chat") or st.session_state.conversation is None:
        st.session_state.conversation = selected_persona.create_conversation()
        st.rerun()
    
    # Display chat header info
    st.write(f"Chatting with: **{st.session_state.conversation.name}**")
    
    # Display message history
    for message in st.session_state.conversation.get_messages():
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle new user input
    if prompt := st.chat_input("What would you like to talk about?"):
        # Add user message to conversation and UI
        st.session_state.conversation.add_message("user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get and display AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.conversation.get_ai_response()
                st.markdown(response)

chat()
