from __future__ import annotations

from pathlib import Path
from textwrap import shorten

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = Path(
    r"C:\Users\Basil.White\OneDrive - USDA\OCIO-STRATUS Governance Document Working Group - Documents"
)
ALIGNMENTS_FILE = SOURCE_DIR / "Alignments.xlsx"
COMPONENTS_FILE = SOURCE_DIR / "Components.xlsx"
TO_BE_FILE = SOURCE_DIR / "To-Be-Crosswalked.xlsx"

DIAGNOSTIC_FILE = BASE_DIR / "excel_diagnostic_report.txt"
OUTPUT_XLSX = BASE_DIR / "top40_alignments.xlsx"
OUTPUT_CSV = BASE_DIR / "top40_alignments.csv"
LEADERSHIP_REPORT = BASE_DIR / "leadership_alignment_report.md"

STARTING_THRESHOLD = 0.64
MINIMUM_THRESHOLD = 0.000001
SELF_MATCH_CEILING = 0.999999
TOP_N = 40
ALIGNMENT_COLUMNS = [
    "Enabling Source",
    "Enabling Component",
    "Enabling Component Description",
    "Dependent Component",
    "Dependent Component Description",
    "Dependent Source",
    "Linkage mandated by what US Code or OMB policy?",
    "Enabling Component URL",
    "Dependent Component URL",
    "Enabling Source Agency",
    "Dependent Source Agency",
    "Notes and keywords",
    "Keywords Tab Items Found",
    "Enabling Component Office of Primary Interest",
    "Dependent Component Office of Primary Interest",
    "edits",
    "valid",
    "similarity",
    "confidence",
    "transitive_support",
    "matched_enabling_index",
    "matched_dependent_index",
    "alignment_rationale",
    "Enabling Fetch Status",
    "Dependent Fetch Status",
    "SimilarityTimesConfidence",
]


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def truncate(value: object, width: int = 260) -> str:
    text = clean_text(value)
    return shorten(text, width=width, placeholder="...") if text else ""


def require_columns(df: pd.DataFrame, workbook: str, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise SystemExit(f"STOP: {workbook} is missing required columns: {missing}")


def diagnostic_pass() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    workbooks = {
        "Alignments.xlsx": ALIGNMENTS_FILE,
        "Components.xlsx": COMPONENTS_FILE,
        "To-Be-Crosswalked.xlsx": TO_BE_FILE,
    }
    diagnostic_lines = [
        "DIAGNOSTIC PASS START",
        f"Working directory: {BASE_DIR}",
        f"Alignments source: {ALIGNMENTS_FILE}",
        f"Components source: {COMPONENTS_FILE}",
        f"To-Be-Crosswalked source: {TO_BE_FILE}",
    ]
    loaded: dict[str, pd.DataFrame] = {}

    for workbook_name, workbook_path in workbooks.items():
        diagnostic_lines.append("\n" + "=" * 100)
        diagnostic_lines.append(f"Workbook: {workbook_name}")
        if not workbook_path.exists():
            raise SystemExit(f"STOP: Missing required file: {workbook_name}")
        try:
            excel = pd.ExcelFile(workbook_path, engine="openpyxl")
        except Exception as exc:
            raise SystemExit(f"STOP: Could not read {workbook_name}: {exc}") from exc

        if not excel.sheet_names:
            raise SystemExit(f"STOP: Workbook has no sheets: {workbook_name}")
        diagnostic_lines.append(f"Sheet names: {excel.sheet_names}")

        for sheet_name in excel.sheet_names:
            try:
                df = pd.read_excel(workbook_path, sheet_name=sheet_name, engine="openpyxl")
            except Exception as exc:
                raise SystemExit(
                    f"STOP: Could not read sheet {sheet_name} in {workbook_name}: {exc}"
                ) from exc
            if df.empty:
                raise SystemExit(f"STOP: Empty sheet {sheet_name} in {workbook_name}")
            diagnostic_lines.append(f"\n--- Sheet: {sheet_name} ---")
            diagnostic_lines.append(f"Shape: {df.shape}")
            diagnostic_lines.append(f"Columns: {list(df.columns)}")
            diagnostic_lines.append("Head:")
            diagnostic_lines.append(df.head(5).map(lambda value: truncate(value, 180)).to_string(index=False))
            if sheet_name == workbook_path.stem or len(excel.sheet_names) == 1:
                loaded[workbook_name] = df

    for workbook_name in workbooks:
        if workbook_name not in loaded:
            raise SystemExit(f"STOP: Could not identify primary sheet in {workbook_name}")

    alignments = loaded["Alignments.xlsx"]
    components = loaded["Components.xlsx"]
    to_be = loaded["To-Be-Crosswalked.xlsx"]

    require_columns(alignments, "Alignments.xlsx", ALIGNMENT_COLUMNS)
    required_component_columns = [
        "component_name",
        "component_description",
        "component_url",
        "component_agency",
        "component_ofc_of_primary_interest",
        "source_id",
        "component_id",
        "fetch_status",
    ]
    require_columns(components, "Components.xlsx", required_component_columns)
    require_columns(to_be, "To-Be-Crosswalked.xlsx", required_component_columns)

    if components["component_description"].dropna().astype(str).str.strip().empty:
        raise SystemExit("STOP: Components.xlsx has no usable component_description values")
    if to_be["component_description"].dropna().astype(str).str.strip().empty:
        raise SystemExit("STOP: To-Be-Crosswalked.xlsx has no usable component_description values")

    diagnostic_lines.append("\nDIAGNOSTIC PASS COMPLETE: all required files readable and structurally valid")
    DIAGNOSTIC_FILE.write_text("\n".join(diagnostic_lines), encoding="utf-8")
    print("Diagnostic pass complete")
    print(f"Diagnostic report: {DIAGNOSTIC_FILE.name}")
    print(f"Alignments rows/columns: {alignments.shape}")
    print(f"Components rows/columns: {components.shape}")
    print(f"To-Be-Crosswalked rows/columns: {to_be.shape}")
    return alignments, components, to_be


def find_alignments(components: pd.DataFrame, to_be: pd.DataFrame) -> tuple[list[dict[str, object]], float, int, int, int, list[tuple[float, int]]]:
    component_descriptions = components["component_description"].fillna("").astype(str).map(clean_text)
    to_be_descriptions = to_be["component_description"].fillna("").astype(str).map(clean_text)
    component_sources = components["source_id"].fillna("").astype(str).map(lambda value: clean_text(value).casefold()).to_numpy()
    to_be_sources = to_be["source_id"].fillna("").astype(str).map(lambda value: clean_text(value).casefold()).to_numpy()

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    combined_corpus = pd.concat([to_be_descriptions, component_descriptions], ignore_index=True)
    vectorizer.fit(combined_corpus)
    to_be_vectors = vectorizer.transform(to_be_descriptions)
    component_vectors = vectorizer.transform(component_descriptions)
    similarity_matrix = cosine_similarity(to_be_vectors, component_vectors)
    cross_source_mask = to_be_sources[:, None] != component_sources[None, :]
    eligible_mask = cross_source_mask & (similarity_matrix < SELF_MATCH_CEILING)

    threshold = STARTING_THRESHOLD
    threshold_matches: list[tuple[int, int, float]] = []
    threshold_history: list[tuple[float, int]] = []
    while threshold >= MINIMUM_THRESHOLD and not threshold_matches:
        threshold_candidates = np.argwhere((similarity_matrix >= threshold) & eligible_mask)
        threshold_matches = [
            (int(to_be_idx), int(component_idx), float(similarity_matrix[to_be_idx, component_idx]))
            for to_be_idx, component_idx in threshold_candidates
        ]
        threshold_history.append((threshold, len(threshold_matches)))
        if not threshold_matches:
            threshold /= 2

    if not threshold_matches:
        threshold = 0.0

    all_candidates = np.argwhere(eligible_mask)
    all_matches = [
        (int(to_be_idx), int(component_idx), float(similarity_matrix[to_be_idx, component_idx]))
        for to_be_idx, component_idx in all_candidates
    ]
    positive_matches = [match for match in all_matches if match[2] > 0]
    selected_matches = sorted(positive_matches, key=lambda item: item[2], reverse=True)[:TOP_N]
    return (
        build_output_rows(selected_matches, components, to_be, vectorizer),
        threshold,
        len(threshold_matches),
        len(all_matches),
        len(positive_matches),
        threshold_history,
    )


def shared_terms(vectorizer: TfidfVectorizer, first_text: str, second_text: str, limit: int = 8) -> str:
    analyzer = vectorizer.build_analyzer()
    first_terms = [term for term in analyzer(first_text) if term not in ENGLISH_STOP_WORDS]
    second_terms = set(term for term in analyzer(second_text) if term not in ENGLISH_STOP_WORDS)
    ordered = []
    for term in first_terms:
        if term in second_terms and term not in ordered and len(term) > 2:
            ordered.append(term)
        if len(ordered) >= limit:
            break
    return ", ".join(ordered)


def get_value(row: pd.Series, column: str) -> object:
    value = row.get(column, "")
    return "" if pd.isna(value) else value


def build_output_rows(
    matches: list[tuple[int, int, float]],
    components: pd.DataFrame,
    to_be: pd.DataFrame,
    vectorizer: TfidfVectorizer,
) -> list[dict[str, object]]:
    output_rows = []
    for to_be_idx, component_idx, score in matches:
        enabling = to_be.iloc[to_be_idx]
        dependent = components.iloc[component_idx]
        enabling_description = clean_text(enabling["component_description"])
        dependent_description = clean_text(dependent["component_description"])
        terms = shared_terms(vectorizer, enabling_description, dependent_description)
        confidence = round(score, 6)
        rationale = (
            f"Potential progression alignment based on shared language"
            f"{': ' + terms if terms else ''}. To-Be-Crosswalked row {to_be_idx + 2}; "
            f"Components row {component_idx + 2}."
        )
        output_rows.append(
            {
                "Enabling Source": get_value(enabling, "source_id"),
                "Enabling Component": get_value(enabling, "component_name"),
                "Enabling Component Description": enabling_description,
                "Dependent Component": get_value(dependent, "component_name"),
                "Dependent Component Description": dependent_description,
                "Dependent Source": get_value(dependent, "source_id"),
                "Linkage mandated by what US Code or OMB policy?": "",
                "Enabling Component URL": get_value(enabling, "component_url"),
                "Dependent Component URL": get_value(dependent, "component_url"),
                "Enabling Source Agency": get_value(enabling, "component_agency"),
                "Dependent Source Agency": get_value(dependent, "component_agency"),
                "Notes and keywords": terms,
                "Keywords Tab Items Found": "",
                "Enabling Component Office of Primary Interest": get_value(enabling, "component_ofc_of_primary_interest"),
                "Dependent Component Office of Primary Interest": get_value(dependent, "component_ofc_of_primary_interest"),
                "edits": "",
                "valid": "",
                "similarity": score,
                "confidence": confidence,
                "transitive_support": "",
                "matched_enabling_index": to_be_idx + 2,
                "matched_dependent_index": component_idx + 2,
                "alignment_rationale": rationale,
                "Enabling Fetch Status": get_value(enabling, "fetch_status"),
                "Dependent Fetch Status": get_value(dependent, "fetch_status"),
                "SimilarityTimesConfidence": score * confidence,
            }
        )
    return output_rows


def write_leadership_report(
    results: pd.DataFrame,
    threshold_used: float,
    threshold_pairs: int,
    total_scored_pairs: int,
    positive_pairs: int,
    threshold_history: list[tuple[float, int]],
    to_be_count: int,
    component_count: int,
) -> None:
    threshold_sentence = "; ".join(f">= {threshold_value:.6f}: {pair_count:,} pairs" for threshold_value, pair_count in threshold_history)
    lines = [
        "# Executive Alignment Report",
        "",
        "## Executive Summary",
        "",
        (
            f"The diagnostic pass successfully loaded Alignments.xlsx, Components.xlsx, and "
            f"To-Be-Crosswalked.xlsx, then compared all {to_be_count:,} To-Be-Crosswalked component descriptions "
            f"against all {component_count:,} Components component descriptions. The scoring pass excluded pairs with "
            f"the same source_id and self-mapping pairs with similarity equal to 1.0. The starting threshold was {STARTING_THRESHOLD:.2f}; "
            f"the first threshold with one or more eligible cross-source pairs was {threshold_used:.6f}, "
            f"producing {threshold_pairs:,} pairs at or above that threshold. The script then considered "
            f"all {total_scored_pairs:,} eligible cross-source scored pairs, including {positive_pairs:,} positive-scoring "
            f"pairs, and exported the {len(results)} highest-similarity cross-source candidate alignments in the exact "
            f"Alignments.xlsx column format. Threshold counts: {threshold_sentence}."
        ),
        "",
        "Leaders should treat these records as candidate alignments for validation, not as final policy determinations. Each candidate identifies a current component that can be managed, clarified, or evidenced to show progress toward the new To-Be requirement.",
        "",
        "## Pair-Specific Recommendations",
        "",
    ]

    if results.empty:
        lines.extend(
            [
                "No eligible cross-source candidate alignments were found after excluding pairs where the To-Be component and Components record share the same source_id.",
                "",
            ]
        )

    for rank, (_, row) in enumerate(results.iterrows(), start=1):
        enabling_name = row["Enabling Component"]
        dependent_name = row["Dependent Component"]
        enabling_row = row["matched_enabling_index"]
        dependent_row = row["matched_dependent_index"]
        similarity = row["similarity"]
        terms = row["Notes and keywords"]
        enabling_description = row["Enabling Component Description"]
        dependent_description = row["Dependent Component Description"]
        lines.extend(
            [
                f"### {rank}. Similarity {similarity:.6f}",
                "",
                f"Matched records: To-Be-Crosswalked.xlsx row {enabling_row}, `{truncate(enabling_name, 180)}`; Components.xlsx row {dependent_row}, `{truncate(dependent_name, 180)}`.",
                "",
                f"Basis: the To-Be record calls for `{truncate(enabling_description, 360)}` The Components record currently addresses `{truncate(dependent_description, 360)}` Shared terms: {terms or 'none captured by TF-IDF analyzer'}.",
                "",
                f"Recommendation: manage `{truncate(dependent_name, 120)}` as an implementation vehicle for the To-Be requirement by adding explicit ownership, milestones, evidence artifacts, and compliance language around `{truncate(terms, 160) or 'the shared operating concepts in the two descriptions'}`. Leadership should direct the responsible office to map its current activities to the To-Be obligation, identify delivery gaps where the current component does not fully satisfy the new language, and update governance status reporting so progress toward `{truncate(enabling_name, 120)}` is visible and auditable.",
                "",
                f"Communication: describe the relationship as a candidate progression alignment: the current component should be communicated as supporting delivery of the To-Be requirement where validation confirms the shared subject matter and operational dependency. Use the row citations above when routing the item for business-owner review.",
                "",
            ]
        )

    LEADERSHIP_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    alignments, components, to_be = diagnostic_pass()
    output_rows, threshold_used, threshold_pairs, total_scored_pairs, positive_pairs, threshold_history = find_alignments(components, to_be)
    results = pd.DataFrame(output_rows, columns=list(alignments.columns))
    results = results.sort_values("similarity", ascending=False)
    results.to_excel(OUTPUT_XLSX, index=False)
    results.to_csv(OUTPUT_CSV, index=False)
    write_leadership_report(results, threshold_used, threshold_pairs, total_scored_pairs, positive_pairs, threshold_history, len(to_be), len(components))

    print("Similarity scoring complete")
    print(f"Threshold used: {threshold_used:.6f}")
    print(f"Candidate cross-source pairs at threshold: {threshold_pairs}")
    print("Threshold history: " + "; ".join(f">= {threshold_value:.6f}: {pair_count}" for threshold_value, pair_count in threshold_history))
    print(f"Total cross-source scored pairs considered: {total_scored_pairs}")
    print(f"Positive cross-source scored pairs considered: {positive_pairs}")
    print(f"Rows exported: {len(results)}")
    print(f"Excel output: {OUTPUT_XLSX.name}")
    print(f"CSV output: {OUTPUT_CSV.name}")
    print(f"Leadership report: {LEADERSHIP_REPORT.name}")


if __name__ == "__main__":
    main()
