import pandas as pd
import numpy as np
import os

def load_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    print(f"\n📥 Loading file: {file_path}\n")

    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file type. Upload CSV or Excel only.")

    return df


def analyze_data(df):
    print("📊 DATA SUMMARY")
    print("-" * 60)

    print("\n🔹 Shape:", df.shape)
    print("\n🔹 Column Types:")
    print(df.dtypes)

    print("\n🔹 Missing Values:")
    print(df.isnull().sum())

    print("\n🔹 Sample Rows:")
    print(df.head())

    print("\n")


def auto_clean(df):
    print("🧹 STARTING AUTOMATIC CLEANING...\n")

    # ----- Remove duplicate rows -----
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    print(f"✔ Removed {before - after} duplicate rows")

    # ----- Remove empty rows -----
    df = df.dropna(how="all")
    print("✔ Removed fully empty rows")

    # ----- Trim whitespace -----
    df.columns = df.columns.str.strip()
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    print("✔ Trimmed spacing in data")

    # ----- Convert numeric columns -----
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    print("✔ Converted numeric columns where possible")

    # ----- Handle missing values -----
    for col in df.columns:

        if df[col].dtype in ["int64", "float64"]:
            mean_value = df[col].mean()
            df[col].fillna(mean_value, inplace=True)
            print(f"✔ Filled missing numeric values in '{col}' with mean")

        else:
            mode_value = df[col].mode()[0] if not df[col].mode().empty else ""
            df[col].fillna(mode_value, inplace=True)
            print(f"✔ Filled missing categorical values in '{col}' with mode")

    print("\n🎉 Cleaning completed!\n")
    return df


def save_cleaned(df, original_path):
    base = os.path.splitext(original_path)[0]
    cleaned_path = base + "_cleaned.csv"

    df.to_csv(cleaned_path, index=False)

    print(f"📤 Cleaned file saved as: {cleaned_path}")
    return cleaned_path


# ---------------- MAIN PIPELINE --------------------

if __name__ == "__main__":

    file_path = input("📁 Enter the path of your CSV or Excel file: ").strip()

    df = load_file(file_path)

    analyze_data(df)

    cleaned_df = auto_clean(df)

    save_cleaned(cleaned_df, file_path)
