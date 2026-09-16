
from firebase_connect import ref

summary_ref = ref.child("summaries")

summary_ref.push({
    "original_text": "Testing speech text",
    "summary": "This is a test summary."
})

print("Data inserted successfully!")
