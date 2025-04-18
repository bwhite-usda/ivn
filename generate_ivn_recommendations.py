"""
Script: generate_ivn_recommendations_robust.py

Purpose:
Generate rich, strategic recommendations for WS NLI using GPT-4.
Handles interruptions, skips completed rows, and saves progress incrementally.

Requirements:
- openai>=1.0.0
- pandas
"""

import pandas as pd
import openai
import time

# Set your OpenAI API key securely
client = openai.OpenAI(api_key="sk-...")  # <-- Insert your API key here

# Settings
INPUT_FILE = "ivntest.xlsx"
OUTPUT_FILE = "generated_recommendations.xlsx"
SAVE_INTERVAL = 5  # Save every N rows

def generate_recommendation(enabling_desc, dependent_desc):
    prompt = f"""
You are a policy analyst generating rich, strategic recommendations for the USDA Wildlife Services Nonlethal Initiative (WS NLI).
Given the following context:

Enabling Component Description:
"{enabling_desc}"

Dependent Component Description:
"{dependent_desc}"

Generate a unique, insightful recommendation explaining how the Enabling Component can progress the Dependent Component.
Focus on strategic clarity, stakeholder value, and alignment with broader WS NLI goals.
Avoid generic or vague language.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content.strip()

    except openai.RateLimitError:
        print("Rate limit hit. Waiting 60 seconds...")
        time.sleep(60)
        return generate_recommendation(enabling_desc, dependent_desc)

    except openai.APIError as e:
        print(f"API error: {e}. Retrying in 30 seconds...")
        time.sleep(30)
        return generate_recommendation(enabling_desc, dependent_desc)

    except Exception as e:
        print(f"Unexpected error: {e}")
        return "ERROR: " + str(e)

def main():
    try:
        df = pd.read_excel(OUTPUT_FILE)  # Try to resume from output file
        print(f"Resuming from {OUTPUT_FILE}")
    except FileNotFoundError:
        df = pd.read_excel(INPUT_FILE)
        df["Recommendation"] = ""

    for idx, row in df.iterrows():
        if pd.notna(row["Recommendation"]) and str(row["Recommendation"]).strip() != "":
            continue  # Skip completed rows

        if pd.isna(row["Enabling Component Description"]) or pd.isna(row["Dependent Component Description"]):
            continue  # Skip rows without both descriptions

        print(f"Generating recommendation for row {idx+1}...")
        rec = generate_recommendation(str(row["Enabling Component Description"]), str(row["Dependent Component Description"]))
        df.at[idx, "Recommendation"] = rec

        if idx % SAVE_INTERVAL == 0:
            df.to_excel(OUTPUT_FILE, index=False)
            print(f"Progress saved at row {idx+1}")

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"All recommendations saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
