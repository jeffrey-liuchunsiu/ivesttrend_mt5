import pandas as pd
import os

def get_csv_file_path(filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)

def download_and_process_CPI_excel(url, sheet_name):
    df = pd.read_excel(url, sheet_name=sheet_name)
    df = df.iloc[:, [0, 16]]
    df = df.rename(columns={"Date": "DATE", "12mo.3": "CORESTICKM159SFRBATL"})
    df['DATE'] = pd.to_datetime(df['DATE']).dt.strftime('%Y-%m-%d')
    df = df[["DATE", "CORESTICKM159SFRBATL"]].reset_index(drop=True)
    df = df[df["CORESTICKM159SFRBATL"] != "na"]
    return df

def save_to_csv(df, file_path):
    df.to_csv(file_path, index=False)

# def main():
#     csv_file_path = get_csv_file_path('CORESTICKM159SFRBATL.csv')
#     url = "https://www.atlantafed.org/-/media/documents/datafiles/research/inflationproject/stickprice/stickyprice.xlsx"
#     df = download_and_process_CPI_excel(url, "Data")
#     print(df.head())
#     save_to_csv(df, csv_file_path)
#     print(df.tail())

import requests
from datetime import datetime, timedelta

def download_unrate_csv():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1320&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=UNRATE&scale=left&cosd=1948-01-01&coed={yesterday}&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Monthly&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&vintage_date={yesterday}&revision_date={yesterday}&nd=1948-01-01"
    
    response = requests.get(url)
    if response.status_code == 200:
        unrate_file_path = get_csv_file_path('UNRATE.csv')
        with open(unrate_file_path, 'wb') as f:
            f.write(response.content)
        print(f"UNRATE.csv downloaded successfully to {unrate_file_path}")
    else:
        print(f"Failed to download UNRATE.csv. Status code: {response.status_code}")

def process_unrate_csv():
    unrate_file_path = get_csv_file_path('UNRATE.csv')
    df = pd.read_csv(unrate_file_path)
    print("UNRATE.csv head:")
    print(df.head())
    print("\nUNRATE.csv tail:")
    print(df.tail())

# Add this function call to the main function
# main_original = main

def main():
    # main_original()
    download_unrate_csv()
    process_unrate_csv()

if __name__ == "__main__":
    main()





