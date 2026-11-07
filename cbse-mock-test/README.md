# CBSE Timed Mock Test

A separate Streamlit app for fresh, timed CBSE-style full-syllabus tests for Classes XI and XII in Mathematics, Physics, Chemistry and Biology.

## Deploy on Streamlit Community Cloud

1. Create a new app from `75neel-ops/deepbluemonkey`, branch `main`.
2. Set the app file path to `cbse-mock-test/app.py`.
3. Select Python 3.12 in the app's deployment settings.
4. In the app's **Settings → Secrets**, add:

```toml
GEMINI_API_KEY = "your Gemini API key"
```

Keep the API key in Streamlit Secrets; do not commit it to GitHub.

## Notes

- Tests have a 3-hour limit.
- Theory maximums: Mathematics 80; Physics, Chemistry and Biology 70.
- Class XII papers follow the available CBSE 2026–27 sample-paper patterns.
- Class XI papers are school-set practice papers based on the listed syllabus.
- The displayed AIR band is illustrative only and is not a real or validated rank prediction.
