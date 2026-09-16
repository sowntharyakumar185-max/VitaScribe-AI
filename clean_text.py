import re

def clean_text(text):
    text = text.replace("hans", "humans")
    text = text.replace("han", "human")
    text = re.sub(r"\s+", " ", text)
    return text

if __name__ == "__main__":
    with open("raw_text.txt", "r", encoding="utf-8") as f:
        text = f.read()
    
    cleaned_text = clean_text(text)
    
    with open("clean_text.txt", "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    print("Text cleaned")
