import requests
import time
import os
from generate_pdf import create_pdf

BASE_URL = 'http://127.0.0.1:5000'

# Generate a dummy PDF directly
summary = 'Test summary\nLine1\nLine2'
pdf_path = create_pdf(summary, 'Test Patient', '25', 'Male', 'Dr. Test')
print('Generated PDF at:', pdf_path)

# Wait a moment for the server to be ready (if just started)
time.sleep(1)

# Download endpoint
resp = requests.get(f'{BASE_URL}/download')
print('Download response status:', resp.status_code)
print('Cache-Control header:', resp.headers.get('Cache-Control'))
print('Content-Type:', resp.headers.get('Content-Type'))
print('Content length:', len(resp.content))
