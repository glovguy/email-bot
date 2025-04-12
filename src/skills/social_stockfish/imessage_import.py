import os
import sqlite3
import datetime
from typing import List, Dict, Optional, Tuple, Any, TypedDict
import traceback

class MessageDict(TypedDict):
    """Represents a single message in the conversation"""
    content: str
    sender_name: str


class ImportedConversationDict(TypedDict):
    messages: List[MessageDict]
    handles: List[str]


class RawImportedConversationDict(TypedDict):
    id: str
    name: str
    identifier: str
    last_message: str
    message_count: int
    raw_display_name: Optional[str]
    participants: Optional[List[str]]


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
    def list_conversations(cls, db_path: Optional[str] = None) -> List[RawImportedConversationDict]:
        """
        Lists available conversations in the iMessage database.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            List of conversation dictionaries
        """
        path = db_path or cls.get_database_path()
        conversations: List[RawImportedConversationDict] = []
        
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
                        "message_count": message_count,
                        "raw_display_name": None,
                        "participants": None
                    })
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error accessing conversations: {str(e)}")
            traceback.print_exc()
            
        return conversations
    
    @classmethod
    def _format_timestamp(cls, timestamp: int) -> str:
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
    def _format_conversation_name(cls, display_name: str, chat_identifier: str, participants: str) -> str:
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
                           limit: int = 100, contacts: Optional[Dict[str, str]] = None,
                           start_from_recent: bool = False) -> ImportedConversationDict:
        """
        Imports messages from a specific conversation.
        
        Args:
            conversation_id: ID of the conversation to import
            db_path: Optional custom path to the database
            limit: Maximum number of messages to import
            contacts: Optional contacts data for name resolution
            start_from_recent: If True, start from most recent messages, otherwise from oldest
            
        Returns:
            List of messages with role, content, sender and is_human fields
        """
        path = db_path or cls.get_database_path()
        messages = []
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
                return {"messages": [], "handles": []}
            
            print(f"Found conversation: {conv_row}")
            
            # Get the handles associated with this conversation
            try:
                cursor.execute("""
                    SELECT DISTINCT h.ROWID, h.id 
                    FROM handle h
                    JOIN message m ON h.ROWID = m.handle_id
                    JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                    WHERE cmj.chat_id = ?
                """, (conversation_id,))
                
                handle_rows = cursor.fetchall()
                print(f"Found {len(handles)} unique handles in conversation")
                handles = [handle_row[1] for handle_row in handle_rows]
                
                # Initialize sender names based on handles
                # for handle_id, handle in handles:
                #     if handle:
                #         sender_names[handle] = handle  # Default to using the handle itself
            except sqlite3.Error as e:
                print(f"Could not get handles: {str(e)}")
            
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
                            _msg_id, text, is_from_me, _date, _handle_id, handle = row
                            
                            if text is None:  # Skip messages with no text (like attachments)
                                continue
                            
                            if is_from_me == 1:
                                sender_name = "Me"
                            else:
                                sender_name = contacts.get(handle, handle)
                            
                            messages.append({
                                "content": text,
                                "sender_name": sender_name,
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
                            _msg_id, text, is_from_me = row
                            
                            if text is None:
                                continue
                            
                            if is_from_me == 1:
                                sender_name = "Me"
                            else:
                                sender_name = "Other Person"
                            
                            messages.append({
                                "content": text,
                                "sender_name": sender_name,
                            })
                        except Exception as row_e:
                            print(f"Error processing row in fallback: {str(row_e)}")
            
            except sqlite3.Error as query_e:
                print(f"Error with queries: {str(query_e)}")
            
            # If we've imported messages in reverse order, we need to reverse them back
            # for proper conversation flow
            if start_from_recent:
                messages.reverse()
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Critical error importing conversation: {str(e)}")
            traceback.print_exc()
            
        return {
            "messages": messages,
            "handles": handles,
        }

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
