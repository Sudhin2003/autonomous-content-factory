import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
import json
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import logging
import zipfile
from fastapi.responses import FileResponse
from datetime import datetime


# Load environment variables
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()
app.state.is_running = False

templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)


class InputText(BaseModel):
    content: str
    tone: str = "Professional & Trustworthy"


class FactSheet(BaseModel):
    Product_Name: str = Field(alias="Product Name")
    Key_Features: list = Field(alias="Key Features")
    Target_Audience: str = Field(alias="Target Audience")
    Value_Proposition: str = Field(alias="Value Proposition")

    class Config:
        populate_by_name = True


class ValidationRequest(BaseModel):
    facts: FactSheet
    content: str

def run_extraction(raw_text: str):
    prompt = f"""
You are the Lead Research & Fact-Check Agent.

Your job:
1) Extract structured factual information.
2) Identify any ambiguous, vague, or unclear statements.

Return ONLY valid JSON in this exact format:

{{
  "Product Name": "",
  "Key Features": [],
  "Target Audience": "",
  "Value Proposition": "",
  "ambiguities": []
}}

Text:
{raw_text}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a strict JSON extraction engine."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content.strip()

    try:
        return json.loads(raw_output)

    except json.JSONDecodeError:
        logging.error("Extraction returned invalid JSON")
        logging.error(raw_output)

        import re

        # Remove JS-style comments
        cleaned = re.sub(r"//.*", "", raw_output)

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)

        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        return {
            "Product Name": "",
            "Key Features": [],
            "Target Audience": "",
            "Value Proposition": "",
            "ambiguities": []
        }

def run_generation(facts: dict, tone: str):
    prompt = f"""

    You are the Creative Copywriter Agent.

Campaign Tone: {tone}

Adjust voice, vocabulary, rhythm, and emotional intensity
to match this tone across all outputs.

Using the structured fact sheet below, generate:

1) A professional 500-word blog post.
2) A 5-post engaging social media thread.
3) A concise email teaser paragraph.

Stay consistent with the facts.
Do NOT invent new features.

Fact Sheet:
Product Name: {facts["Product Name"]}
Key Features: {facts["Key Features"]}
Target Audience: {facts["Target Audience"]}
Value Proposition: {facts["Value Proposition"]}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional marketing copywriter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()    

def run_validation(facts: dict, content: str):
    prompt = f"""
You are a Senior Editorial Quality Control Agent.

Your job is to determine whether the generated content introduces
NEW FACTUAL CLAIMS not present in the fact sheet.

Very Important Rules:

1. Do NOT flag persuasive marketing language.
2. Do NOT flag emotional tone.
3. Do NOT flag rhetorical headlines.
4. Only flag statements that introduce:
   - New features
   - New capabilities
   - New technical claims
   - New guarantees
   - New offers
   - Specific measurable claims not in fact sheet

If content only reframes existing facts persuasively,
it should PASS.

A hallucination must be a concrete factual addition.

Return ONLY valid JSON in this exact structure:

{{
  "status": "PASS",
  "hallucinations": [],
  "missing_points": [],
  "exaggerations": [],
  "correction_note": "",
  "summary": ""
}}

Definitions:

- hallucinations = concrete factual additions not in fact sheet,If a capability logically follows from listed features, do not flag it.
- missing_points = key features from fact sheet completely omitted
- exaggerations = measurable or performance claims not supported
- correction_note = only if FAIL
- summary = short reasoning

Fact Sheet:
Product Name: {facts["Product Name"]}
Key Features: {facts["Key Features"]}
Target Audience: {facts["Target Audience"]}
Value Proposition: {facts["Value Proposition"]}

Generated Content:
{content}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a strict factual auditor."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content.strip()

    try:
     return json.loads(raw_output)

    except json.JSONDecodeError:
     logging.error("Validator returned invalid JSON")

     import re
     match = re.search(r"\{.*\}", raw_output, re.DOTALL)

     if match:
        try:
            return json.loads(match.group())
        except:
            pass

     return {
        "status": "FAIL",
        "hallucinations": [],
        "missing_points": [],
        "exaggerations": [],
        "correction_note": "Validator returned malformed JSON.",
        "summary": "Validation formatting failure."
        }

def run_generation_with_correction(facts: dict, correction_note: str):

    prompt = f"""
The previous draft was rejected by the Editor.

Correction instructions:
{correction_note}

Regenerate the campaign content strictly following the fact sheet and corrections.

Fact Sheet:
Product Name: {facts["Product Name"]}
Key Features: {facts["Key Features"]}
Target Audience: {facts["Target Audience"]}
Value Proposition: {facts["Value Proposition"]}

Generate:
1) A professional 500-word blog post.
2) A 5-post engaging social media thread.
3) A concise email teaser paragraph.

Do NOT invent new features.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional marketing copywriter correcting a rejected draft."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )

    return response.choices[0].message.content.strip()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/extract-facts")
def extract_facts(data: InputText):
    prompt = f"""
    Extract the following from the text below:

    Return ONLY valid JSON.
    no markdown.
    no explanations.

    Required JSON format:
    {{
        "Product Name": "",
        "Key Features": [],
        "Target Audience": "",
        "Value Proposition": ""
    }}

    Text:
    {data.content}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a strict JSON extraction engine."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content.strip()

    try:
        parsed_json = json.loads(raw_output)
        return parsed_json
    except:
        return {"error": "Invalid JSON returned", "raw_output": raw_output}


@app.post("/generate-content")
def generate_content(facts: FactSheet):
    prompt = f"""
    Using the structured fact sheet below, generate:

    1) A professional 500-word blog post.
    2) A 5-post engaging social media thread.
    3) A concise email teaser paragraph.

    Stay consistent with the facts.
    Do NOT invent new features.

    Fact Sheet:
    Product Name: {facts.Product_Name}
    Key Features: {facts.Key_Features}
    Target Audience: {facts.Target_Audience}
    Value Proposition: {facts.Value_Proposition}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional marketing copywriter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return {"generated_content": response.choices[0].message.content}




@app.post("/validate-content")
def validate_content(request: ValidationRequest):

    facts = request.facts
    content = request.content

    prompt = f"""
You are a strict AI content auditor.

Compare the fact sheet with the generated content.

Identify:
- Invented features
- Exaggerated claims
- Added offers or capabilities
- Missing key features

Return ONLY valid JSON in this exact structure:

{{
  "status": "PASS",
  "hallucinations": [],
  "missing_points": [],
  "exaggerations": [],
  "summary": ""
}}

The "status" field must be either PASS or FAIL.
Do not return explanations outside JSON.

If the generated content implies capabilities not explicitly stated in the fact sheet, treat them as hallucinations.

Fact Sheet:
Product Name: {facts.Product_Name}
Key Features: {facts.Key_Features}
Target Audience: {facts.Target_Audience}
Value Proposition: {facts.Value_Proposition}

Generated Content:
{content}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a strict factual auditor."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw_output)
        return parsed
    except Exception:
        return {
            "status": "ERROR",
            "raw_output": raw_output
        }
    
@app.post("/run-campaign")
def run_campaign(data: InputText):

    # 🔒 Prevent parallel execution
    if app.state.is_running:
        return {
            "status": "BUSY",
            "message": "Campaign already running. Please wait."
        }

    app.state.is_running = True

    try:
        logging.info("Running campaign generation")

        facts = run_extraction(data.content)
        logging.info(f"Facts extracted: {facts}")

        generated_content = run_generation(facts, data.tone)
        logging.info("Initial content generated")

        validation = run_validation(facts, generated_content)
        logging.info(f"Validation result: {validation.get('status')}")

        # 🔥 FEEDBACK LOOP
        if validation.get("status") == "FAIL":
            logging.info("Editor rejected content. Regenerating with correction note.")

            correction_note = validation.get("correction_note", "")

            regenerated_content = run_generation_with_correction(facts, correction_note)

            validation = run_validation(facts, regenerated_content)

            generated_content = regenerated_content

        campaign_result = {
         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "source_text": data.content,
         "tone": data.tone,
         "facts": facts,
         "generated_content": generated_content,
         "validation": validation
        }

        with open("campaign_log.json", "a") as f:
            f.write(json.dumps(campaign_result) + "\n")

        return campaign_result

    except Exception as e:
        logging.error(f"Campaign failed: {str(e)}")
        return {
            "status": "SYSTEM_ERROR",
            "message": str(e)
        }

    finally:
        # 🔓 Always release lock
        app.state.is_running = False
    
@app.post("/export-campaign")
def export_campaign(data: dict):

    blog = data.get("blog", "")
    social = data.get("social", "")
    email = data.get("email", "")
    facts = data.get("facts", {})

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"campaign_{timestamp}.zip"

    with zipfile.ZipFile(zip_filename, "w") as zipf:
        zipf.writestr("blog.txt", blog)
        zipf.writestr("social_thread.txt", social)
        zipf.writestr("email_teaser.txt", email)
        zipf.writestr("facts.json", json.dumps(facts, indent=2))

    return FileResponse(
        zip_filename,
        media_type="application/zip",
        filename=zip_filename
    )    

@app.get("/campaign-history")
def get_campaign_history():

    history = []

    if os.path.exists("campaign_log.json"):
        with open("campaign_log.json", "r") as f:
            for line in f:
                try:
                    history.append(json.loads(line))
                except:
                    continue

    # Return newest first
    return list(reversed(history[-20:]))

@app.delete("/delete-campaign/{index}")
def delete_campaign(index: int):

    if not os.path.exists("campaign_log.json"):
        return {"status": "NO_HISTORY"}

    with open("campaign_log.json", "r") as f:
        lines = f.readlines()

    if index < 0 or index >= len(lines):
        return {"status": "INVALID_INDEX"}

    lines.pop(index)

    with open("campaign_log.json", "w") as f:
        f.writelines(lines)

    return {"status": "DELETED"}