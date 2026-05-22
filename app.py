import streamlit as st
from datetime import datetime,timedelta,date
import time
import pandas as pd
import base64


# import local module
from config_loader import load_config
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.local_storage_manager import local_storage_manager

config = load_config()

from backend import load_data, load_data_all, get_inspection_data, get_CTQ_SpecNo,merge_OT_DataLake_Questdb,get_questdb_data,get_historical_data,get_KPI_Data,get_History_Inspection_Data,get_questdb_offset_history
from helper import set_timer_style, plot_IMR, calculate_ppk,plot_selected_columns_by_pieces_made,plot_RPMGraph,plotIMRByPlotly,read_csv_data,plot_KPI_Graph,plotNormalDistributionPlotly,BalanceClustering,plot_OffSet_History_Graph,GetAllMachineToolChange,SplitToolDataByOperator,calculate_savings

# ---- Load app setting from config ----

PAGE_REFRESH = config['refresh']['page_refresh']
OFFSET_CACHE = config['refresh']['offset_cache']
DEFAULT_CACHE_LIFE  = PAGE_REFRESH-OFFSET_CACHE #offset to avoid race
INSPECTION_DATA_CACHE = config['refresh']['inspection_data_cache']
PLANT_CODE_LIST = config['PlantCodeList']
DISPLAY_MODE_LIST = ["Compact View","Standard","Condition Sorting","Full Information"]

# ---- Caching functions ----

# Load data into cache

@st.cache_data(ttl= DEFAULT_CACHE_LIFE)
def load_data_cached(plant_code: int = 2100):
    df_tool_data = load_data(plant_code=plant_code)
    df_tool_data_all = load_data_all(plant_code=plant_code)
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

@st.cache_data(ttl= INSPECTION_DATA_CACHE)
def get_Current_Tool_Offset_History(MachineName, Position,StartDate, EndDate,ToolNo):
    df_Offet_Data = get_questdb_offset_history(MachineName, Position,StartDate, EndDate, ToolNo)
    return df_Offet_Data

def get_History_Tool_Data(MachineName, Position, ToolingStation, StartDate, EndDate, plant_code: int = 2100):
    df_Tool_Data = get_historical_data(MachineName, Position, ToolingStation, StartDate, EndDate, plant_code=plant_code)
    return df_Tool_Data

def get_Inspection_History_Data(MachineName,StartDate,EndDate):
    df_Inspection_History = get_History_Inspection_Data(MachineName,StartDate,EndDate)
    return df_Inspection_History

# ---- UI ----
# ---- Page config ----
page_title = config['app']['title']
Tool_Change_min = config['thresholds']['ToolChange_min']
st.set_page_config(page_title=page_title, layout="wide")
storage = local_storage_manager()
if not storage.ready():
    st.stop()

#! deprecating! UI flickers and lost session state...(filter selection etc gone...)
# html meta tags to refresh at browser level
#st.markdown(f'<meta http-equiv="refresh" content="{PAGE_REFRESH}">',unsafe_allow_html=True)

# Inject global CSS styles
st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem !important;
        }
        .circle-container {
                display: flex;
                align-items: center;
                justify-content: space-around;
                height: 100px; /* Adjust height as needed */
        }
        .circle-button {
                height: 40px;
                width: 40px;
                border-radius: 50%;
                border: 1px solid #000;
                box-shadow: 2px 2px 2px rgba(0, 0, 0, 0.3);
        }
        .legendDiv{
            display: flex;
            align-items: center;
            justify-content: space-around;
        }

        .legendDiv span {
            margin-left: 1rem;
        }

    </style>
""", unsafe_allow_html=True)

# header
st.markdown(
    f"""
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
    
if 'clicked_Common_Location' not in st.session_state:
    st.session_state.clicked_Common_Location = None
    
if 'clicked_NormalDistribution' not in st.session_state:
    st.session_state.clicked_NormalDistribution = None
    
if 'toggle_FullInfoFlag' not in st.session_state:
    st.session_state.toggle_FullInfoFlag = False
    
if 'toggle_OverView' not in st.session_state:
    st.session_state.toggle_OverView = False
    
if 'toggle_Detail' not in st.session_state:
    st.session_state.toggle_Detail = False

if 'toggle_Status' not in st.session_state:
    st.session_state.toggle_Status = False
    
if 'LAST_SELECTED_PLANT' not in st.session_state:
    
    stored = storage.get("LAST_SELECTED_PLANT", PLANT_CODE_LIST[0])
    # safety if options change
    st.session_state.LAST_SELECTED_PLANT = (
        stored if stored in PLANT_CODE_LIST else PLANT_CODE_LIST[0]
    )
    
if 'LAST_SELECTED_DISPLAYMODE' not in st.session_state:
    
    stored = storage.get("LAST_SELECTED_DISPLAYMODE", "Condition Sorting")
    # safety if options change
    st.session_state.LAST_SELECTED_DISPLAYMODE = (
        stored if stored in DISPLAY_MODE_LIST else DISPLAY_MODE_LIST[0]
    )


# ---- Information Display ----

# Read the image file and encode it to base64
with open("images/robot-arm.png", "rb") as image_file:
    robotArmBase64 = base64.b64encode(image_file.read()).decode()
    
# Read the image file and encode it to base64
with open("images/milling-machine.png", "rb") as image_file:
    machineBase64 = base64.b64encode(image_file.read()).decode()
    
# Read the image file and encode it to base64
with open("images/milling-machine_OverView.png", "rb") as image_file:
    machineOverViewBase64 = base64.b64encode(image_file.read()).decode()
    
# Read the image file and encode it to base64
with open("images/robot-arm_OverView.png", "rb") as image_file:
    robotArmOverViewBase64 = base64.b64encode(image_file.read()).decode()
    
# Read the image file and encode it to base64
with open("images/milling-machine_OverViewWhite.png", "rb") as image_file:
    machineOverViewWhiteBase64 = base64.b64encode(image_file.read()).decode()
    
# Read the image file and encode it to base64
with open("images/robot-arm_OverViewWhite.png", "rb") as image_file:
    robotArmOverViewWhiteBase64 = base64.b64encode(image_file.read()).decode()

df_tool_data, df_tool_data_all, last_refresh = load_data_cached(st.session_state.LAST_SELECTED_PLANT)
with st.container():
        col1, col2, col3,col4,col5,col6 = st.columns(6)

        with col2:
            
            def persist():
                storage["LAST_SELECTED_PLANT"] = st.session_state.LAST_SELECTED_PLANT

            st.selectbox(label='Plant', options=PLANT_CODE_LIST, label_visibility='collapsed',on_change=persist, key="LAST_SELECTED_PLANT")
            
        
        with col3:
            operator_df = (
                df_tool_data[['EmpNo', 'EmpName']]
                .drop_duplicates()
                .sort_values('EmpNo')
            )

            operator_options = list(operator_df.itertuples(index=False, name=None))

            selected = st.multiselect(
                label='Operator',
                options=operator_options,
                format_func=lambda x: f"{x[0]} - {x[1]}",
                placeholder='Choose Operator',
                label_visibility='collapsed',
                max_selections=1
            )
            selected_empnos = [opt[0] for opt in selected]
                
        with col4:
            
            filtered = df_tool_data
            if len(selected_empnos)>0:
                filtered = df_tool_data[df_tool_data['EmpNo'].isin(selected_empnos)]
            location_options = sorted(filtered['Location'].dropna().unique())

            selected_locations = st.multiselect(label = ' ', label_visibility='collapsed', options=location_options, placeholder='Choose Machine')
        with col5:
            def persist():
                storage["LAST_SELECTED_DISPLAYMODE"] = st.session_state.LAST_SELECTED_DISPLAYMODE
                
            PageMode = st.selectbox(
                        label='Page Mode',
                        options=DISPLAY_MODE_LIST,
                        label_visibility='collapsed',
                        on_change=persist, key="LAST_SELECTED_DISPLAYMODE"
                    )
            if PageMode == "Compact View":
                st.session_state.toggle_OverView = True
                
                st.session_state.toggle_Detail = False
                st.session_state.toggle_FullInfoFlag = False
                st.session_state.toggle_Status = False
                
                st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
                st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
            elif PageMode == "Standard":
                st.session_state.toggle_Detail = True
                
                st.session_state.toggle_OverView = False
                st.session_state.toggle_FullInfoFlag = False
                st.session_state.toggle_Status = False
                
                st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
                st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
            elif PageMode == "Condition Sorting":
                st.session_state.toggle_Status = True
                
                st.session_state.toggle_OverView = False
                st.session_state.toggle_FullInfoFlag = False
                st.session_state.toggle_Detail = False
                
                st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
                st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
            elif PageMode == "Full Information":
                st.session_state.toggle_FullInfoFlag = True
                
                st.session_state.toggle_OverView = False
                st.session_state.toggle_Detail = False
                st.session_state.toggle_Status = False
                

                
                
                
@st.fragment(run_every=str(PAGE_REFRESH)+"s")
def ShowTimerInfo():
    df_tool_data, df_tool_data_all, last_refresh = load_data_cached(st.session_state.LAST_SELECTED_PLANT)
    if df_tool_data.empty:
        st.warning("No data available for the selected plant.")
        return
                
    filtered_df = df_tool_data.copy()
    filtered_df = GetAllMachineToolChange(filtered_df,df_tool_data_all,Tool_Change_min)
    if selected_empnos:
        filtered_df = filtered_df[filtered_df["EmpNo"].isin(selected_empnos)]
    if selected_locations:
        filtered_df = filtered_df[filtered_df["Location"].isin(selected_locations)]
    
    filtered_df = SplitToolDataByOperator(filtered_df)
    #filtered_df = filtered_df.sort_values(by=['MacLEDRed','MacLEDYellow','TechRequired','MacLEDGreen','DurationMins'],ascending=[False,False,False,False,True]).reset_index(drop=True)
    if st.session_state.toggle_Status:
        filtered_df = filtered_df.sort_values(by=['MacLEDRed','MacLEDYellow','TechRequired','MacLEDGreen','DurationMins'],ascending=[False,False,False,False,True]).reset_index(drop=True)
    elif st.session_state.toggle_OverView:
        filtered_df = filtered_df.sort_values(by=['MachineTurnOff','DurationMins'],ascending=[True,True]).reset_index(drop=True)
    else:
        filtered_df = filtered_df.sort_values(by=['MachineTurnOff','DurationMins'],ascending=[True,True]).reset_index(drop=True)
    st.markdown(f"<p style='text-align: center; color: grey;'>Last refreshed: {last_refresh}</p>", unsafe_allow_html=True)
    
    if st.session_state.toggle_OverView:
        with st.container():
            MachineChunks = [filtered_df[i:i+7] for i in range(0, len(filtered_df), 7)]
            for MachineList in MachineChunks:
                
                row_cols = st.columns(7)

                for i, col in enumerate(row_cols):
                        # If there's an item for this column, render it; otherwise leave blank
                        machine = MachineList.iloc[i] if i < len(MachineList) else None

                        # NOTE: Streamlit's container() does not support a `height` argument.
                        # You can still use container(), and control appearance inside.
                        tile = col.container()  # e.g., tile = col.container(border=True) if you want borders

                        if machine is not None:
                            NoToolDataFlag =  machine['ToolingStation'] == 9999
                            backGroundColor, blink_style = set_timer_style(machine['SuggestedToolChangeTime'] if pd.notna(machine['SuggestedToolChangeTime']) else machine['DurationMins'],True)
                            # Replace :balloon: and the following lines with what you want to display
                            TowerLightBackGroundColor = (
                                'red' if machine['MacLEDRed'] else
                                '#FFBF00' if machine['MacLEDYellow'] else
                                '#00FF00' if machine['MacLEDGreen'] else
                                'black'
                            )
                            
                            FontColor = 'white'
                            MachineOverviewIcon = machineOverViewWhiteBase64
                            RobotArmOverviewIcon = robotArmOverViewWhiteBase64
                            
                            if not machine['MachineTurnOff']:
                                FontColor = 'black'
                                MachineOverviewIcon = machineOverViewBase64
                                RobotArmOverviewIcon = robotArmOverViewBase64
                            
                            #tile.title(machine['Location'])
                            tile.markdown(
                            f"""
                            <style>
                                @keyframes blinker {{
                                    50% {{ opacity: 0; }}
                                }}
                            </style>
                            <div class='circle-container' style="height:auto;justify-content: space-evenly;font-size: 1.99vw; border: 1px solid grey; 
                                    border-radius: 0.5rem; margin-bottom:5px; background:{TowerLightBackGroundColor};{"" if NoToolDataFlag or  machine['MachineTurnOff'] else f"{blink_style};"}">
                                <span style=" color: {FontColor}">
                                    <strong>
                                        {machine['Location']} 
                                    </strong>
                                </span>
                                <span style='{"font-size: 1.99vw;animation: blinker 1s linear infinite;" if machine['TechRequired'] and not machine['MachineTurnOff'] else "color: gray; opacity: 0;"}'>
                                            <img src='data:image/png;base64,{ RobotArmOverviewIcon if machine['MacErrorType'] == 2 and machine['TechRequired'] else MachineOverviewIcon}' alt='icon' style='height: 1em; vertical-align: middle; background:'/>
                                </span>
                                <span style=" {"color:black;" if machine['MachineTurnOff'] else (f"color:{FontColor}" if NoToolDataFlag else f"color:{FontColor}; {blink_style};" )}">{"N/A" if NoToolDataFlag else (str(max(0,machine['SuggestedToolChangeTime'])) if pd.notna(machine['SuggestedToolChangeTime']) else machine['DurationMins'])}{f"<sup style='font-size: 0.7em;color: #A3A8B8'>{machine['AdjustTime']}</sup>" if pd.notna(machine['SuggestedToolChangeTime']) else ""}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    else:
        DetailNFullInfoUI(filtered_df)

   

def DetailNFullInfoUI(filtered_df):
    with st.container(height=70):
        col1, col2, col3 = st.columns([1,40,1])
        
        with col2:
            # Header row
            header_cols = st.columns([1,1,1, 1,1,1, 1, 1,1,1])
            header_titles = []
            if st.session_state.toggle_FullInfoFlag:
                header_cols = st.columns([1,1,1, 1,1,1, 1, 1,1,1])
                header_titles = ['Machine','Call Tech (min)','Status','Cnt Down(min)','Change Time','Tool Change', 'Tool Detail', 'History', 'Ppk','KPI']
                
            else:
                header_cols = st.columns([1,1,1, 1,1,1, 1, 1])
                header_titles = ['Machine','Call Tech (min)','Status','Count Down(min)','Change Time','Tool Change', 'Tool Detail', 'Ppk']
            
            for col, title in zip(header_cols, header_titles):
                col.markdown(
                    f"<div style='text-align: center; border-bottom: 2px solid white; font-size: 1.1vw; font-weight: bold;'>{title}</div>",
                    unsafe_allow_html=True
                )

    with st.container(height=700):
        col1, col2, col3 = st.columns([1,60,1])
        
        with col2:
            for index, row in filtered_df.iterrows():   
                
                NoToolDataFlag =  row['ToolingStation'] == 9999
                backGroundColor, blink_style = set_timer_style(row['SuggestedToolChangeTime'] if pd.notna(row['SuggestedToolChangeTime']) else row['DurationMins'])
                    
                if st.session_state.toggle_FullInfoFlag:
                    col_name,colTechCall,colMacStatus, col_timer,colChangeTime,colToolChange, col_tool, col_history, col_button, col_kpi = st.columns([1,1,1, 1,1,1, 1, 1,1,1])  # adjust ratios as needed
                else:
                    col_name,colTechCall,colMacStatus, col_timer,colChangeTime,colToolChange, col_tool, col_button = st.columns([1,1,1, 1,1,1, 1,1])

                with col_name:
                     st.markdown(f"""
                                <div class='circle-container' style='font-size: 2.5vw;'>
                                    <strong>
                                        {row['Location']} 
                                    </strong></div>""", unsafe_allow_html=True)  
                    
                with colTechCall:
                    st.markdown(f"""
                                    <div class='circle-container' style='font-size: 1.99vw; {"animation: blinker 1s linear infinite;" if row['TechRequired'] else "color: gray; opacity: 0.2;"}'>
                                        <strong>
                                            <span>
                                                <img src='data:image/png;base64,{robotArmBase64 if row['MacErrorType'] == 2 and row['TechRequired'] else machineBase64}' alt='icon' style='height: 1em; vertical-align: middle;'/> 
                                                {row['TechRequestMin']}
                                            </span>
                                        </strong></div>""", unsafe_allow_html=True)
                                                                     
                with colMacStatus:
                    TowerLightBackGroundColor = (
                        'red' if row['MacLEDRed'] else
                        '#FFBF00' if row['MacLEDYellow'] else
                        '#00FF00' if row['MacLEDGreen'] else
                        '#373737'
                    )
                    
                    colorUI = GetTowerLightUI(TowerLightBackGroundColor)

                    st.markdown(f"""
                                <div class='circle-container' style='font-size:50px;'>
                                    </strong>{colorUI}</div>""", unsafe_allow_html=True) 

                with col_timer:

                    st.markdown(
                        f"""
                        <style>
                            @keyframes blinker {{
                                50% {{ opacity: 0; }}
                            }}
                        </style>
                        <div class='circle-container' style="justify-content: space-evenly; font-size: 1.99vw;">
                            <span style="{ "color: #555755" if NoToolDataFlag else f"color: {backGroundColor}; {blink_style};"}">
                                {"N/A" if NoToolDataFlag else (str(max(0,row['SuggestedToolChangeTime'])) if pd.notna(row['SuggestedToolChangeTime']) else row['DurationMins'])}{f"<sup style='font-size: 0.7em;color: #A3A8B8'>{row['AdjustTime']}</sup>" if pd.notna(row['SuggestedToolChangeTime']) else ""}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                        #help= str(row['SuggestedToolChangeTime']) if pd.notna(row['SuggestedToolChangeTime']) else None
                    )
                        #print(row['SuggestedToolChangeTime'])
                with colChangeTime:
                    currentTime = datetime.now()
                    ToolChangeTime = currentTime + timedelta(minutes=row['DurationMins'])
                    if pd.notna(row['SuggestedToolChangeTime']):
                        SuggestedToolChangeTime = currentTime + timedelta(minutes=row['SuggestedToolChangeTime'])

                    st.markdown(
                        f"""
                        <style>
                            @keyframes blinker {{
                                50% {{ opacity: 0; }}
                            }}
                        </style>
                        <div class='circle-container' style="font-size: {1.78 if st.session_state.toggle_FullInfoFlag else 1.99 }vw; justify-content: space-evenly;">
                            <span style="{ "color: #555755" if NoToolDataFlag else f"color: {backGroundColor}; {blink_style};"}">{"N/A" if NoToolDataFlag else (SuggestedToolChangeTime.strftime('%I:%M %p').lstrip('0') if pd.notna(row['SuggestedToolChangeTime']) else ToolChangeTime.strftime('%I:%M %p').lstrip('0'))}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                        help=f"Original time: {ToolChangeTime.strftime('%I:%M %p').lstrip('0')}"if pd.notna(row['SuggestedToolChangeTime']) and st.session_state.toggle_FullInfoFlag else ""
                    )
                    
                with colToolChange:
                        st.markdown(
                            f"""
                            <style>
                                @keyframes blinker {{
                                    50% {{ opacity: 0; }}
                                }}
                            </style>
                            <div class='circle-container' style="font-size: 1.99vw; justify-content: space-evenly;">
                                <span style="{ "color: #555755" if NoToolDataFlag else f"color: {backGroundColor}; {blink_style};"}">{"N/A" if NoToolDataFlag else row['ToolChangeNumber']}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                            #help=f"{savings} minute(s) saved"
                        )                    
                            
                with col_tool:
                    st.markdown("<div style='height:25px;'></div>", unsafe_allow_html=True)  # Top spacer

                    if NoToolDataFlag:
                        st.button("Show 🛠️", key=f"btn_{row['Location']}", use_container_width=True,disabled=True)
                        
                    else:
                        buttonType = "primary" if row['LoadPeak_Alm_L'] or row['LoadPeak_Warn_L'] or row['LoadPeak_Alm_R'] or row['LoadPeak_Warn_R'] else 'secondary'

                        
                        # Store selected location for showing details at bottom section
                        if st.button("Show 🛠️", key=f"btn_{row['Location']}", use_container_width=True,type=buttonType):
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
                            st.rerun()
            
                with col_button:
                    
                    key = f"CurrentMachineMaterial_{row['MachineID']}_LowestPpk"
                    LowestPpk = st.session_state[key] if key in st.session_state and st.session_state[key] else "N/A"
                    buttonType = "primary" if LowestPpk == "N/A" else "primary" if float(LowestPpk) < 0.7 else "secondary"
                    BtnBackGroundColor = '#00FF00' if LowestPpk == "N/A" else "red" if float(LowestPpk) < 0.7 else '#00FF00' if float(LowestPpk) > 1.0 else '#FFBF00'
                    color = "black" if LowestPpk == "N/A" else "white" if float(LowestPpk) < 0.7 else "black"
                    st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)  # Top spacer
                    with stylable_container(
                        key=f"insp{row['Location']}_button",
                        css_styles=f"""
                            button {{
                                background-color: {BtnBackGroundColor};
                                color: {color};
                                border: 1px solid #000;
                            }}
                            
                            button div[data-testid="stMarkdownContainer"] p {{
                                        font-size: 1.3vw !important;
                                        margin: 0;
                                        font-weight:500;
                                    }}

                            """,
                    ):
                        # Store selected materialcode for plotting at bottom section
                        if st.button(f"{LowestPpk}", key=f"btn_{row['MachineID']}", use_container_width=True,type=buttonType):
                            # #toggle off
                            # if st.session_state.clicked_materialcode == row['MaterialCode']:
                            #     st.session_state.clicked_materialcode = None # clear session state
                            # #toggle on
                            # else:
                            st.session_state.clicked_materialcode = row['MaterialCode'] # update session state
                            st.session_state.clicked_materialdesc = row['MaterialDesc'] # update session state
                            st.session_state.clicked_Common_Location = row['Location']

                            st.session_state.clicked_location = None  # 👈 force close the clicked_location button
                            st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
                            st.session_state.clicked_search_History = None # 👈 force close the clicked_search_History button
                            st.session_state.clicked_KPI = None # 👈 force close the clicked_KPI button
                            st.rerun()
                
                if st.session_state.toggle_FullInfoFlag:
                    with col_history:
                        st.markdown("<div style='height:25px;'></div>", unsafe_allow_html=True)  # Top spacer

                        if NoToolDataFlag:
                            st.button("History 🛠️", key=f"btn_{row['Location']}_History", use_container_width=True,disabled=True)
                        else:
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
                                st.rerun()                            
                    with col_kpi:
                        st.markdown("<div style='height:25px;'></div>", unsafe_allow_html=True)  # Top spacer

                        if NoToolDataFlag:
                            st.button("KPI 🛠️", key=f"btn_{row['Location']}_KPI", use_container_width=True,disabled=True)
                            
                        else:
                            if st.button("KPI 🛠️", key=f"btn_{row['Location']}_KPI", use_container_width=True):
                                st.session_state.clicked_KPI = row['MachineID'] # update session state
                                st.session_state.clicked_Common_Location = row['Location']

                                st.session_state.clicked_materialcode = None  # 👈 force close the clicked_materialcode button
                                st.session_state.clicked_materialdesc = None  # 👈 Reset material description
                                st.session_state.clicked_location = None # 👈 force close the clicked_location button
                                st.session_state.clicked_location_History = None # 👈 force close the clicked_location_History button
                                st.session_state.clicked_search_History = None # 👈 force close the clicked_search_History button
                                st.rerun()
       
     # Placeholder for dynamic content
    
    placeholder = st.empty()

    # ---- Bottom Section: Show tool data for clicked_location ----
    if st.session_state.clicked_location:
        with placeholder.container():
            col1, col2, col3 = st.columns([1,60,1])

            with col2:
                def clear_selection_clicked_location():
                    st.session_state.clicked_location = None
                    placeholder.empty()

                
                st.markdown('---')
                st.button("❌ Close",key = f'close_{st.session_state.clicked_location}' , on_click=clear_selection_clicked_location)
                st.markdown(f"### 📋 Upcoming Tool Change for {st.session_state.clicked_location}")

                cols = ['Turret','Tool','Process','Balance (mins)', 'Balance (pcs)','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter', 'LoadX_Alm', 'LoadZ_Alm','mmToolID','ToolLife_predicted','Segment_Based_Explanation_md','MesCT','UnitPrice']
                df = df_tool_data_all[df_tool_data_all['Location']==st.session_state.clicked_location]
                df = df[cols].reset_index(drop=True)
                df = BalanceClustering(df)
                
                df['ToolLife_predicted_final'] = df.apply(process_tool_life, axis=1)

                min_balance = df['Balance (mins)'].min()
                min_cluster = df[df['Balance (mins)'] == min_balance]['Hierarchical_Distance'].iloc[0]
                filtered_df = df[(df['Hierarchical_Distance'] == min_cluster) | (df['Balance (mins)'] <= (min_balance + Tool_Change_min))]
                minPcs_balance = filtered_df['Balance (pcs)'].min()
                maxPcs_balance = filtered_df['Balance (pcs)'].max()
                

                #min_balance = df['Balance (mins)'].min() + Tool_Change_min

                # Header row
                #header_cols = st.columns([1, 1, 2, 1, 1,1,1, 1,1,1])
                header_cols = st.columns([1, 1, 2, 1, 1,1,1, 1])
                #header_titles = ['Turret', 'Tool', 'Process','Predicted (pcs)','Preset (pcs)','Actual (pcs)', 'Balance (pcs)', 'Balance (mins)', 'LoadX', 'LoadZ']
                header_titles = ['Turret', 'Tool', 'Process','Predicted (pcs)','Preset (pcs)','Actual (pcs)', 'Balance (pcs)', 'Balance (mins)']
                for col, title in zip(header_cols, header_titles):
                    col.markdown(f"**{title}**")
                
                def clear_Selected_Graph(i):
                    st.session_state[f'visible_graph_row_{i}']= None

                # Render table with buttons
                for i, row in df.iterrows():

                    if f'visible_graph_row_{i}' not in st.session_state:
                        st.session_state[f'visible_graph_row_{i}'] = None
                    
                    # Check if this row should be highlighted
                    #highlight = row['Balance (mins)'] <= min_balance
                    highlight = row['Hierarchical_Distance'] == min_cluster or row['Balance (mins)'] <= (min_balance + Tool_Change_min)
                    
                    style = "background-color: #ff3333; padding: 5px;" if highlight else ""
                    UnitPrice = round(row['UnitPrice']/row['PresetCounter'], 5)
                    DiffPcs = row['Balance (pcs)'] - minPcs_balance
                    savings,OriginalTime,CurrentTime,ExtraProduce = calculate_savings(len(filtered_df),df.iloc[0]['MesCT'],DiffPcs,UnitPrice)
                    savingText = f"Original need {OriginalTime}, currently need {CurrentTime}, total time saving {savings} minutes, extra produce {ExtraProduce} pcs"


                    #cols = st.columns([1, 1, 2, 1, 1,1,1, 1,1,1])  # Adjust column widths
                    cols = st.columns([1, 1, 2, 1, 1,1,1, 1])  # Adjust column widths

                    # cols[0].markdown(f"<div style='{style}'>{row['Turret']}</div>", unsafe_allow_html=True, help = savingText if highlight else None)
                    cols[0].markdown(f"<div style='{style}'>{row['Turret']}</div>", unsafe_allow_html=True)
                    cols[1].markdown(f"<div style='{style}'>{row['Tool']} ({row['ToolNoID']})</div>", unsafe_allow_html=True)
                    cols[2].markdown(f"<div>{row['Process']} - {row['mmToolID']}</div>", unsafe_allow_html=True)
                    # cols[3].markdown(f"<div>{row['ToolLife_predicted_final']}</div>", unsafe_allow_html=True,help= None if row['ToolLife_predicted_final'] == '-' else row['Segment_Based_Explanation_md'])
                    cols[3].markdown(f"<div>{row['ToolLife_predicted_final']}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div>{row['PresetCounter']}</div>", unsafe_allow_html=True)
                    cols[5].markdown(f"<div>{row['TotalCounter']}</div>", unsafe_allow_html=True)
                    cols[6].markdown(f"<div>{row['Balance (pcs)']}</div>", unsafe_allow_html=True)
                    cols[7].markdown(f"<div style='{style}'>{row['Balance (mins)']}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='height:25px;'></div>", unsafe_allow_html=True)  # Top spacer

                        

                    # if cols[8].button("LoadX", key=f"btn_LoadX_{i}"):
                    #     if st.session_state[f'visible_graph_row_{i}'] == "LoadX":
                    #         st.session_state[f'visible_graph_row_{i}'] = None # Hide if already visible
                    #     else:
                    #         st.session_state[f'visible_graph_row_{i}'] = "LoadX"

                    # if cols[9].button("LoadZ", key=f"btn_LoadZ_{i}"):
                    #     if st.session_state[f'visible_graph_row_{i}'] == "LoadZ":
                    #         st.session_state[f'visible_graph_row_{i}'] = None # Hide if already visible
                    #     else:
                    #         st.session_state[f'visible_graph_row_{i}'] = "LoadZ"
                    
                        
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
                                PresetCounter=row['PresetCounter'],
                                ToolingStation= row['Tool'],
                                IsHistory=False,
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
                                PresetCounter=row['PresetCounter'],
                                ToolingStation= row['Tool'],
                                IsHistory=False,
                            )

                            #st.pyplot(fig)
                            st.plotly_chart(fig)
                        


                
                st.markdown('---')
     
                                
   
def GetTowerLightUI(color):
    colorUI = f"""
                            <span class="circle-button" style=" background: {color};"></span>
                        """
    return colorUI

@st.fragment(run_every=str(INSPECTION_DATA_CACHE)+"s")
def GetLowestCPK():
    df_tool_data = read_csv_data("LowestCPK.csv")
    filtered_df = df_tool_data.copy()
    for index, row in filtered_df.iterrows():
        MachineID = row['MachineID']
        if f'CurrentMachineMaterial_{MachineID}_LowestPpk' not in st.session_state:
            st.session_state[f'CurrentMachineMaterial_{MachineID}_LowestPpk'] = None
        st.session_state[f'CurrentMachineMaterial_{MachineID}_LowestPpk'] = (
            None if pd.isna(row['Value']) else row['Value']
        )


def process_tool_life(row):
    if pd.isna(row['ToolLife_predicted']):
        return 0
    rounded = int(round(row['ToolLife_predicted'] / 50) * 50)
    return rounded if rounded >= row['PresetCounter'] else '-'


GetLowestCPK()      
ShowTimerInfo()

 # Placeholder for dynamic content
placeholder = st.empty()

if st.session_state.clicked_materialcode:
    with placeholder.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_materialcode():
                st.session_state.clicked_materialcode = None
                placeholder.empty()

            
            st.markdown('---')
            st.markdown(f"### 🔍 Loading Inspection Details (CTQ & CTP) For {st.session_state.clicked_Common_Location} ...")

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

                    st.info(f"#### Showing details for: `{st.session_state.clicked_materialcode} | {materialdesc}`")
                    title =f"SpecNo:{specno}| {df_inspection_data['Description'].iloc[0]} | Ppk = {ppk}"
                    fig = plotIMRByPlotly(df_inspection_data,df_inspection_data['USL'].iloc[0],df_inspection_data['LSL'].iloc[0],title = title) 
                    #st.pyplot(fig)
                    st.plotly_chart(fig)
                else:
                    st.warning(f"No inspection data available for `{st.session_state.clicked_materialcode}`.")

            
            st.markdown('---')

 # ---- Bottom Section: Show History data for clicked_History ----

if st.session_state.clicked_location_History:
    _, df_tool_data_all, _ = load_data_cached(st.session_state.LAST_SELECTED_PLANT)
    with placeholder.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_location():
                st.session_state.clicked_location_History = None
                placeholder.empty()

            
            st.markdown('---')
            st.button("❌ Close",key = f'close_{st.session_state.clicked_location_History}' , on_click=clear_selection_clicked_location)
            st.markdown(f"### 📋 History Tool Change for: {st.session_state.clicked_location_History}")
            cols = ['Turret','Tool','Process','Balance (mins)', 'Balance (pcs)','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter', 'LoadX_Alm', 'LoadZ_Alm']
            df = df_tool_data_all[df_tool_data_all['Location']==st.session_state.clicked_location_History]
            df = df[cols].reset_index(drop=True)

            ColOptionTurret, ColOptionStation, ColStartDatePicker, ColEndDatePicker,ColSearchButton,ColNormalDistribution = st.columns([1,1,1,1,1,1])
            OptionTurret= ''
            OptionStation = ''
            StartDate = None
            EndDate = None
            with ColOptionTurret:
                OptionTurret = st.selectbox("Turret Position",
                        options=sorted(df['Turret'].unique()),
                        index=None,
                        placeholder="Select Turret Position...",
                    )
            with ColOptionStation:
                if OptionTurret:
                    # Filter tools based on selected turret
                    filtered_tools = sorted(df[df['Turret'] == OptionTurret]['Tool'].unique())
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
                        st.session_state.clicked_NormalDistribution = None
                        
            with ColNormalDistribution:
                st.markdown(f"""<div style='height:25px;'></div>""", unsafe_allow_html=True)
                if st.button("Tool Analysis", use_container_width=True):
                    #all selection need to be made else show error
                    if not OptionTurret or not OptionStation or not StartDate or not EndDate:
                        st.error("Please select Turret, Station and Date Range to search.")
                        st.session_state.clicked_NormalDistribution = None
                    # Check if Start Date is before or equal to End Date
                    elif StartDate > EndDate:
                        st.error("Start Date must be earlier than or equal to End Date.")
                        st.session_state.clicked_NormalDistribution = None
                    else:
                        st.session_state.clicked_NormalDistribution = st.session_state.clicked_machineID_History
                        st.session_state.clicked_search_History = None
                        
            if st.session_state.clicked_search_History:
                if not OptionTurret or not OptionStation or not StartDate or not EndDate:
                    st.session_state.clicked_search_History = None
                # Check if Start Date is before or equal to End Date
                elif StartDate > EndDate:
                    st.error("Start Date must be earlier than or equal to End Date.")
                else:
                    df_history = get_History_Tool_Data(
                        MachineName=st.session_state.clicked_search_History,
                        Position=OptionTurret,
                        ToolingStation=OptionStation,
                        StartDate=StartDate,
                        EndDate=EndDate,
                        plant_code=st.session_state.LAST_SELECTED_PLANT
                    )
                    cols = ['Turret','Tool','Process','MachineID', 'ToolNoID', 'StartDate', 'TotalCounter','PresetCounter','CompletedDate','LoadX_Alm', 'LoadZ_Alm','mmToolID']
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
                        cols[1].write(f"{row['Process']} - {row['mmToolID']}")
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
                                    PresetCounter=row['PresetCounter'],
                                    ToolingStation= row['Tool'],
                                    IsHistory=True,
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
                                    PresetCounter=row['PresetCounter'],
                                    ToolingStation= row['Tool'],
                                    IsHistory=True,
                                )

                                #st.pyplot(fig)
                                st.plotly_chart(fig)
            
            if st.session_state.clicked_NormalDistribution:
                if not OptionTurret or not OptionStation or not StartDate or not EndDate:
                    st.session_state.clicked_NormalDistribution = None
                # Check if Start Date is before or equal to End Date
                elif StartDate > EndDate:
                    st.error("Start Date must be earlier than or equal to End Date.")
                else:
                
                    df_history = get_History_Tool_Data(
                        MachineName=st.session_state.clicked_NormalDistribution,
                        Position=OptionTurret,
                        ToolingStation=OptionStation,
                        StartDate=StartDate,
                        EndDate=EndDate,
                        plant_code=st.session_state.LAST_SELECTED_PLANT
                    )
                    
                    df_PPKHistory = get_Inspection_History_Data(
                        MachineName= st.session_state.clicked_NormalDistribution,
                        StartDate=StartDate,  
                        EndDate=EndDate
                    )
                    if df_history.empty:
                                st.error(f"No data available for {st.session_state.clicked_location_History}-{OptionTurret} on {OptionStation} from {StartDate} to {EndDate}.")
                    else:
                        Process = df_history.iloc[0]['Process']
                        mmToolID = df_history.iloc[0]['mmToolID']
                        fig = plotNormalDistributionPlotly(df_history,title=f"Normal Distribution for {st.session_state.clicked_location_History}-{OptionTurret} on station {OptionStation}:  {Process}-{mmToolID} from {StartDate} to {EndDate}")
                        st.plotly_chart(fig)
                        offsetX_fig = plot_OffSet_History_Graph(df=df_history,selectedStation=OptionStation,selectedAxis='X',MachineName=st.session_state.clicked_NormalDistribution)
                        offsetZ_fig = plot_OffSet_History_Graph(df=df_history,selectedStation=OptionStation,selectedAxis='Z',MachineName=st.session_state.clicked_NormalDistribution)
                        st.plotly_chart(offsetX_fig)
                        st.plotly_chart(offsetZ_fig)
                    
                    if df_PPKHistory.empty:
                        st.error(f"No inspection data available for {st.session_state.clicked_location_History}-{OptionTurret} on {OptionStation} from {StartDate} to {EndDate}.")
                    else:
                        grouped = df_PPKHistory.groupby(['ControlPlanId', 'CharId'])
                        separated_df = {f"ControlPlanId{cp}_CharId_{i}": group for (cp, i), group in grouped}
                        
                        
                        for name, table in separated_df.items():
                            # Calculate ppk
                            table['LSL'] = pd.to_numeric(table['LSL'], errors='coerce')
            
                            table['USL'] = pd.to_numeric(table['USL'], errors='coerce')
                            table['MeasValue']= pd.to_numeric(table['MeasValue'], errors='coerce')

                            ppk = calculate_ppk(table['MeasValue'],table['USL'].iloc[0],table['LSL'].iloc[0])
                            title =f"SpecNo:{table['SpecNo'].iloc[0]}| {table['DimensionDesc'].iloc[0]} | Ppk = {ppk}"
                            st.info(f"Ppk for: {table['MaterialCode'].iloc[0]} | {table['MaterialDesc'].iloc[0]} | {title}")
                            
                            #fig = plotIMRByPlotly(table,table['USL'].iloc[0],table['LSL'].iloc[0],title = title) 
                            #st.pyplot(fig)
                            #st.plotly_chart(fig)
            st.markdown('---')

# ---- Bottom Section: Show KPI data for clicked_KPI ----
if st.session_state.clicked_KPI:
    with st.container():
        col1, col2, col3 = st.columns([1,30,1])

        with col2:
            def clear_selection_clicked_location():
                st.session_state.clicked_KPI = None
                placeholder.empty()

            st.markdown('---')
            st.button("❌ Close",key = f'close_{st.session_state.clicked_KPI}' , on_click=clear_selection_clicked_location)
            st.markdown(f"### 📋 KPI (Key Performance Indicator) for: {st.session_state.clicked_Common_Location}")

            
            KPIDf = get_KPI_Data_Cache(
                MachineName=st.session_state.clicked_KPI
            )

            if KPIDf.empty:
                st.error(f"No data available for machine {st.session_state.clicked_KPI}")
            else:
                
                df_low = KPIDf[KPIDf['PresetCounter'] < 1000]
                df_mid = KPIDf[(KPIDf['PresetCounter'] >= 1000) & (KPIDf['PresetCounter'] < 3000)]
                df_high = KPIDf[KPIDf['PresetCounter'] >= 3000]

                fig_low = plot_KPI_Graph(
                    df_low,
                    st.session_state.clicked_Common_Location
                )
                fig_medium = plot_KPI_Graph(
                    df_mid,
                    st.session_state.clicked_Common_Location
                )
                fig_high = plot_KPI_Graph(
                    df_high,
                    st.session_state.clicked_Common_Location
                )
                if fig_low:
                    st.plotly_chart(fig_low)
                if fig_medium:
                    st.plotly_chart(fig_medium)
                if fig_high:
                    st.plotly_chart(fig_high)
                    
            st.markdown('---')



with st.container():
        col1, col2, col3 = st.columns([1,70,1])

        with col2:
            RedColorUI = GetTowerLightUI('red')

            YellowColorUI = GetTowerLightUI('#FFBF00')

            GreenColorUI = GetTowerLightUI('#00FF00')
            GreyColorUI = GetTowerLightUI('#373737')

            st.markdown( f"<div class='circle-container' style='text-align: center; border-bottom: 2px solid white; font-size: 1.5rem;'><div class='legendDiv'>{RedColorUI} <span>Alarm/Stop</span></div> |<div class='legendDiv'>{YellowColorUI} <span>Waiting</span></div> |<div class='legendDiv'>{GreenColorUI} <span>Running</span></div> |<div class='legendDiv'>{GreyColorUI} <span>Machine Off</span></div> |  <div class='legendDiv'> <span><img src='data:image/png;base64,{machineBase64}' alt='icon' style='height: 2.5em; vertical-align: middle;'/> </span> <span>Machine Error</span></div> | <div class='legendDiv'> <span><img src='data:image/png;base64,{robotArmBase64}' alt='icon' style='height: 2.5em; vertical-align: middle;'/> </span> <span>Automation Error</span></div></div>",
                    unsafe_allow_html=True)
                
            #st.markdown('---')

# Tooling countdown times
