import whisper

# Load model
model = whisper.load_model("base")

# Convert speech to text
result = model.transcribe("seminar_female_voice.mp3")

# Save text to file
with open("report.txt", "w", encoding="utf-8") as f:
    f.write("SPEECH TO TEXT REPORT\n")
    f.write("---------------------\n")
    f.write(result["text"])

print("✅ Report generated successfully!")
