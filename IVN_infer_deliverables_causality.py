# IVN_infer_requirements_causality.py
# Enhanced with CoreAI RAG Pipeline retrieval for context-grounded causal inference
# Last updated: 2025-07-24
# Modified: Uses local TF-IDF vectorizer for semantic similarity (no HuggingFace dependency)

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib
import base64
import io
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests

def load_classifier():
    model_base64 = """gASV+AEAAAAAAACMHnNrbGVhcm4ubGluZWFyX21vZGVsLl9sb2dpc3RpY5SMEkxvZ2lzdGljUmVncmVzc2lvbpSTlCmBlH2UKIwHcGVuYWx0eZSMAmwylIwEZHVhbJSJjAN0b2yURz8aNuLrHEMtjAFDlEc/8AAAAAAAAIwNZml0X2ludGVyY2VwdJSIjBFpbnRlcmNlcHRfc2NhbGluZ5RLAYwMY2xhc3Nfd2VpZ2h0lE6MDHJhbmRvbV9zdGF0ZZROjAZzb2x2ZXKUjAVsYmZnc5SMCG1heF9pdGVylEtkjAttdWx0aV9jbGFzc5SMBGF1dG+UjAd2ZXJib3NllEsAjAp3YXJtX3N0YXJ0lImMBm5fam9ic5ROjAhsMV9yYXRpb5ROjBFmZWF0dXJlX25hbWVzX2luX5SME2pvYmxpYi5udW1weV9waWNrbGWUjBFOdW1weUFycmF5V3JhcHBlcpSTlCmBlH2UKIwIc3ViY2xhc3OUjAVudW1weZSMB25kYXJyYXmUk5SMBXNoYXBllEsChZSMBW9yZGVylGgJjAVkdHlwZZRoHmgkk5SMAk84lImIh5RSlChLA4wBfJROTk5K/////0r/////Sz90lGKMCmFsbG93X21tYXCUiYwbbnVtcHlfYXJyYXlfYWxpZ25tZW50X2J5dGVzlEsQdWKAAmNudW1weS5jb3JlLm11bHRpYXJyYXkKX3JlY29uc3RydWN0CnEAY251bXB5Cm5kYXJyYXkKcQFLAIVxAmNfY29kZWNzCmVuY29kZQpxA1gBAAAAYnEEWAYAAABsYXRpbjFxBYZxBlJxB4dxCFJxCShLAUsChXEKY251bXB5CmR0eXBlCnELWAIAAABPOHEMiYiHcQ1ScQ4oSwNYAQAAAHxxD05OTkr/////Sv////9LP3RxEGKJXXERKFgKAAAAU2ltaWxhcml0eXESWBIAAABUcmFuc2l0aXZlIFN1cHBvcnRxE2V0cRRiLpVlAAAAAAAAAIwObl9mZWF0dXJlc19pbl+USwKMCGNsYXNzZXNflGgaKYGUfZQoaB1oIGghSwKFlGgjaAloJGgljAJmOJSJiIeUUpQoSwOMATyUTk5OSv////9K/////0sAdJRiaCuIaCxLEHViAv//AAAAAAAAAAAAAAAAAADwP5VPAAAAAAAAAIwHbl9pdGVyX5RoGimBlH2UKGgdaCBoIUsBhZRoI2gJaCRoJYwCaTSUiYiHlFKUKEsDaDVOTk5K/////0r/////SwB0lGJoK4hoLEsQdWIH/////////wMAAACVLQAAAAAAAACMBWNvZWZflGgaKYGUfZQoaB1oIGghSwFLAoaUaCNoCWgkaDRoK4hoLEsQdWIF//////8gckxXPRuZPwAAAAAAAAAAlTAAAAAAAAAAjAppbnRlcmNlcHRflGgaKYGUfZQoaB1oIGghSwGFlGgjaAloJGg0aCuIaCxLEHViBv///////4SkFir6bJW/lR4AAAAAAAAAjBBfc2tsZWFybl92ZXJzaW9ulIwFMS4xLjOUdWIu"""
    model_bytes = base64.b64decode(model_base64.encode("utf-8"))
    return joblib.load(io.BytesIO(model_bytes))

def retrieve_rag_context(en_desc, dep_desc, top_k=2):
    """
    Retrieve supporting documentation or prior causal inferences for similar requirement pairs
    using a CoreAI RAG Pipeline endpoint.
    Returns a list of dicts with 'document', 'snippet', and 'score'.
    """
    # Example RAG API endpoint (update as needed for your deployment)
    RAG_API_URL = "http://localhost:8000/rag/retrieve"
    payload = {
        "query": f"Enabling: {en_desc}\nDependent: {dep_desc}",
        "top_k": top_k
    }
    try:
        response = requests.post(RAG_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            return []
    except Exception as e:
        print(f"RAG retrieval failed: {e}")
        return []

def aggregate_rag_features(rag_results):
    """
    Aggregate RAG results into features for classifier or LLM.
    Returns: (support_score, context_snippet)
    """
    if not rag_results:
        return 0.0, ""
    # Use the highest scoring snippet as context, and average the scores
    support_score = np.mean([r.get("score", 0.0) for r in rag_results])
    context_snippet = rag_results[0].get("snippet", "")
    return support_score, context_snippet

# Load the Excel dataset
input_file = "ivntest.xlsx"
df = pd.read_excel(input_file)

# Extract relevant columns
en_desc_col = "Enabling Component Description"
dep_desc_col = "Dependent Component Description"

# Fix: restore correct Enabling Component Descriptions if overwritten
dup_mask = df[en_desc_col] == df[dep_desc_col]
fix_map = df[~dup_mask].drop_duplicates(subset=["Enabling Component"])[["Enabling Component", en_desc_col]]
fix_dict = dict(zip(fix_map["Enabling Component"], fix_map[en_desc_col]))
df.loc[dup_mask, en_desc_col] = df.loc[dup_mask, "Enabling Component"].map(fix_dict).fillna(df.loc[dup_mask, en_desc_col])

# Drop rows without both component descriptions
df = df[df[en_desc_col].notna() & df[dep_desc_col].notna()]

# Compute cosine similarity between components using TF-IDF (no HuggingFace dependency)
en_texts = df[en_desc_col].astype(str).tolist()
dep_texts = df[dep_desc_col].astype(str).tolist()
all_texts = en_texts + dep_texts
vectorizer = TfidfVectorizer().fit(all_texts)
en_vectors = vectorizer.transform(en_texts)
dep_vectors = vectorizer.transform(dep_texts)
cosine_scores = np.array([cosine_similarity(en_vectors[i], dep_vectors[i])[0, 0] for i in range(len(df))])
df["Similarity"] = cosine_scores

# Retrieve RAG context and features for each row
rag_support_scores = []
rag_contexts = []
print("Retrieving RAG context for each requirement pair...")
for idx, row in df.iterrows():
    en_desc = row[en_desc_col]
    dep_desc = row[dep_desc_col]
    rag_results = retrieve_rag_context(en_desc, dep_desc, top_k=2)
    support_score, context_snippet = aggregate_rag_features(rag_results)
    rag_support_scores.append(support_score)
    rag_contexts.append(context_snippet)
df["RAG_Support_Score"] = rag_support_scores
df["RAG_Context"] = rag_contexts

# Load and apply classifier (now with RAG support score as additional feature)
classifier = load_classifier()
df["Transitive Support"] = df["Transitive Support"].fillna(0)
# If classifier was trained with RAG_Support_Score, include it; else, fallback to previous features
feature_cols = ["Similarity", "Transitive Support", "RAG_Support_Score"] if "RAG_Support_Score" in getattr(classifier, "feature_names_in_", []) else ["Similarity", "Transitive Support"]
X = df[feature_cols].values
df["Confidence"] = classifier.predict_proba(X)[:, 1]

# Generate explainable justification for each row
def generate_justification(row):
    en = row.get("Enabling Component", "")
    dep = row.get("Dependent Component", "")
    en_desc = row.get(en_desc_col, "")
    dep_desc = row.get(dep_desc_col, "")
    rag_context = row.get("RAG_Context", "")
    sim = row.get("Similarity", 0)
    rag_score = row.get("RAG_Support_Score", 0)
    # Compose justification
    base = f'"{en}" enables "{dep}" by {en_desc.split(".")[0].lower()}'
    if rag_context:
        base += f". This is supported by prior documentation: {rag_context}"
    if rag_score > 0.5:
        base += f" (High RAG support: {rag_score:.2f})"
    elif sim > 0.7:
        base += f" (High semantic similarity: {sim:.2f})"
    return base

df["Justification"] = df.apply(generate_justification, axis=1)

# Append empty Valid column for inferred rows
df["Valid"] = df["Valid"].fillna("")

# Save to CSV with all relevant columns
output_cols = [
    "Enabling Component",
    "Dependent Component",
    en_desc_col,
    dep_desc_col,
    "Similarity",
    "Transitive Support",
    "RAG_Support_Score",
    "Confidence",
    "Justification",
    "RAG_Context",
    "Valid"
]
df.to_csv("IVN_inferred_with_confidence_and_rag.csv", columns=output_cols, index=False)
print("Inference complete. Output saved to IVN_inferred_with_confidence_and_rag.csv")
