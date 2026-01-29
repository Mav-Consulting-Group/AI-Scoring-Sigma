# main.py
import os
import json
import random
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from zoho_utils import update_zoho_lead_score, fetch_org_id, fetch_org_variable
from ingest_contacts import ingest_contacts

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Lead Scoring API is running!"}

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
BASE_INDEX_NAME = os.getenv("PINECONE_INDEX", "contact-scoring")
SCORE_FIELD_NAME = os.getenv("SCORE_FIELD_NAME", "AI_Score")
JUSTIFICATION_FIELD_NAME = os.getenv("JUSTIFICATION_FIELD_NAME", "AI_Justification")
RECOMMENDATION_FIELD_NAME = os.getenv("RECOMMENDATION_FIELD_NAME", "AI_Recommendation")
TESTING = os.getenv("TESTING", "false").lower() == "true"

app = FastAPI()

if not TESTING:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    pc = Pinecone(api_key=PINECONE_API_KEY)


def safe_parse_json(resp_text):
    resp_text = resp_text.strip()
    first_brace = resp_text.find("{")
    last_brace = resp_text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        resp_text = resp_text[first_brace:last_brace+1]
    else:
        resp_text = '{"score":50,"reason":"AI parsing fallback"}'
    try:
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"score": 50, "reason": "AI parsing fallback"}


def format_lead_text(lead: dict):
    parts = []
    for k in lead.keys():
        if v := lead.get(k):
            parts.append(f"{k}: {v}")
    return "; ".join(parts) if parts else json.dumps(lead)


@app.post("/zoho/webhook")
async def score_new_lead(request: Request):
    payload = await request.json()
    lead = payload.get("data", [{}])[0]
    notes = payload.get("Notes",[])
    emails = payload.get("Emails",[])
    numCalls = payload.get("Number_Of_Calls",int)
    numMeetings = payload.get("Number_Of_Meetings",int)
    refreshToken = payload.get("Refresh_Token", str)
    lead_id = str(lead.get("id"))
    lead_status = str(lead.get("Lead_Status"))
    userPrompt = fetch_org_variable("aileadscore__Prompt", refreshToken)

    lead_text = format_lead_text(lead)

    orgId = fetch_org_id(refreshToken)
    indexName = f"{BASE_INDEX_NAME}-{orgId}"

    index = pc.Index(indexName)

    if TESTING:
        score = random.randint(55, 90)
        reason = "TESTING mode: dummy score"
    else:
        # 1) Embed lead
        emb_resp = openai_client.embeddings.create(model="text-embedding-3-small", input=[json.dumps(lead)])
        query_vec = emb_resp.data[0].embedding

        # 2) Query Pinecone
        qres = index.query(vector=query_vec, top_k=8, include_metadata=True)
        matches = qres.get("matches", [])

        examples = []
        for m in matches:
            md = m.get("metadata", {})
            examples.append(md)

        if not examples:
            examples_prompt = "No historical contacts available. Use lead data only."
        else:
            examples_prompt = json.dumps(examples, indent=2)

        prompt = f"""
    You are a data scientist. 
    Estimate a 0-100 score for this lead. 
    If there are no Historical Contacts, use the lead data, Number Of Calls, Number Of Meetings, Emails, Notes and Lead Status to generate a score. 
    If there are Historical Contacts then the score depends 50% on hiscotrical matches and 50% on lead data, Number Of Calls, Number Of Meetings, Emails, Notes and Lead Status. 
    Focus on timestamps and directions of the SMS and Emails and go through the contents of Notes, also through the subjects of emails as well as they indicate lead sentiments and should impact the score as well. 
    IMPORTANT : Focus on Lead Status as well, and provide precise scores, not just in multiples of 5, even a single score point matters. 
    IMPORTANT : The score, reasoning and recommendations should always take lead status, Number of Calls, Meetings, Notes and emails into account. 
    
    Lead Status Pipeline (STRICT ORDER):
       New Prospect →
       Tour Scheduled →
       Application Started →
       Application Completed →
       Screening Completed →
       Approved →
       Ready For Move In

    Historical contacts (JSON): 
    {examples_prompt} 

    lead data: 
    {lead_text} 

    Number of Calls : {numCalls} 
    Number of Meetings : {numMeetings} 

    Emails : 
    {emails} 

    Notes : 
    {notes}

    Org Specific Custom Prompt :
    {userPrompt}

    Important : If Org Specefic Custom Prompt is mentioned, consider it for scoring as well

    Lead Status: {lead_status} 
    Return JSON: {{ "score": <int 0-100>, "reason": "<one-sentence>", "recommendation": "<one-sentence>" }}

    """

        chat = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a data scientist. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        resp_text = chat.choices[0].message.content
        resp_json = safe_parse_json(resp_text)
        score = int(resp_json.get("score", 50))
        reason = resp_json.get("reason", "AI parsing fallback")
        recom = resp_json.get("recommendation", "AI parsing fallback")

    result = update_zoho_lead_score(refreshToken, lead_id, score, reason, recom, SCORE_FIELD_NAME, JUSTIFICATION_FIELD_NAME, RECOMMENDATION_FIELD_NAME)
    print("Zoho update result:", result)
    return {
        "status": "success",
        "lead_id": lead_id,
        "score": score,
        "reason": reason,
        "recommendation": recom,
        "zoho_update": result
    }

@app.post("/zoho/ingest_contacts")
async def ingest_contacts_api(request: Request):
    payload = await request.json()
    refresh_token = payload.get("Refresh_Token" ,str)
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing Refresh_Token in payload")
    result = await ingest_contacts(refresh_token)
    return result
