import pandas as pd

from backend import load_data,get_CTQ_SpecNo,get_inspection_data
from helper import calculate_ppk,insert_data_into_csv



def GetLowestCPK():
    df_tool_data = load_data()
    filtered_df = df_tool_data.copy()
    LowestCpkdataFrame =  pd.DataFrame(columns=["MachineID", "ToolNoID","Value"])
    for index, row in filtered_df.iterrows():
        materialcode = row['MaterialCode']
        
        specnoList = get_CTQ_SpecNo(materialcode)
        ppkList = []
        for specno in specnoList['BalloonNo'].unique():
            df_inspection_data = get_inspection_data(materialcode, specno)

            if not df_inspection_data.empty:
                # Calculate ppk
                df_inspection_data['LSL'] = pd.to_numeric(df_inspection_data['LSL'], errors='coerce')

                df_inspection_data['USL'] = pd.to_numeric(df_inspection_data['USL'], errors='coerce')

                ppk = calculate_ppk(df_inspection_data['MeasVal'],df_inspection_data['USL'].iloc[0],df_inspection_data['LSL'].iloc[0])
                ppkList.append(ppk)
                
        if ppkList:
            min_ppk = min(ppkList)
        else:
            min_ppk = None
            
        LowestCpkdataFrame.loc[len(LowestCpkdataFrame)] = {
            "MachineID": row['MachineID'],
            "ToolNoID": '',
            "Value": min_ppk
        }
    # Save the results to a CSV file
    insert_data_into_csv(LowestCpkdataFrame, "LowestCPK.csv")

GetLowestCPK()