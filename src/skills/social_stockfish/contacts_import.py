import os
import sqlite3
import traceback
from typing import Dict, Optional, Tuple, TypedDict
from src.skills.social_stockfish.models import Contact

class ContactsImportDict(TypedDict):
    all: Dict[str, str]
    phone: Dict[str, str]
    email: Dict[str, str]


class ContactsImporter:
    """
    Utility class to import macOS contacts and match them with iMessage conversations.
    """
    
    @classmethod
    def get_database_path(cls) -> str:
        """Returns the default path to the Contacts database on macOS"""
        # Try both possible locations - the exact path can vary by macOS version
        paths = [
            os.path.expanduser("~/Library/Application Support/AddressBook/AddressBook-v22.abcddb"),
            os.path.expanduser("~/Library/Application Support/AddressBook/Sources"),
            os.path.expanduser("~/Library/Application Support/ContactsAgent")
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
                
        # Return default path even if it doesn't exist
        return paths[0]
    
    @classmethod
    def check_database_accessible(cls, db_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Checks if the Contacts database is accessible.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            Tuple of (success, message)
        """
        path = db_path or cls.get_database_path()
        
        if not os.path.exists(path):
            return False, f"Contacts database not found at {path}"
        
        # AddressBook might be a directory with multiple sources
        if os.path.isdir(path):
            # Check if we can list files
            try:
                files = os.listdir(path)
                if not files:
                    return False, "Contacts directory exists but is empty or can't be read"
                # Look for SQLite files
                sqlite_files = [f for f in files if f.endswith('.abcddb') or f.endswith('.sqlite')]
                if not sqlite_files:
                    return False, "No contact database files found in directory"
                return True, f"Contacts directory accessible with {len(sqlite_files)} database files"
            except PermissionError:
                return False, "Cannot access contacts directory due to permission restrictions"
        
        # Regular file
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            conn.close()
            return True, "Contacts database is accessible"
        except sqlite3.Error as e:
            # Provide more detailed guidance about permissions
            error_msg = f"Error accessing contacts database: {str(e)}"
            help_msg = "\n\nMacOS strictly protects contacts data. You have these options:\n\n"
            help_msg += "1. Grant Full Disk Access:\n"
            help_msg += "   • Go to System Settings > Privacy & Security > Full Disk Access\n"
            help_msg += "   • Add Terminal (or VS Code/your IDE) to the allowed apps\n\n"
            help_msg += "2. Copy the database manually:\n"
            help_msg += "   • Open Finder, press Cmd+Shift+G, enter ~/Library/Application Support/AddressBook/\n"
            help_msg += "   • Copy AddressBook-v22.abcddb to your Documents folder\n"
            help_msg += "   • Use that copy's path here\n\n"
            help_msg += "3. Manually enter contact mappings in the 'Manual Contacts' option"
            
            return False, error_msg + help_msg
    
    @classmethod
    def copy_database(cls, target_path: str) -> Tuple[bool, str]:
        """
        Creates a copy of the Contacts database that might be easier to access.
        
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
            
            # Handle directory vs file
            if os.path.isdir(source_path):
                shutil.copytree(source_path, target_path)
                return True, f"Contacts directory copied successfully to {target_path}"
            else:
                # Copy the file
                shutil.copy2(source_path, target_path)
                return True, f"Contacts database copied successfully to {target_path}"
        except Exception as e:
            # Provide specific guidance for permission errors
            error_msg = f"Error copying database: {str(e)}"
            if "Operation not permitted" in str(e):
                help_msg = "\n\nThis is due to macOS security restrictions. Please try these steps instead:\n\n"
                help_msg += "1. Open Finder\n"
                help_msg += "2. Press Cmd+Shift+G and enter: ~/Library/Application Support/AddressBook/\n"
                help_msg += "3. Copy contacts files manually to your Documents folder\n"
                help_msg += "4. Then enter the path to your copied file in the 'Custom database path' field"
                return False, error_msg + help_msg
            return False, error_msg
    
    @classmethod
    def import_contacts(cls, db_path: Optional[str] = None) -> ContactsImportDict:
        """
        Imports contacts from the Address Book database.
        
        Args:
            db_path: Optional custom path to the database
            
        Returns:
            Dictionary mapping phone numbers and emails to contact names
        """
        path = db_path or cls.get_database_path()
        contacts: ContactsImportDict = {
            "phone": {},  # Maps phone numbers to names
            "email": {},  # Maps emails to names
            "all": {}     # Maps all identifiers to names
        }
        
        if not os.path.exists(path):
            return contacts
            
        # This is complex as different macOS versions store contacts differently
        # and the schema changes
        if os.path.isdir(path):
            # Try to find SQLite databases in the directory
            try:
                for root, _dirs, files in os.walk(path):
                    for file in files:
                        if file.endswith('.abcddb') or file.endswith('.sqlite'):
                            db_file = os.path.join(root, file)
                            try:
                                # Try to extract contacts from each database file
                                cls._extract_contacts_from_db(db_file, contacts)
                            except Exception as e:
                                print(f"Error processing {db_file}: {str(e)}")
            except Exception as e:
                print(f"Error walking contacts directory: {str(e)}")
        else:
            # Direct database file
            try:
                cls._extract_contacts_from_db(path, contacts)
            except Exception as e:
                print(f"Error extracting contacts: {str(e)}")
                
        print(f"Imported {len(contacts['all'])} contacts with {len(contacts['phone'])} phone numbers and {len(contacts['email'])} emails")
        return contacts
    
    @classmethod
    def _extract_contacts_from_db(cls, db_path: str, contacts: ContactsImportDict) -> None:
        """
        Extracts contacts from a specific database file.
        Updates the contacts dictionary in place.
        
        Args:
            db_path: Path to the database file
            contacts: Contacts dictionary to update
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check tables in this database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Different versions of the Contacts database have different schemas
            # Try several common schemas
            
            # Schema version 1: Modern Contacts app
            if 'ZABCDRECORD' in tables and 'ZABCDPHONENUMBER' in tables:
                # Extract names
                try:
                    cursor.execute("""
                        SELECT 
                            r.ZFIRSTNAME, 
                            r.ZLASTNAME, 
                            p.ZFULLNUMBER 
                        FROM 
                            ZABCDRECORD r
                        JOIN 
                            ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
                        WHERE 
                            r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL
                    """)
                    
                    for row in cursor.fetchall():
                        first_name, last_name, phone = row
                        name = f"{first_name or ''} {last_name or ''}".strip()
                        if name and phone:
                            # Normalize phone number
                            phone = Contact.normalize_identifier(phone, 'phone')
                            contacts['phone'][phone] = name
                            contacts['all'][phone] = name
                except Exception as e:
                    print(f"Error extracting phone numbers (schema 1): {str(e)}")
                
                # Extract emails
                try:
                    cursor.execute("""
                        SELECT 
                            r.ZFIRSTNAME, 
                            r.ZLASTNAME, 
                            e.ZADDRESS 
                        FROM 
                            ZABCDRECORD r
                        JOIN 
                            ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
                        WHERE 
                            (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL)
                            AND e.ZADDRESS IS NOT NULL
                    """)
                    
                    for row in cursor.fetchall():
                        first_name, last_name, email = row
                        name = f"{first_name or ''} {last_name or ''}".strip()
                        if name and email:
                            email = Contact.normalize_identifier(email, 'email')
                            contacts['email'][email] = name
                            contacts['all'][email] = name
                except Exception as e:
                    print(f"Error extracting emails (schema 1): {str(e)}")
            
            # Schema version 2: Older Address Book
            elif 'ABPerson' in tables and 'ABMultiValue' in tables:
                try:
                    cursor.execute("""
                        SELECT 
                            p.First, 
                            p.Last, 
                            m.value 
                        FROM 
                            ABPerson p
                        JOIN 
                            ABMultiValue m ON m.record_id = p.ROWID
                        WHERE 
                            m.label = 3  -- Phone numbers
                    """)
                    
                    for row in cursor.fetchall():
                        first_name, last_name, phone = row
                        name = f"{first_name or ''} {last_name or ''}".strip()
                        if name and phone:
                            phone = Contact.normalize_identifier(phone, 'phone')
                            contacts['phone'][phone] = name
                            contacts['all'][phone] = name
                except Exception as e:
                    print(f"Error extracting phone numbers (schema 2): {str(e)}")
                
                # Extract emails
                try:
                    cursor.execute("""
                        SELECT 
                            p.First, 
                            p.Last, 
                            m.value 
                        FROM 
                            ABPerson p
                        JOIN 
                            ABMultiValue m ON m.record_id = p.ROWID
                        WHERE 
                            m.label = 4  -- Email addresses
                    """)
                    
                    for row in cursor.fetchall():
                        first_name, last_name, email = row
                        name = f"{first_name or ''} {last_name or ''}".strip()
                        if name and email:
                            contacts['email'][email.lower()] = name
                            contacts['all'][email.lower()] = name
                except Exception as e:
                    print(f"Error extracting emails (schema 2): {str(e)}")
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            traceback.print_exc()
    
    @classmethod
    def _normalize_phone(cls, phone: str) -> str:
        """Normalize a phone number for better matching"""
        # Remove non-numeric characters
        digits = ''.join(c for c in phone if c.isdigit())
        
        # Handle US numbers with/without country code
        if len(digits) == 10:
            return digits
        elif len(digits) == 11 and digits.startswith('1'):
            return digits[1:]  # Strip leading 1 for US numbers
        
        return digits 