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
Lade den Auswertungsbericht als Excel Datei hoch und erhalte die BMF Klassifizierung, welche die aktuellsten gesetzlichen Vorgaben erfüllt. Aktuell werden nur Berichte des Labors Agrolab unterstützt.
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

    ############################################################
    #START PRIMARY CLASSIFICATION PART OF CODE
    ############################################################

        def classify_bmf(row, df, subcategory=None):
            stoff = row['Stoff']
            aggregat = row['Aggregat']
            menge = row['Menge']

            # Map 'Stoff' to 'Aggregat' if needed
            if stoff in ['Sulfat', 'Sulfat (SO4)']:
                aggregat = 'mg/l'

            # Determine 'toc_indicator' within the function
            # Initialize 'toc_indicator'
            toc_indicator = None

            # Check if 'Kohlenstoff(C) organisch (TOC)' exists in the dataframe
            if 'Kohlenstoff(C) organisch (TOC)' in df['Stoff'].values:
                # Get the 'Menge' value for 'Kohlenstoff(C) organisch (TOC)'
                toc_menge = df.loc[df['Stoff'] == 'Kohlenstoff(C) organisch (TOC)', 'Menge'].iloc[0]
                # Determine the 'toc_indicator' value
                if toc_menge > 0.5:
                    toc_indicator = 'TOC'
                else:
                    toc_indicator = 'no_TOC'
            else:
                # Default value if 'Kohlenstoff(C) organisch (TOC)' is not found
                toc_indicator = 'no_TOC'

            # Classification logic
            if stoff in classification_table and aggregat in classification_table[stoff]:
                stoff_agg = classification_table[stoff][aggregat]

                # Check if subcategory is needed
                if isinstance(stoff_agg, dict) and 'thresholds' not in stoff_agg:
                    # Subcategory is needed
                    if subcategory in stoff_agg:
                        stoff_data = stoff_agg[subcategory]
                    elif toc_indicator in stoff_agg:
                        # Use 'toc_indicator' as subcategory
                        stoff_data = stoff_agg[toc_indicator]
                    else:
                        # Proceed as if there was no subcategory
                        row['BMF_primär'] = "Not Classified"
                        return row
                else:
                    stoff_data = stoff_agg

                thresholds = stoff_data['thresholds']
                classifications = stoff_data['classifications']

                # Find the smallest threshold larger than 'menge'
                valid_thresholds = [threshold for threshold in thresholds if threshold > menge]

                if valid_thresholds:
                    # Get the smallest threshold larger than 'menge'
                    min_threshold = min(valid_thresholds)

                    # Find the rightmost occurrence of this smallest threshold
                    #for idx in range(len(thresholds) - 1, -1, -1):
                    #    if thresholds[idx] == min_threshold:
                    #        row['BMF_primär'] = classifications[idx]
                    #        break

                    # Find the leftmost occurrence of this smallest threshold
                    for idx, threshold in enumerate(thresholds):
                        if threshold == min_threshold:
                            row['BMF_primär'] = classifications[idx]
                            break
                    
                else:
                    # Handle cases where no valid threshold is found
                    # Check if "Stoff" is "Benzo(a)pyren" or "EOX" and "Menge" exceeds the rightmost threshold
                    if stoff in ["Benzo(a)pyren", "EOX"] and menge > thresholds[-1]:
                        row['BMF_primär'] = "> BM-0 BG-0"
                    else:
                        row['BMF_primär'] = ">BM-F3 BG-F3"
            else:
                row['BMF_primär'] = "Not Classified"

            return row
        

        ############################################################
        #END PRIMARY CLASSIFICATION PART OF CODE
        ############################################################



        ############################################################
        #START DETAILED CLASSIFICATION PART OF CODE
        ############################################################

        def check_combinations(df):
            # Extract the combinations of Stoff and Aggregat from the new dataframe
            current_combinations = list(df[['Stoff', 'Aggregat']].drop_duplicates().itertuples(index=False, name=None))
            
            # Only compare the first two values (Stoff and Aggregat) from complete_df_stoffe
            stoffe_aggregat_combinations = [(stoff, aggregat) for stoff, aggregat, _ in complete_df_stoffe]
            
            # Identify the missing combinations
            missing_combinations = [comb for comb in stoffe_aggregat_combinations if comb not in current_combinations]
            
            # If there are missing combinations, raise an error with details
            if missing_combinations:
                raise ValueError(f"Missing combinations: {missing_combinations}")
            else:
                print("All combinations are present.")

        ###############################################################
        # Step one: Initialize new columns and apply default conditions


        
        # Erklärung der drei Spalten
        # BMF_primär = Primäre Klassifizierung ohne Fußnoten
        # BMF_sekundär = Sekundäre Klassifizierung inklusive aller Fußnoten
        # Relevante_Klassen = Ausschließlich für die Ausweisung relevante Klassen
   
        # Definition der relevanten Spalten für die Eluat Klausel Funktion
        # Ausnahme von Stoffen, welche nur BM-0* und gar nicht BM-0 werden können: - 
        #     - Naphthalin/Methylnaph.-Summe gem. ErsatzbaustoffV
        #     - EOX
        #     - TOC
        #     - Beide Kohlenwasserstoffe
        #     - Alle Eluat-Werte
        #     - elektr. Leitfähigkeit
        #     - pH-Wert
        # 11 Stoffe, welche einen Eluat Wert haben, der bei "BM-0*" Klasse geprüft werden muss
        

        eluat_stoffe = [
            'Arsen (As)', 'Blei (Pb)', 'Cadmium (Cd)', 'Chrom (Cr)', 'Kupfer (Cu)',
            'Nickel (Ni)', 'Quecksilber (Hg)', 'Thallium (Tl)', 'Zink (Zn)',
            'PAK EPA Summe gem. ErsatzbaustoffV', 'PCB 7 Summe gem. ErsatzbaustoffV'
        ]
        eluat_list = eluat_stoffe.copy()

        #Definition der Stoffe, welche in ihrer F-Klasse relevant sind und alle Eluat Werte triggern
        # Naphthalin, beide PCBs, EOX und Benzo(a)pyren haben keine F-Klasse, daher auch nicht in Eskalationsliste
        f_eskalation_stoffe = [
            'Arsen (As)', 'Blei (Pb)', 'Cadmium (Cd)', 'Chrom (Cr)', 'Kupfer (Cu)',
            'Nickel (Ni)', 'Quecksilber (Hg)', 'Thallium (Tl)', 'Zink (Zn)',
            'PAK EPA Summe gem. ErsatzbaustoffV', 'Sulfat (SO4)', 'Kohlenwasserstoffe C10-C22 (GC)',
            'Kohlenwasserstoffe C10-C40', 'Kohlenstoff(C) organisch (TOC)', 'EOX', 'PCB 7 Summe gem. ErsatzbaustoffV'
        ]
        f_eskalation_list = f_eskalation_stoffe.copy()

        alle_stoffe = [
            'Arsen (As)', 'Blei (Pb)', 'Cadmium (Cd)', 'Chrom (Cr)', 'Kupfer (Cu)',
            'Nickel (Ni)', 'Quecksilber (Hg)', 'Thallium (Tl)', 'Zink (Zn)',
            'PAK EPA Summe gem. ErsatzbaustoffV', 'Sulfat (SO4)', 'Kohlenwasserstoffe C10-C22 (GC)',
            'Kohlenwasserstoffe C10-C40', 'Kohlenstoff(C) organisch (TOC)', 'EOX', 'PCB 7 Summe gem. ErsatzbaustoffV'
        ]

        # Definition der kritischen Klassen, welche eine Eskalation auslösen
        bmf_f_list = ['>BM-0* BG-0*', 'BM-F0* BG-F0*', 'BM-F1 BG-F1', 'BM-F2 BG-F2', 'BM-F3 BG-F3']

        # Definition eines triggers, welcher alle Stoffe für die Auswertung relevant macht (F-Klasse bei einem der Stoffe)
        # Konsequenz: Jeder Stoff wird in der Auswertung berücksichtigt
        f_trigger = False

        # Definition eines triggers, welcher relevant wird, wenn eine Feststoff Klasse im BM-0* liegt
        # Konsequenz: Elektrische Leitfähigkeit wird in der Auswertung berücksichtigt
        d_trigger = False

        ###############################################################
        # Step two: Initialize eluat and f-trigger functions
        
        def eluat_klausel(df):

            global f_trigger  # Declare to modify the global f_trigger
            global d_trigger  # Declare to modify the global f_trigger


            # Checken welche Stoffe relevant sind für die Eluat Klausel, und ob ein Stoff ausschlägt
            eluat_condition = df['Stoff'].isin(eluat_list) & (df['Aggregat']!= 'µg/l') & (df['BMF_primär'] == 'BM-0* BG-0*')
            eluat_relevant = df.loc[eluat_condition, 'Stoff'].unique().tolist()

            if eluat_relevant: 

                d_trigger = True

                # Für alle Werte, die BM-0* erfüllen, relevante Klassen ausfüllen 
                df.loc[eluat_condition, ['Relevante_Klassen']] = 'BM-0* BG-0*'

                # Für jeden Wert in die Fallprüfung gehen
                for stoff in eluat_relevant:
                    condition_stoff_ug_l = (df['Stoff'] == stoff) & (df['Aggregat'] == 'µg/l')
                    if not condition_stoff_ug_l.any():
                        continue

                    # Falls der Eluat Wert in der BM-0* Klasse liegt, nichts tun
                    bmf_klass_ug_l = df.loc[condition_stoff_ug_l, 'BMF_primär'].values[0]
                    if bmf_klass_ug_l == 'BM-0* BG-0*':
                        continue
                    
                    # !!GROßER ELUATESKALATIONSFALL EINS!!
                    # Falls der Eluat in einer kritische Klasse liegt, triggert das den großen Eluat Eskalationsfall
                    elif bmf_klass_ug_l in bmf_f_list:

                        # Erste Konsequenz: Die relevante Klasse für diesen Eluat Wert ausfüllen
                        df.loc[condition_stoff_ug_l, 'Relevante_Klassen'] = bmf_klass_ug_l
                        
                        # Zweite Konsequenz: Der globale F-Klasse trigger wird aktiviert, was für die Auswertung relevanter Werte später relevant ist
                        f_trigger = True

            return df

        def f_klausel(df):
            
            global f_trigger  # Declare to modify the global f_trigger
            
            # Checken welche Stoffe relevant sind für die F-trigger Klausel, und ob ein Stoff ausschlägt
            f_condition = df['Stoff'].isin(f_eskalation_list) & (df['Aggregat']!= 'µg/l') & (df['BMF_primär'].isin(bmf_f_list))
            f_relevant = df.loc[f_condition, 'Stoff'].unique().tolist()
            
            if f_relevant: 

                # F-klausel aktivieren, falls Stoffe in dieser liste sind
                f_trigger = True

                # Nicht notwendig, die relevante Klasse auszufüllen, denn das wird später eh gemacht, da der f_trigger aktiviert ist

            return df

        
        # Erste Relevanzprüfung:
        # - Wenn f_trigger true 
        #     -> Alle Stoffe prüfen
        #     -> Wenn ein Stoff nicht seine niedrigmöglichste  Klasse hat, dann in relevante Spalte schreiben
        # - Wenn d_trigger true
        #     -> elektrische Leitfähigkeit prüfen und wenn nicht in niedrigster Klasse, dann in relevante Spalte schreiben
        


        def erste_relevanzprüfung(df):

            # Checken, ob irgendein Stoff nicht seine kleinste BMF Klasse hat ->  Falls Ja: Übertrag in relevante Spalte
            if f_trigger == True:

                # Create a dictionary from complete_df_stoffe for quick lookup
                stoffe_aggregat_dict = {(stoff, aggregat): smallest_BMF for stoff, aggregat, smallest_BMF in complete_df_stoffe}

                # Iterate through each row in df
                for index, row in df.iterrows():
                    stoff = row['Stoff']
                    aggregat = row['Aggregat']
                    bmf_sekundär = row['BMF_sekundär']
                    
                    # Lookup the smallest_BMF for the combination of Stoff and Aggregat
                    if (stoff, aggregat) in stoffe_aggregat_dict:
                        smallest_bmf = stoffe_aggregat_dict[(stoff, aggregat)]
                        
                        # Check if the BMF_sekundär is not equal to the smallest_BMF
                        if bmf_sekundär != smallest_bmf:
                            # Update the Relevante_Klassen column with smallest_BMF
                            df.at[index, 'Relevante_Klassen'] = bmf_sekundär

            if d_trigger == True: 

                # Create a dictionary from complete_df_stoffe for quick lookup
                stoffe_aggregat_dict = {(stoff, aggregat): smallest_BMF for stoff, aggregat, smallest_BMF in complete_df_stoffe}

                # Iterate through each row in df
                for index, row in df.iterrows():
                    stoff = row['Stoff']
                    aggregat = row['Aggregat']
                    bmf_sekundär = row['BMF_sekundär']

                    if stoff == "elektrische Leitfähigkeit":
                    
                        # Lookup the smallest_BMF for the combination of Stoff and Aggregat
                        if (stoff, aggregat) in stoffe_aggregat_dict:
                            smallest_bmf = stoffe_aggregat_dict[(stoff, aggregat)]
                            
                            # Check if the BMF_sekundär is not equal to the smallest_BMF
                            if bmf_sekundär != smallest_bmf:
                                # Update the Relevante_Klassen column with smallest_BMF
                                df.at[index, 'Relevante_Klassen'] = bmf_sekundär
            
            return df


        ###############################################################
        # Step four: Define more special cases

        # TODO!!

        ############################################################
        #END DETAILED CLASSIFICATION PART OF CODE
        ############################################################


        ############################################################
        #START PUT IT ALL TOGETHER PART OF CODE
        ############################################################

        def fullpipeline(df, subcategory="Sand", eluat=True, fremdbestandteile_under_10=True):
            # 1 Step: Apply the classify_bmf function to the dataframe with the given subcategory
            df = df.apply(lambda row: classify_bmf(row, df, subcategory=subcategory), axis=1)
            df['BMF_sekundär'] = df['BMF_primär']
            df['Relevante_Klassen'] = ''

            # 3 Step: Eluat Prüfung
            if eluat:
                #print("Running Eluat Prüfung...")
                df = eluat_klausel(df)

            # 4 Step: F-Klasse Prüfung
            #print("Running F-Klasse Prüfung...")
            df = f_klausel(df)

            # 5 Step: Erste Relevanzprüfung 
            #print("Running Erste Relevanzprüfung...")
            df = erste_relevanzprüfung(df)

            check_combinations(df)
            #print("Pipeline completed.")
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
