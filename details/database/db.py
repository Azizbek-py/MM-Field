from tinydb import TinyDB, Query, where
from tinydb.database import Document

db1 = TinyDB('details/database/base.json', indent=4)

users = db1.table("Users")
admins = db1.table("Admins")
query = Query()

def get(table, user_id=None):
    if table == "users":
        if user_id == None:
            return users.all()
        else:
            try:
                return users.get(doc_id=user_id)
            except:
                return None
    if table == "admins":
        if user_id == None:
            return admins.all()
        else:
            try:
                return admins.get(doc_id=user_id)
            except:
                return None

def insert(table, data, user_id=None):
    if table == "users":
        try:
            doc = Document(
                value=data,
                doc_id=user_id
            )
            users.insert(doc)

        except:
            users.update(data, doc_ids=[user_id])

def upd(table, data, user_id=None):
    if table == "users":
        users.update(data, doc_ids=[user_id])

def delete(table, user_id=None):
    if table == "users":
        users.remove(doc_ids=[user_id])