import firebase_admin
from firebase_admin import credentials, db

# Prevent re-initialization error
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://speech-ai-project-57206-default-rtdb.firebaseio.com/'
    })

# Create global reference
ref = db.reference()