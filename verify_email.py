import requests

def test_email():
    url = "http://127.0.0.1:5000/send-email"
    payload = {"email": "test@example.com"}
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Email test PASS: Server returned 200 OK")
            print("Response:", response.json())
        else:
            print(f"Email test FAIL: Status {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"Email test ERROR: {e}")
        print("Make sure the flask app is running in another terminal!")

if __name__ == "__main__":
    test_email()
