import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go

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

def plotIMRByPlotly(df, usl, lsl,title):
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
    
    
    # Tick selection
    all_ticks = df['X']
    selected_ticks = all_ticks
    if len(selected_ticks) == 0 or selected_ticks.iloc[-1] != all_ticks.iloc[-1]: # show last label too
        selected_ticks = pd.concat([pd.Series(selected_ticks), pd.Series([all_ticks.iloc[-1]])], ignore_index=True)
    selected_labels = df['MeasDate'].dt.strftime('%m-%d %H:%M')

    # Create Plotly figure
    fig = go.Figure()

    # I Chart line
    fig.add_trace(go.Scatter(x=df['X'], y=df['I'], mode='lines+markers', name='I', marker=dict(color='cyan')))

    # Control lines
    fig.add_trace(go.Scatter(x=df['X'], y=[I_bar]*len(df), mode='lines', name='I-bar', line=dict(color='green', dash='dash')))
    fig.add_trace(go.Scatter(x=df['X'], y=[GLSL]*len(df), mode='lines', name='GLSL', line=dict(color='green', dash='dash')))
    fig.add_trace(go.Scatter(x=df['X'], y=[GUSL]*len(df), mode='lines', name='GUSL', line=dict(color='green', dash='dash')))
    fig.add_trace(go.Scatter(x=df['X'], y=[YLSL]*len(df), mode='lines', name='YLSL', line=dict(color='#FFBF00', dash='dash')))
    fig.add_trace(go.Scatter(x=df['X'], y=[YUSL]*len(df), mode='lines', name='YUSL', line=dict(color='#FFBF00', dash='dash')))

    # Simulated USL/LSL values for red lines
    fig.add_trace(go.Scatter(x=df['X'], y=[usl]*len(df), mode='lines', name='USL', line=dict(color='red', dash='dash')))
    fig.add_trace(go.Scatter(x=df['X'], y=[lsl]*len(df), mode='lines', name='LSL', line=dict(color='red', dash='dash')))

    # Update layout for dark mode
    fig.update_layout(
        title=dict(text=title, 
        x=0.5,  # Center the title
        xanchor='center',
        font=dict(size=16, color='white')
        ),
        xaxis=dict(
            title="Measurement Date",
            tickmode='array',
            tickvals=selected_ticks,
            ticktext=selected_labels,
            tickangle=45,
            color='white'
        ),
        yaxis=dict(title="Measurement Value", color='white'),
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white'),
        legend=dict(font=dict(color='white'))
    )
    return fig


# ---- Visualise Data by Plotly ----
# This function visualises the data using Plotly, including regression lines and annotations.
def VisualiseDataByPlotly(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn,DataToShow):
    df_machineMax = GroupCurrentToolCountNQuestdbValueMax.copy()#.tail(DataToShow).copy()
    df_machineMean = GroupCurrentToolCountNQuestdbValueMean.copy()#.tail(DataToShow).copy()
    # Extract data
    xMax = df_machineMax['Count']
    yMax = df_machineMax[selectedColumn]
    xMean = df_machineMean['Count']
    yMean = df_machineMean[selectedColumn]

    # Compute linear regression
    slopeMax, interceptMax, _, _, _ = linregress(xMax, yMax)
    regression_lineMax = slopeMax * xMax + interceptMax

    slopeMean, interceptMean, _, _, _ = linregress(xMean, yMean)
    regression_lineMean = slopeMean * xMean + interceptMean

    # Determine color based on slope sign
    colorMax = "red"  # Customize based on slopeMax if needed
    colorMean = "red"  # Customize based on slopeMean if needed

    # Create Plotly figure
    fig = go.Figure()

    # Add max and mean lines
    fig.add_trace(go.Scatter(x=xMax, y=yMax, mode='lines', name='Max of ' + selectedColumn,
                            line=dict(color='white', width=1.2), opacity=0.4))
    fig.add_trace(go.Scatter(x=xMean, y=yMean, mode='lines', name='Mean of ' + selectedColumn,
                            line=dict(color='yellow', width=1.2), opacity=0.4))

    # Add regression lines
    fig.add_trace(go.Scatter(x=xMax, y=regression_lineMax, mode='lines', name='Linear Regression (max)',
                            line=dict(color=colorMax, width=4, dash='dash')))
    fig.add_trace(go.Scatter(x=xMean, y=regression_lineMean, mode='lines', name='Linear Regression (mean)',
                            line=dict(color=colorMean, width=4, dash='dot')))

    # Annotate 6 points on each regression line
    def annotate_points(x, y, label_prefix):
        indices = np.linspace(0, len(x) - 1, 6, dtype=int)
        for i in indices:
            fig.add_trace(go.Scatter(
                x=[x[i]], y=[y[i]],
                mode='text',
                text=[f'{label_prefix}: {y[i]:.2f}'],
                textposition='top center',
                textfont=dict(size=15, color='red'),
                marker=dict(color='white'),
                showlegend=False
            ))

    annotate_points(xMax, regression_lineMax, 'Max')
    annotate_points(xMean, regression_lineMean, 'Mean')

    # Add labels and title
    ToolingStation = df_machineMax['ToolingStation'].iloc[0]
    fig.update_layout(
        title=dict(text=f'Tooling Station {ToolingStation} | Column {selectedColumn}',
        x=0.5,  # Center the title
        xanchor='center',
        font=dict(size=16, color='white')
        ),
        xaxis_title='Output Count',
        yaxis_title=selectedColumn,
        legend_title='Legend',
        width=1200,
        height=400,
        xaxis=dict(tickangle=45),
        plot_bgcolor='black'
    )
    return fig

# ---- plot Selected Column by pieces made ----
def plot_selected_columns_by_pieces_made(df, selectedColumn,TotalCounter, DataToShow=200):
    GroupCurrentToolCountNQuestdbValueMax = GroupDfByPiecesMade(df)
    GroupCurrentToolCountNQuestdbValueMean = GroupDfByPiecesMade(df,False)
    GroupCurrentToolCountNQuestdbValueMax = GroupCurrentToolCountNQuestdbValueMax[GroupCurrentToolCountNQuestdbValueMax['Count']<=TotalCounter]
    GroupCurrentToolCountNQuestdbValueMean = GroupCurrentToolCountNQuestdbValueMean[GroupCurrentToolCountNQuestdbValueMean['Count']<=TotalCounter]
    fig = VisualiseDataByPlotly(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn, DataToShow)#VisualiseData(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn, DataToShow)
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
    
    