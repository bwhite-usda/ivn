# ivn_intelligent_component_crosswalk.py is a policy component crosswalk analysis tool that uses AI models (OpenAI and Anthropic) to discover and evaluate relationships between policy components from Excel data.

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

# ===== CONFIGURATION =====
# Set the OpenAI API key as an environment variable
os.environ["OPENAI_API_KEY"] = "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"

# API Configuration
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
openai_client = OpenAI(api_key=openai_api_key)
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# Model Selection
EMBEDDING_MODEL = "text-embedding-3-large"
LLM_MODEL = "claude-3-opus-20240229"  # Alternatives: "gpt-4-turbo"
SIMILARITY_THRESHOLD = 0.3  # Top 30% matches for LLM analysis
LLM_TEMPERATURE = 0.1
PAUSE_BETWEEN_CALLS = 1.2  # Seconds to avoid rate limits

# Data Sources
SHEET_URL = "ivntest.xlsx"
OUTPUT_FILE = "policy_component_crosswalk_results.xlsx"

# ===== INITIALIZATION =====
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# ===== DATA LOADING & PREPARATION =====
def load_data():
    """Load and prepare datasets from Excel file"""
    print("Loading data from Excel file...")

    # Load existing pairs (Tab1)
    existing_pairs = pd.read_excel(SHEET_URL, sheet_name="Tab1")

    # Load unpaired components (Tab2)
    unpaired = pd.read_excel(SHEET_URL, sheet_name="Tab2")

    # Prepare data dictionaries
    existing_enablings = existing_pairs['Enabling Component'].unique().tolist()
    existing_dependents = existing_pairs['Dependent Component'].unique().tolist()
    unpaired_components = unpaired['Component'].tolist()

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

# ===== INTELLIGENT COMPARISON ENGINE =====
def build_prompt(enabling, dependent):
    """Construct rich prompt with policy context and examples"""
    return f"""
## Policy Component Relationship Analysis
You are an expert in public policy delivery analysis. Determine if delivering the Enabling Component 
is >50% likely to progress the Dependent Component toward implementation. Consider:

1. Causal dependencies in policy implementation
2. Practical delivery pathways
3. Regulatory/operational prerequisites
4. Temporal sequencing requirements
5. Resource allocation impacts

### Examples for Guidance:
Example 1:
Enabling: "Implement statewide data-sharing protocols"
Dependent: "Deploy AI-based case routing in social services"
Likelihood: YES (Score: 92)
Reasoning: Data-sharing protocols provide essential training data infrastructure required for AI systems.

Example 2:
Enabling: "Secure federal funding for sustainable agriculture"
Dependent: "Launch farm-to-school pilot programs"
Likelihood: YES (Score: 88)
Reasoning: Funding enables staffing, procurement, and operational capabilities needed for pilots.

Example 3:
Enabling: "Finalize cybersecurity standards for IoT devices"
Dependent: "Roll out smart agriculture sensor networks"
Likelihood: YES (Score: 95)
Reasoning: Security standards are prerequisite for safe deployment of connected devices.

### Current Analysis:
Enabling Component: "{enabling}"
Dependent Component: "{dependent}"

### Instructions:
1. Provide concise reasoning (1-2 sentences)
2. Assign likelihood score (0-100)
3. Final verdict: YES if score > 50, NO otherwise

### Output Format:
Reasoning: [your analysis]
Score: [0-100]
Verdict: [YES/NO]
"""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def llm_compare(enabling, dependent):
    """Intelligent comparison with rich policy context"""
    prompt = build_prompt(enabling, dependent)
    
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

# ===== CROSSWALK ENGINE =====
def perform_crosswalk(data, embeddings_data):
    """Execute both crosswalk directions with pre-filtering"""
    print("Starting crosswalk analysis...")
    results = []
    
    # Crosswalk 1: Unpaired as Enablers → Existing Dependents
    print("\n=== Crosswalk 1: Unpaired Components as Enablers ===")
    for i, comp in enumerate(data["unpaired_components"]):
        print(f"Processing unpaired enabling {i+1}/{len(data['unpaired_components'])}: {comp[:50]}...")
        
        candidates = prefilter_candidates(
            embeddings_data["embeddings"][comp],
            embeddings_data["existing_dependents_emb"],
            data["existing_dependents"]
        )
        
        print(f"  Pre-filtered to {len(candidates)} candidates")
        
        for dep, sim_score in candidates:
            comparison = llm_compare(comp, dep)
            
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
    print("\n=== Crosswalk 2: Unpaired Components as Dependents ===")
    for i, comp in enumerate(data["unpaired_components"]):
        print(f"Processing unpaired dependent {i+1}/{len(data['unpaired_components'])}: {comp[:50]}...")
        
        candidates = prefilter_candidates(
            embeddings_data["embeddings"][comp],
            embeddings_data["existing_enablings_emb"],
            data["existing_enablings"]
        )
        
        print(f"  Pre-filtered to {len(candidates)} candidates")
        
        for en, sim_score in candidates:
            comparison = llm_compare(en, comp)
            
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

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    # Load and prepare data
    data = load_data()
    
    # Generate embeddings
    embeddings_data = generate_all_embeddings(data)
    
    # Perform crosswalk analysis
    results_df = perform_crosswalk(data, embeddings_data)
    
    # Save results
    save_results(results_df, data)
    
    print("\nCrosswalk analysis completed successfully!")