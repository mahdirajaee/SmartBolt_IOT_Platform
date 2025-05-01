import os
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State, dash_table
import flask
from flask import Flask, redirect, request, session, url_for
import functools

BASE_URL = os.environ.get('BASE_URL', 'http://localhost')
ACCOUNT_MANAGER_URL = os.environ.get('ACCOUNT_MANAGER_URL', f'{BASE_URL}:8000')
RESOURCE_CATALOG_URL = os.environ.get('RESOURCE_CATALOG_URL', f'{BASE_URL}:8080')
ANALYTICS_URL = os.environ.get('ANALYTICS_URL', f'{BASE_URL}:8001')
TIMESERIES_URL = os.environ.get('TIMESERIES_URL', f'{BASE_URL}:8002')

server = Flask(__name__)
server.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')

app = dash.Dash(
    __name__,
    server=server,
    routes_pathname_prefix='/dashboard/',
    suppress_callback_exceptions=True
)

def login_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

@server.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect('/dashboard/')

@server.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            response = requests.post(
                f'{ACCOUNT_MANAGER_URL}/login',
                json={'username': username, 'password': password}
            )
            
            if response.status_code == 200:
                session['username'] = username
                return redirect('/')
            else:
                error = 'Invalid credentials. Please try again.'
        except requests.exceptions.RequestException:
            error = 'Could not connect to authentication service.'
    
    return flask.render_template('login.html', error=error)

@server.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

def fetch_sectors():
    try:
        response = requests.get(f'{RESOURCE_CATALOG_URL}/sectors')
        if response.status_code == 200:
            return response.json().get('sectors', [])
        return []
    except requests.exceptions.RequestException:
        return []

def fetch_device_data(device_id):
    try:
        response = requests.get(f'{RESOURCE_CATALOG_URL}/devices/{device_id}')
        if response.status_code == 200:
            return response.json()
        return {}
    except requests.exceptions.RequestException:
        return {}

def fetch_historical_data(device_id, sensor_type, days=7):
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        response = requests.get(
            f'{TIMESERIES_URL}/query',
            params={
                'device_id': device_id,
                'sensor_type': sensor_type,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
        )
        
        if response.status_code == 200:
            data = response.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
        return pd.DataFrame()
    except requests.exceptions.RequestException:
        return pd.DataFrame()

def fetch_analytics_insights(device_id=None):
    try:
        params = {}
        if device_id:
            params['device_id'] = device_id
            
        response = requests.get(f'{ANALYTICS_URL}/insights', params=params)
        if response.status_code == 200:
            return response.json().get('insights', [])
        return []
    except requests.exceptions.RequestException:
        return []

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='user-info', className='user-info'),
    html.Div(id='page-content')
])

def create_dashboard_layout():
    return html.Div([
        html.H1('Smart Irrigation Dashboard'),
        html.A('Logout', href='/logout', className='logout-btn'),
        
        html.Div([
            html.Div([
                html.H2('Sectors'),
                dcc.Dropdown(id='sector-dropdown', placeholder='Select a sector'),
                html.Div(id='sector-info', className='sector-info'),
            ], className='dashboard-column'),
            
            html.Div([
                html.H2('Devices'),
                dcc.Dropdown(id='device-dropdown', placeholder='Select a device'),
                html.Div(id='device-status', className='device-status'),
            ], className='dashboard-column'),
        ], className='dashboard-row'),
        
        html.Div([
            html.H2('Sensor Data'),
            dcc.Tabs([
                dcc.Tab(label='Current Status', children=[
                    html.Div(id='current-sensors', className='sensor-container')
                ]),
                dcc.Tab(label='Historical Data', children=[
                    dcc.Dropdown(id='sensor-type-dropdown', placeholder='Select sensor type'),
                    dcc.Graph(id='historical-graph'),
                    dcc.RadioItems(
                        id='time-range',
                        options=[
                            {'label': '1 Day', 'value': 1},
                            {'label': '1 Week', 'value': 7},
                            {'label': '1 Month', 'value': 30},
                        ],
                        value=7,
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    )
                ]),
                dcc.Tab(label='Analytics Insights', children=[
                    html.Div(id='analytics-insights', className='insights-container')
                ]),
            ]),
        ], className='dashboard-row'),
    ])

@app.callback(
    Output('user-info', 'children'),
    Input('url', 'pathname')
)
def display_user_info(pathname):
    if 'username' in session:
        return html.Div([
            html.Span(f'Logged in as: {session["username"]}')
        ])
    return html.Div()

@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/dashboard/':
        if 'username' in session:
            return create_dashboard_layout()
        return redirect(url_for('login'))
    return html.Div([
        html.H1('404 - Page not found'),
        html.A('Go to Dashboard', href='/dashboard/')
    ])

@app.callback(
    Output('sector-dropdown', 'options'),
    Input('url', 'pathname')
)
def populate_sectors(pathname):
    if pathname == '/dashboard/':
        sectors = fetch_sectors()
        return [{'label': sector['name'], 'value': sector['id']} for sector in sectors]
    return []

@app.callback(
    Output('sector-info', 'children'),
    Input('sector-dropdown', 'value')
)
def display_sector_info(sector_id):
    if not sector_id:
        return html.Div()
    
    sectors = fetch_sectors()
    sector = next((s for s in sectors if s['id'] == sector_id), None)
    
    if sector:
        return html.Div([
            html.H3(sector['name']),
            html.P(f"Location: {sector.get('location', 'N/A')}"),
            html.P(f"Area: {sector.get('area', 'N/A')} sq meters"),
            html.P(f"Status: {sector.get('status', 'N/A')}"),
        ])
    return html.Div()

@app.callback(
    [Output('device-dropdown', 'options'),
     Output('device-dropdown', 'value')],
    Input('sector-dropdown', 'value')
)
def populate_devices(sector_id):
    if not sector_id:
        return [], None
    
    sectors = fetch_sectors()
    sector = next((s for s in sectors if s['id'] == sector_id), None)
    
    if sector and 'devices' in sector:
        options = [{'label': device['name'], 'value': device['id']} for device in sector['devices']]
        value = options[0]['value'] if options else None
        return options, value
    return [], None

@app.callback(
    [Output('device-status', 'children'),
     Output('sensor-type-dropdown', 'options'),
     Output('current-sensors', 'children')],
    Input('device-dropdown', 'value')
)
def display_device_info(device_id):
    if not device_id:
        return html.Div(), [], html.Div()
    
    device_data = fetch_device_data(device_id)
    
    if not device_data:
        return html.Div("Device information unavailable"), [], html.Div()
    
    device_info = html.Div([
        html.H3(device_data.get('name', 'Unknown Device')),
        html.P(f"Type: {device_data.get('type', 'N/A')}"),
        html.P(f"Status: {device_data.get('status', 'N/A')}"),
        html.P(f"Last Update: {device_data.get('last_update', 'N/A')}"),
    ])
    
    sensors = device_data.get('sensors', [])
    sensor_options = [{'label': s['name'], 'value': s['type']} for s in sensors]
    
    current_sensors = html.Div([
        html.Div([
            html.H4(sensor['name']),
            html.P(f"Value: {sensor.get('value', 'N/A')} {sensor.get('unit', '')}"),
            html.P(f"Status: {sensor.get('status', 'N/A')}"),
            html.P(f"Last Update: {sensor.get('last_update', 'N/A')}")
        ], className='sensor-card') for sensor in sensors
    ])
    
    return device_info, sensor_options, current_sensors

@app.callback(
    Output('historical-graph', 'figure'),
    [Input('device-dropdown', 'value'),
     Input('sensor-type-dropdown', 'value'),
     Input('time-range', 'value')]
)
def update_historical_graph(device_id, sensor_type, days):
    if not device_id or not sensor_type:
        return go.Figure()
    
    df = fetch_historical_data(device_id, sensor_type, days)
    
    if df.empty:
        return go.Figure().update_layout(
            title=f"No historical data available for {sensor_type}",
            xaxis_title="Time",
            yaxis_title="Value"
        )
    
    fig = px.line(
        df, 
        x='timestamp', 
        y='value',
        title=f"Historical {sensor_type} Data"
    )
    
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title=f"Value ({df['unit'].iloc[0] if 'unit' in df.columns and not df['unit'].empty else ''})"
    )
    
    return fig

@app.callback(
    Output('analytics-insights', 'children'),
    Input('device-dropdown', 'value')
)
def display_analytics_insights(device_id):
    insights = fetch_analytics_insights(device_id)
    
    if not insights:
        return html.Div("No analytics insights available")
    
    return html.Div([
        html.Div([
            html.H4(insight.get('title', 'Insight')),
            html.P(insight.get('description', 'No description')),
            html.P(f"Generated: {insight.get('timestamp', 'N/A')}"),
            html.Div([
                dcc.Graph(
                    figure=go.Figure(
                        data=insight.get('chart_data', []),
                        layout=insight.get('chart_layout', {})
                    )
                ) if 'chart_data' in insight else html.Div()
            ])
        ], className='insight-card') for insight in insights
    ])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=True, host='0.0.0.0', port=port) 