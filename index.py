# Vercel entry point — imports the FastAPI app from main.py
from main import app

# Vercel expects a variable named `handler`
handler = app
