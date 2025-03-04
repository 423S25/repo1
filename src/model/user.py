import uuid
from peewee import *
from flask_security import UserMixin

user_db = SqliteDatabase('users.db')

class User(UserMixin, user_db.Model):
    id = AutoField()
    email = TextField(null=True)
    username = TextField()
    password = TextField()
    active = BooleanField(default=True)
    fs_uniquifier = TextField(default=lambda: str(uuid.uuid4()))
    #confirmed_at = DateTimeField(null=True)

    @staticmethod
    def all() -> list['User']:
        return list(User.select())
    
    @staticmethod
    def get_by_uid(u: str) -> 'User':
        sel = User.select().where(User.fs_uniquifier == u)
        return sel.first()
    
    @staticmethod
    def get_by_username(uid: str) -> 'User':
        sel = User.select().where(User.username == uid)
        return sel.first()
        
    
    @staticmethod
    def add_user(username: str, hashed_password: str):
        user = User.get_or_create(
             username = username,
             password = hashed_password
        )
        return user
    
    def update_email(self, email: str):
        self.email = email
        self.save()


    class Meta:
        database = user_db