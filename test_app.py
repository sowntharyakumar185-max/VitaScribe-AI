import requests
import time
import os

# Assuming the Flask app is running on localhost:5000
BASE_URL = 'http://127.0.0.1:5000'

# Helper to upload a dummy audio file (we'll just send empty file)
files = {'audio': ('dummy.wav', b'')}
data = {
    'patient_name': 'John Doe',
    'age': '30',
    'gender': 'Male',
    'doctor_name': 'Dr. Smith'
}

# Record endpoint
resp = requests.post(f'{BASE_URL}/record', files=files, data=data)
print('Record response:', resp.status_code, resp.json())

# Wait a moment for PDF generation
time.sleep(1)

# Download endpoint
resp = requests.get(f'{BASE_URL}/download')
print('Download response status:', resp.status_code)
print('Headers:', resp.headers.get('Cache-Control'))
print('Content-Type:', resp.headers.get('Content-Type'))
print('Content length:', len(resp.content))

# Clean up: stop after test

