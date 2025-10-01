# ivn_intelligent_component_crosswalk.py is a policy component crosswalk analysis tool that uses AI models (OpenAI and Anthropic) to discover and evaluate relationships between policy components from Excel data.
# Now enhanced with Retrieval-Augmented Generation (RAG) for evidence-based, explainable, and auditable outputs.

import pandas as pd
import numpy as np
import openai
from openai import OpenAI
import anthropic
import os
import time
from sklearn.metrics.pairwise import cosine_similarity
import re
from tenacity import retry, stop_after_attempt, wait_exponential
from pathlib import Path

# ===== CONFIGURATION =====
# Prompt for the OpenAI API key if not set in environment
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    openai_api_key = input("Enter your OpenAI API key (input will be visible): ")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run this script.")
openai_client = OpenAI(api_key=openai_api_key)

anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# Model Selection
EMBEDDING_MODEL = "text-embedding-3-large"
LLM_MODEL = "claude-3-opus-20240229"  # Alternatives: "gpt-4-turbo"
SIMILARITY_THRESHOLD = 0.3  # Top 30% matches for LLM analysis
LLM_TEMPERATURE = 0.1
PAUSE_BETWEEN_CALLS = 1.2  # Seconds to avoid rate limits

# Data Sources
SHEET_URL = "ivntest.xlsx"
OUTPUT_FILE = "policy_component_crosswalk_results.xlsx"

# RAG Knowledge Base Directory
KNOWLEDGE_BASE_DIR = "knowledge_base_docs"  # Place .txt/.md docs here

# ===== DATA LOADING & PREPARATION =====
def load_data():
    """Load and prepare datasets from Excel file, using first and second sheets regardless of name."""
    print("Loading data from Excel file...")

    # Read all sheets as an ordered dict
    xl = pd.ExcelFile(SHEET_URL)
    sheet_names = xl.sheet_names
    if len(sheet_names) < 2:
        raise RuntimeError("Excel file must have at least two sheets (tabs).")

    # Use first sheet for existing_pairs, second for unpaired
    existing_pairs = xl.parse(sheet_names[0])
    unpaired = xl.parse(sheet_names[1])

    # Debug: Show columns if KeyError occurs
    try:
        existing_enablings = existing_pairs['Enabling Component'].unique().tolist()
        existing_dependents = existing_pairs['Dependent Component'].unique().tolist()
    except KeyError:
        print("First sheet columns:", existing_pairs.columns.tolist())
        raise

    try:
        unpaired_components = unpaired['component_name'].tolist()  # <-- changed here
    except KeyError:
        print("Second sheet columns:", unpaired.columns.tolist())
        raise

    print(f"Loaded: {len(existing_enablings)} existing enablings, "
          f"{len(existing_dependents)} existing dependents, "
          f"{len(unpaired_components)} unpaired components")

    return {
        "existing_pairs": existing_pairs,
        "unpaired": unpaired,
        "existing_enablings": existing_enablings,
        "existing_dependents": existing_dependents,
        "unpaired_components": unpaired_components
    }

# ===== EMBEDDING MANAGEMENT =====
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_embedding(text, model=EMBEDDING_MODEL):
    """Get embedding with retry logic"""
    response = openai_client.embeddings.create(
        input=[text],
        model=model
    )
    return response.data[0].embedding

def generate_all_embeddings(data):
    """Generate embeddings for all components"""
    print("Generating embeddings for semantic pre-filtering...")
    
    # Combine all unique components
    all_components = (data["existing_enablings"] + 
                      data["existing_dependents"] + 
                      data["unpaired_components"])
    
    # Generate embeddings with progress tracking
    embeddings = {}
    for i, comp in enumerate(all_components):
        if i % 50 == 0:
            print(f"Processing embedding {i+1}/{len(all_components)}")
        embeddings[comp] = get_embedding(comp)
        time.sleep(0.1)  # Gentle rate limiting
    
    # Prepare arrays for similarity calculation
    existing_enablings_emb = [embeddings[comp] for comp in data["existing_enablings"]]
    existing_dependents_emb = [embeddings[comp] for comp in data["existing_dependents"]]
    
    return {
        "embeddings": embeddings,
        "existing_enablings_emb": existing_enablings_emb,
        "existing_dependents_emb": existing_dependents_emb
    }

# ===== RAG: KNOWLEDGE BASE INGESTION & RETRIEVAL =====
def load_knowledge_base():
    """Load and embed all knowledge base documents."""
    kb_files = list(Path(KNOWLEDGE_BASE_DIR).glob("*.txt")) + list(Path(KNOWLEDGE_BASE_DIR).glob("*.md"))
    kb_texts, kb_sources = [], []
    for file in kb_files:
        text = file.read_text(encoding="utf-8")
        kb_texts.append(text)
        kb_sources.append(str(file))
    print(f"Loaded {len(kb_texts)} knowledge base documents.")
    # Embed all docs
    kb_embeddings = [get_embedding(text[:2000]) for text in kb_texts]  # Truncate for embedding limits
    return list(zip(kb_texts, kb_sources, kb_embeddings))

def retrieve_relevant_context(query, kb_data, top_k=3):
    """Retrieve top-k relevant docs for a query using cosine similarity."""
    query_emb = get_embedding(query[:2000])
    kb_embeddings = [emb for _, _, emb in kb_data]
    sims = cosine_similarity([query_emb], kb_embeddings)[0]
    top_indices = np.argsort(sims)[-top_k:][::-1]
    context_blocks = []
    for idx in top_indices:
        text, source, _ = kb_data[idx]
        context_blocks.append(f"[Source: {source}]\n{text[:800]}")  # Limit context length
    return "\n\n".join(context_blocks)

# ===== SEMANTIC PREFILTERING =====
def prefilter_candidates(query_emb, target_embs, targets):
    """Find top candidates using cosine similarity"""
    similarities = cosine_similarity([query_emb], target_embs)[0]
    threshold = np.quantile(similarities, 1 - SIMILARITY_THRESHOLD)
    return [
        (targets[i], similarities[i])
        for i, sim in enumerate(similarities) 
        if sim >= threshold
    ]

# ===== INTELLIGENT COMPARISON ENGINE (RAG-ENABLED) =====
def build_prompt_with_rag(enabling, dependent, retrieved_context):
    """Construct prompt with retrieved context for RAG."""
    return f"""
## Policy Component Relationship Analysis (RAG-Enhanced)
You are an expert in public policy delivery analysis. Use the retrieved context below to determine if delivering the Enabling Component is >50% likely to progress the Dependent Component toward implementation. Cite sources where relevant.

### Retrieved Context:
{retrieved_context}

### Components:
Enabling Component: "{enabling}"
Dependent Component: "{dependent}"

### Instructions:
1. Use the context above to inform your reasoning.
2. Provide concise reasoning (1-2 sentences), citing sources as [Source: ...].
3. Assign likelihood score (0-100).
4. Final verdict: YES if score > 50, NO otherwise.

### Output Format:
Reasoning: [your analysis, with citations]
Score: [0-100]
Verdict: [YES/NO]
"""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def llm_compare_rag(enabling, dependent, kb_data):
    """LLM comparison using RAG context."""
    query = f"{enabling} {dependent}"
    retrieved_context = retrieve_relevant_context(query, kb_data)
    prompt = build_prompt_with_rag(enabling, dependent, retrieved_context)
    if "claude" in LLM_MODEL:
        response = anthropic_client.messages.create(
            model=LLM_MODEL,
            max_tokens=300,
            temperature=LLM_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
            system="You are a policy delivery expert specialized in causal relationships between government requirements."
        )
        content = response.content[0].text
    else:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        content = response.choices[0].message.content

    # Parse structured response
    reasoning = re.search(r"Reasoning:\s*(.+)", content, re.DOTALL)
    score = re.search(r"Score:\s*(\d+)", content)
    verdict = re.search(r"Verdict:\s*(YES|NO)", content)
    return {
        "reasoning": reasoning.group(1).strip() if reasoning else "Not provided",
        "score": int(score.group(1)) if score else 0,
        "verdict": verdict.group(1) if verdict else "ERROR",
        "raw_response": content
    }

# ===== CROSSWALK ENGINE (RAG-ENABLED) =====
def perform_crosswalk_rag(data, embeddings_data, kb_data):
    """Crosswalk with RAG context injection."""
    print("Starting RAG-enhanced crosswalk analysis...")
    results = []
    # Crosswalk 1: Unpaired as Enablers → Existing Dependents
    print("\n=== Crosswalk 1: Unpaired Components as Enablers (RAG) ===")
    for i, comp in enumerate(data["unpaired_components"]):
        print(f"RAG: Processing unpaired enabling {i+1}/{len(data['unpaired_components'])}: {comp[:50]}...")
        candidates = prefilter_candidates(
            embeddings_data["embeddings"][comp],
            embeddings_data["existing_dependents_emb"],
            data["existing_dependents"]
        )
        print(f"  Pre-filtered to {len(candidates)} candidates")
        for dep, sim_score in candidates:
            comparison = llm_compare_rag(comp, dep, kb_data)
            if comparison["verdict"] == "YES":
                results.append({
                    "Enabling Component": comp,
                    "Dependent Component": dep,
                    "Direction": "Unpaired → Existing Dependent",
                    "Similarity Score": f"{sim_score:.3f}",
                    "LLM Likelihood Score": comparison["score"],
                    "LLM Verdict": comparison["verdict"],
                    "LLM Reasoning": comparison["reasoning"],
                    "LLM Raw Response": comparison["raw_response"]
                })
            time.sleep(PAUSE_BETWEEN_CALLS)
    # Crosswalk 2: Unpaired as Dependents → Existing Enablings
    print("\n=== Crosswalk 2: Unpaired Components as Dependents (RAG) ===")
    for i, comp in enumerate(data["unpaired_components"]):
        print(f"RAG: Processing unpaired dependent {i+1}/{len(data['unpaired_components'])}: {comp[:50]}...")
        candidates = prefilter_candidates(
            embeddings_data["embeddings"][comp],
            embeddings_data["existing_enablings_emb"],
            data["existing_enablings"]
        )
        print(f"  Pre-filtered to {len(candidates)} candidates")
        for en, sim_score in candidates:
            comparison = llm_compare_rag(en, comp, kb_data)
            if comparison["verdict"] == "YES":
                results.append({
                    "Enabling Component": en,
                    "Dependent Component": comp,
                    "Direction": "Existing Enabling → Unpaired",
                    "Similarity Score": f"{sim_score:.3f}",
                    "LLM Likelihood Score": comparison["score"],
                    "LLM Verdict": comparison["verdict"],
                    "LLM Reasoning": comparison["reasoning"],
                    "LLM Raw Response": comparison["raw_response"]
                })
            time.sleep(PAUSE_BETWEEN_CALLS)
    return pd.DataFrame(results)

# ===== OUTPUT MANAGEMENT =====
def save_results(results_df, data):
    """Save comprehensive results to Excel"""
    print("\nSaving results...")
    with pd.ExcelWriter(OUTPUT_FILE) as writer:
        # Main results
        results_df.to_excel(writer, sheet_name='Discovered Relationships', index=False)
        
        # Original data
        data["existing_pairs"].to_excel(
            writer, sheet_name='Existing Pairs', index=False
        )
        data["unpaired"].to_excel(
            writer, sheet_name='Unpaired Components', index=False
        )
        
        # Analysis summary
        summary = pd.DataFrame({
            "Metric": ["Total Potential Pairs", "Pre-filtered Pairs", 
                       "LLM Evaluated Pairs", "Positive Matches"],
            "Count": [
                len(data["unpaired_components"]) * 
                (len(data["existing_enablings"]) + len(data["existing_dependents"])),
                results_df.shape[0],
                results_df.shape[0],
                results_df[results_df["LLM Verdict"] == "YES"].shape[0]
            ]
        })
        summary.to_excel(writer, sheet_name='Analysis Summary', index=False)
    
    print(f"Results saved to {OUTPUT_FILE}")

# ===== MAIN EXECUTION (RAG-ENABLED) =====
if __name__ == "__main__":
    # Load and prepare data
    data = load_data()
    
    # Generate embeddings
    embeddings_data = generate_all_embeddings(data)
    
    # Load and embed knowledge base
    kb_data = load_knowledge_base()
    
    # Perform RAG-enhanced crosswalk analysis
    results_df = perform_crosswalk_rag(data, embeddings_data, kb_data)
    
    # Save results
    save_results(results_df, data)
    
    print("\nRAG-enhanced crosswalk analysis completed successfully!")

# ==========================================================
# CoreAI RAG Pipeline Quick Start (from https://github.com/Infotrend-Inc/CoreAI-DemoProjects/tree/main/RAG_Pipeline)
#
# Run one of the following commands from the folder where this script is located:
#
# podman command:
# podman run --rm -it --userns=keep-id --device nvidia.com/gpu=all -e WANTED_UID=`id -u` -e WANTED_GID=`id -g` -e CoreAI_VERBOSE="yes" -v `pwd`:/iti -p 8888:8888 docker.io/infotrend/coreai:latest  /run_jupyter.sh
#
# docker command:
# docker run --rm -it --runtime=nvidia --gpus all -e WANTED_UID=`id -u` -e WANTED_GID=`id -g` -e CoreAI_VERBOSE="yes" -v `pwd`:/iti -p 8888:8888 docker.io/infotrend/coreai:latest  /run_jupyter.sh
#
# After the container starts, access CoreAI at http://localhost:8888 (password: iti).
# Load the notebook RAG_Pipeline.ipynb and follow the instructions.