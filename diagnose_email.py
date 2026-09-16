import os
import smtplib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def diagnose():
    print("--- Starting Email Diagnosis ---")

    # 1. Check .env file
    if not os.path.exists(".env"):
        print("CRITICAL: .env file NOT found in project directory.")
        return
    else:
        print(".env file found.")

    # 2. Check Credentials
    email = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    
    if not email:
        print("CRITICAL: SENDER_EMAIL is missing in .env")
    elif email == "your_email@gmail.com":
        print("CRITICAL: SENDER_EMAIL is still the default placeholder value.")
    else:
        print(f"SENDER_EMAIL found: {email}")

    if not password:
        print("CRITICAL: SENDER_PASSWORD is missing in .env")
    elif password == "your_app_password":
        print("CRITICAL: SENDER_PASSWORD is still the default placeholder value.")
    else:
        print("SENDER_PASSWORD found.")

    if not email or not password or email == "your_email@gmail.com":
        print("\nACTION REQUIRED: Please edit the .env file with real credentials.")
        return

    # 3. Check PDF
    if os.path.exists("seminar_report.pdf"):
        print("seminar_report.pdf found.")
    else:
        print("WARNING: seminar_report.pdf NOT found. (Email code will fail if file is missing, but connection check can proceed).")

    # 4. Check SMTP Connection
    print("\n--- Testing Gmail Connection (smtp.gmail.com:465) ---")
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        print("Connected to Gmail SMTP server.")
        
        try:
            server.login(email, password)
            print("Login SUCCESSFUL! Credentials are correct.")
        except smtplib.SMTPAuthenticationError:
            print("Login FAILED: Username and Password not accepted.")
            print("   Tip: Ensure you are using an 'App Password', not your regular login password.")
            print("   Tip: Check if 2-Factor Authentication is enabled on Google account (required for App Passwords).")
        except Exception as e:
            print(f"Login FAILED with error: {e}")
        finally:
            server.quit()

    except Exception as e:
        print(f"Connection FAILED: {e}")
        print("   Check your internet connection or firewall/antivirus settings.")

if __name__ == "__main__":
    diagnose()
