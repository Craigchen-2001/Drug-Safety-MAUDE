import json
import os
from openai import AzureOpenAI
from PyPDF2 import PdfReader
from tqdm import tqdm

api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

client = AzureOpenAI(
    api_key=api_key,
    api_version="2025-01-01-preview",
    azure_endpoint=endpoint
)
deployment_name = "gpt-4o"

def load_prompt(path):
    with open(path, "r") as f:
        return f.read()

def extract_pdf_text(pdf_path, limit=16000):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text[:limit]
    except:
        return ""

prompt_template = load_prompt("/Users/chenweichi/Desktop/Drug_Safety_Project/experiments/prompts/generate_mesh.txt")

input_path = "/Users/chenweichi/Desktop/Drug_Safety_Project/experiments/with_pdf_17.json"
pdf_dir = "/Users/chenweichi/Desktop/Drug_Safety_Project/experiments/pdf_17"

with open(input_path, "r") as f:
    data = json.load(f)

if isinstance(data, dict):
    data = [data]

print(f"Total records: {len(data)}")
choice = input("How many records to process? (number or all): ").strip()
if choice.lower() == "all":
    n_to_run = len(data)
else:
    try:
        n_to_run = min(int(choice), len(data))
    except:
        n_to_run = len(data)

print("\nSelect mode:")
print("1 = Title + Abstract (if Abstract missing, use text_excerpt)")
print("2 = Title + Abstract + PDF (if PDF exists)")
print("3 = Run both (Abstract-only and FullText)")
mode = input("Enter mode (1/2/3): ").strip()

for entry in tqdm(data[:n_to_run], desc="Processing", unit="paper"):
    pmid = entry.get("PMID", "N/A")
    title = entry.get("Title", "")
    abstract = entry.get("Abstract", "") or entry.get("text_excerpt", "")
    pdf_path = os.path.join(pdf_dir, f"{pmid}.pdf")
    pdf_text = extract_pdf_text(pdf_path) if os.path.exists(pdf_path) else ""

    if mode in ["1", "3"]:
        prompt_abs = prompt_template.format(PMID=pmid, Title=title, Abstract=abstract, FullText="")
        resp_abs = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are an expert in biomedical informatics and MeSH indexing."},
                {"role": "user", "content": prompt_abs},
            ],
            temperature=0
        )
        try:
            mesh_abs = json.loads(resp_abs.choices[0].message.content.strip())
        except:
            mesh_abs = []
        if mode == "1":
            entry["GeneratedMeshTerms"] = mesh_abs
        else:
            entry["GeneratedMeshTerms_Abstract"] = mesh_abs

    if mode in ["2", "3"]:
        prompt_full = prompt_template.format(PMID=pmid, Title=title, Abstract=abstract, FullText=pdf_text)
        resp_full = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are an expert in biomedical informatics and MeSH indexing."},
                {"role": "user", "content": prompt_full},
            ],
            temperature=0
        )
        try:
            mesh_full = json.loads(resp_full.choices[0].message.content.strip())
        except:
            mesh_full = []
        if mode == "2":
            entry["GeneratedMeshTerms"] = mesh_full
        else:
            entry["GeneratedMeshTerms_FullText"] = mesh_full

with open(input_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Updated file saved:", input_path)
