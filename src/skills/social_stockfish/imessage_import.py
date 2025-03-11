import os
import sqlite3
import datetime
from typing import List, Dict, Optional, Tuple, Any
import traceback

class iMessageImporter:
    """
    Utility class to import conversations from macOS iMessage database.
    """
    
    @classmethod
    def get_database_path(cls) -> str:
        """Returns the default path to the iMessage database on macOS"""
        return os.path.expanduser("~/Library/Messages/chat.db")
    
    @classmethod
    def check_database_accessible(cls, db_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Checks if the iMessage database is accessible.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            Tuple of (success, message)
        """
        path = db_path or cls.get_database_path()
        
        if not os.path.exists(path):
            return False, f"iMessage database not found at {path}"
        
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            conn.close()
            return True, "iMessage database is accessible"
        except sqlite3.Error as e:
            # Provide more detailed guidance about permissions
            error_msg = f"Error accessing iMessage database: {str(e)}"
            help_msg = "\n\nMacOS strictly protects message data. You have these options:\n\n"
            help_msg += "1. Grant Full Disk Access:\n"
            help_msg += "   • Go to System Settings > Privacy & Security > Full Disk Access\n"
            help_msg += "   • Add Terminal (or VS Code/your IDE) to the allowed apps\n\n"
            help_msg += "2. Copy the database manually:\n"
            help_msg += "   • Open Finder, press Cmd+Shift+G, enter ~/Library/Messages/\n"
            help_msg += "   • Copy chat.db to your Documents folder\n"
            help_msg += "   • Use that copy's path here\n\n"
            help_msg += "3. Use the 'Manual Export' tab to paste messages directly"
            
            return False, error_msg + help_msg
    
    @classmethod
    def normalized_identifier(cls, identifier: str) -> str:
        """Normalize the identifier to remove special characters and format"""
        return identifier.replace("-", "").replace("+1", "")

    @classmethod
    def list_conversations(cls, db_path: Optional[str] = None) -> List[Dict]:
        """
        Lists available conversations in the iMessage database.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            List of conversation dictionaries
        """
        path = db_path or cls.get_database_path()
        conversations = []
        
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Query to get conversations with the most recent messages first
            # Include chat identifiers and display names for better labeling
            query = """
            SELECT 
                c.ROWID as conversation_id,
                c.display_name,
                c.chat_identifier,
                MAX(m.date) as last_message_date,
                COUNT(m.ROWID) as message_count,
                GROUP_CONCAT(DISTINCT h.id) as participants
            FROM 
                chat as c
            JOIN 
                chat_message_join as cmj ON c.ROWID = cmj.chat_id
            JOIN 
                message as m ON cmj.message_id = m.ROWID
            LEFT JOIN
                handle as h ON m.handle_id = h.ROWID
            GROUP BY 
                c.ROWID
            ORDER BY 
                last_message_date DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                try:
                    conv_id, display_name, chat_identifier, last_message_date, message_count, participants = row
                    
                    # Format timestamp as before
                    date_str = cls._format_timestamp(last_message_date)
                    
                    # Create a more user-friendly name for the conversation
                    name = cls._format_conversation_name(display_name, chat_identifier, participants)
                    
                    conversations.append({
                        "id": conv_id,
                        "name": name,
                        "identifier": chat_identifier,
                        "last_message": date_str,
                        "message_count": message_count,
                        "raw_display_name": display_name,
                        "participants": participants.split(',') if participants else []
                    })
                except Exception as e:
                    print(f"Error processing conversation row: {str(e)}")
                    # Try simplified row handling
                    conv_id = row[0]
                    message_count = row[4] if len(row) > 4 else 0
                    conversations.append({
                        "id": conv_id,
                        "name": f"Conversation {conv_id}",
                        "identifier": f"Unknown-{conv_id}",
                        "last_message": "Unknown date",
                        "message_count": message_count
                    })
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error accessing conversations: {str(e)}")
            traceback.print_exc()
            
        return conversations
    
    @classmethod
    def _format_timestamp(cls, timestamp) -> str:
        """Format a timestamp from the iMessage database into a readable date string"""
        try:
            if timestamp:
                # Try multiple conversion methods
                try:
                    # Standard macOS timestamp (microseconds since 2001-01-01)
                    unix_timestamp = (timestamp / 1000000) + 978307200
                    date_str = datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, OverflowError):
                    # Try nanoseconds
                    try:
                        unix_timestamp = (timestamp / 1000000000) + 978307200
                        date_str = datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, OverflowError):
                        # Fall back to showing the raw timestamp
                        date_str = f"Raw timestamp: {timestamp}"
            else:
                date_str = "Unknown"
        except Exception:
            date_str = f"Raw timestamp: {timestamp}"
        
        return date_str
    
    @classmethod
    def _format_conversation_name(cls, display_name, chat_identifier, participants) -> str:
        """Format a user-friendly name for the conversation"""
        # If there's a display name, use it
        if display_name:
            return display_name
        
        # For iMessage emails and phone numbers, format them nicely
        if chat_identifier:
            # Handle phone numbers - try to format with dashes
            if chat_identifier.isdigit() or (chat_identifier.startswith('+') and chat_identifier[1:].isdigit()):
                # Format phone numbers in a standard way if possible
                if len(chat_identifier) == 10 and chat_identifier.isdigit():  # US format
                    return f"{chat_identifier[:3]}-{chat_identifier[3:6]}-{chat_identifier[6:]}"
                elif chat_identifier.startswith('+1') and len(chat_identifier) == 12:  # US with country code
                    return f"{chat_identifier[2:5]}-{chat_identifier[5:8]}-{chat_identifier[8:]}"
            
            # If it's an email, just use it directly
            if '@' in chat_identifier:
                return chat_identifier
            
            # For iMessage phone numbers sometimes the format is different
            if ';-;' in chat_identifier:
                parts = chat_identifier.split(';-;')
                if parts and parts[0]:
                    return parts[0]
        
        # Try to get participant information if available
        if participants:
            participant_list = participants.split(',')
            # Filter out empty or None values
            participant_list = [p for p in participant_list if p]
            
            if len(participant_list) == 1:
                # Single participant - format the phone/email
                p = participant_list[0]
                if '@' in p:
                    return p  # Email address
                
                # Format phone number if possible
                if p.isdigit() and len(p) == 10:  # US format
                    return f"{p[:3]}-{p[3:6]}-{p[6:]}"
                
                return p
            elif len(participant_list) > 1:
                # Group chat - show number of participants
                return f"Group Chat ({len(participant_list)} participants)"
        
        # Fallback
        return f"Chat {chat_identifier or 'Unknown'}"
    
    @classmethod
    def import_conversation(cls, conversation_id: int, db_path: Optional[str] = None, 
                           limit: int = 100, contacts: Optional[Dict] = None,
                           start_from_recent: bool = False) -> List[Dict[str, str]]:
        """
        Imports messages from a specific conversation.
        
        Args:
            conversation_id: ID of the conversation to import
            db_path: Optional custom path to the database
            limit: Maximum number of messages to import
            contacts: Optional contacts data for name resolution
            start_from_recent: If True, start from most recent messages, otherwise from oldest
            
        Returns:
            List of messages in the format expected by Social Stockfish
        """
        path = db_path or cls.get_database_path()
        messages = []
        sender_names = {}
        handles = []  # Initialize handles list
        
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Enable more verbose error reporting
            conn.set_trace_callback(print)
            
            # First, verify that the conversation exists
            verify_query = "SELECT ROWID, display_name FROM chat WHERE ROWID = ?"
            cursor.execute(verify_query, (conversation_id,))
            conv_row = cursor.fetchone()
            
            if not conv_row:
                print(f"Warning: Conversation with ID {conversation_id} not found")
                return []
            
            print(f"Found conversation: {conv_row}")
            
            # Get chat name/identifier for conversation
            chat_name = conv_row[1] or "Unknown"
            
            # Get the handles associated with this conversation
            try:
                cursor.execute("""
                    SELECT DISTINCT h.ROWID, h.id 
                    FROM handle h
                    JOIN message m ON h.ROWID = m.handle_id
                    JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                    WHERE cmj.chat_id = ?
                """, (conversation_id,))
                
                handles = cursor.fetchall()
                print(f"Found {len(handles)} unique handles in conversation")
                
                # Initialize sender names based on handles
                for handle_id, handle in handles:
                    if handle:
                        sender_names[handle] = handle  # Default to using the handle itself
            except sqlite3.Error as e:
                print(f"Could not get handles: {str(e)}")
            
            # Default names if we can't get specific ones
            sender_names["me"] = "Me"
            sender_names["other"] = chat_name if chat_name != "Unknown" else "Other Person"
            
            # Check schema to adapt our query
            cursor.execute("PRAGMA table_info(message)")
            message_cols = [col[1] for col in cursor.fetchall()]
            
            # Try to get all messages from this conversation with sender info
            try:
                # Determine sort order based on start_from_recent parameter
                sort_order = "DESC" if start_from_recent else "ASC"
                
                # Try to get handle_id for identifying the sender
                if "handle_id" in message_cols:
                    query = f"""
                    SELECT 
                        m.ROWID,
                        m.text,
                        m.is_from_me,
                        m.date,
                        m.handle_id,
                        h.id
                    FROM 
                        message as m
                    LEFT JOIN
                        handle as h ON m.handle_id = h.ROWID
                    JOIN 
                        chat_message_join as cmj ON m.ROWID = cmj.message_id
                    WHERE 
                        cmj.chat_id = ?
                    ORDER BY 
                        m.date {sort_order}
                    LIMIT ?
                    """
                    
                    cursor.execute(query, (conversation_id, limit))
                    rows = cursor.fetchall()
                    print(f"Found {len(rows)} messages in conversation {conversation_id}")
                    
                    for row in rows:
                        try:
                            msg_id, text, is_from_me, date, handle_id, handle = row
                            
                            if text is None:  # Skip messages with no text (like attachments)
                                continue
                            
                            # Determine role and sender
                            if is_from_me == 1:
                                role = "user"
                                sender = sender_names.get("me", "Me")
                            else:
                                role = "assistant"
                                sender = handle if handle else sender_names.get("other", "Other Person")
                            
                            messages.append({
                                "role": role,
                                "content": text,
                                "sender": sender,
                                "is_human": True
                            })
                        except Exception as row_e:
                            print(f"Error processing row {row}: {str(row_e)}")
                else:
                    # Fallback to simpler query without handle info
                    fallback_query = f"""
                    SELECT 
                        m.ROWID,
                        m.text,
                        m.is_from_me
                    FROM 
                        message as m
                    JOIN 
                        chat_message_join as cmj ON m.ROWID = cmj.message_id
                    WHERE 
                        cmj.chat_id = ?
                    ORDER BY
                        m.date {sort_order}
                    LIMIT ?
                    """
                    
                    cursor.execute(fallback_query, (conversation_id, limit))
                    rows = cursor.fetchall()
                    print(f"Fallback query found {len(rows)} messages")
                    
                    for row in rows:
                        try:
                            msg_id, text, is_from_me = row
                            
                            if text is None:
                                continue
                            
                            # Determine role and sender
                            if is_from_me == 1:
                                role = "user"
                                sender = sender_names.get("me", "Me")
                            else:
                                role = "assistant"
                                sender = sender_names.get("other", "Other Person")
                            
                            messages.append({
                                "role": role,
                                "content": text,
                                "sender": sender,
                                "is_human": True
                            })
                        except Exception as row_e:
                            print(f"Error processing row in fallback: {str(row_e)}")
            
            except sqlite3.Error as query_e:
                print(f"Error with queries: {str(query_e)}")
            
            # Update the sender name lookup to use contacts data
            if contacts and contacts.get('all'):
                # Look up handles in contacts
                for handle_id, handle in handles:
                    if handle:
                        # Check for phone number contact
                        if handle.isdigit() or (handle.startswith('+') and handle[1:].isdigit()):
                            # Normalize phone number
                            normalized = ''.join(c for c in handle if c.isdigit())
                            if normalized in contacts.get('phone', {}):
                                sender_names[handle] = contacts['phone'][normalized]
                                print(f"Mapped handle {handle} to contact: {contacts['phone'][normalized]}")
                        
                        # Check for email contact
                        elif '@' in handle and handle.lower() in contacts.get('email', {}):
                            sender_names[handle] = contacts['email'][handle.lower()]
                            print(f"Mapped email {handle} to contact: {contacts['email'][handle.lower()]}")
                        
                        # Direct lookup
                        elif handle in contacts.get('all', {}):
                            sender_names[handle] = contacts['all'][handle]
                            print(f"Direct mapping for {handle}: {contacts['all'][handle]}")
            
            print(f"After contact resolution, have {len(sender_names)} named senders")
            
            # If we've imported messages in reverse order, we need to reverse them back
            # for proper conversation flow
            if start_from_recent:
                messages.reverse()
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Critical error importing conversation: {str(e)}")
            traceback.print_exc()
            
        # Add debugging information
        print(f"Imported {len(messages)} messages")
        for i, msg in enumerate(messages[:3]):  # Print first 3 messages for debugging
            print(f"Message {i+1}: {msg['role']} - {msg['sender']} - {msg['content'][:50]}...")
        
        return messages

    @classmethod
    def copy_database(cls, target_path: str) -> Tuple[bool, str]:
        """
        Creates a copy of the iMessage database that might be easier to access.
        
        Args:
            target_path: Where to save the copy
            
        Returns:
            Tuple of (success, message)
        """
        source_path = cls.get_database_path()
        target_path = os.path.expanduser(target_path)
        
        if not os.path.exists(source_path):
            return False, f"Source database not found at {source_path}"
        
        try:
            import shutil
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            # Copy the file
            shutil.copy2(source_path, target_path)
            return True, f"Database copied successfully to {target_path}"
        except Exception as e:
            # Provide specific guidance for permission errors
            error_msg = f"Error copying database: {str(e)}"
            if "Operation not permitted" in str(e):
                help_msg = "\n\nThis is due to macOS security restrictions. Please try these steps instead:\n\n"
                help_msg += "1. Open Finder\n"
                help_msg += "2. Press Cmd+Shift+G and enter: ~/Library/Messages/\n"
                help_msg += "3. Copy chat.db manually to your Documents folder\n"
                help_msg += "4. Then enter the path to your copied file in the 'Custom database path' field"
                return False, error_msg + help_msg
            return False, error_msg 

    @classmethod
    def diagnose_database(cls, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Diagnoses the structure of the iMessage database and returns information
        about tables and sample data.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            Dictionary with diagnostic information
        """
        path = db_path or cls.get_database_path()
        diagnostics = {
            "tables": [],
            "sample_timestamps": [],
            "error": None
        }
        
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            diagnostics["tables"] = [t[0] for t in tables]
            
            # Check for message table and get sample timestamps
            if "message" in diagnostics["tables"]:
                cursor.execute("SELECT date FROM message ORDER BY ROWID DESC LIMIT 5")
                timestamps = cursor.fetchall()
                diagnostics["sample_timestamps"] = [t[0] for t in timestamps]
                
                # Try to interpret first timestamp with different methods
                if timestamps and timestamps[0][0]:
                    ts = timestamps[0][0]
                    interpretations = []
                    
                    # Method 1: microseconds since 2001
                    try:
                        unix_ts = (ts / 1000000) + 978307200
                        dt = datetime.datetime.fromtimestamp(unix_ts)
                        interpretations.append(f"microseconds since 2001: {dt}")
                    except:
                        pass
                    
                    # Method 2: nanoseconds since 2001
                    try:
                        unix_ts = (ts / 1000000000) + 978307200
                        dt = datetime.datetime.fromtimestamp(unix_ts)
                        interpretations.append(f"nanoseconds since 2001: {dt}")
                    except:
                        pass
                    
                    # Method 3: direct Unix timestamp (seconds since 1970)
                    try:
                        dt = datetime.datetime.fromtimestamp(ts)
                        interpretations.append(f"seconds since 1970: {dt}")
                    except:
                        pass
                    
                    # Method 4: milliseconds since 1970
                    try:
                        dt = datetime.datetime.fromtimestamp(ts / 1000)
                        interpretations.append(f"milliseconds since 1970: {dt}")
                    except:
                        pass
                    
                    diagnostics["timestamp_interpretations"] = interpretations
            
            conn.close()
            
        except Exception as e:
            diagnostics["error"] = str(e)
            traceback.print_exc()
            
        return diagnostics 

    @classmethod
    def inspect_schema(cls, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspects the database schema in detail to help with debugging.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            Dictionary with schema information
        """
        path = db_path or cls.get_database_path()
        schema = {"tables": {}, "error": None}
        
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get schema for each table
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                schema["tables"][table] = {
                    "columns": [
                        {"name": col[1], "type": col[2], "notnull": col[3], "pk": col[5]}
                        for col in columns
                    ]
                }
                
                # Get sample rows for key tables
                if table in ["message", "chat", "chat_message_join", "handle"]:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                    sample = cursor.fetchone()
                    if sample:
                        schema["tables"][table]["sample"] = {
                            col["name"]: sample[i] for i, col in enumerate(schema["tables"][table]["columns"])
                        }
            
            # Check specific relationships
            try:
                # Check join between chat and message
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM chat c
                    JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
                    JOIN message m ON cmj.message_id = m.ROWID
                    LIMIT 1
                """)
                schema["join_test"] = {"chat_message": cursor.fetchone()[0] > 0}
            except sqlite3.Error as je:
                schema["join_test"] = {"error": str(je)}
            
            conn.close()
            
        except Exception as e:
            schema["error"] = str(e)
            traceback.print_exc()
            
        return schema 