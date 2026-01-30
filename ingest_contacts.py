import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from zoho_utils import fetch_all_contacts, fetch_org_id
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
BASE_INDEX_NAME = os.getenv("PINECONE_INDEX", "contact-scoring")
PINECONE_REG = os.getenv("PINECONE_REG", "us-west1")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)


def ingest_contacts(refresh_token: str):
    org_id = fetch_org_id(refresh_token)
    index_name = f"{BASE_INDEX_NAME}-{org_id}"

    existing = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing:
        pc.create_index(name=index_name, dimension=1536, metric="cosine", spec=ServerlessSpec(cloud="aws", region=PINECONE_REG))
    index = pc.Index(index_name)

    contacts = fetch_all_contacts(refresh_token)

    print(f"Fetched {len(contacts)} contacts from Zoho")

    for contact in contacts:
        contact_id = contact.get("id")
        if isinstance(contact.get("Account_Name"), dict):
            contact["Account_Name"] = contact["Account_Name"].get("id")
        text = json.dumps(contact)
        emb = openai_client.embeddings.create(model="text-embedding-3-small", input=[text])
        vec = emb.data[0].embedding
        index.upsert(vectors=[{"id": str(contact_id), "values": vec, "metadata": contact}])

    print("✅ Ingestion completed.")
    return {"status": "success", "count": len(contacts)}


if __name__ == "__main__":
    ingest_contacts("")
