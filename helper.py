import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.figure_factory as ff

from sklearn.preprocessing import StandardScaler
from scipy.cluster.hierarchy import linkage, fcluster
from datetime import datetime


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


def find_usl_lsl_for_cpk(USL,LSL, target_cpk=1.0):

    mu = np.mean([LSL,USL])

    # Calculate the required distance from mean to USL and LSL
    Green_margin = (USL-LSL)/(target_cpk*6)*1.5
    Yellow_margin = (USL-LSL)/(target_cpk*6)*3
    # Determine USL and LSL
    Gusl = Green_margin + mu
    Glsl = mu - Green_margin   
    Yusl = Yellow_margin + mu
    Ylsl = mu - Yellow_margin

    return round(Gusl, 3), round(Glsl, 3), round(Yusl, 3), round(Ylsl, 3)

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
    GUSL,GLSL,YUSL,YLSL = find_usl_lsl_for_cpk(usl, lsl, target_cpk=1.0) # calculate USL and LSL for Cpk >= 1.0
    
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

def plotIMRByPlotly(df, usl, lsl,title,isHistorical = False):
    df = df.sort_values(by='MeasDate').reset_index(drop=True)
    # Calculate I and MR values
    
    if 'MeasValue' in df.columns:
        df['I'] = df['MeasValue']
    else:
        df['I'] = df['MeasVal']

    df['MR'] = df['I'].diff().abs()

    # Calculate control limits
    I_bar = df['I'].mean()
    MR_bar = df['MR'][1:].mean() #skips the first NaN in the MR column caused by .diff()
    UCL_I = I_bar + 2.66 * MR_bar
    LCL_I = I_bar - 2.66 * MR_bar
    UCL_MR = 3.268 * MR_bar
    GUSL,GLSL,YUSL,YLSL = find_usl_lsl_for_cpk(usl, lsl, target_cpk=1.0) # calculate USL and LSL for Cpk >= 1.0

    # Set X-axis as categorical using index (MeasDate are not evenly spaced - very cluttered continuous plot)
    df['X'] = range(len(df))
    
    
    # Tick selection
    all_ticks = df['X']
    selected_ticks = all_ticks
    if len(selected_ticks) == 0 or selected_ticks.iloc[-1] != all_ticks.iloc[-1]: # show last label too
        selected_ticks = pd.concat([pd.Series(selected_ticks), pd.Series([all_ticks.iloc[-1]])], ignore_index=True)
    selected_labels = df['MeasDate'].dt.strftime('%b-%d %H:%M')

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
def VisualiseDataByPlotly(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn,DataToPredict):
    df_machineMax = GroupCurrentToolCountNQuestdbValueMax.copy()#.tail(200).copy()
    df_machineMean = GroupCurrentToolCountNQuestdbValueMean.copy()#.tail(200).copy()
    # Extract data
    xMax = df_machineMax['Count']
    yMax = df_machineMax[selectedColumn]
    xMean = df_machineMean['Count']
    yMean = df_machineMean[selectedColumn]

    # Compute linear regression
    slopeMax, interceptMax, _, _, _ = linregress(xMax, yMax)
    

    slopeMean, interceptMean, _, _, _ = linregress(xMean, yMean)
    multiplyValue = 2
    
    if DataToPredict >= 5000:
        multiplyValue = 1.2
    elif DataToPredict >= 2000:
        multiplyValue = 1.5
    
    # Compute the start value safely
    start_value = min(xMax.min(), xMean.min())
    if start_value == 0:
        start_value = 1  # Ensure it's explicitly set to 1 if both are zero

    # Generate future x values
    x_future = np.arange(0, (DataToPredict*multiplyValue)+1)
    regression_lineMax = slopeMax * x_future + interceptMax
    regression_lineMean = slopeMean * x_future + interceptMean

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

    # Annotate 6 points on each regression line
    def annotate_points(x, y, label_prefix,setIndex = 6):
        indices = np.linspace(0, len(x) - 1, setIndex, dtype=int)
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
    # Add labels and title
    ToolingStation = df_machineMax['ToolingStation'].iloc[0]
    dataCountForPrediction = 1000 if DataToPredict*0.5 > 1000 else DataToPredict*0.5
    title = f'Tooling Station {ToolingStation} | Column {selectedColumn} |  Prediction Requires ≥ {dataCountForPrediction:.0f} pcs'
    if len(xMax) > 1000 or len(xMax)>DataToPredict*0.5:
        #Add regression lines
        fig.add_trace(go.Scatter(x=x_future, y=regression_lineMax, mode='lines', name='Linear Regression (max)',
                                line=dict(color=colorMax, width=2, dash='dash')))
        fig.add_trace(go.Scatter(x=x_future, y=regression_lineMean, mode='lines', name='Linear Regression (mean)',
                                line=dict(color=colorMean, width=2, dash='dot')))


        annotate_points(x_future, regression_lineMax, 'Max')
        annotate_points(x_future, regression_lineMean, 'Mean')
    else:
        # Add regression lines
        fig.add_trace(go.Scatter(x=xMax, y=regression_lineMax, mode='lines', name='Linear Regression (max)',
                                line=dict(color=colorMax, width=2, dash='dash')))
        fig.add_trace(go.Scatter(x=xMean, y=regression_lineMean, mode='lines', name='Linear Regression (mean)',
                                line=dict(color=colorMean, width=2, dash='dot')))
        annotate_points(xMax, regression_lineMax, 'Max',2)
        annotate_points(xMean, regression_lineMean, 'Mean',2)


    fig.add_shape(
            type="line",
            x0=DataToPredict, y0=min(min(yMax), min(yMean)),
            x1=DataToPredict, y1=max(max(yMax), max(yMean)),
            line=dict(color="white", width=2, dash="dash"),
    )
    
    fig.add_shape(
            type="line",
            x0=len(x_future), y0=min(min(yMax), min(yMean)),
            x1=len(x_future), y1=max(max(yMax), max(yMean)),
            line=dict(color="black", width=2, dash="dash"),
    )
    
    fig.update_layout(
        title=dict(text=title,
        x=0.5,  # Center the title
        xanchor='center',
        font=dict(size=16, color='white')
        ),
        xaxis_title='Output Count',
        yaxis_title=selectedColumn,
        legend_title='Legend',
        width=1200,
        height=400,
        xaxis=dict(tickangle=-45),
        plot_bgcolor='black'
    )
    return fig

# ---- plot Selected Column by pieces made ----
def plot_selected_columns_by_pieces_made(df, selectedColumn,TotalCounter,PresetCounter, DataToShow=200):
    GroupCurrentToolCountNQuestdbValueMax = GroupDfByPiecesMade(df)
    GroupCurrentToolCountNQuestdbValueMean = GroupDfByPiecesMade(df,False)
    GroupCurrentToolCountNQuestdbValueMax = GroupCurrentToolCountNQuestdbValueMax[GroupCurrentToolCountNQuestdbValueMax['Count']<=TotalCounter]
    GroupCurrentToolCountNQuestdbValueMean = GroupCurrentToolCountNQuestdbValueMean[GroupCurrentToolCountNQuestdbValueMean['Count']<=TotalCounter]
    fig = VisualiseDataByPlotly(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn, PresetCounter)#VisualiseData(GroupCurrentToolCountNQuestdbValueMax,GroupCurrentToolCountNQuestdbValueMean,selectedColumn, DataToShow)
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
    
def insert_data_into_csv(df, filename):
    """
    Insert data into a CSV file.
    If the file exists, append the data; otherwise, create a new file.
    """
    try:
        df.to_csv(filename, mode='w', header=True, index=False)
        print(f"Data successfully inserted into {filename}")
    except Exception as e:
        print(f"Error inserting data into {filename}: {e}")
        
def read_csv_data(filename):
    """
    Read data from a CSV file.
    If the file does not exist, return an empty DataFrame.
    """
    try:
        df = pd.read_csv(filename)
        print(f"Data successfully read from {filename}")
        return df
    except FileNotFoundError:
        print(f"{filename} not found. Returning empty DataFrame.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading data from {filename}: {e}")
        return pd.DataFrame()  
        
def plot_KPI_Graph(df, machineName):
    if df.empty:
        print(f"No data available to plot KPI Graph for {machineName}")
        return None
    
    fig = go.Figure()
    df = df[['Year', 'Month', 'AvgCnt', 'ToolingStation', 'ToolingMainCategory']].copy()

    # Create a 'Year-Month' column
    df['YearMonth'] = df['Year'].astype(str) + '-' + df['Month'].astype(str).str.zfill(2)

    # Create a unique identifier for each tool and side
    df['ToolSide'] = df['ToolingStation'].astype(str) + '_' + df['ToolingMainCategory']

    # Pivot the data for plotting
    pivot_df = df.pivot_table(index='ToolSide', columns='YearMonth', values='AvgCnt')
    

    # First non-null value per ToolSide (earliest valid month)
    baseline = pivot_df.bfill(axis=1).iloc[:, 0]

    # Avoid divide-by-zero (treat 0 baseline as NaN so % becomes NaN instead of inf)
    safe_baseline = baseline.replace(0, np.nan)

    # % change vs first value
    pct_df = (pivot_df.divide(safe_baseline, axis=0) - 1) * 100


    # Bar width and offset setup
    bar_width = 0.15
    tool_sides = list(pivot_df.index)
    year_months = list(pivot_df.columns)

    # Create a mapping from ToolSide to numeric x positions
    tool_side_positions = {tool: i for i, tool in enumerate(tool_sides)}


    # Add traces for each column
    for i, year_month in enumerate(pivot_df.columns):
        text_vals = pct_df[year_month].round(1)
        text_vals = text_vals.where(text_vals.notna(), '')
        formatted_name = datetime.strptime(year_month, "%Y-%m").strftime("%Y-%b")


        fig.add_trace(go.Bar(
            x=tool_sides,
            y=pivot_df[year_month],
            name=formatted_name,
            text=text_vals,
            texttemplate='%{y:,.0f} (%{text:+.1f}%)',
            textfont=dict(size=15, color='white'),
            textposition='outside',
            hovertemplate=(
                f"ToolSide=%{{x}}<br>"
                f"{year_month} AvgCnt=%{{y}}<br>"
                "Δ vs ori: %{text}"
                "<extra></extra>"
            ),
            width=bar_width,
            offset=i * bar_width - (bar_width * len(year_months) / 2)
        ))

        # Add annotations below each bar
        for tool in tool_sides:
            x_pos = tool_side_positions[tool] + (i * bar_width - (bar_width * len(year_months) / 2))
            fig.add_annotation(
                x=x_pos,
                y=-10,  # Adjust based on your y-axis range
                text=formatted_name,
                showarrow=False,
                font=dict(size=12, color='white'),
                textangle=-45,
                xanchor='center',
                yanchor='top'
            )

    # Update layout
    fig.update_layout(
        title=dict(text=f"KPI Graph for {machineName}", 
        x=0.5,  # Center the title
        xanchor='center',
        font=dict(size=16, color='white')
        ),
        xaxis=dict(
                title=dict(
                        text='Tooling Station',
                        font=dict(size=20, color='white')  # Correct way to set font size and color
                    ),
                tickfont=dict(size=16, color='white')    # Font size for x-axis tick labels
            ),
        yaxis_title='Output (mean)',
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white',size=20),
        legend=dict(font=dict(color='white'))
    )
    
    # Ensure text above bars isn't clipped by the plotting area
    fig.update_traces(cliponaxis=False)

    return fig

def plotNormalDistributionPlotly(df,title):
    fig = go.Figure()
    
    # Create KDE curve using create_distplot
    hist_data = [df['TotalCounter']]
    group_labels = ['TotalCounter']
    if len(df) > 1:
        fig_kde = ff.create_distplot(hist_data, group_labels,
                                 show_hist=False, show_curve=True,colors=['white'])
    
        # Extract KDE curve trace and scale y-values to number of records
        kde_trace = fig_kde.data[0]
        kde_trace_scaled = go.Scatter(
            x=kde_trace.x,
            y=[y * len(df['TotalCounter'])*50 for y in kde_trace.y],
            mode='lines',
            name='KDE Curve (Scaled)',
            line=dict(color='white')
        )
        # Add KDE curve
        fig.add_trace(kde_trace_scaled)

    # Define bin edges
    nbins = 20
    bin_edges = np.histogram_bin_edges(df['TotalCounter'], bins=nbins)
    
    # Assign each record to a bin
    bin_indices = np.digitize(df['TotalCounter'], bin_edges, right=False)
    
    # Aggregate hover text per bin
    hover_text_by_bin = {}
    for idx, bin_idx in enumerate(bin_indices):
        if bin_idx not in hover_text_by_bin:
            hover_text_by_bin[bin_idx] = []
        hover_text_by_bin[bin_idx].append(f"ToolID: {df['ToolNoID'][idx]}, CompletedDate: {df['CompletedDate'][idx]}, TotalCounter: {df['TotalCounter'][idx]}")
    
    # Create final hover text list for each bin
    final_hover_texts = []
    counts = []
    x_vals = []
    for bin_idx in sorted(hover_text_by_bin.keys()):
        bin_center = (bin_edges[bin_idx-1] + bin_edges[bin_idx-1]) / 2
        x_vals.append(bin_center)
        counts.append(len(hover_text_by_bin[bin_idx]))
        final_hover_texts.append("<br>".join(hover_text_by_bin[bin_idx]))
    
    # Create bar chart manually to allow custom hover text
    fig.add_trace(go.Bar(
        x=x_vals,
        y=counts,
        name='Counter Frequency',
        marker_color='skyblue',
        hovertext=final_hover_texts,
        hoverinfo='text',
        text=counts,  # This adds the y-values as text labels
        textfont=dict(size=15, color='white'),
        textposition='outside'  # Positions the text labels outside the bars
    ))
    
    # Add KDE curve
    fig.add_trace(kde_trace_scaled)

    # Add vertical line for preset counter
    fig.add_shape(
        type="line",
        x0=df['PresetCounter'][0], x1=df['PresetCounter'][0],
        y0=0, y1=1,
        line=dict(color="red", width=2, dash="dash"),
        xref='x', yref='paper'
    )
    
    # Add annotation for the preset line
    fig.add_annotation(x=df['PresetCounter'][0], y=1, yref='paper', text=f'Preset Counter ({df["PresetCounter"][0]})',
                       showarrow=True, arrowhead=1, ax=0, ay=-40)
    
    # Update layout
    fig.update_layout(
        title="Frequency Distribution of :"+title,
        xaxis_title="Counter",
        yaxis_title="Number of Records",
        bargap=0.1,
        height=500
    )
    return fig

def BalanceClustering(df):
    # Extract and scale the relevant feature
    X = df[['Balance (mins)']]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Apply hierarchical clustering using a very tight distance threshold (0.1)
    linked = linkage(X_scaled, method='ward')
    df['Hierarchical_Distance'] = fcluster(linked, t=0.1, criterion='distance')
    return df
