import requests
import json

url = "http://127.0.0.1:5000/send-email"
payload = {"email": "sandhiya7906@gmail.com"}
headers = {"Content-Type": "application/json"}

try:
    print(f"Sending POST to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.text)
except Exception as e:
    print(f"Request Failed: {e}")
