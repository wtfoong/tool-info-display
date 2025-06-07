import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('dark_background') # #see all styles --> print(plt.style.available)

# import local module
from config_loader import load_config
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

# ---- plot IMR ----
def plot_IMR(df, usl, lsl):

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

    # Set X-axis as categorical using index (MeasDate are not evenly spaced - very cluttered continuous plot)
    df['X'] = range(len(df))

    # Plot IMR chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)

    # --- Common tick selection ---
    all_ticks = df['X']
    selected_ticks = all_ticks[::5] # show every 5th label
    if len(selected_ticks) == 0 or selected_ticks.iloc[-1] != all_ticks.iloc[-1]: # show last label too
        selected_ticks = pd.concat([selected_ticks, pd.Series([all_ticks.iloc[-1]])], ignore_index=True)
    selected_labels = df['MeasDate'].dt.strftime('%m-%d %H:%M').iloc[selected_ticks]

    # I Chart
    ax1.plot(df['X'], df['I'], marker='o')
    ax1.axhline(I_bar, color='green', linestyle='--', label='I-bar', lw=0.9)
    ax1.axhline(UCL_I, color='#FFBF00', linestyle='--', label='UCL', lw=0.9)
    ax1.axhline(LCL_I, color='#FFBF00', linestyle='--', label='LCL', lw=0.9)
    ax1.axhline(usl, color='red', linestyle='--', label='USL', lw=0.9)
    ax1.axhline(lsl, color='red', linestyle='--', label='LSL', lw=0.9)
    ax1.set_title(f"Individual (I) Chart")
    ax1.set_ylabel("Measurement Value")

    # Set spine (border) thickness
    for spine in ax1.spines.values():
        spine.set_linewidth(0.4)

    # MR Chart
    ax2.plot(df['X'], df['MR'], marker='o')
    ax2.axhline(MR_bar, color='green', linestyle='--', label='MR-bar', lw=0.9)
    ax2.axhline(UCL_MR, color='red', linestyle='--', label='UCL', lw=0.9)
    ax2.set_title("Moving Range (MR) Chart")
    ax2.set_ylabel("Moving Range")
    ax2.set_xlabel("")
    ax2.set_xticks(selected_ticks)
    ax2.set_xticklabels(selected_labels, rotation=45)

    # Set spine (border) thickness
    for spine in ax2.spines.values():
        spine.set_linewidth(0.4)

    plt.tight_layout()
    return fig