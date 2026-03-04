# Autonomous Content Factory

## Project Title
Autonomous Content Factory – AI-Powered Multi-Agent Marketing Content System

## The Problem
Marketing teams spend significant time drafting and validating information.Ai generating the info may bring about hallucinations or inaccurate data 

## The Solution
Autonomous Content Factory simulates multiagent workflow in a structured way

- Research Agent: Extracts structured facts from source text.
- Copywriter Agent: Generates blog, social media thread, and email content.
- Editor Agent: Validates generated content against the fact sheet and detects hallucinations.
- Automatic Regeneration: If validation fails, content is regenerated with correction instructions.

The system creates a closed-loop AI workflow that improves reliability of generated marketing content.

## Tech Stack
- Python 3.10+
- FastAPI
- Jinja2
- Groq API (LLaMA 3.1)
- HTML/CSS
- JavaScript
- Uvicorn

## Setup Instructions

1. Install Python (3.10 or higher)

2. Clone repository:
   git clone <repo-link>
   cd backend

3. Create virtual environment:
   python3 -m venv venv
   source venv/bin/activate

4. Install dependencies:
   pip install -r requirements.txt

5. Create .env file:
   GROQ_API_KEY=your_key_here

6. Run server:
   uvicorn main:app --reload

Open:
http://127.0.0.1:8000
