import streamlit as st
st.set_page_config(layout="wide")  # Set the layout to wide
import pandas as pd
from pathlib import Path
import numpy as np
import pickle

# Load the dictionary from the pickle file
with open('classification_table.pkl', 'rb') as file:
    classification_table = pickle.load(file)

# Load the list from the pickle file
with open('complete_df_stoffe.pkl', 'rb') as file:
    complete_df_stoffe = pickle.load(file)

# Title and Description
st.title("BMF Klassifizierung")
st.write("""
Lade den agrolab Auswertungsbericht als Excel Datei hoch und erhalte die BMF Klassifizierung, welche die aktuellsten gesetzlichen Vorgaben erfüllt. Aktuell werden nur Berichte zu einer einzigen Probe unterstützt.
""")

# Step 1: Upload an Excel file
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

if uploaded_file is not None:
    ############################################################
    #START DATA PART OF CODE - WITHOUT FIRST LINE
    ############################################################
    
    # Define filter_values
    filter_values = [
        "Kohlenstoff(C) organisch (TOC)",
        "EOX",
        "Arsen (As)",
        "Blei (Pb)",
        "Cadmium (Cd)",
        "Chrom (Cr)",
        "Kupfer (Cu)",
        "Nickel (Ni)",
        "Quecksilber (Hg)",
        "Thallium (Tl)",
        "Zink (Zn)",
        "Kohlenwasserstoffe C10-C22 (GC)",
        "Kohlenwasserstoffe C10-C40",
        "Benzo(a)pyren",
        "PAK EPA Summe gem. ErsatzbaustoffV",
        "PCB 7 Summe gem. ErsatzbaustoffV",
        "pH-Wert",
        "elektrische Leitfähigkeit",
        "Sulfat (SO4)",
        "Naphthalin/Methylnaph.-Summe gem. ErsatzbaustoffV",
        "PAK 15 Summe gem. ErsatzbaustoffV"
    ]

    # Clean and convert the 'Menge' column to numeric
    def clean_menge(value):
        if isinstance(value, str):
            value = value.replace('<', '') \
                            .replace('>', '') \
                            .replace('<=', '') \
                            .replace('≥', '') \
                            .replace('>=', '') \
                            .replace('≤', '') \
                            .replace('=', '') \
                            .replace(',', '.') \
                            .strip()
        return pd.to_numeric(value, errors='coerce')

    # Step 1: Read the first 6 rows to check if column F exists and if F6 has data
    try:
        temp_df = pd.read_excel(uploaded_file, header=None, nrows=6)
        
        # Check if column F exists in the dataframe
        if temp_df.shape[1] > 5:  # Check if there are more than 5 columns (i.e., column F exists)
            f6_value = temp_df.iloc[5, 5]  # Access cell F6 (row 6, column 6)
            if pd.isna(f6_value):
                f6_exists = False  # F6 exists but is empty
            else:
                f6_exists = True  # F6 exists and is not empty
        else:
            f6_exists = False  # F6 does not exist (out of bounds)

    except Exception as e:
        print(f"Error reading file: {e}")
        f6_exists = False  # If any error occurs, assume F6 is empty or non-existent

    # Step 2: Based on whether F6 exists and is not empty, proceed accordingly
    if not f6_exists:  # Cell F6 is empty or out of bounds
        print("Cell F6 is empty or out of bounds. Proceeding with the usual process...")
        
        # Read the first 15 rows without header to check cell values
        temp_df = pd.read_excel(uploaded_file, header=None, nrows=15)

        # Determine the header row based on cell values
        if temp_df.iloc[9, 0] == "Parameter":
            header_row = 10
        elif temp_df.iloc[6, 0] == "Parameter":
            header_row = 7
        elif temp_df.iloc[13, 0] == "PARAMETER MIT BEWERTUNG NACH MANTELV":
            header_row = 15
        else:
            raise ValueError("Unknown Excel format")

        # Read the data with the correct header
        df = pd.read_excel(uploaded_file, header=header_row, usecols=[0, 1, 4])
        
        # Rename columns based on column indexes
        df.columns = ['Stoff', 'Aggregat', 'Menge']

        # Proceed with filtering and cleaning as before
        df = df[df["Stoff"].isin(filter_values)]
        df['Menge'] = df['Menge'].apply(clean_menge)

        # Update 'Aggregat' for 'pH-Wert'
        df.loc[df['Stoff'] == 'pH-Wert', 'Aggregat'] = '-'

        # Delete the row where 'Stoff' is 'Benzo(a)pyren' and 'Aggregat' is 'µg/l'
        df = df[~((df['Stoff'] == 'Benzo(a)pyren') & (df['Aggregat'] == 'µg/l'))]
        df = df.reset_index(drop=True)
        dataframes = [df]  # Wrap the single dataframe into a list

    else:  # Cell F6 is NOT empty
        print("Cell F6 is not empty. Handling multiple tables...")

        # Check how many columns starting from column E are not empty
        temp_df = pd.read_excel(uploaded_file, header=None, nrows=6)
        non_empty_columns = temp_df.iloc[5, 4:].notna().sum()

        dataframes = []
        for i in range(non_empty_columns):
            col_letter = chr(ord('E') + i)
            df = pd.read_excel(uploaded_file, header=10, usecols=[0, 1, 4 + i])
            df.columns = ['Stoff', 'Aggregat', 'Menge']
            df = df[df["Stoff"].isin(filter_values)]
            df['Menge'] = df['Menge'].apply(clean_menge)
            df.loc[df['Stoff'] == 'pH-Wert', 'Aggregat'] = '-'
            df = df[~((df['Stoff'] == 'Benzo(a)pyren') & (df['Aggregat'] == 'µg/l'))]
            df = df.reset_index(drop=True)
            dataframes.append(df)


    ############################################################
    #END DATA PART OF CODE
    ############################################################

    # User inputs via dropdowns
    subcategory_options = ['Sand', 'Lehm Schluff', 'Ton']
    subcategory = st.selectbox('Select Subcategory', subcategory_options)
    
    fremdbestandteile_option = st.selectbox('Are Fremdbestandteile under 10%?', ['Yes', 'No'])
    fremdbestandteile_under_10 = True if fremdbestandteile_option == 'Yes' else False

    if st.button('Run'):
        def classify_bmf(row, df, subcategory=None):
            stoff = row['Stoff']
            aggregat = row['Aggregat']
            menge = row['Menge']

            if stoff in ['Sulfat', 'Sulfat (SO4)']:
                aggregat = 'mg/l'

            toc_indicator = None

            if 'Kohlenstoff(C) organisch (TOC)' in df['Stoff'].values:
                toc_menge = df.loc[df['Stoff'] == 'Kohlenstoff(C) organisch (TOC)', 'Menge'].iloc[0]
                toc_indicator = 'TOC' if toc_menge > 0.5 else 'no_TOC'
            else:
                toc_indicator = 'no_TOC'

            if stoff in classification_table and aggregat in classification_table[stoff]:
                stoff_agg = classification_table[stoff][aggregat]

                if isinstance(stoff_agg, dict) and 'thresholds' not in stoff_agg:
                    if subcategory in stoff_agg:
                        stoff_data = stoff_agg[subcategory]
                    elif toc_indicator in stoff_agg:
                        stoff_data = stoff_agg[toc_indicator]
                    else:
                        row['BMF_primär'] = "Not Classified"
                        return row
                else:
                    stoff_data = stoff_agg

                thresholds = stoff_data['thresholds']
                classifications = stoff_data['classifications']

                valid_thresholds = [threshold for threshold in thresholds if threshold > menge]
                if valid_thresholds:
                    min_threshold = min(valid_thresholds)
                    for idx, threshold in enumerate(thresholds):
                        if threshold == min_threshold:
                            row['BMF_primär'] = classifications[idx]
                            break
                else:
                    if stoff in ["Benzo(a)pyren", "EOX"] and menge > thresholds[-1]:
                        row['BMF_primär'] = "> BM-0 BG-0"
                    else:
                        row['BMF_primär'] = ">BM-F3 BG-F3"
            else:
                row['BMF_primär'] = "Not Classified"

            return row

        def fullpipeline(df, subcategory="Sand", eluat=True, fremdbestandteile_under_10=True):
            df = df.apply(lambda row: classify_bmf(row, df, subcategory=subcategory), axis=1)
            df['BMF_sekundär'] = df['BMF_primär']
            df['Relevante_Klassen'] = ''
            return df

        final_dfs = []
        for idx, df in enumerate(dataframes):
            final_df = fullpipeline(df, subcategory=subcategory, eluat=True, fremdbestandteile_under_10=fremdbestandteile_under_10)
            final_dfs.append(final_df)

        # Display each dataframe as a separate table in Streamlit
        for i, final_df in enumerate(final_dfs):
            st.subheader(f"Ausgewertete Tabelle {i + 1}")
            st.dataframe(final_df, use_container_width=True)

        # Combine all dataframes if needed for download
        final_result = pd.concat(final_dfs, ignore_index=True)

        # Provide download option for the combined dataframe
        csv = final_result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download data as CSV",
            data=csv,
            file_name='processed_dataframe.csv',
            mime='text/csv',
        )
else:
    st.info("Please upload an Excel file to proceed.")
