import streamlit as st
import os
import platform
import pandas as pd

from src.models import db_session, User, AppSetting # type: ignore
from src.skills.email_skill import OAuthCredential # type: ignore
from src.skills.zettel import zettel # type: ignore
from src.skills.interest import OpenQuestion # type: ignore
from src.skills.social_stockfish.models import Contact
from src.skills.social_stockfish.imessage_import import iMessageImporter
from src.skills.social_stockfish.contacts_import import ContactsImporter

# Set page title
st.set_page_config(page_title="iMessage & Contact Import", page_icon="📱")

# Initialize session state for contacts data
if 'contacts_data' not in st.session_state:
    st.session_state.contacts_data = {
        "phone": {},
        "email": {},
        "all": {}
    }
if 'manual_contacts' not in st.session_state:
    st.session_state.manual_contacts = []

# Get current user (or default to None)
current_user_id = 1
try:
    if 'current_user' in st.session_state and st.session_state.current_user:
        current_user_id = st.session_state.current_user.id
except:
    pass

# Main title
st.title("📱 iMessage & Contact Import")
st.write("Import and manage your iMessage conversations and contacts")

# Create tabs for different import functions
imessage_tab, contacts_tab = st.tabs(["iMessage Import", "Contacts Import"])

with imessage_tab:
    st.header("iMessage Database Setup")
    
    if platform.system() != "Darwin":
        st.warning("iMessage import is only available on macOS")
    else:
        # Check if we have a saved path in the database
        saved_db_path = AppSetting.get("imessage_db_path", user_id=current_user_id)
        db_exists = False
        
        if saved_db_path:
            # Check if the saved path still exists
            if os.path.exists(os.path.expanduser(saved_db_path)):
                st.success(f"Using previously configured iMessage database at: {saved_db_path}")
                db_exists = True
                db_path = saved_db_path
            else:
                st.warning(f"Previously configured database at {saved_db_path} no longer accessible")
        
        if not db_exists:
            # Check if default iMessage database is accessible
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
                    db_path = expanded_path
                    db_exists = True
                    
                    # Save to database
                    if st.button("Save this path for future use"):
                        AppSetting.set("imessage_db_path", expanded_path, user_id=current_user_id)
                        st.success("Database path saved for future sessions")
                else:
                    st.error(message)
                    db_exists = False
            else:
                db_path = iMessageImporter.get_database_path()
                db_exists = True
                
                # Save default path
                if st.button("Save default path for future use"):
                    AppSetting.set("imessage_db_path", db_path, user_id=current_user_id)
                    st.success("Default database path saved for future sessions")
        
        # Show database tools
        if db_exists:
            st.header("Database Tools")
            
            # Advanced schema inspection tool
            if st.button("Inspect Database Schema"):
                with st.spinner("Analyzing database structure..."):
                    try:
                        schema = iMessageImporter.inspect_schema(db_path)
                        
                        st.subheader("Database Schema")
                        
                        # Display table information in expandable sections
                        for table_name, table_info in schema["tables"].items():
                            with st.expander(f"Table: {table_name}"):
                                st.write("Columns:")
                                cols_df = pd.DataFrame(table_info["columns"])
                                st.dataframe(cols_df)
                                
                                if "sample" in table_info:
                                    st.write("Sample data:")
                                    st.json(table_info["sample"])
                    except Exception as e:
                        st.error(f"Error inspecting schema: {str(e)}")

with contacts_tab:
    st.header("Contacts Import")
    
    if platform.system() != "Darwin":
        st.warning("Contacts import is only available on macOS")
    else:
        # First check if we have contacts in the database
        contacts_in_db = 0
        if current_user_id:
            contacts_in_db = db_session.query(Contact).filter_by(user_id=current_user_id).count()
        
        if contacts_in_db > 0:
            st.success(f"Found {contacts_in_db} contacts in your database")
            
            # Load contacts from database
            if st.button("Load contacts from database"):
                with st.spinner("Loading contacts..."):
                    # Query all contacts
                    contacts = db_session.query(Contact).filter_by(user_id=current_user_id).all()
                    
                    # Reset session state contacts data
                    st.session_state.contacts_data = {
                        "phone": {},
                        "email": {},
                        "all": {}
                    }
                    
                    # Populate contacts data
                    for contact in contacts:
                        if str(contact.identifier_type) == 'phone':
                            st.session_state.contacts_data['phone'][contact.normalized_identifier] = contact.name
                        elif str(contact.identifier_type) == 'email':
                            st.session_state.contacts_data['email'][contact.normalized_identifier] = contact.name
                        st.session_state.contacts_data['all'][contact.normalized_identifier] = contact.name
                    
                    st.success(f"Loaded {len(contacts)} contacts")
            
            # Option to clear contacts
            if st.button("Clear all contacts from database", help="This will permanently delete all your saved contacts"):
                if current_user_id:
                    contacts_to_delete = db_session.query(Contact).filter_by(user_id=current_user_id).all()
                    count = len(contacts_to_delete)
                    
                    for contact in contacts_to_delete:
                        db_session.delete(contact)
                    
                    db_session.commit()
                    st.warning(f"Deleted {count} contacts from database")
                    
                    # Reset session state
                    st.session_state.contacts_data = {
                        "phone": {},
                        "email": {},
                        "all": {}
                    }
        
        # Show import options
        st.subheader("Import Options")
        
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
                    
                    expanded_path = os.path.expanduser(contacts_custom_path)
                    status, message = ContactsImporter.check_database_accessible(expanded_path)
                    
                    if status:
                        st.success(f"Successfully connected to contacts database at {expanded_path}")
                        
                        if st.button("Import Contacts From Database"):
                            with st.spinner("Importing contacts..."):
                                contacts_data = ContactsImporter.import_contacts(expanded_path)
                                
                                # Store in session state
                                st.session_state.contacts_data = contacts_data
                                
                                # Save to database if user is logged in
                                if current_user_id:
                                    # First clear existing contacts
                                    existing = db_session.query(Contact).filter_by(user_id=current_user_id).all()
                                    for contact in existing:
                                        db_session.delete(contact)
                                    
                                    # Add all new contacts
                                    new_contacts = []
                                    
                                    # Add phone contacts
                                    for phone, name in contacts_data.get('phone', {}).items():
                                        contact = Contact(
                                            name=name,
                                            identifier=phone,
                                            identifier_type='phone',
                                            normalized_identifier=phone,
                                            user_id=current_user_id
                                        )
                                        new_contacts.append(contact)
                                    
                                    # Add email contacts
                                    for email, name in contacts_data.get('email', {}).items():
                                        contact = Contact(
                                            name=name,
                                            identifier=email,
                                            identifier_type='email',
                                            normalized_identifier=email.lower(),
                                            user_id=current_user_id
                                        )
                                        new_contacts.append(contact)
                                    
                                    # Commit to database
                                    db_session.add_all(new_contacts)
                                    db_session.commit()
                                    
                                    st.success(f"Imported {len(new_contacts)} contacts to database")
                                else:
                                    st.success(f"Imported {len(contacts_data['all'])} contacts to session")
                                    st.warning("Log in to save contacts permanently")
                    else:
                        st.error(message)
            else:
                # Default path accessible
                if st.button("Import Contacts"):
                    with st.spinner("Importing contacts..."):
                        contacts_data = ContactsImporter.import_contacts()
                        
                        # Store in session state
                        st.session_state.contacts_data = contacts_data
                        
                        total_contacts = len(contacts_data.get('all', {}))
                        
                        # Save to database if user is logged in
                        if current_user_id and total_contacts > 0:
                            # First clear existing contacts
                            existing = db_session.query(Contact).filter_by(user_id=current_user_id).all()
                            for contact in existing:
                                db_session.delete(contact)
                            db_session.commit()
                            
                            # Add all new contacts
                            new_contacts = []
                            
                            # Add phone contacts
                            for phone, name in contacts_data.get('phone', {}).items():
                                contact = Contact(
                                    name=name,
                                    identifier=phone,
                                    identifier_type='phone',
                                    normalized_identifier=phone,
                                    user_id=current_user_id
                                )
                                new_contacts.append(contact)
                            
                            # Add email contacts
                            for email, name in contacts_data.get('email', {}).items():
                                contact = Contact(
                                    name=name,
                                    identifier=email,
                                    identifier_type='email',
                                    normalized_identifier=email.lower(),
                                    user_id=current_user_id
                                )
                                new_contacts.append(contact)
                            
                            # Commit to database
                            db_session.add_all(new_contacts)
                            db_session.commit()
                            
                            st.success(f"Imported {len(new_contacts)} contacts to database")
                        else:
                            st.success(f"Imported {total_contacts} contacts to session")
                            if not current_user_id:
                                st.warning("Log in to save contacts permanently")
        
        with contacts_manual_tab:
            st.markdown("### Add Individual Contacts")
            
            # Initialize manual contacts list if needed
            if 'manual_contacts' not in st.session_state:
                st.session_state.manual_contacts = []
            
            # Form for adding a contact
            contact_name = st.text_input("Contact Name", key="manual_contact_name")
            contact_identifier = st.text_input("Phone Number or Email", key="manual_contact_identifier")
            
            if st.button("Add Contact"):
                if contact_name and contact_identifier:
                    # Add to manual list
                    st.session_state.manual_contacts.append({
                        "name": contact_name,
                        "identifier": contact_identifier
                    })
                    
                    # Initialize contacts_data if needed
                    if not st.session_state.contacts_data:
                        st.session_state.contacts_data = {
                            "phone": {},
                            "email": {},
                            "all": {}
                        }
                    
                    # Determine if it's a phone or email
                    if '@' in contact_identifier:
                        identifier_type = 'email'
                        normalized = contact_identifier.lower()
                        st.session_state.contacts_data['email'][normalized] = contact_name
                    else:
                        identifier_type = 'phone'
                        # Normalize phone number
                        normalized = ''.join(c for c in contact_identifier if c.isdigit())
                        st.session_state.contacts_data['phone'][normalized] = contact_name
                    
                    # Add to the 'all' category
                    st.session_state.contacts_data['all'][normalized] = contact_name
                    
                    # Save to database if user is logged in
                    if current_user_id:
                        # Check if contact already exists
                        existing = db_session.query(Contact).filter_by(
                            user_id=current_user_id, 
                            normalized_identifier=normalized
                        ).first()
                        
                        if not existing:
                            contact = Contact(
                                name=contact_name,
                                identifier=contact_identifier,
                                identifier_type=identifier_type,
                                normalized_identifier=normalized,
                                user_id=current_user_id
                            )
                            db_session.add(contact)
                            db_session.commit()
                            st.success(f"Added contact to database: {contact_name}")
                        else:
                            # Update existing contact
                            existing.name = contact_name
                            existing.identifier = contact_identifier
                            db_session.commit()
                            st.success(f"Updated existing contact: {contact_name}")
                    else:
                        st.success(f"Added contact: {contact_name}")
                        st.warning("Log in to save contacts permanently")
                    
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
                            # Get normalized identifier
                            contact_id = contact["identifier"]
                            if '@' in contact_id:
                                normalized = contact_id.lower()
                            else:
                                normalized = ''.join(c for c in contact_id if c.isdigit())
                            
                            # Remove from manual list
                            st.session_state.manual_contacts.pop(i)
                            
                            # Also remove from contacts data
                            if normalized in st.session_state.contacts_data['all']:
                                del st.session_state.contacts_data['all'][normalized]
                                
                                if '@' in contact_id:
                                    if normalized in st.session_state.contacts_data['email']:
                                        del st.session_state.contacts_data['email'][normalized]
                                else:
                                    if normalized in st.session_state.contacts_data['phone']:
                                        del st.session_state.contacts_data['phone'][normalized]
                            
                            # Remove from database if logged in
                            if current_user_id:
                                existing = db_session.query(Contact).filter_by(
                                    user_id=current_user_id, 
                                    normalized_identifier=normalized
                                ).first()
                                
                                if existing:
                                    db_session.delete(existing)
                                    db_session.commit()
                            
                            st.rerun()

        # Display contact stats
        if st.session_state.contacts_data and st.session_state.contacts_data['all']:
            st.subheader("Contacts Summary")
            st.write(f"Total contacts: {len(st.session_state.contacts_data['all'])}")
            st.write(f"Phone contacts: {len(st.session_state.contacts_data['phone'])}")
            st.write(f"Email contacts: {len(st.session_state.contacts_data['email'])}")
            
            # Show sample contacts
            with st.expander("Show sample contacts"):
                sample_size = min(5, len(st.session_state.contacts_data['all']))
                sample = list(st.session_state.contacts_data['all'].items())[:sample_size]
                
                for identifier, name in sample:
                    st.write(f"{name}: {identifier}")
