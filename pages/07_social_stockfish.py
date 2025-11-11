import streamlit as st
import json
import os
import platform
import traceback
from typing import List

# Import models and skills
from src.models import db_session, User # type: ignore
from src.skills.email_skill import OAuthCredential # type: ignore
from src.skills.zettel import Zettel # type: ignore
from src.skills.interest import OpenQuestion # type: ignore
from src.skills.social_stockfish.social_stockfish_skill import SocialStockfishSkill
from src.skills.social_stockfish.contacts_import import ContactsImportDict
from src.skills.social_stockfish.models import Contact
from src.skills.social_stockfish.imessage_import import iMessageImporter
from src.models import AppSetting

# Initialize session state variables
if 'conversation_data' not in st.session_state:
    st.session_state.conversation_data = None
if 'objectives' not in st.session_state:
    st.session_state.objectives = []
if 'simulated_branches' not in st.session_state:
    st.session_state.simulated_branches = []
if 'selected_branch' not in st.session_state:
    st.session_state.selected_branch = None
if 'contacts_data' not in st.session_state:
    contacts_data: ContactsImportDict = {
        "phone": {},
        "email": {},
        "all": {}
    }
    st.session_state.contacts_data = contacts_data
if 'manual_contacts' not in st.session_state:
    st.session_state.manual_contacts = []

# Load saved contacts and database path
def load_saved_contacts():
    """Load contacts from the database into session state"""
    if 'contacts_data' not in st.session_state or not st.session_state.contacts_data.get('all'):
        # Get current user
        current_user_id = 1
        try:
            if 'current_user' in st.session_state and st.session_state.current_user:
                current_user_id = st.session_state.current_user.id
        except:
            pass

        # Check if contacts exist in the database
        contacts_in_db = db_session.query(Contact).filter_by(user_id=current_user_id).count()

        if contacts_in_db > 0:
            # Initialize contacts data structure if needed
            if 'contacts_data' not in st.session_state:
                st.session_state.contacts_data = {
                    "phone": {},
                    "email": {},
                    "all": {}
                }

            # Load contacts from database
            contacts = db_session.query(Contact).filter_by(user_id=current_user_id).all()

            # Populate contacts into session state
            for contact in contacts:
                normalized = contact.normalized_identifier
                name = contact.name

                # Add to the appropriate category
                if str(contact.identifier_type) == 'phone':
                    st.session_state.contacts_data['phone'][normalized] = name
                elif str(contact.identifier_type) == 'email':
                    st.session_state.contacts_data['email'][normalized] = name

                # Add to the 'all' category
                st.session_state.contacts_data['all'][normalized] = name

            return True
    return False

# Load contacts into session state if not already loaded
contacts_loaded = load_saved_contacts()

st.title("Social Stockfish")
st.divider()

tab1, tab2 = st.tabs(["Conversation History", "Conversation Simulation"])

with tab1:
    st.header("Conversation History")

    # Create subtabs for different conversation sources
    conv_tab1, conv_tab2, conv_tab3 = st.tabs(["View Conversation", "iMessage Import", "Contacts"])

    with conv_tab1:
        # This is the original conversation display code
        if not st.session_state.conversation_data:
            st.info("Upload a conversation file or import from iMessage to get started.")
        else:
            for i, message in enumerate(st.session_state.conversation_data):
                sender_name = message.get("sender_name", "Unknown")
                
                # Determine message styling based on role
                if sender_name == "Me":
                    # Right-aligned for the user's messages
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
                        <div style="background-color: #e6f7ff; border-radius: 15px; padding: 10px; max-width: 70%;">
                            <p style="margin: 0; font-weight: bold; color: #000000;">{sender_name}</p>
                            <p style="margin: 0; color: #000000;">{message['content']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Left-aligned for others' messages
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-start; margin-bottom: 10px;">
                        <div style="background-color: #f0f0f0; border-radius: 15px; padding: 10px; max-width: 70%;">
                            <p style="margin: 0; font-weight: bold; color: #000000;">{sender_name}</p>
                            <p style="margin: 0; color: #000000;">{message['content']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    with conv_tab2:
        st.subheader("Import from iMessages")

        if platform.system() != "Darwin":
            st.warning("iMessage import is only available on macOS")
        else:
            # Get current user
            current_user_id = 1

            # Check for saved database path
            saved_db_path = AppSetting.get("imessage_db_path", user_id=None)
            db_exists = False
            db_path = None

            if saved_db_path:
                # Check if the saved path still exists
                expanded_path = os.path.expanduser(saved_db_path)
                if os.path.exists(expanded_path):
                    st.success(f"Using configured iMessage database")
                    db_exists = True
                    db_path = expanded_path
                else:
                    st.warning(f"Previously configured database is no longer accessible. Please go to iMessage Import page to set it up.")
            else:
                # Check if default iMessage database is accessible
                db_status, db_message = iMessageImporter.check_database_accessible()

                if db_status:
                    db_path = iMessageImporter.get_database_path()
                    db_exists = True
                    st.success("Using default iMessage database")
                else:
                    st.error(f"No iMessage database configured. Please go to iMessage Import page to set it up.")

            if db_exists and db_path:
                with st.spinner("Loading conversations..."):
                    conversations = iMessageImporter.list_conversations(db_path)

                if not conversations:
                    st.warning("No conversations found in iMessage database")
                else:
                    st.subheader("Filter Conversations")
                    filter_col1, filter_col2, filter_col3 = st.columns(3)

                    with filter_col1:
                        show_contacts = st.checkbox("Show direct messages with contacts", value=True,
                                                  help="Show one-on-one conversations with people in your contacts")

                    with filter_col2:
                        show_non_contacts = st.checkbox("Show direct messages with non-contacts", value=False,
                                                      help="Show one-on-one conversations with numbers/emails not in your contacts")

                    with filter_col3:
                        show_groups = st.checkbox("Show group chats", value=True,
                                                help="Show conversations with multiple participants")

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
                        elif st.session_state.contacts_data and conv['participants'] is not None:
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

                    # Create a formatted list of conversation options with better names
                    conversation_options: List[str] = []
                    for c in sorted(conversations, key=lambda x: x['last_message'], reverse=True):
                        if not st.session_state.contacts_data:
                            # Format the display name with message count and date
                            name = c['name']
                        else:
                            formatted_id = iMessageImporter.normalized_identifier(c['identifier'])
                            name = st.session_state.contacts_data['all'].get(formatted_id, c['name'])

                        # Add the message count
                        msg_info = f"{c['message_count']} messages"

                        option_display = f"{name} ({msg_info})"
                        conversation_options.append(option_display)

                    if conversation_options:
                        selected_conv_idx = st.selectbox(
                            "Select conversation:",
                            range(len(conversations)),
                            format_func=lambda i: conversation_options[i]
                        )

                        selected_conv = conversations[selected_conv_idx]

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
                                imported_convo = iMessageImporter.import_conversation(
                                    int(selected_conv["id"]),
                                    limit=msg_limit,
                                    db_path=db_path,
                                    contacts=st.session_state.contacts_data['all'],
                                    start_from_recent=start_from_recent
                                )
                                messages = imported_convo['messages']
                                handles = imported_convo['handles']

                                if messages:
                                    st.session_state.conversation_data = messages
                                    st.success(f"Imported {len(messages)} messages!")
                                    st.rerun()
                                else:
                                    st.error("No messages found or error importing conversation")
                                    st.info("Check your terminal/console for detailed error messages.")
                                    

    with conv_tab3:
        st.subheader("Contacts")

        if 'contacts_data' in st.session_state and st.session_state.contacts_data and st.session_state.contacts_data['all']:
            st.success(f"Using {len(st.session_state.contacts_data['all'])} contacts from your database")

            st.write(f"Phone contacts: {len(st.session_state.contacts_data['phone'])}")
            st.write(f"Email contacts: {len(st.session_state.contacts_data['email'])}")

            st.write("To manage your contacts, go to the [iMessage & Contact Import](/iMessage_Import) page.")

            with st.expander("View Sample Contacts"):
                sample_size = min(10, len(st.session_state.contacts_data['all']))
                sample = list(st.session_state.contacts_data['all'].items())[:sample_size]

                for name, identifier in sample:
                    st.write(f"**{name}**: {identifier}")
        else:
            st.warning("No contacts loaded. Please import your contacts on the [iMessage & Contact Import](/iMessage_Import) page.")
            if st.button("Reload Contacts"):
                load_saved_contacts()
                st.rerun()

with tab2:
    st.header("Conversation Simulation")

    st.subheader("Objective")
    if 'objective' not in st.session_state:
        st.session_state.objective = ""

    st.session_state.objective = st.text_area(
        "What do you want to achieve with this conversation?",
        value=st.session_state.objective,
        help="Be specific about your goals. For example: 'Convince my friend to join me for a weekend trip' or 'Resolve a misunderstanding with my colleague'"
    )

    st.subheader("Constraints")
    if 'constraints' not in st.session_state:
        st.session_state.constraints = ""

    st.session_state.constraints = st.text_area(
        "What constraints should the simulation consider?",
        value=st.session_state.constraints,
        help="Note any limitations or contextual factors. For example: 'This person is very busy' or 'We have a history of disagreements on this topic'"
    )

    st.subheader("Simulation Settings")

    if not st.session_state.conversation_data:
        st.warning("Please upload conversation data first.")
    elif not st.session_state.objective:
        st.warning("Please define an objective for the conversation.")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            num_branches = st.number_input("Number of branches", min_value=2, max_value=5, value=3)

        with col2:
            branch_depth = st.number_input("Branch depth", min_value=1, max_value=9, value=2,
                                          help="Number of back-and-forth exchanges to simulate")

        with col3:
            model = st.selectbox("Model", ["claude-3-5-haiku-latest", "claude-3-7-sonnet-latest"],
                                index=1)

        if st.button("Generate Alternative Branches"):
            with st.spinner("Simulating alternative conversation branches..."):
                try:
                    # TODO: change to adhere to MessageDict (especially sender_name and populate it from identifier)
                    conversation_data = st.session_state.conversation_data

                    social_stockfish_skill = SocialStockfishSkill(
                        conversation_data,
                        model=model,
                        contacts_data=st.session_state.contacts_data['all']
                    )
                    convo_sim_analysis = social_stockfish_skill.analyze_conversation(
                        objective=st.session_state.objective,
                        constraints=st.session_state.constraints,
                        num_branches=num_branches,
                        branch_depth=branch_depth,
                    )

                    # Check if there was an error
                    if "error" in convo_sim_analysis:
                        st.error(f"Error generating branches: {convo_sim_analysis['error']}")
                        with st.expander("Show detailed error information"):
                            st.code(convo_sim_analysis['traceback'])
                        st.warning("You can try reducing the branch depth, using a different model, or simplifying the conversation.")
                    else:
                        # Store the results in session state
                        approaches = convo_sim_analysis["approaches"]
                        
                        # Create simulated branches from the results
                        st.session_state.simulated_branches = convo_sim_analysis["approaches"]

                        st.success("Generated alternative conversation branches!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.code(traceback.format_exc())
                    st.warning("Please try again with different settings or check the logs for more details.")

        if not st.session_state.simulated_branches and os.path.exists("simulated_branches.json"):
            # load from local json file if it exists
            print("loading simulated branches from file")
            with open("simulated_branches.json", "r") as f:
                st.session_state.simulated_branches = json.load(f)
        
        if st.session_state.simulated_branches and not os.path.exists("simulated_branches.json"):
            # save to local json file
            print("saving simulated branches to file")
            with open("simulated_branches.json", "w") as f:
                json.dump(st.session_state.simulated_branches, f)
        
        # Display branches
        if st.session_state.simulated_branches:
            st.subheader("Simulated Conversation Branches")

            # Display branches in order of score
            sorted_branches = sorted(
                st.session_state.simulated_branches,
                key=lambda b: b["success_likelihood"],
                reverse=True
            )

            for branch in sorted_branches:
                with st.expander(
                    f"{branch['description']} (Success Likelihood: {branch['success_likelihood']:.1%})",
                    expanded=False  # All branches start collapsed
                ):
                    # Display approach description
                    st.markdown("**Approach:**")
                    st.markdown(branch["description"])
                    st.divider()
                    
                    # Display simulated conversation nodes
                    if "simulated_conversation_nodes" in branch:
                        st.markdown("### Simulated Exchanges")
                        with st.chat_message("Me"):
                            st.markdown(branch["first_message"])
                        for i, node in enumerate(reversed(branch["simulated_conversation_nodes"])):
                            # st.markdown(f"#### Exchange {i+1}")
                            print("node: ", node)
                            
                            # Display new messages in this exchange
                            for message in node["new_simulated_messages"]:
                                print("message: ", message)
                                with st.chat_message(message["sender_name"]):
                                    st.markdown(message["content"])
                                    
                                    # Display evaluation for this message
                                    eval_data = node["evaluation"]
                                    st.markdown("**Exchange Evaluation:**")
                                    metrics_col1, metrics_col2 = st.columns(2)
                                    with metrics_col1:
                                        st.metric(
                                            "Success Likelihood", 
                                            f"{eval_data['success_likelihood']:.1%}"
                                        )
                                    with metrics_col2:
                                        st.metric(
                                            "Constraint Compliance",
                                            "✅" if eval_data["constraint_compliance"] else "❌"
                                        )
                                    
                                    if eval_data.get("side_effects"):
                                        st.info(f"**Potential Side Effects:** {eval_data['side_effects']}")
