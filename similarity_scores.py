# similarity_scores.py performs causal inference alignment between two sets of components from an Excel file, using simple heuristics and semantic similarity, to automatically infer and document plausible causal relationships between components in two datasets, aiding in causal analysis and alignment for IVN (Integrated Value Network) projects.

import os
import sys
import time
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Paths and loading
script_dir = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(script_dir, 'ivntest.xlsx')

df_usda = pd.read_excel(input_path, sheet_name='Internal-Dataset')
df_unaligned = pd.read_excel(input_path, sheet_name='new-unaligned-components')

def is_valid(row, prefix):
    return pd.notna(row.get(f"{prefix} Component")) and pd.notna(row.get(f"{prefix} Component Description")) \
        and str(row.get(f"{prefix} Component")).strip() and str(row.get(f"{prefix} Component Description")).strip()

def extract_components(df, prefix):
    return [
        (
            row[f"{prefix} Component"],
            row[f"{prefix} Component Description"],
            row.get(f"{prefix} Source", ""),
            row.get(f"{prefix} Component URL", "")
        )
        for _, row in df.iterrows()
        if is_valid(row, prefix)
    ]

en_usda = extract_components(df_usda, "Enabling")
dep_usda = extract_components(df_usda, "Dependent")
en_unaligned = extract_components(df_unaligned, "Enabling")
dep_unaligned = extract_components(df_unaligned, "Dependent")

def infer_causal_link(enabling, dependent):
    """
    Returns (justification, score) if a plausible causal link exists, else (None, 0).
    This is a placeholder for a more advanced causal inference model.
    """
    en_name, en_desc, _, _ = enabling
    dep_name, dep_desc, _, _ = dependent

    # 1. Avoid topic-only matches (basic filter: skip if high similarity but no action/resource/causal verb)
    # 2. Prefer cross-agency, cross-domain, or cross-document links
    # 3. Check for enabling verbs/resources in Enabling, and outcome/requirement in Dependent

    # Simple heuristics for demonstration:
    causal_verbs = ["enable", "support", "provide", "supply", "reduce", "accelerate", "improve", "facilitate", "ensure", "deliver", "implement", "develop", "guide", "authorize", "fund", "connect", "integrate"]
    outcome_words = ["outcome", "result", "compliance", "delivery", "performance", "risk", "speed", "law", "priority", "goal", "objective", "requirement", "platform", "environment", "system"]

    # Check if enabling description contains a causal verb
    en_desc_lower = en_desc.lower()
    dep_desc_lower = dep_desc.lower()
    if not any(verb in en_desc_lower for verb in causal_verbs):
        return (None, 0)

    # Check if dependent description contains an outcome word
    if not any(word in dep_desc_lower for word in outcome_words):
        return (None, 0)

    # If both are present, infer a causal link
    # Justification template:
    justification = f"{en_name} {en_desc.split('.')[0]} enables or accelerates {dep_name.lower()} by providing critical inputs or reducing barriers."
    # Score: combine semantic similarity and presence of causal terms
    vectorizer = TfidfVectorizer().fit([en_desc, dep_desc])
    sim = cosine_similarity(vectorizer.transform([en_desc]), vectorizer.transform([dep_desc]))[0, 0]
    # Boost score if both causal and outcome terms are present
    score = int(60 + 40 * sim)
    return (justification, score)

def generate_ivn_alignments(enabling_list, dependent_list):
    alignments = []
    total = len(enabling_list) * len(dependent_list)
    done = 0
    start_time = time.time()
    for i, en in enumerate(enabling_list):
        for j, dep in enumerate(dependent_list):
            justification, score = infer_causal_link(en, dep)
            if score >= 60:  # Only keep plausible causal links
                alignments.append({
                    "Enabling Component": en[0],
                    "Dependent Component": dep[0],
                    "Justification": justification,
                    "Similarity Score": score
                })
            done += 1
            if done % 1000 == 0 or done == total:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                left = total - done
                eta = left / rate if rate > 0 else 0
                status = f"Processed: {done}/{total} | Left: {left} | ETA: {int(eta)}s"
                sys.stdout.write('\r' + ' ' * 80 + '\r')
                sys.stdout.write(status)
                sys.stdout.flush()
    print()
    return alignments

print("Inferring IVN causal alignments (Enabling → Dependent)...")
alignments1 = generate_ivn_alignments(en_usda, dep_unaligned)
print("Inferring IVN causal alignments (Dependent → Enabling)...")
alignments2 = generate_ivn_alignments(dep_usda, en_unaligned)

all_alignments = alignments1 + alignments2
output_df = pd.DataFrame(all_alignments)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = os.path.join(script_dir, f'ivn_inferred_causal_output_{timestamp}.csv')
print("Saving output file...")
output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"Output saved to: {output_path}")