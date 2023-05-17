import sqlite3

class Database:
    _instance = None

    def __new__(cls, db="db.sqlite"):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self, db="db.sqlite"):
        self.db = db
        self.conn = None
        self.cursor = None

    def create_db(self):
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()

    def create_table(self):
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS conversations (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                title TEXT NOT NULL,
                                group_id INTEGER NOT NULL,
                                data TEXT NOT NULL,
                                abstract TEXT,
                                salt TEXT,
                                deleted INTEGER DEFAULT 0,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP) """)
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS groups (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP) """)
        
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS tag (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS conversation_tag (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                conversation_id INTEGER NOT NULL,
                                tag_id INTEGER NOT NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS actions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                action_type TEXT NOT NULL,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                details TEXT)""")

        self.cursor.execute("""INSERt INTO groups (id, name) VALUES (1, 'Default')""")
        
        self.conn.commit()
    
    def initialize(self):
        self.create_db()
        self.create_table()

    def connect(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db)
    
    def get_cursor(self):
        if not self.cursor:
            self.connect()
            self.cursor = self.conn.cursor()
        return self.cursor
    
    def close(self):
        self.conn.close()

class Conversation:
    def __init__(self, id, title, group_id, data, abstract, salt):
        self.title = title
        self.group_id = group_id
        self.data = data
        self.abstract = abstract
        self.id = id
        self.salt = salt
        self.tags = []
    
    def __str__(self):
        return f"Conversation {self.id}: {self.title}"
    
    def add_tags(self, tags):
        self.tags.extend(tags)

    @classmethod
    def get_all(cls, cursor):
        cursor.execute("SELECT id, title, group_id, data, abstract, salt FROM conversations WHERE deleted=0")
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def get_all_with_pagination(cls, cursor, page=1, per_page=10):
        cursor.execute("SELECT id, title, group_id, data, abstract, salt FROM conversations WHERE deleted=0 ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, (page-1)*per_page))
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def get_by_id(cls, id, cursor):
        cursor.execute("SELECT id, title, group_id, data, abstract, salt FROM conversations WHERE id=? AND deleted=0", (id,))
        row = cursor.fetchone()
        return cls(*row)
    
    @classmethod
    def get_by_group_id(cls, group_id, cursor):
        cursor.execute("SELECT id, title, group_id, data, abstract, salt FROM conversations WHERE group_id=? AND deleted=0", (group_id,))
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def get_by_tag_id(cls, tag_id, cursor):
        cursor.execute("SELECT c.id, c.title, c.group_id, c.data, c.abstract, c.salt FROM conversations c INNER JOIN conversation_tag ct ON c.id=ct.conversation_id WHERE ct.tag_id=? AND c.deleted=0", (tag_id,))
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def add(cls, conversation, cursor):
        cursor.execute("INSERT INTO conversations (title, group_id, data, abstract, salt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (conversation.title, conversation.group_id, conversation.data, conversation.abstract, conversation.salt))
        
        return cursor.lastrowid
    
    @classmethod
    def save(cls, conversation, cursor):
        cursor.execute("INSERT INTO conversations (title, group_id, data, abstract, created_at, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (conversation.title, conversation.group_id, conversation.data, conversation.abstract, conversation.salt))
        

    @classmethod
    def update(cls, conversation, cursor):
        cursor.execute("UPDATE conversations SET title=?, group_id=?, data=?, abstract=?, salt=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation.title, conversation.group_id, conversation.data, conversation.abstract, conversation.salt, conversation.id))
        
    
    @classmethod
    def delete(cls, id, cursor):
        cursor.execute("UPDATE conversations SET deleted=1 WHERE id=?", (id,))
        
    
    @classmethod
    def add_tag(cls, conversation_id, tag_id, cursor):
        cursor.execute("INSERT INTO conversation_tag (conversation_id, tag_id) VALUES (?, ?)", (conversation_id, tag_id))
        

    @classmethod
    def remove_tag(cls, conversation_id, tag_id, cursor):
        cursor.execute("DELETE FROM conversation_tag WHERE conversation_id=? AND tag_id=?", (conversation_id, tag_id))
        
        
class Group:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return f"Group {self.id}: {self.name}"
    
    @classmethod
    def get_by_id(cls, id, cursor):
        cursor.execute("SELECT id, name FROM groups WHERE id=?", (id,))
        row = cursor.fetchone()
        return cls(*row)
    
    @classmethod
    def get_all(cls, cursor):
        cursor.execute("SELECT id, name FROM groups")
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def add(cls, group, cursor):
        cursor.execute("INSERT INTO groups (name, created_at, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (group.name,))
        
        return cursor.lastrowid

    @classmethod
    def update(cls, group, cursor):
        cursor.execute("UPDATE groups SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (group.name, group.id))
        
    
    @classmethod
    def delete(cls, id, cursor):
        cursor.execute("UPDATE conversations SET group_id=1 WHERE group_id=?", (id,))
        cursor.execute("DELETE FROM groups WHERE id=?", (id,))
        

    @classmethod
    def get_by_conversation_id(cls, conversation_id, cursor):
        cursor.execute("SELECT g.id, g.name FROM groups g INNER JOIN conversations c ON g.id=c.group_id WHERE c.id=?", (conversation_id,))
        row = cursor.fetchone()
        return cls(*row)
    
class Tag:
    def __init__(self, id, name):
        self.id = id
        self.name = name
    
    def __str__(self):
        return f"Tag {self.id}: {self.name}"
    
    @classmethod
    def get_all(cls, cursor):
        cursor.execute("SELECT id, name FROM tag")
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def get_by_conversation_id(cls, conversation_id, cursor):
        cursor.execute("SELECT t.id, t.name FROM tag t INNER JOIN conversation_tag ct ON t.id=ct.tag_id WHERE ct.conversation_id=?", (conversation_id,))
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def add(cls, tag, cursor):
        cursor.execute("INSERT INTO tag (name, created_at, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (tag.name,))
        
        return cursor.lastrowid

    @classmethod
    def update(cls, tag, cursor):
        cursor.execute("UPDATE tag SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (tag.name, tag.id))
        
    
    @classmethod
    def delete(cls, id, cursor):
        cursor.execute("DELETE FROM tag WHERE id=?", (id,))
        

    def add_tag_to_conversation(cls, conversation_id, tag_id, cursor):
        cursor.execute("INSERT INTO conversation_tag (conversation_id, tag_id) VALUES (?, ?)", (conversation_id, tag_id))
        
    
    def remove_tag_from_conversation(cls, conversation_id, tag_id, cursor):
        cursor.execute("DELETE FROM conversation_tag WHERE conversation_id=? AND tag_id=?", (conversation_id, tag_id))
        

class Action:
    def __init__(self, id, action_type, details):
        self.id = id
        self.action_type = action_type
        self.details = details

    def __str__(self):
        return f"Action {self.id}: {self.action_type}"
    
    # with pagination
    @classmethod
    def get_all(cls, cursor, page=1, per_page=10):
        cursor.execute("SELECT id, action_type, details FROM actions ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, (page-1)*per_page))
        rows = cursor.fetchall()
        return [cls(*row) for row in rows]
    
    @classmethod
    def add(cls, action, cursor):
        cursor.execute("INSERT INTO actions (action_type, details, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (action.action_type, action.details))
        
        return cursor.lastrowid