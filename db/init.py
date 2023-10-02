import sqlite3

def setup_database():
    # Create a new SQLite database or connect to it if it exists
    conn = sqlite3.connect('email_bot.db')
    cursor = conn.cursor()

    # Create the emails table with the subject field and parent foreign key
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY,
            sender TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            parent_id INTEGER,
            uid INTEGER NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES emails(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Create the documents table without the question and embedding attributes
    # but with the content attribute
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            email_id INTEGER,
            content TEXT NOT NULL,
            FOREIGN KEY (email_id) REFERENCES emails(id)
        )
        ''')

    # Create the authorized_senders table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        email_address TEXT UNIQUE NOT NULL
    )
    ''')

    # Commit changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()
