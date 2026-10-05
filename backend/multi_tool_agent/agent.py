import os
import math
import pandas as pd  # type: ignore
import numpy as np
from typing import List, Optional
from google.adk.agents import Agent

# ======================================================
# SESSION & UTILITIES
# ======================================================
SESSION = {
    "last_file_path": None,
    "original_df": None,   # stores original dataframe (unchanged)
    "history": []          # list[str] of techniques applied in order
}

def json_safe(obj):
    """Convert NaN & Infinity to JSON-safe None."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(i) for i in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

# Helper: apply a list of techniques to a DataFrame (mutates copy)
def apply_techniques_to_df(df: pd.DataFrame, techniques: List[str]) -> pd.DataFrame:
    """Apply techniques in order to a dataframe and return the transformed df."""
    # safe datetime function
    def safe_to_datetime(val):
        try:
            return pd.to_datetime(val)
        except Exception:
            return val

    # operate on a copy
    df = df.copy()

    for step in techniques:
        if step == "remove_duplicates":
            df = df.drop_duplicates()

        elif step == "trim_whitespace":
            # Trim whitespace only on object/string columns (safer)
            for col in df.select_dtypes(include=["object"]).columns:
                # keep NaNs intact
                df[col] = df[col].astype("string").str.strip().replace("<NA>", pd.NA)
                # convert back to original dtype if needed (string dtype kept is fine)

        elif step.startswith("fill_missing_numeric:"):
            col = step.split(":", 1)[1]
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())

        elif step.startswith("fill_missing_categorical:"):
            col = step.split(":", 1)[1]
            if col in df.columns:
                mode = df[col].mode()
                df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "")

        elif step.startswith("remove_outliers_iqr:"):
            col = step.split(":", 1)[1]
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                df = df[(df[col] >= Q1 - 1.5 * IQR) & (df[col] <= Q3 + 1.5 * IQR)]

        elif step.startswith("convert_to_datetime:"):
            col = step.split(":", 1)[1]
            if col in df.columns:
                # apply safe conversion that keeps non-dates
                df[col] = df[col].apply(safe_to_datetime)

        elif step.startswith("frequency_encoding:"):
            col = step.split(":", 1)[1]
            if col in df.columns:
                freq = df[col].value_counts(normalize=True)
                df[col] = df[col].map(freq).fillna(0)

        # Unknown / unsupported steps are ignored silently
    return df

# ======================================================
# TOOL 1 — analyze_dataset
# ======================================================
def analyze_dataset(file_path: str) -> dict:
    """
    Load CSV/Excel and return dataset summary.
    Stores the original DataFrame snapshot for undo/rebuild behavior.
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            return {"status": "error", "error_message": "Unsupported file type. Upload CSV or Excel only."}

        # store snapshot and reset history
        SESSION["last_file_path"] = file_path
        SESSION["original_df"] = df.copy()
        SESSION["history"] = []

        summary = {
            "shape": df.shape,
            "column_types": df.dtypes.astype(str).to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "missing_percent": (df.isnull().mean() * 100).round(2).replace(np.nan, 0).to_dict(),
            "cardinality": df.nunique().to_dict(),
            "sample_rows": df.head(5).fillna("").to_dict(orient="records")
        }

        # outlier detection (IQR) for numeric columns
        outliers = {}
        for col in df.select_dtypes(include=["number"]).columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            mask = (df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))
            outliers[col] = int(mask.sum())
        summary["outliers"] = outliers

        return {"status": "success", "analysis": json_safe(summary)}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ======================================================
# TOOL 2 — recommend_cleaning_steps
# ======================================================
def recommend_cleaning_steps(analysis: dict) -> dict:
    """Recommend cleaning techniques based on dataset analysis dict returned by analyze_dataset."""
    try:
        missing = analysis.get("missing_percent", {})
        outliers = analysis.get("outliers", {})
        coltypes = analysis.get("column_types", {})
        cardinality = analysis.get("cardinality", {})
        sample_rows = analysis.get("sample_rows", [])

        suggestions = []

        # Missing values
        for col, perc in missing.items():
            if perc > 0:
                if coltypes.get(col) in ["int64", "float64"]:
                    method = "mean" if perc < 20 else "median"
                    suggestions.append({
                        "technique": f"fill_missing_numeric:{col}",
                        "reason": f"{perc}% missing — numeric — recommend {method} imputation."
                    })
                else:
                    suggestions.append({
                        "technique": f"fill_missing_categorical:{col}",
                        "reason": f"{perc}% missing — categorical — recommend mode imputation."
                    })

        # Outliers
        for col, count in outliers.items():
            if count > 0:
                suggestions.append({
                    "technique": f"remove_outliers_iqr:{col}",
                    "reason": f"{count} outliers detected — recommend IQR removal."
                })

        # Duplicates
        suggestions.append({"technique": "remove_duplicates", "reason": "Check for duplicate rows."})

        # Trim whitespace
        if any(v == "object" for v in coltypes.values()):
            suggestions.append({"technique": "trim_whitespace", "reason": "Trim whitespace from string columns."})

        # Date-like heuristic (simple)
        for col in coltypes:
            if coltypes[col] == "object":
                values = [row.get(col) for row in sample_rows if row.get(col)]
                if any(isinstance(v, str) and ("/" in v or "-" in v) for v in values):
                    suggestions.append({
                        "technique": f"convert_to_datetime:{col}",
                        "reason": f"Column '{col}' contains date-like patterns."
                    })

        # High-cardinality
        for col, unique in cardinality.items():
            if coltypes.get(col) == "object" and unique > 25:
                suggestions.append({
                    "technique": f"frequency_encoding:{col}",
                    "reason": f"{unique} unique values — high-cardinality encoding candidate."
                })

        return {"status": "success", "suggestions": json_safe(suggestions)}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ======================================================
# TOOL 3 — clean_dataset (rebuild-from-original semantics)
# ======================================================
def clean_dataset(file_path: Optional[str] = None, techniques: Optional[List[str]] = None) -> dict:
    """
    Apply selected techniques. Behavior:
    - If techniques provided, they are appended to SESSION['history'] (skipping already-applied ones).
    - The cleaned dataset is built by starting from SESSION['original_df'] and applying all techniques in SESSION['history'] in order.
    """
    try:
        if not file_path:
            file_path = SESSION.get("last_file_path")
        if not file_path:
            return {"status": "error", "error_message": "No file selected. Analyze a file first."}
        if SESSION.get("original_df") is None:
            return {"status": "error", "error_message": "Original dataset not available. Run analyze_dataset first."}
        if not techniques:
            return {"status": "error", "error_message": "No techniques provided."}

        # Ensure techniques is a list
        new_techs = list(techniques)

        # Append only techniques that are not already in history (avoid duplicates)
        skipped = []
        appended = []
        for t in new_techs:
            if t in SESSION["history"]:
                skipped.append(t)
            else:
                SESSION["history"].append(t)
                appended.append(t)

        # Rebuild from original by applying the full history
        df_orig = SESSION["original_df"].copy()
        df_clean = apply_techniques_to_df(df_orig, SESSION["history"])

        # Save cleaned file
        cleaned_path = os.path.splitext(file_path)[0] + "_cleaned.csv"
        df_clean.to_csv(cleaned_path, index=False)
        cleaned_json = df_clean.fillna("").to_dict(orient="records")


        return {
            "status": "success",
            "message": "Techniques applied.",
            "applied": SESSION["history"],
            "skipped_already_applied": skipped,
            "cleaned_file_path": cleaned_path,
            "cleaned_data": json_safe(cleaned_json) 
        }

    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ======================================================
# TOOL 4 — undo_cleaning (supports full & selective undo via rebuild)
# ======================================================
def undo_cleaning(techniques_to_undo: Optional[List[str]] = None) -> dict:
    """
    Undo behavior (rebuild-from-original):
    - If techniques_to_undo is None or empty -> full undo: restore original file and clear history.
    - If a list of techniques is provided, remove those techniques from SESSION['history'] (all occurrences)
      and rebuild the cleaned file by applying the remaining techniques from the original.
    """
    try:
        if SESSION.get("original_df") is None or SESSION.get("last_file_path") is None:
            return {"status": "error", "error_message": "No dataset to undo. Analyze first."}

        original_path = SESSION["last_file_path"]
        original_df = SESSION["original_df"].copy()

        # Full undo if no specific techniques passed
        if not techniques_to_undo:
            restored_path = os.path.splitext(original_path)[0] + "_restored.csv"
            original_df.to_csv(restored_path, index=False)
            # clear history
            SESSION["history"] = []
            return {"status": "success", "message": "Full undo performed. Original restored.", "restored_file": restored_path}

        # Selective undo: remove the provided techniques from history (all occurrences)
        remaining_history = [t for t in SESSION["history"] if t not in techniques_to_undo]
        SESSION["history"] = remaining_history

        # Rebuild cleaned DF using the remaining history
        df_rebuilt = apply_techniques_to_df(original_df, SESSION["history"])
        cleaned_path = os.path.splitext(original_path)[0] + "_cleaned.csv"
        df_rebuilt.to_csv(cleaned_path, index=False)

        return {
            "status": "success",
            "message": "Selective undo performed. Rebuilt cleaned dataset without the specified techniques.",
            "remaining_history": SESSION["history"],
            "cleaned_file": cleaned_path
        }

    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ======================================================
# AGENT DEFINITION
# ======================================================
root_agent = Agent(
    name="data_cleaning_agent",
    model="gemini-2.0-flash",
    description="Data-cleaning agent with rebuild-from-original undo and selective undo support.",
   instruction=(
    "You are a data-cleaning assistant. Follow these rules EXACTLY:\n\n"

    "==================== ANALYSIS RULE ====================\n"
    "When the user types any of the following patterns, you MUST call:\n"
    "   analyze_dataset(file_path=<path>)\n\n"
    "Valid analysis commands include:\n"
    "   • Analyze <file_path>\n"
    "   • Analyze this file: <file_path>\n"
    "   • Analyze dataset <file_path>\n"
    "   • Run analysis on <file_path>\n"
    "   • Load and analyze <file_path>\n"
    "Where <file_path> is a path ending in .csv, .xlsx, or .xls.\n\n"
    "After analyze_dataset returns, you MUST call recommend_cleaning_steps(analysis).\n"
    "Then STOP and WAIT for user instructions.\n\n"

    "==================== CLEANING RULE ====================\n"
    "If the user says 'apply', 'clean', 'use', 'perform', or gives a list of techniques,\n"
    "you MUST call:\n"
    "   clean_dataset(techniques=[...])\n"
    "Do NOT apply cleaning automatically.\n\n"

    "==================== UNDO RULE ====================\n"
    "If the user says 'undo', 'restore', or 'revert':\n"
    "   • If no techniques listed → call undo_cleaning()\n"
    "   • If techniques listed → call undo_cleaning(techniques_to_undo=[...])\n\n"

    "==================== NEVER DO THESE ====================\n"
    "• NEVER apply any technique automatically.\n"
    "• NEVER undo automatically.\n"
    "• NEVER assume which technique the user wants.\n"
    "• NEVER call multiple tools unless required in the steps above.\n\n"

    "Your job is ONLY to call tools when the USER explicitly asks.\n"
),


    tools=[analyze_dataset, recommend_cleaning_steps, clean_dataset, undo_cleaning]
)
