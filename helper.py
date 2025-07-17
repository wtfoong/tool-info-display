import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('dark_background') # #see all styles --> print(plt.style.available)

# import local module
from config_loader import load_config
from scipy.stats import norm,linregress
from datetime import datetime
config = load_config()

# ---- set timer style ----
def set_timer_style(DurationMin):

    DurationMin_Red = config['thresholds']['duration_min']['red']
    DurationMin_Amber = config['thresholds']['duration_min']['amber']

    if DurationMin == DurationMin_Red:
        color = 'red'
        blink_style = "animation: blinker 1s linear infinite;"
    elif DurationMin <= DurationMin_Amber:
        color = '#FFBF00'
        blink_style = "animation: blinker 1s linear infinite;"
    else:
        blink_style = ""
        color = '#00FF00'
    return color, blink_style

# ---- calculate ppk ----
def calculate_ppk(series, usl, lsl):
    '''
    make sure to pass in 1D array (np array or pd series)
    '''
    mu = np.mean(series)
    sigma = np.std(series, ddof=1)  # sample standard deviation
    one_side_upper = (usl - mu) / (3 * sigma)
    one_side_lower = (mu - lsl) / (3 * sigma)
    ppk = min(one_side_upper, one_side_lower)
    return f'{ppk:.3f}' #convert np.float64(1.3232313) string with 3 decimal places


def calculate_cpk(series, usl, lsl):
    '''
    Calculate Cpk from a 1D array (np array or pd series)
    '''
    mu = np.mean(series)
    sigma = np.std(series, ddof=0) # population standard deviation
    one_side_upper = (usl - mu) / (3 * sigma)
    one_side_lower = (mu - lsl) / (3 * sigma)
    cpk = min(one_side_upper, one_side_lower)
    return f'{cpk:.3f}' # formatted to 3 decimal places


def find_usl_lsl_for_cpk(series, target_cpk=1.0):
    """
    Given a 1D array of process data, calculate the minimum USL and maximum LSL
    such that the Cpk is greater than or equal to the target_cpk.
    """
    mu = np.mean(series)
    sigma = np.std(series, ddof=0) # population standard deviation 
    # Calculate the required distance from mean to USL and LSL
    margin = (3 * sigma) / target_cpk 
    # Determine USL and LSL
    usl = mu + margin
    lsl = mu - margin   
    return round(usl, 3), round(lsl, 3)

def GroupDfByPiecesMade(df, IsMax=True):
    if IsMax:
        GroupCurrentToolCountNQuestdbValue = df.groupby(['VALUE', 'ToolingStation','SeqNo'])[['FeedRate', 'SpdlSpd_RPM','SpdlSpd_RPM_SP','Load_X','Load_Z','Load_Spdl']].max().reset_index()
    else:
       GroupCurrentToolCountNQuestdbValue = df.groupby(['VALUE', 'ToolingStation','SeqNo'])[['FeedRate', 'SpdlSpd_RPM','SpdlSpd_RPM_SP','Load_X','Load_Z','Load_Spdl']].mean().reset_index()
        
    GroupCurrentToolCountNQuestdbValue['ToolingStationSeqNum'] = GroupCurrentToolCountNQuestdbValue['ToolingStation'].astype(str) +'-'+ GroupCurrentToolCountNQuestdbValue['SeqNo'].astype(str)
    GroupCurrentToolCountNQuestdbValue = GroupCurrentToolCountNQuestdbValue.sort_values(by=['VALUE'], ascending=[False]).reset_index(drop=True)
    
    GroupCurrentToolCountNQuestdbValue['Count'] = range(1, len(GroupCurrentToolCountNQuestdbValue) + 1)

    return GroupCurrentToolCountNQuestdbValue

# ---- plot IMR ----
def plot_IMR(df, usl, lsl,title):

    df = df.sort_values(by='MeasDate').reset_index(drop=True)

    # Calculate I and MR values
    df['I'] = df['MeasVal']
    df['MR'] = df['I'].diff().abs()

    # Calculate control limits
    I_bar = df['I'].mean()
    MR_bar = df['MR'][1:].mean() #skips the first NaN in the MR column caused by .diff()
    UCL_I = I_bar + 2.66 * MR_bar
    LCL_I = I_bar - 2.66 * MR_bar
    UCL_MR = 3.268 * MR_bar
    GUSL,GLSL = find_usl_lsl_for_cpk(df['MeasVal'], target_cpk=1.0) # calculate USL and LSL for Cpk >= 1.0
    YUSL,YLSL = find_usl_lsl_for_cpk(df['MeasVal'], target_cpk=0.9) # calculate USL and LSL for Cpk >= 1.0

    # Set X-axis as categorical using index (MeasDate are not evenly spaced - very cluttered continuous plot)
    df['X'] = range(len(df))

    # Plot IMR chart
    #fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    fig, (ax1) = plt.subplots(1, 1, figsize=(15, 6), sharex=True)

    # --- Common tick selection ---
    all_ticks = df['X']
    selected_ticks = all_ticks[::5] # show every 5th label
    if len(selected_ticks) == 0 or selected_ticks.iloc[-1] != all_ticks.iloc[-1]: # show last label too
        selected_ticks = pd.concat([selected_ticks, pd.Series([all_ticks.iloc[-1]])], ignore_index=True)
    selected_labels = df['MeasDate'].dt.strftime('%m-%d %H:%M').iloc[selected_ticks]

    # I Chart
    ax1.plot(df['X'], df['I'], marker='o')
    ax1.axhline(I_bar, color='green', linestyle='--', label='I-bar', lw=0.9)
    ax1.axhline(GLSL, color='green', linestyle='--', label='I-bar', lw=0.9)
    ax1.axhline(GUSL, color='green', linestyle='--', label='I-bar', lw=0.9)
    ax1.axhline(YLSL, color='#FFBF00', linestyle='--', label='UCL', lw=0.9)
    ax1.axhline(YUSL, color='#FFBF00', linestyle='--', label='LCL', lw=0.9)
    # ax1.axhline(UCL_I, color='#FFBF00', linestyle='--', label='UCL', lw=0.9)
    # ax1.axhline(LCL_I, color='#FFBF00', linestyle='--', label='LCL', lw=0.9)
    ax1.axhline(usl, color='red', linestyle='--', label='USL', lw=0.9)
    ax1.axhline(lsl, color='red', linestyle='--', label='LSL', lw=0.9)
    ax1.set_title(title, fontsize=16, fontweight='bold')
    ax1.set_ylabel("Measurement Value")

    # Set spine (border) thickness
    for spine in ax1.spines.values():
        spine.set_linewidth(0.4)

    # # MR Chart
    # ax2.plot(df['X'], df['MR'], marker='o')
    # ax2.axhline(MR_bar, color='green', linestyle='--', label='MR-bar', lw=0.9)
    # ax2.axhline(UCL_MR, color='red', linestyle='--', label='UCL', lw=0.9)
    # ax2.set_title("Moving Range (MR) Chart")
    # ax2.set_ylabel("Moving Range")
    # ax2.set_xlabel("")
    ax1.set_xticks(selected_ticks)
    ax1.set_xticklabels(selected_labels, rotation=45)

    # # Set spine (border) thickness
    # for spine in ax2.spines.values():
    #     spine.set_linewidth(0.4)

    plt.tight_layout()
    return fig


def VisualiseData(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn,DataToShow):
    df_machineMax = GroupCurrentToolCountNQuestdbValueMax.copy()#.tail(DataToShow).copy()
    df_machineMean = GroupCurrentToolCountNQuestdbValueMean.copy()#.tail(DataToShow).copy()
    
    
    # Create a new figure for each machine
    fig, (ax1) = plt.subplots(1, 1, figsize=(30, 10), sharex=True)
    
    # Plot different parameters for the machine
    ax1.plot(df_machineMax['Count'],df_machineMax[selectedColumn], label='Max of '+ selectedColumn, color='w',linewidth=1.2, alpha=0.4)
    ax1.plot(df_machineMean['Count'],df_machineMean[selectedColumn], label='Mean of '+selectedColumn, color='y',linewidth=1.2, alpha=0.4)

    # Compute linear regression for 'Acts' column
    xMax = df_machineMax['Count']

    yMax = df_machineMax[selectedColumn]
    slope, intercept, _, _, _ = linregress(xMax, yMax)
    regression_lineMax = slope * xMax + intercept
    
    
    xMean = df_machineMean['Count']
    yMean = df_machineMean[selectedColumn]
    slope, intercept, _, _, _ = linregress(xMean, yMean)
    regression_lineMean = slope * xMean + intercept
    
    # Determine color based on slope sign
    color = "red" #if slope > 0 else "red"
    #plt.ylim(0, 30)
    
    # Plot regression line with dynamic color
    ax1.plot(xMax, regression_lineMax, linestyle="--", color=color, label="Linear Regression (max)", linewidth=4)
    ax1.plot(xMean, regression_lineMean, linestyle=":", color=color, label="Linear Regression (mean)", linewidth=4)
    
    
    # Annotate 6 points on each regression line: start, end, and 4 evenly spaced points
    def annotate_points(x, y, label_prefix):
        indices = np.linspace(0, len(x) - 1, 6, dtype=int)
        for i in indices:
            ax1.text(x[i], y[i], f'{label_prefix}: {y[i]:.2f}', fontsize=15, ha='center', va='bottom',color='red',backgroundcolor='white', bbox=dict(facecolor='white', edgecolor='none', boxstyle='round,pad=0.1'))

    annotate_points(xMax, regression_lineMax, 'Max')
    annotate_points(xMean, regression_lineMean, 'Mean')


    ToolingStation = df_machineMax['ToolingStation'].iloc[0]
    # Add labels and title
    ax1.set_title(f'Tooling Station {ToolingStation} | Column {selectedColumn}',fontsize=16, fontweight='bold')
    
    ax1.set_xlabel('Smartbox Count')
    ax1.set_ylabel(selectedColumn)
    ax1.legend()
    ax1.tick_params(axis='x', rotation=45)

    ax1.grid(False)
    return fig

# ---- plot Selected Column by pieces made ----
def plot_selected_columns_by_pieces_made(df, selectedColumn,TotalCounter, DataToShow=200):
    GroupCurrentToolCountNQuestdbValueMax = GroupDfByPiecesMade(df)
    GroupCurrentToolCountNQuestdbValueMean = GroupDfByPiecesMade(df,False)
    GroupCurrentToolCountNQuestdbValueMax = GroupCurrentToolCountNQuestdbValueMax[GroupCurrentToolCountNQuestdbValueMax['Count']<=TotalCounter]
    GroupCurrentToolCountNQuestdbValueMean = GroupCurrentToolCountNQuestdbValueMean[GroupCurrentToolCountNQuestdbValueMean['Count']<=TotalCounter]
    fig = VisualiseData(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn, DataToShow)
    return fig
    
# ---- plot RPM ----
def plot_RPMGraph(df,start_date):
    #df = df.tail(DataToShow)
    fig, ax = plt.subplots(figsize=(30, 10))
    
    # Plot Spindle RPM
    ax.plot(range(len(df)), df['SpdlSpd_RPM'], label='Spindle RPM', color='w', linewidth=2)
    
    # Plot Spindle RPM Setpoint
    ax.plot(range(len(df)), df['SpdlSpd_RPM_SP'], label='Spindle RPM Setpoint', color='y', linewidth=2)
    
    # Add labels and title
    ax.set_title(f'Spindle RPM and Setpoint from {start_date.strftime("%H:%M:%S")} to {datetime.now().strftime("%H:%M:%S")}')
    ax.set_xlabel('Smartbox Count')
    ax.set_ylabel('RPM')
    ax.legend()
    
    ax.tick_params(axis='x', rotation=45)
    ax.grid(False)
    
    return fig
    
    