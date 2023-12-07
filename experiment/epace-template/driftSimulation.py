import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import numpy as np
import math

# Function for exponential decay
def exponentialDecay(flowRate, conc0, time):
    return conc0 * math.e ** (-flowRate * time)

driftConc = 50 # Drift inducer concentration
selecConc = 50 # Selection inducer concentration

#### Flow Rate Variables ####
initRate = 0.5 # V/h; initial lagoon flow rate
targetRate = 3 # V/h; target flow rate
timeToTarget = 100 # hours; sets the slope of the flow rate increase

#### Drift Variables ####
driftInterval = 8 # hours; time between periods of drift
driftLength = 3 # hours; time that drift is fully on
intervalModifier = 2 # additional time added to driftInterval after each drift
numDriftCycles = 6 # the number of drift cycles to perform

# Dash app initialization
app = dash.Dash(__name__)

# Define layout
app.layout = html.Div([
    # Slider labels
    html.Label('Initial Flow Rate'),
    dcc.Slider(id='initRate-slider', min=0, max=3, step=0.1, value=initRate),
    
    html.Label('Target Flow Rate'),
    dcc.Slider(id='targetRate-slider', min=0, max=3, step=0.1, value=targetRate),
    
    html.Label('Time to Target'),
    dcc.Slider(id='timeToTarget-slider', min=5, max=200, step=5, value=timeToTarget),
    
    html.Label('Drift Interval'),
    dcc.Slider(id='driftInterval-slider', min=0, max=20, step=1, value=driftInterval),
    
    html.Label('Drift Length'),
    dcc.Slider(id='driftLength-slider', min=0, max=20, step=1, value=driftLength),
    
    html.Label('Interval Modifier'),
    dcc.Slider(id='intervalModifier-slider', min=0, max=10, step=0.5, value=intervalModifier),
    
    html.Label('Number of Drift Cycles'),
    dcc.Slider(id='numDriftCycles-slider', min=1, max=20, step=1, value=numDriftCycles),

    # Line graph
    dcc.Graph(id='line-graph') 
])

# Define callback to update graph based on slider values
@app.callback(
    Output('line-graph', 'figure'),
    [
        Input('initRate-slider', 'value'),
        Input('targetRate-slider', 'value'),
        Input('timeToTarget-slider', 'value'),
        Input('driftInterval-slider', 'value'),
        Input('driftLength-slider', 'value'),
        Input('intervalModifier-slider', 'value'),
        Input('numDriftCycles-slider', 'value')
    ]
)
def update_graph(initRate, targetRate, timeToTarget, driftInterval, driftLength, intervalModifier, numDriftCycles):
    # Reset variables
    elapsed_time = 0
    timeIncrement = 0.25
    
    currentRate = initRate
    flowSlope = (targetRate - initRate) / timeToTarget
    flowStep = flowSlope * timeIncrement
    
    cycleNum = 0
    driftStart = 0
    driftEnd = driftStart + driftLength
    
    total = driftLength + 10
    di = driftInterval
    for c in range(1, numDriftCycles):
        total += driftLength + di
        di += intervalModifier
    steps = int(total / timeIncrement)
    
    diluted = False
    timeIncrements = []
    concTimeSeries = []
    flowTimeSeries = []

    # Run simulation
    for i in range(steps):
        # determine current flowRate
        if round(currentRate,2) != targetRate:
            currentRate += flowStep

        # determine current concentration of inducer
        if driftStart <= elapsed_time <= driftEnd: #if we have drift on
            currentConc = driftConc
            # print(f'{i} | {elapsed_time} | Drifting')

        elif driftEnd < elapsed_time: #if we are not in a drift cycle        
            driftStart = driftEnd + driftInterval # set the start of the next cycle
            currentConc = exponentialDecay(currentRate, currentConc, timeIncrement)

            if driftStart < elapsed_time: # We are starting a new drift cycle
                # print(f'{i} | {elapsed_time} | Drift START')
                driftInterval += intervalModifier # increase space between cycles each time
                driftEnd = driftStart + driftLength # set the end of the drift
                currentConc = driftConc
                diluted = False
                ++cycleNum  # Increment the cycle

            elif np.round(currentConc,1) == 0 and not diluted:
                # print(f'{elapsed_time}hr Drift Inducer Diluted Out | Concentration: {currentConc:.2}')
                diluted = True
        
        # Save Data
        flowTimeSeries.append(currentRate)
        concTimeSeries.append(currentConc)
        timeIncrements.append(elapsed_time)

        elapsed_time += timeIncrement
    
    title = " ".join([f"Initial Flow Rate: {initRate} | Target Flow Rate: {targetRate} | Time to Target: {timeToTarget} | Drift Interval: {driftInterval} | Drift Length: {driftLength} | Interval Modifier: {intervalModifier} | Number of Drift Cycles: {numDriftCycles}"])    
    # title = ""
    
    # Create the line graph
    fig = {
        'data': [
            {'x': timeIncrements, 'y': flowTimeSeries, 'type': 'line', 'name': 'Flow Rate'},
            {'x': timeIncrements, 'y': concTimeSeries, 'type': 'line', 'name': '[Drift Inducer]', 'yaxis': 'y2'},
        ],
        'layout': {
            'title': title,
            'xaxis': {'title': 'Time [hr]'},
            'yaxis': {'title': 'Flow Rate [V/hr]', 'range': [0, 3.2]},
            'yaxis2': {'title': '[Drift Inducer]', 'overlaying': 'y', 'side': 'right'},
        }
    }

    return fig

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True,jupyter_mode="tab")
