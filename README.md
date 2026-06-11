[README.md](https://github.com/user-attachments/files/28847027/README.md)
# Super Speech AI

Super Speech AI is a Python Streamlit app that helps students create and practise speeches.

It can:

- Find useful online sources for a speech topic
- Rank sources by relevance and usefulness
- Create a source-based speech
- Adjust grammar level from Grade 3 to University
- Generate speeches for a specific word count or time length
- Give suggestions for improving the speech
- Help the user practise pacing and tell them if they should speak faster or slower

## Files Needed

Upload these files to your GitHub repository:

- `super_speech_ai.py`
- `requirements.txt`
- `README.md`

## How To Run Locally

Install the requirements:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run super_speech_ai.py
```

## How To Deploy On Streamlit Community Cloud

1. Create a GitHub repository called `super-speech-ai`.
2. Upload `super_speech_ai.py`, `requirements.txt`, and `README.md`.
3. Go to Streamlit Community Cloud.
4. Choose **Create app**.
5. Select your GitHub repository.
6. Use these settings:

```text
Repository: your-username/super-speech-ai
Branch: main
Main file path: super_speech_ai.py
```

7. Click **Deploy**.

## Important Note

The app needs internet access because it searches for sources online.

The practice coach works by letting the user enter their practice time and transcript. This makes it easier to use on school laptops and online app runners where microphone access may be blocked.
