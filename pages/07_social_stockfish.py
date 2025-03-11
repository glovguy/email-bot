import streamlit as st
import pandas as pd
import json
from io import StringIO
import uuid
from datetime import datetime
import os
import platform
import traceback
import logging

# Import models and skills
from src.models import db_session, User
from src.skills.social_stockfish import SocialStockfishSkill, ConversationBranch
from src.skills.social_stockfish.models import ConversationHistory, Objective, Simulation, SelectedApproach
from src.skills.social_stockfish.imessage_import import iMessageImporter
from src.skills.social_stockfish.contacts_import import ContactsImporter

# Initialize session state variables
if 'conversation_data' not in st.session_state:
    st.session_state.conversation_data = None
if 'objectives' not in st.session_state:
    st.session_state.objectives = []
if 'simulated_branches' not in st.session_state:
    st.session_state.simulated_branches = []
if 'selected_branch' not in st.session_state:
    st.session_state.selected_branch = None
if 'evaluations' not in st.session_state:
    st.session_state.evaluations = {}
if 'comparative_analysis' not in st.session_state:
    st.session_state.comparative_analysis = None
if 'contacts_data' not in st.session_state:
    st.session_state.contacts_data = {
        "phone": {},
        "email": {},
        "all": {}
    }
if 'manual_contacts' not in st.session_state:
    st.session_state.manual_contacts = []

st.title("Social Stockfish")
st.divider()

with st.sidebar:
    st.header("Controls")
    
    # Add tabs for different import methods
    import_tab1, import_tab2, import_tab3 = st.tabs(["File Upload", "iMessage Import", "Contacts"])
    
    with import_tab1:
        uploaded_file = st.file_uploader("Upload conversation data", type=["json", "csv", "txt"])
        
        if uploaded_file is not None:
            # Process the uploaded file
            try:
                if uploaded_file.name.endswith('.json'):
                    conversation_data = json.loads(uploaded_file.getvalue().decode('utf-8'))
                elif uploaded_file.name.endswith('.csv'):
                    conversation_data = pd.read_csv(uploaded_file).to_dict(orient='records')
                else:  # Text file - assume chat log format
                    lines = uploaded_file.getvalue().decode('utf-8').split('\n')
                    conversation_data = []
                    current_role = None
                    current_message = ""
                    
                    for line in lines:
                        if line.startswith("User:"):
                            if current_role:
                                conversation_data.append({"role": current_role, "content": current_message.strip()})
                            current_role = "user"
                            current_message = line[5:].strip()
                        elif line.startswith("Assistant:"):
                            if current_role:
                                conversation_data.append({"role": current_role, "content": current_message.strip()})
                            current_role = "assistant"
                            current_message = line[10:].strip()
                        else:
                            current_message += "\n" + line
                    
                    if current_role:
                        conversation_data.append({"role": current_role, "content": current_message.strip()})
                
                st.session_state.conversation_data = conversation_data
                st.success("Conversation data loaded successfully!")
            except Exception as e:
                st.error(f"Error loading conversation data: {str(e)}")
    
    with import_tab2:
        if platform.system() != "Darwin":
            st.warning("iMessage import is only available on macOS")
        else:
            st.subheader("Import from iMessages")
            
            # Add option tabs for different import methods
            db_tab, manual_tab = st.tabs(["Database Import", "Manual Export"])
            
            with db_tab:
                # Check if iMessage database is accessible
                db_status, db_message = iMessageImporter.check_database_accessible()
                
                if not db_status:
                    st.error(db_message)
                    
                    st.subheader("Chat DB Path")
                    st.markdown("If you have a copy of the database, specify its path:")
                    custom_path = st.text_input("Custom database path:", 
                                                value="~/Documents/messages/chat.db", 
                                                help="Path to your iMessage chat.db file or a copy")
                    
                    
                    expanded_path = os.path.expanduser(custom_path)
                    status, message = iMessageImporter.check_database_accessible(expanded_path)
                    
                    if status:
                        st.success(f"Successfully connected to database at {expanded_path}")
                        db_status = True
                        db_path = expanded_path
                    else:
                        st.error(message)
                
                # Add more detailed schema inspection option
                if db_status:
                    if st.button("Advanced Schema Inspection"):
                        with st.spinner("Inspecting database schema..."):
                            try:
                                schema = iMessageImporter.inspect_schema(db_path)
                                
                                st.subheader("Database Schema")
                                
                                # Display table information
                                for table_name, table_info in schema["tables"].items():
                                    if st.checkbox(f"Table: {table_name}", key=f"table_{table_name}"):
                                        st.write("Columns:")
                                        cols_df = pd.DataFrame(table_info["columns"])
                                        st.dataframe(cols_df)
                                        
                                        if "sample" in table_info:
                                            st.write("Sample data:")
                                            st.json(table_info["sample"])
                                
                                # Show relationship test results
                                if "join_test" in schema:
                                    st.subheader("Relationship Tests")
                                    if "error" in schema["join_test"]:
                                        st.error(f"Join test error: {schema['join_test']['error']}")
                                    else:
                                        st.success(f"Chat-Message join working: {schema['join_test']['chat_message']}")
                                        
                                if schema["error"]:
                                    st.error(f"Schema inspection error: {schema['error']}")
                            except Exception as e:
                                st.error(f"Error inspecting schema: {str(e)}")
                else:
                    db_path = iMessageImporter.get_database_path()
            
                if db_status:
                    # List available conversations
                    conversations = iMessageImporter.list_conversations(db_path)
                    
                    if not conversations:
                        st.warning("No conversations found in iMessage database")
                    else:
                        # Add filtering options
                        st.subheader("Filter Conversations")
                        filter_show_dm_contacts, filter_show_dm_non_contacts, filter_show_groups = st.columns(3)
                        
                        with filter_show_dm_contacts:
                            show_contacts = st.checkbox("Show direct messages with contacts", value=True,
                                                       help="Show one-on-one conversations with people in your contacts")
                        
                        with filter_show_dm_non_contacts:
                            show_non_contacts = st.checkbox("Show direct messages with non-contacts", value=False,
                                                           help="Show one-on-one conversations with numbers/emails not in your contacts")
                        
                        with filter_show_groups:
                            show_groups = st.checkbox("Show group chats", value=True,
                                                    help="Show conversations with multiple participants")
                        
                        # Apply filters to conversation list
                        filtered_conversations = []
                        for conv in conversations:
                            # Determine conversation type
                            is_group = False
                            is_with_contact = False
                            
                            # Check if it's a group chat (has multiple participants)
                            if 'participants' in conv and isinstance(conv['participants'], list) and len(conv['participants']) > 1:
                                is_group = True
                            
                            # Check if it's with a contact 
                            # First try direct identifier lookup
                            identifier = iMessageImporter.normalized_identifier(conv.get('identifier', ''))
                            if st.session_state.contacts_data and identifier in st.session_state.contacts_data['all']:
                                is_with_contact = True
                            # Next check if any participant is in contacts
                            elif st.session_state.contacts_data and 'participants' in conv:
                                for participant in conv['participants']:
                                    clean_participant = participant.replace("+1", "").replace("-", "") if participant else ""
                                    if clean_participant and clean_participant in st.session_state.contacts_data['all']:
                                        is_with_contact = True
                                        break
                            
                            # Apply filters
                            should_include = (is_group and show_groups) or \
                                             (not is_group and is_with_contact and show_contacts) or \
                                             (not is_group and not is_with_contact and show_non_contacts)
                            
                            if should_include:
                                filtered_conversations.append(conv)
                        
                        # Update the conversation list if filtered
                        if filtered_conversations:
                            conversations = filtered_conversations
                            st.success(f"Showing {len(conversations)} conversations after filtering")
                        else:
                            st.warning("No conversations match your filters. Please adjust your filter settings.")
                            conversations = []  # Empty the list if nothing matches
                        
                        # Now display the filtered conversations
                        # Create a formatted list of conversation options with better names
                        conversation_options = []
                        for c in sorted(conversations, key=lambda x: x['last_message'], reverse=True):
                            if not st.session_state.contacts_data:
                                # Format the display name with message count and date
                                name = c['name']
                            else:
                                formatted_id = iMessageImporter.normalized_identifier(c['identifier'])
                                name = st.session_state.contacts_data['all'].get(formatted_id, c['name'])
                            
                            # Add the message count
                            msg_info = f"{c['message_count']} messages"
                            
                            # Add the last message date if available and not a raw timestamp
                            # date_info = ""
                            # if c['last_message'] and not c['last_message'].startswith("Raw timestamp"):
                            #     date_info = f", last: {c['last_message']}"
                            
                            option_display = f"{name} ({msg_info})"
                            conversation_options.append(option_display)
                        
                        selected_conv_idx = st.selectbox(
                            "Select conversation:", 
                            range(len(conversations)), 
                            format_func=lambda i: conversation_options[i]
                        )
                        
                        if selected_conv_idx is not None:
                            selected_conv = conversations[selected_conv_idx]
                        else:
                            st.error("No conversation selected")
                            selected_conv = None
                        
                        # Limit selection
                        msg_limit = st.number_input("Message limit", min_value=10, max_value=1000, value=100, step=10)
                        order_col1, order_col2 = st.columns(2)
                        
                        with order_col1:
                            start_from_recent = st.checkbox("Start from most recent messages", 
                                                          value=True,
                                                          help="When checked, will import the most recent messages. Otherwise starts from the oldest.")
                        
                        with order_col2:
                            if start_from_recent:
                                st.info("Showing most recent messages first")
                            else:
                                st.info("Showing from beginning of conversation")
                        
                        if st.button("Import Selected Conversation"):
                            with st.spinner("Importing messages..."):
                                # Include contacts data if available
                                contacts_data = st.session_state.contacts_data if 'contacts_data' in st.session_state else None
                                
                                messages = iMessageImporter.import_conversation(
                                    selected_conv["id"], 
                                    limit=msg_limit,
                                    db_path=db_path,
                                    contacts=contacts_data,
                                    start_from_recent=start_from_recent
                                )
                                
                                if messages:
                                    st.session_state.conversation_data = messages
                                    st.success(f"Imported {len(messages)} messages!")
                                    st.rerun()
                                else:
                                    st.error("No messages found or error importing conversation")
                                    st.info("Check your terminal/console for detailed error messages. If running in Streamlit Cloud, these may not be visible.")
                                    
                                    # Add a retry with diagnostic info option
                                    if st.button("Retry with Diagnostics"):
                                        st.info("Attempting import with detailed diagnostics...")
                                        # Turn on debugging output
                                        logging.basicConfig(level=logging.DEBUG)
                                        
                                        # Display the conversation details
                                        st.write(f"Conversation ID: {selected_conv['id']}")
                                        st.write(f"Name: {selected_conv['name']}")
                                        st.write(f"Messages count (expected): {selected_conv['message_count']}")
                                        
                                        # Display contacts info
                                        if 'contacts_data' in st.session_state and st.session_state.contacts_data:
                                            st.write(f"Contacts available: {len(st.session_state.contacts_data['all'])}")
                                            if st.checkbox("Show contacts mapping"):
                                                st.json(st.session_state.contacts_data)
                                        else:
                                            st.write("No contacts data available")
                                        
                                        # Try the import again with more verbose output
                                        try:
                                            messages = iMessageImporter.import_conversation(
                                                selected_conv["id"], 
                                                limit=msg_limit,
                                                db_path=db_path
                                            )
                                            st.write(f"Result: {len(messages)} messages imported")
                                        except Exception as e:
                                            st.error(f"Diagnostic import error: {str(e)}")
                                            st.write("Traceback:", traceback.format_exc())
            
            with manual_tab:
                st.markdown("### Manual Export Method")
                st.markdown("""
                If you're having permission issues with the database, you can export messages directly:
                
                1. Open the Messages app on your Mac
                2. Select the conversation you want to analyze
                3. Select all messages (Edit → Select All, or Cmd+A)
                4. Copy them (Edit → Copy, or Cmd+C)
                5. Paste them in the text area below
                """)
                
                manual_text = st.text_area("Paste conversation here:", height=300)
                
                if st.button("Process Manual Conversation"):
                    if not manual_text.strip():
                        st.error("Please paste a conversation first")
                    else:
                        # Process the pasted text
                        lines = manual_text.split('\n')
                        conversation_data = []
                        
                        # Track unique senders to identify user vs others
                        senders = set()
                        current_sender = None
                        current_message = []
                        
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                                
                            # Check for new message (sender: message)
                            import re
                            sender_match = re.match(r'^(.+?):\s+(.+)$', line)
                            
                            if sender_match:
                                # Save previous message if exists
                                if current_sender and current_message:
                                    # Add sender to our set of observed senders
                                    senders.add(current_sender)
                                    
                                    # Will determine role after processing all messages
                                    conversation_data.append({
                                        "sender": current_sender, 
                                        "content": "\n".join(current_message)
                                    })
                                    current_message = []
                                
                                # Start new message
                                current_sender = sender_match.group(1)
                                current_message.append(sender_match.group(2))
                            else:
                                # Continuation of previous message
                                if current_sender:
                                    current_message.append(line)
                        
                        # Add the last message if exists
                        if current_sender and current_message:
                            senders.add(current_sender)
                            conversation_data.append({
                                "sender": current_sender, 
                                "content": "\n".join(current_message)
                            })
                        
                        # Now determine roles based on observed senders
                        if conversation_data:
                            # Assume the first sender in alphabetical order is "Me" (the user)
                            # This is a simplification - might need adjustment
                            if len(senders) >= 2:
                                sorted_senders = sorted(list(senders))
                                user_sender = sorted_senders[0]
                                
                                # Now assign roles
                                for msg in conversation_data:
                                    if msg["sender"] == user_sender:
                                        msg["role"] = "user"
                                    else:
                                        msg["role"] = "assistant"
                                    msg["is_human"] = True
                            else:
                                # If only one sender, assume they're the assistant
                                for msg in conversation_data:
                                    msg["role"] = "assistant" 
                                    msg["is_human"] = True
                        
                            st.session_state.conversation_data = conversation_data
                            st.success(f"Imported {len(conversation_data)} messages!")
                            st.rerun()
                        else:
                            st.error("Couldn't parse any messages from the text. Please check the format.")
    
    with import_tab3:
        if platform.system() != "Darwin":
            st.warning("Contacts import is only available on macOS")
        else:
            st.subheader("Import macOS Contacts")
            
            # Add option tabs for different import methods
            contacts_db_tab, contacts_manual_tab = st.tabs(["Database Import", "Manual Mapping"])
            
            with contacts_db_tab:
                # Check if contacts database is accessible
                contacts_db_status, contacts_db_message = ContactsImporter.check_database_accessible()
                
                if not contacts_db_status:
                    st.error(contacts_db_message)
                    
                    # Option to provide custom path
                    st.subheader("Options")
                    contacts_copy_col, contacts_path_col = st.columns(2)
                    
                    with contacts_copy_col:
                        st.markdown("### Copy Database")
                        st.markdown("Create a copy of the Contacts database in a location you can access:")
                        contacts_copy_target = st.text_input("Copy target path:", 
                                                  value="~/Documents/messages/AddressBook-v22.abcddb",
                                                  help="Where to save the copy of the database",
                                                  key="contacts_copy_path")
                        
                        if st.button("Copy Contacts Database"):
                            success, message = ContactsImporter.copy_database(contacts_copy_target)
                            if success:
                                st.success(message)
                                st.markdown("Now use this path in the 'Custom database path' field →")
                            else:
                                st.error(message)
                    
                    with contacts_path_col:
                        st.markdown("### Custom Path")
                        st.markdown("If you have a copy of the database, specify its path:")
                        contacts_custom_path = st.text_input("Custom database path:", 
                                                  value="~/Documents/messages/AddressBook-v22.abcddb", 
                                                  help="Path to your Contacts database file or directory",
                                                  key="contacts_custom_path")
                        
                        if contacts_custom_path:
                            expanded_path = os.path.expanduser(contacts_custom_path)
                            status, message = ContactsImporter.check_database_accessible(expanded_path)
                            
                            if status:
                                st.success(f"Successfully connected to contacts at {expanded_path}")
                                contacts_db_status = True
                                contacts_db_path = expanded_path
                            else:
                                st.error(message)
                else:
                    contacts_db_path = ContactsImporter.get_database_path()
                
                # Import contacts button
                if contacts_db_status or os.path.exists(os.path.expanduser(contacts_custom_path)):
                    if st.button("Import Contacts"):
                        with st.spinner("Importing contacts..."):
                            try:
                                db_path = contacts_db_path if contacts_db_status else os.path.expanduser(contacts_custom_path)
                                contacts = ContactsImporter.import_contacts(db_path)
                                
                                if contacts and contacts['all']:
                                    st.session_state.contacts_data = contacts
                                    st.success(f"Imported {len(contacts['all'])} contacts with {len(contacts['phone'])} phone numbers and {len(contacts['email'])} email addresses!")
                                else:
                                    st.warning("No contacts found in the database.")
                            except Exception as e:
                                st.error(f"Error importing contacts: {str(e)}")
                
                # Show imported contacts stats
                if st.session_state.contacts_data and st.session_state.contacts_data['all']:
                    st.subheader("Imported Contacts")
                    st.write(f"Total contacts: {len(st.session_state.contacts_data['all'])}")
                    st.write(f"Phone numbers: {len(st.session_state.contacts_data['phone'])}")
                    st.write(f"Email addresses: {len(st.session_state.contacts_data['email'])}")
                    
                    # Option to view some samples
                    if st.checkbox("Show sample contacts"):
                        # Show up to 10 sample contacts
                        st.subheader("Sample Contacts")
                        samples = list(st.session_state.contacts_data['all'].items())[:10]
                        for identifier, name in samples:
                            st.write(f"**{name}**: {identifier}")
            
            with contacts_manual_tab:
                st.markdown("### Manual Contact Mapping")
                st.markdown("""
                If you're having issues importing your contacts database, you can manually add 
                mappings for phone numbers or email addresses to contact names:
                """)
                
                # Add a new mapping
                st.subheader("Add New Contact")
                contact_col1, contact_col2 = st.columns(2)
                
                with contact_col1:
                    contact_name = st.text_input("Contact Name", key="new_contact_name")
                    
                with contact_col2:
                    contact_identifier = st.text_input("Phone or Email", key="new_contact_identifier")
                
                if st.button("Add Contact"):
                    if contact_name and contact_identifier:
                        # Add to session state
                        st.session_state.manual_contacts.append({
                            "name": contact_name,
                            "identifier": contact_identifier
                        })
                        
                        # Also add to contacts data
                        if 'contacts_data' not in st.session_state:
                            st.session_state.contacts_data = {
                                "phone": {},
                                "email": {},
                                "all": {}
                            }
                        
                        # Determine if it's a phone or email
                        if '@' in contact_identifier:
                            st.session_state.contacts_data['email'][contact_identifier] = contact_name
                        else:
                            # Normalize phone number
                            phone = ''.join(c for c in contact_identifier if c.isdigit())
                            st.session_state.contacts_data['phone'][phone] = contact_name
                        
                        # Add to the 'all' category
                        st.session_state.contacts_data['all'][contact_identifier] = contact_name
                        
                        st.success(f"Added contact: {contact_name}")
                        st.rerun()
                
                # Display existing manual contacts
                if st.session_state.manual_contacts:
                    st.subheader("Your Manual Contacts")
                    for i, contact in enumerate(st.session_state.manual_contacts):
                        col1, col2, col3 = st.columns([3, 3, 1])
                        with col1:
                            st.write(contact["name"])
                        with col2:
                            st.write(contact["identifier"])
                        with col3:
                            if st.button("Remove", key=f"remove_contact_{i}"):
                                # Remove from manual list
                                st.session_state.manual_contacts.pop(i)
                                # Also remove from contacts data
                                if contact["identifier"] in st.session_state.contacts_data['all']:
                                    del st.session_state.contacts_data['all'][contact["identifier"]]
                                    
                                    if '@' in contact["identifier"] and contact["identifier"] in st.session_state.contacts_data['email']:
                                        del st.session_state.contacts_data['email'][contact["identifier"]]
                                    else:
                                        phone = ''.join(c for c in contact["identifier"] if c.isdigit())
                                        if phone in st.session_state.contacts_data['phone']:
                                            del st.session_state.contacts_data['phone'][phone]
                                
                                st.rerun()

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["Conversation", "Objectives", "Simulation", "Recommendations"])

with tab1:
    st.header("Conversation Data")
    
    if st.session_state.conversation_data:
        # Check if this is a conversation with real people (has 'sender' field)
        is_human_conversation = any('sender' in msg for msg in st.session_state.conversation_data)
        
        if is_human_conversation:
            # Custom styling for human conversation
            for i, message in enumerate(st.session_state.conversation_data):
                sender = message.get("sender", "Unknown")
                role = message.get("role", "user")
                
                # Determine message styling based on role
                if role == "user":
                    # Right-aligned for the user's messages
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
                        <div style="background-color: #e6f7ff; border-radius: 15px; padding: 10px; max-width: 70%;">
                            <p style="margin: 0; font-weight: bold; color: #000000;">{sender}</p>
                            <p style="margin: 0; color: #000000;">{message['content']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Left-aligned for others' messages
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-start; margin-bottom: 10px;">
                        <div style="background-color: #f0f0f0; border-radius: 15px; padding: 10px; max-width: 70%;">
                            <p style="margin: 0; font-weight: bold; color: #000000;">{sender}</p>
                            <p style="margin: 0; color: #000000;">{message['content']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            # Regular display for non-human conversations
            for message in st.session_state.conversation_data:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
    else:
        st.info("Upload a conversation file to get started.")
        
        st.subheader("Manual Entry")
        col1, col2 = st.columns(2)
        
        with col1:
            manual_role = st.selectbox("Role", ["user", "assistant"])
        
        with col2:
            manual_content = st.text_area("Message Content")
            
        if st.button("Add Message"):
            if manual_content.strip():
                if not st.session_state.conversation_data:
                    st.session_state.conversation_data = []
                
                st.session_state.conversation_data.append({
                    "role": manual_role,
                    "content": manual_content
                })
                st.rerun()

with tab2:
    st.header("Conversation Objectives")
    
    # Display existing objectives
    for i, objective in enumerate(st.session_state.objectives):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"{i+1}. {objective}")
        with col2:
            if st.button("Remove", key=f"remove_obj_{i}"):
                st.session_state.objectives.pop(i)
                st.rerun()
    
    # Add new objective
    new_objective = st.text_input("New Objective")
    if st.button("Add Objective"):
        if new_objective.strip():
            st.session_state.objectives.append(new_objective)
            st.rerun()
    
    # Importance weights
    if st.session_state.objectives:
        st.subheader("Objective Weights")
        weights = {}
        total = 0
        
        for i, objective in enumerate(st.session_state.objectives):
            weight = st.slider(f"Weight for: {objective}", 1, 10, 5, key=f"weight_{i}")
            weights[objective] = weight
            total += weight
        
        # Normalize weights
        if total > 0:
            normalized_weights = {obj: round(w/total, 2) for obj, w in weights.items()}
            
            st.subheader("Normalized Weights")
            for obj, weight in normalized_weights.items():
                st.write(f"{obj}: {weight}")

with tab3:
    st.header("Conversation Simulation")
    
    if not st.session_state.conversation_data:
        st.warning("Please upload conversation data first.")
    elif not st.session_state.objectives:
        st.warning("Please define at least one objective.")
    else:
        # Simulation settings
        st.subheader("Simulation Settings")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            num_branches = st.number_input("Number of branches", min_value=2, max_value=5, value=3)
        
        with col2:
            branch_depth = st.number_input("Branch depth", min_value=1, max_value=9, value=2, 
                                          help="Number of back-and-forth exchanges to simulate")
        
        with col3:
            model = st.selectbox("Model", ["claude-3-5-haiku-latest", "claude-3-7-sonnet-latest"], 
                                index=1)
        
        # Generate branches button
        if st.button("Generate Alternative Branches"):
            # Combine all objectives into a single objective string
            combined_objective = "; ".join(st.session_state.objectives)
            
            with st.spinner("Simulating alternative conversation branches..."):
                try:
                    # Ensure our conversation_data has proper sender information when from iMessage
                    conversation_data = st.session_state.conversation_data
                    
                    # Use the SocialStockfishSkill to analyze the conversation
                    recommendations = SocialStockfishSkill.analyze_conversation(
                        conversation_history=conversation_data,  # Changed parameter name for clarity
                        objective=combined_objective,
                        num_branches=num_branches,
                        branch_depth=branch_depth,
                        model=model
                    )
                    
                    # Check if there was an error
                    if "error" in recommendations["detailed_analysis"]:
                        st.error(f"Error generating branches: {recommendations['detailed_analysis']['error']}")
                        with st.expander("Show detailed error information"):
                            st.code(recommendations['detailed_analysis']['traceback'])
                        st.warning("You can try reducing the branch depth, using a different model, or simplifying the conversation.")
                    else:
                        # Store the results in session state
                        if "detailed_analysis" in recommendations and "all_approaches" in recommendations["detailed_analysis"]:
                            approaches = recommendations["detailed_analysis"]["all_approaches"]
                            
                            # Store comparative analysis
                            if "comparative_analysis" in recommendations["detailed_analysis"]:
                                st.session_state.comparative_analysis = recommendations["detailed_analysis"]["comparative_analysis"]
                            
                            # Create simulated branches from the results
                            st.session_state.simulated_branches = []
                            st.session_state.evaluations = {}
                            
                            # Get the best branch information
                            best_branch_id = str(uuid.uuid4())
                            st.session_state.selected_branch = best_branch_id
                            
                            # Add the best branch
                            best_approach = approaches[0]
                            best_response = recommendations["best_response"]
                            
                            st.session_state.simulated_branches.append({
                                "id": best_branch_id,
                                "name": f"Branch 1: {best_approach['approach'][:50]}...",
                                "approach": best_approach["approach"],
                                "messages": [
                                    {"role": "assistant", "content": best_response}
                                ],
                                "score": best_approach["score"]
                            })
                            
                            # Add the evaluation for the best branch
                            st.session_state.evaluations[best_branch_id] = {
                                "overall": float(best_approach["score"])
                            }
                            
                            # Add alternative branches using simulated_branches (new format)
                            if "simulated_branches" in recommendations["detailed_analysis"]:
                                simulated_branches = recommendations["detailed_analysis"]["simulated_branches"]
                                
                                for i, branch in enumerate(simulated_branches):
                                    # Skip the first branch since we already added it above
                                    if i == 0:
                                        continue
                                    
                                    branch_id = str(uuid.uuid4())
                                    
                                    # Extract approach and messages
                                    approach = branch.get("approach", f"Alternative {i+1}")
                                    messages = branch.get("messages", [])
                                    score = branch.get("score", 0.5)
                                    
                                    # Add to the list of branches
                                    st.session_state.simulated_branches.append({
                                        "id": branch_id,
                                        "name": f"Branch {i+1}: {approach[:50]}...",
                                        "approach": approach,
                                        "messages": messages,
                                        "score": score
                                    })
                                    
                                    # Add the evaluation for this branch
                                    st.session_state.evaluations[branch_id] = {
                                        "overall": float(score)
                                    }
                            
                            st.success("Generated alternative conversation branches!")
                        else:
                            st.error("Failed to generate branches with detailed analysis.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.code(traceback.format_exc())
                    st.warning("Please try again with different settings or check the logs for more details.")
        
        # Display branches
        if st.session_state.simulated_branches:
            st.subheader("Simulated Conversation Branches")
            
            # Display branches in order of score
            sorted_branches = sorted(
                st.session_state.simulated_branches, 
                key=lambda b: st.session_state.evaluations[b["id"]]["overall"], 
                reverse=True
            )
            print(f"Sorted branches: {sorted_branches}")
            
            for branch in sorted_branches:
                branch_id = branch["id"]
                is_selected = branch_id == st.session_state.selected_branch
                score = st.session_state.evaluations[branch_id]["overall"]
                
                with st.expander(
                    f"{branch['name']} (Score: {score:.1f}/10) {' ✅' if is_selected else ''}", 
                    expanded=is_selected
                ):
                    # Display approach description
                    if "approach" in branch:
                        st.markdown("**Approach:**")
                        st.markdown(branch["approach"])
                        st.divider()
                    
                    # Display conversation
                    st.markdown("**Response:**")
                    for message in branch["messages"]:
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                    
                    # Select button
                    if not is_selected:
                        if st.button("Select This Approach", key=f"select_{branch_id}"):
                            st.session_state.selected_branch = branch_id
                            st.rerun()

with tab4:
    st.header("Recommendations")
    
    if st.session_state.selected_branch:
        selected_branch = next(
            (b for b in st.session_state.simulated_branches 
             if b["id"] == st.session_state.selected_branch),
            None
        )
        
        if selected_branch:
            st.subheader("Selected Approach")
            if "approach" in selected_branch:
                st.write(selected_branch["approach"])
            else:
                st.write(selected_branch["name"])
            
            # Display score with visual indicator
            score = st.session_state.evaluations[selected_branch["id"]]["overall"]
            st.progress(score / 10.0)
            st.write(f"Score: {score:.1f}/10")
            
            st.subheader("Recommended Response")
            for message in selected_branch["messages"]:
                if message["role"] == "assistant":
                    response_text = message["content"]
                    st.text_area(
                        "Copy this response:",
                        response_text,
                        height=200
                    )
                    
                    # Copy button
                    st.button("Copy to Clipboard", 
                             on_click=lambda: st.write('<script>navigator.clipboard.writeText("' + 
                                                     response_text.replace('"', '\\"').replace('\n', '\\n') + 
                                                     '");</script>', unsafe_allow_html=True))
            
            # Show comparative analysis if available
            if "comparative_analysis" in st.session_state and st.session_state.comparative_analysis:
                st.subheader("Comparative Analysis")
                st.markdown(st.session_state.comparative_analysis)
            
            # Implementation tips section
            st.subheader("Implementation Tips")
            tips = [
                "Consider adapting the tone based on your relationship with the recipient",
                "Add specific details relevant to your situation",
                "Follow up within 2-3 days if no response"
            ]
            for i, tip in enumerate(tips):
                st.write(f"{i+1}. {tip}")
    else:
        st.info("Generate and select a conversation branch to see recommendations.")