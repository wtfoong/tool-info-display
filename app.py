import streamlit as st
from datetime import datetime,timedelta,date
import time
import pandas as pd
import base64


# import local module
from config_loader import load_config
from streamlit_extras.stylable_container import stylable_container
config = load_config()

from backend import load_data, load_data_all, get_inspection_data, get_CTQ_SpecNo,merge_OT_DataLake_Questdb,get_questdb_data,get_historical_data,get_KPI_Data
from helper import set_timer_style, plot_IMR, calculate_ppk,plot_selected_columns_by_pieces_made,plot_RPMGraph,plotIMRByPlotly,read_csv_data,plot_KPI_Graph

# ---- Load app setting from config ----

PAGE_REFRESH = config['refresh']['page_refresh']
OFFSET_CACHE = config['refresh']['offset_cache']
DEFAULT_CACHE_LIFE  = PAGE_REFRESH-OFFSET_CACHE #offset to avoid race
INSPECTION_DATA_CACHE = config['refresh']['inspection_data_cache']

# ---- Caching functions ----

# Load data into cache

@st.cache_data(ttl= DEFAULT_CACHE_LIFE)
def load_data_cached():
    df_tool_data = load_data()
    df_tool_data_all = load_data_all()
    last_refresh = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return df_tool_data, df_tool_data_all, last_refresh

@st.cache_data(ttl= INSPECTION_DATA_CACHE)
def get_inspection_data_cached(sapcode, specno):
    df_inspection_data = get_inspection_data(sapcode, specno)
    return df_inspection_data

@st.cache_data(ttl= INSPECTION_DATA_CACHE)
def get_CTQ_SpecNo_cached(sapcode):
    df_inspection_data = get_CTQ_SpecNo(sapcode)
    return df_inspection_data

@st.cache_data(ttl= INSPECTION_DATA_CACHE)
def get_Current_Tool_Column_Data(MachineName, Position, ToolingStation,StartDate, AlarmColumn, AlarmFilter,historyFlag=False, EndDate=None):
    df_Tool_Data = merge_OT_DataLake_Questdb(MachineName, Position, ToolingStation,StartDate, AlarmColumn, AlarmFilter,historyFlag=historyFlag, EndDate=EndDate)
    return df_Tool_Data

@st.cache_data(ttl= DEFAULT_CACHE_LIFE)
def get_KPI_Data_Cache(MachineName):

    df_KPI_Data = get_KPI_Data(MachineName)

    return df_KPI_Data


def get_History_Tool_Data(MachineName, Position, ToolingStation,StartDate, EndDate):
    df_Tool_Data = get_historical_data(MachineName, Position, ToolingStation,StartDate,EndDate)
    return df_Tool_Data


# ---- UI ----
# ---- Page config ----
page_title = config['app']['title']
st.set_page_config(page_title=page_title, layout="wide")

#! deprecating! UI flickers and lost session state...(filter selection etc gone...)
# html meta tags to refresh at browser level
#st.markdown(f'<meta http-equiv="refresh" content="{PAGE_REFRESH}">',unsafe_allow_html=True)

# header
st.markdown(
    f"""
    <style>
        .block-container {{
            padding-top: 3rem !important;
        }}
    </style>
    <h1 style='text-align: center;'>{page_title}</h1>
    """,
    unsafe_allow_html=True
)




# ---- Initialize state ----

# Session_state (Note: this will not persist if browser tab refresh)
if 'clicked_materialcode' not in st.session_state:
    st.session_state.clicked_materialcode = None

if 'clicked_location' not in st.session_state:
    st.session_state.clicked_location = None
    
if 'clicked_materialdesc' not in st.session_state:
    st.session_state.clicked_materialdesc = None
    
if 'clicked_location_History' not in st.session_state:
    st.session_state.clicked_location_History = None
    
if 'clicked_machineID_History' not in st.session_state:
    st.session_state.clicked_machineID_History = None

if 'clicked_search_History' not in st.session_state:
    st.session_state.clicked_search_History = None
    
if 'clicked_KPI' not in st.session_state:
    st.session_state.clicked_KPI = None

# ---- Information Display ----

# Read the image file and encode it to base64
with open("plandwt.png", "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode()

@st.fragment(run_every=str(PAGE_REFRESH)+"s")
def ShowTimerInfo():
    df_tool_data, df_tool_data_all, last_refresh = load_data_cached()

    # ---- Filters ----
    with st.container():
        col1, col2, col3 = st.columns(3)

        with col2:
            location_options = list(df_tool_data["Location"].unique())
            selected_locations = st.multiselect(label = ' ', label_visibility='collapsed', options=location_options, placeholder='Choose Machine')

    filtered_df = df_tool_data.copy()

    if selected_locations:
        filtered_df = filtered_df[filtered_df["Location"].isin(selected_locations)]
    
    st.markdown(f"<p style='text-align: center; color: grey;'>Last refreshed: {last_refresh}</p>", unsafe_allow_html=True)
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])
        
        with col2:
            # Header row
            header_cols = st.columns([3, 2, 1, 1,1,1])
            header_titles = ['Machine Condition', 'Count Down', 'Inspection Detail', 'Tool Detail', 'History','KPI']
            for col, title in zip(header_cols, header_titles):
                col.markdown(
                    f"<div style='text-align: center; border-bottom: 2px solid white; font-size: 1.25rem; font-weight: bold;'>{title}</div>",
                    unsafe_allow_html=True
                )


            for index, row in filtered_df.iterrows():   
                # Create 3 columns: machine name | timer | button
                col_name, col_timer, col_button, col_tool, col_history, col_kpi = st.columns([3, 2, 1, 1,1,1])  # adjust ratios as needed

                with col_name:
                    backGroundColor = (
                        'red' if row['MacLEDRed'] else
                        '#FFBF00' if row['MacLEDYellow'] else
                        '#00FF00' if row['MacLEDGreen'] else
                        '#373737'
                    )
                    
                    colorUI = GetTowerLightUI(backGroundColor)

                    if row['TechRequired']:
                        st.markdown(f"""
                                <div class='circle-container' style='font-size: 50px;animation: blinker 1s linear infinite;'>
                                    <strong>
                                        {row['Location']} 
                                        <span>
                                            <img src='data:image/png;base64,{encoded_string}' alt='icon' style='height: 1em; vertical-align: middle;'/> 
                                            {row['TechRequestMin']} mins
                                        </span>
                                    </strong>{colorUI}</div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                                <div class='circle-container' style='font-size: 50px;'>
                                    <strong>
                                        {row['Location']} 
                                        <span style='color: gray; opacity: 0.2;'>
                                            <img src='data:image/png;base64,{encoded_string}' alt='icon' style='height: 1em; vertical-align: middle;'/> {row['TechRequestMin']} mins
                                        </span>
                                    </strong>{colorUI}</div>""", unsafe_allow_html=True)                             


                with col_timer:
                    backGroundColor, blink_style = set_timer_style(row['DurationMins'])

                    st.markdown(
                        f"""
                        <style>
                            @keyframes blinker {{
                                50% {{ opacity: 0; }}
                            }}
                        </style>
                        <div style="color: {backGroundColor}; font-size: 50px; {blink_style}">
                            {row['DurationMins']} mins
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with col_button:
                    # Store selected materialcode for plotting at bottom section
                    LowestPpk = st.session_state[f"CurrentMachineMaterial_{row['MaterialCode']}_LowestPpk"]
                    buttonType = "primary" if float(LowestPpk) < 0.7 else "secondary"
                    backGroundColor = "red" if float(LowestPpk) < 0.7 else '#00FF00' if float(LowestPpk) > 1.0 else '#FFBF00'
                    color = "white" if float(LowestPpk) < 0.7 else "black"
                    st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)  # Top spacer
                    with stylable_container(
                        key=f"insp{row['Location']}_button",
                        css_styles=f"""
                            button {{
                                background-color: {backGroundColor};
                                color: {color};
                                border: 1px solid #000;
                            }}
                            """,
                    ):
                        if st.button(f"Ppk = {LowestPpk} 📈", key=f"btn_{row['MaterialCode']}", use_container_width=True,type=buttonType):
                            # #toggle off
                            # if st.session_state.clicked_materialcode == row['MaterialCode']:
                            #     st.session_state.clicked_materialcode = None # clear session state
                            # #toggle on
                            # else:
                            st.session_state.clicked_materialcode = row['MaterialCode'] # update session state
                            st.session_state.clicked_materialdesc = row['MaterialDesc'] # update session state

                            st.session_state.clicked_location = None  # 👈 force close the clicked_location button
                            st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
                            st.session_state.clicked_search_History = None # 👈 force close the clicked_search_History button
                            st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
                            
                with col_tool:
                    st.markdown("<div style='height:25px;'></div>", unsafe_allow_html=True)  # Top spacer

                    # Store selected location for showing details at bottom section
                    if st.button("Show 🛠️", key=f"btn_{row['Location']}", use_container_width=True):
                        # #toggle off
                        # if st.session_state.clicked_location == row['Location']:
                        #     st.session_state.clicked_location = None # clear session state
                        # #toggle on
                        # else:
                        st.session_state.clicked_location = row['Location'] # update session state

                        st.session_state.clicked_materialcode = None  # 👈 force close the clicked_materialcode button
                        st.session_state.clicked_materialdesc = None  # 👈 Reset material description
                        st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
                        st.session_state.clicked_search_History = None # 👈 force close the clicked_search_History button
                        st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button

                with col_history:
                    st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)  # Top spacer
                    # Store selected location for showing details at bottom section
                    if st.button("History 🛠️", key=f"btn_{row['Location']}_History", use_container_width=True):
                        # #toggle off
                        # if st.session_state.clicked_location == row['Location']:
                        #     st.session_state.clicked_location = None # clear session state
                        # #toggle on
                        # else:
                        st.session_state.clicked_location_History = row['Location'] # update session state
                        st.session_state.clicked_machineID_History = row['MachineID'] # update session state

                        st.session_state.clicked_materialcode = None  # 👈 force close the clicked_materialcode button
                        st.session_state.clicked_materialdesc = None  # 👈 Reset material description
                        st.session_state.clicked_location = None # 👈 force close the clicked_location button
                        st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
            
                with col_kpi:
                    st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)
                    if st.button("KPI 🛠️", key=f"btn_{row['Location']}_KPI", use_container_width=True):
                        st.session_state.clicked_KPI = row['MachineID'] # update session state

                        st.session_state.clicked_materialcode = None  # 👈 force close the clicked_materialcode button
                        st.session_state.clicked_materialdesc = None  # 👈 Reset material description
                        st.session_state.clicked_location = None # 👈 force close the clicked_location button
                        st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
                        st.session_state.clicked_search_History = None # 👈 force close the clicked_search_History button
                    
                    
                    
                    
                    
                            
    # ---- Bottom Section: Show tool data for clicked_location ----
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_location():
                st.session_state.clicked_location = None

            if st.session_state.clicked_location:
                st.markdown('---')
                st.button("❌ Close",key = f'close_{st.session_state.clicked_location}' , on_click=clear_selection_clicked_location)
                st.markdown("### 📋 Upcoming Tool Change")
                st.info(f"Showing data for: `{st.session_state.clicked_location}`")

                cols = ['Turret','Tool','Process','Balance (mins)', 'Balance (pcs)','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter', 'LoadX_Alm', 'LoadZ_Alm']
                df = df_tool_data_all[df_tool_data_all['Location']==st.session_state.clicked_location]
                df = df[cols].reset_index(drop=True)

                # Header row
                header_cols = st.columns([1, 1, 2, 1, 1,1,1, 1,1])
                header_titles = ['Turret', 'Tool', 'Process','Preset (pcs)','Actual (pcs)', 'Balance (pcs)', 'Balance (mins)', 'LoadX', 'LoadZ']
                for col, title in zip(header_cols, header_titles):
                    col.markdown(f"**{title}**")
                
                def clear_Selected_Graph(i):
                    st.session_state[f'visible_graph_row_{i}']= None

                # Render table with buttons
                for i, row in df.iterrows():

                    if f'visible_graph_row_{i}' not in st.session_state:
                        st.session_state[f'visible_graph_row_{i}'] = None

                    cols = st.columns([1, 1, 2, 1, 1,1,1, 1,1])  # Adjust column widths
                    cols[0].write(row['Turret'])
                    cols[1].write(str(row['Tool'])+" ("+str(row['ToolNoID'])+")")
                    cols[2].write(row['Process'])
                    cols[3].write(str(row['PresetCounter']))
                    cols[4].write(str(row['TotalCounter']))
                    
                    cols[5].write(str(row['Balance (pcs)']))
                    cols[6].write(str(row['Balance (mins)']))
                        

                    if cols[7].button("LoadX", key=f"btn_LoadX_{i}"):
                        if st.session_state[f'visible_graph_row_{i}'] == "LoadX":
                            st.session_state[f'visible_graph_row_{i}'] = None # Hide if already visible
                        else:
                            st.session_state[f'visible_graph_row_{i}'] = "LoadX"

                    if cols[8].button("LoadZ", key=f"btn_LoadZ_{i}"):
                        if st.session_state[f'visible_graph_row_{i}'] == "LoadZ":
                            st.session_state[f'visible_graph_row_{i}'] = None # Hide if already visible
                        else:
                            st.session_state[f'visible_graph_row_{i}'] = "LoadZ"
                    
                        
                    if st.session_state[f'visible_graph_row_{i}'] == "LoadX":
                        
                        loadXDf = get_Current_Tool_Column_Data(
                            MachineName=row['MachineID'],
                            Position=row['Turret'],
                            ToolingStation=row['Tool'],
                            StartDate=row['StartDate'],
                            AlarmColumn='Load_X',
                            AlarmFilter=row['LoadX_Alm']
                        )
                        st.button("❌ Close",key = f'close_loadX{i}' , on_click=clear_Selected_Graph, args=(i,))
                        if loadXDf.empty:
                            st.error(f"No data available for Tool {row['Tool']} (Load_X).")
                        else:
                            fig = plot_selected_columns_by_pieces_made(
                                loadXDf,
                                selectedColumn='Load_X',
                                TotalCounter=row['TotalCounter'],
                                PresetCounter=row['PresetCounter']
                            )

                            #st.pyplot(fig)
                            st.plotly_chart(fig)
                        

                    elif st.session_state[f'visible_graph_row_{i}'] == "LoadZ":
                        loadZDf = get_Current_Tool_Column_Data(
                            MachineName=row['MachineID'],
                            Position=row['Turret'],
                            ToolingStation=row['Tool'],
                            StartDate=row['StartDate'],
                            AlarmColumn='Load_Z',
                            AlarmFilter=row['LoadZ_Alm']
                        )
                        st.button("❌ Close",key = f'close_loadZ{i}' , on_click=clear_Selected_Graph, args=(i,))
                        if loadZDf.empty:
                            st.error(f"No data available for Tool {row['Tool']} (Load_Z).")
                        else:
                        
                            fig = plot_selected_columns_by_pieces_made(
                                loadZDf,
                                selectedColumn='Load_Z',
                                TotalCounter=row['TotalCounter'],
                                PresetCounter=row['PresetCounter']
                            )

                            #st.pyplot(fig)
                            st.plotly_chart(fig)
                        


                
                st.markdown('---')

    # ---- Bottom Section: Show IMR Chart for clicked_materialcode ----
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_materialcode():
                st.session_state.clicked_materialcode = None

            if st.session_state.clicked_materialcode:
                st.markdown('---')
                st.markdown("### 🔍 Loading Inspection Details (CTQ & CTP)...")

                materialcode = st.session_state.clicked_materialcode
                materialdesc = st.session_state.clicked_materialdesc
                specnoList = get_CTQ_SpecNo_cached(materialcode)
                st.button("❌ Close",key = f'close_{st.session_state.clicked_materialcode}', on_click=clear_selection_clicked_materialcode)
                for specno in specnoList['BalloonNo'].unique():
                    df_inspection_data = get_inspection_data_cached(materialcode, specno)

                    if not df_inspection_data.empty:
                        # Calculate ppk
                        df_inspection_data['LSL'] = pd.to_numeric(df_inspection_data['LSL'], errors='coerce')
        
                        df_inspection_data['USL'] = pd.to_numeric(df_inspection_data['USL'], errors='coerce')

                        ppk = calculate_ppk(df_inspection_data['MeasVal'],df_inspection_data['USL'].iloc[0],df_inspection_data['LSL'].iloc[0])

                        st.info(f"Showing details for: `{st.session_state.clicked_materialcode} | {materialdesc}`")
                        title =f"SpecNo:{specno}| {df_inspection_data['Description'].iloc[0]} | Ppk = {ppk}"
                        fig = plotIMRByPlotly(df_inspection_data,df_inspection_data['LSL'].iloc[0],df_inspection_data['USL'].iloc[0],title = title) 
                        #st.pyplot(fig)
                        st.plotly_chart(fig)
                    else:
                        st.warning(f"No inspection data available for `{st.session_state.clicked_materialcode}`.")

                
                st.markdown('---')

    # ---- Bottom Section: Show History data for clicked_History ----
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_location():
                st.session_state.clicked_location_History = None

            if st.session_state.clicked_location_History:
                st.markdown('---')
                st.button("❌ Close",key = f'close_{st.session_state.clicked_location_History}' , on_click=clear_selection_clicked_location)
                st.markdown("### 📋 History Tool Change")
                st.info(f"Showing history data for: `{st.session_state.clicked_location_History}`")
                
                cols = ['Turret','Tool','Process','Balance (mins)', 'Balance (pcs)','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter', 'LoadX_Alm', 'LoadZ_Alm']
                df = df_tool_data_all[df_tool_data_all['Location']==st.session_state.clicked_location_History]
                df = df[cols].reset_index(drop=True)
                
                ColOptionTurret, ColOptionStation, ColStartDatePicker, ColEndDatePicker,ColSearchButton = st.columns([1,1,1,1,1])
                OptionTurret= ''
                OptionStation = ''
                StartDate = None
                EndDate = None
                with ColOptionTurret:
                    OptionTurret = st.selectbox("Turret Position",
                            options=df['Turret'].unique(),
                            index=None,
                            placeholder="Select Turret Position...",
                        )
                with ColOptionStation:
                    if OptionTurret:
                        # Filter tools based on selected turret
                        filtered_tools = df[df['Turret'] == OptionTurret]['Tool'].unique()
                        OptionStation = st.selectbox(
                            "Station",
                            options=filtered_tools,
                            index=None,
                            placeholder="Select Station...",
                            key="station"
                        )
                    else:
                        st.selectbox(
                            "Station",
                            options=[''],
                            index=None,
                            placeholder="Select Turret first...",
                            disabled=True,
                            key="station_disabled"
                        )

                    
                with ColStartDatePicker:
                    StartDate = st.date_input("Start Date", value=None, min_value=None, max_value=date.today(), key="start_date")
                    
                with ColEndDatePicker:
                    EndDate = st.date_input("End Date", value=None, min_value=None, max_value=date.today(), key="end_date")
                
                with ColSearchButton:
                    st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)
                    if st.button("Search", use_container_width=True):
                        #all selection need to be made else show error
                        if not OptionTurret or not OptionStation or not StartDate or not EndDate:
                            st.error("Please select Turret, Station and Date Range to search.")
                            st.session_state.clicked_search_History = None
                        # Check if Start Date is before or equal to End Date
                        elif StartDate > EndDate:
                            st.error("Start Date must be earlier than or equal to End Date.")
                            st.session_state.clicked_search_History = None
                        else:
                            st.session_state.clicked_search_History = st.session_state.clicked_machineID_History


                if st.session_state.clicked_search_History:
                    if not OptionTurret or not OptionStation or not StartDate or not EndDate:
                        st.session_state.clicked_search_History = None
                        return
                    # Check if Start Date is before or equal to End Date
                    elif StartDate > EndDate:
                        st.error("Start Date must be earlier than or equal to End Date.")
                        return
                    
                    df_history = get_History_Tool_Data(
                        MachineName=st.session_state.clicked_search_History,
                        Position=OptionTurret, 
                        ToolingStation=OptionStation,  
                        StartDate=StartDate,  
                        EndDate=EndDate
                    )
                    cols = ['Turret','Tool','Process','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter','CompletedDate','LoadX_Alm', 'LoadZ_Alm']
                    df_history = df_history[cols].reset_index(drop=True)
                
                    # Header row
                    header_cols = st.columns([1, 2, 1,1,1,1,1])
                    #header_titles = ['Tool ID', 'Process','Preset (pcs)','Actual (pcs)', 'Start Date','Completed Date','LoadX', 'LoadZ']
                    header_titles = ['Tool ID', 'Process','Actual (pcs)', 'Start Date','Completed Date','LoadX', 'LoadZ']
                    for col, title in zip(header_cols, header_titles):
                        col.markdown(f"**{title}**")
                    
                    def clear_Selected_Graph(i):
                        st.session_state[f'visible_history_graph_row_{i}']= None

                    # Render table with buttons
                    for i, row in df_history.iterrows():

                        if f'visible_history_graph_row_{i}' not in st.session_state:
                            st.session_state[f'visible_history_graph_row_{i}'] = None

                        cols = st.columns([1, 2, 1,1,1,1,1])  # Adjust column widths
                        cols[0].write(str(row['ToolNoID']))
                        cols[1].write(row['Process'])
                        #cols[2].write(str(row['PresetCounter']))
                        cols[2].write(str(row['TotalCounter']))
                        cols[3].write(str(row['StartDate']))
                        cols[4].write(str(row['CompletedDate']))


                        if cols[5].button("LoadX", key=f"btn_LoadX_{i}"):
                            if st.session_state[f'visible_history_graph_row_{i}'] == "LoadX":
                                st.session_state[f'visible_history_graph_row_{i}'] = None # Hide if already visible
                            else:
                                st.session_state[f'visible_history_graph_row_{i}'] = "LoadX"

                        if cols[6].button("LoadZ", key=f"btn_LoadZ_{i}"):
                            if st.session_state[f'visible_history_graph_row_{i}'] == "LoadZ":
                                st.session_state[f'visible_history_graph_row_{i}'] = None # Hide if already visible
                            else:
                                st.session_state[f'visible_history_graph_row_{i}'] = "LoadZ"

                        if st.session_state[f'visible_history_graph_row_{i}'] == "LoadX":
                            loadXDf = get_Current_Tool_Column_Data(
                                MachineName=row['MachineID'],
                                Position=row['Turret'],
                                ToolingStation=row['Tool'],
                                StartDate=row['StartDate'],
                                AlarmColumn='Load_X',
                                AlarmFilter=row['LoadX_Alm'],
                                historyFlag=True,
                                EndDate=row['CompletedDate'],
                            )
                            st.button("❌ Close",key = f'close_loadX{i}' , on_click=clear_Selected_Graph, args=(i,))
                            if loadXDf.empty:
                                st.error(f"No data available for Tool {row['Tool']} (Load_X).")
                            else:
                                fig = plot_selected_columns_by_pieces_made(
                                    loadXDf,
                                    selectedColumn='Load_X',
                                    TotalCounter=row['TotalCounter'],
                                    PresetCounter=row['PresetCounter']
                                )

                                #st.pyplot(fig)
                                st.plotly_chart(fig)
                            

                        elif st.session_state[f'visible_history_graph_row_{i}'] == "LoadZ":
                            loadZDf = get_Current_Tool_Column_Data(
                                MachineName=row['MachineID'],
                                Position=row['Turret'],
                                ToolingStation=row['Tool'],
                                StartDate=row['StartDate'],
                                AlarmColumn='Load_Z',
                                AlarmFilter=row['LoadZ_Alm'],
                                historyFlag=True,
                                EndDate=row['CompletedDate'],
                            )
                            st.button("❌ Close",key = f'close_loadZ{i}' , on_click=clear_Selected_Graph, args=(i,))
                            if loadZDf.empty:
                                st.error(f"No data available for Tool {row['Tool']} (Load_Z).")
                            else:
                            
                                fig = plot_selected_columns_by_pieces_made(
                                    loadZDf,
                                    selectedColumn='Load_Z',
                                    TotalCounter=row['TotalCounter'],
                                    PresetCounter=row['PresetCounter']
                                )

                                #st.pyplot(fig)
                                st.plotly_chart(fig)
                st.markdown('---')

    # ---- Bottom Section: Show KPI data for clicked_KPI ----
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_location():
                st.session_state.clicked_KPI = None

            if st.session_state.clicked_KPI:
                st.markdown('---')
                st.button("❌ Close",key = f'close_{st.session_state.clicked_KPI}' , on_click=clear_selection_clicked_location)
                st.markdown("### 📋 KPI")
                st.info(f"Showing KPI data for: `{st.session_state.clicked_KPI}`")

                
                KPIDf = get_KPI_Data_Cache(
                    MachineName=st.session_state.clicked_KPI
                )

                if KPIDf.empty:
                    st.error(f"No data available for machine {st.session_state.clicked_KPI}")
                else:
                    
                    df_low = KPIDf[KPIDf['AvgCnt'] < 1000]
                    df_mid = KPIDf[(KPIDf['AvgCnt'] >= 1000) & (KPIDf['AvgCnt'] < 3000)]
                    df_high = KPIDf[KPIDf['AvgCnt'] >= 3000]

                    fig_low = plot_KPI_Graph(
                        df_low,
                        st.session_state.clicked_KPI,
                    )
                    fig_medium = plot_KPI_Graph(
                        df_mid,
                        st.session_state.clicked_KPI,
                    )
                    fig_high = plot_KPI_Graph(
                        df_high,
                        st.session_state.clicked_KPI,
                    )
                    st.plotly_chart(fig_low)
                    st.plotly_chart(fig_medium)
                    st.plotly_chart(fig_high)
                st.markdown('---')


def GetTowerLightUI(color):
    colorUI = f"""
                            <style>
                                .circle-container {{
                                        display: flex;
                                        align-items: center;
                                        justify-content: space-around;
                                        height: 100px; /* Adjust height as needed */
                                }}
                                .circle-button {{
                                        height: 40px;
                                        width: 40px;
                                        border-radius: 50%;
                                        border: 1px solid #000;
                                        box-shadow: 2px 2px 2px rgba(0, 0, 0, 0.3);
                                }}
                            </style>
                            <span class="circle-button" style=" background: {color};"></span>
                        """
    return colorUI

@st.fragment(run_every=str(INSPECTION_DATA_CACHE)+"s")
def CalculateCPK():
    df_tool_data, df_tool_data_all, last_refresh = load_data_cached()
    filtered_df = df_tool_data.copy()
    for index, row in filtered_df.iterrows():
        materialcode = row['MaterialCode']
        if f'CurrentMachineMaterial_{materialcode}_LowestPpk' not in st.session_state:
            st.session_state[f'CurrentMachineMaterial_{materialcode}_LowestPpk'] = None
        
        specnoList = get_CTQ_SpecNo_cached(materialcode)
        ppkList = []
        for specno in specnoList['BalloonNo'].unique():
            df_inspection_data = get_inspection_data_cached(materialcode, specno)

            if not df_inspection_data.empty:
                # Calculate ppk
                df_inspection_data['LSL'] = pd.to_numeric(df_inspection_data['LSL'], errors='coerce')

                df_inspection_data['USL'] = pd.to_numeric(df_inspection_data['USL'], errors='coerce')

                ppk = calculate_ppk(df_inspection_data['MeasVal'],df_inspection_data['USL'].iloc[0],df_inspection_data['LSL'].iloc[0])
                ppkList.append(ppk)
                
        if ppkList:
            min_ppk = min(ppkList)
            st.session_state[f'CurrentMachineMaterial_{materialcode}_LowestPpk'] = min_ppk

CalculateCPK()      
ShowTimerInfo()

with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            RedColorUI = GetTowerLightUI('red')

            YellowColorUI = GetTowerLightUI('#FFBF00')

            GreenColorUI = GetTowerLightUI('#00FF00')
            GreyColorUI = GetTowerLightUI('#373737')

            st.markdown( f"<div class='circle-container' style='text-align: center; border-bottom: 2px solid white; font-size: 1.15rem;'>{RedColorUI} Alarm/Stop |{YellowColorUI} Waiting |{GreenColorUI} Running |{GreyColorUI} Machine Off |  <span><img src='data:image/png;base64,{encoded_string}' alt='icon' style='height: 2.5em; vertical-align: middle;'/> </span> Technician Call </div>",
                    unsafe_allow_html=True)
                
            st.markdown('---')

# Tooling countdown times
