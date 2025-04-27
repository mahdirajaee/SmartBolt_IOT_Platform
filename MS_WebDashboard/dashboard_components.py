import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# Modern color scheme
COLORS = {
    'primary': '#2563eb',    # Blue
    'secondary': '#0f172a',  # Dark blue
    'success': '#16a34a',    # Green
    'danger': '#dc2626',     # Red
    'warning': '#f59e0b',    # Amber
    'info': '#0ea5e9',       # Light blue
    'light': '#f8fafc',      # Light gray
    'dark': '#1e293b',       # Dark gray
    'white': '#ffffff',
    'background': '#f1f5f9',
    'card': '#ffffff',
    'text': '#334155',
    'border': '#e2e8f0'
}

# Chart color schemes
CHART_COLORS = {
    'temperature': ['#2563eb', '#93c5fd'],
    'pressure': ['#16a34a', '#86efac'],
    'flow': ['#f59e0b', '#fcd34d']
}

def create_header():
    """Create dashboard header with logo and title"""
    return dbc.Navbar(
        dbc.Container(
            [
                html.A(
                    dbc.Row(
                        [
                            dbc.Col(html.I(className="fas fa-bolt-lightning fs-2 text-primary me-2")),
                            dbc.Col(dbc.NavbarBrand("Smart Bolt Dashboard", className="ms-2 fw-bold")),
                        ],
                        align="center",
                    ),
                    href="/dashboard/",
                    style={"textDecoration": "none"},
                ),
                dbc.NavbarToggler(id="navbar-toggler"),
                dbc.Collapse(
                    dbc.Nav(
                        [
                            dbc.NavItem(html.Div(id='live-clock', className="nav-link text-dark")),
                            dbc.NavItem(
                                dbc.Button(
                                    [html.I(className="fas fa-sign-out-alt me-2"), "Logout"],
                                    color="outline-danger",
                                    className="ms-2",
                                    size="sm",
                                    href="/logout"
                                )
                            ),
                        ],
                        className="ms-auto",
                        navbar=True,
                    ),
                    id="navbar-collapse",
                    navbar=True,
                ),
            ],
            fluid=True,
        ),
        color="white",
        className="shadow-sm mb-4",
        sticky="top",
    )

def create_system_status_card(statuses):
    """Create system status card showing health of services"""
    status_items = []
    
    all_ok = all(statuses.values())
    
    for service, is_ok in statuses.items():
        status_icon = "fa-check-circle" if is_ok else "fa-times-circle"
        status_color = "text-success" if is_ok else "text-danger"
        
        status_items.append(
            dbc.ListGroupItem(
                [
                    html.I(className=f"fas {status_icon} {status_color} me-2"),
                    html.Span(service, className="fw-medium")
                ],
                className="border-0 py-2 px-3"
            )
        )
    
    status_badge = html.Span(
        [
            html.I(className=f"fas {'fa-check-circle' if all_ok else 'fa-exclamation-triangle'} me-2"),
            "All Systems Operational" if all_ok else "System Issues Detected"
        ],
        className=f"badge {'bg-success' if all_ok else 'bg-warning text-dark'} rounded-pill px-3 py-2"
    )
    
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Div(
                        [
                            html.I(className="fas fa-server me-2 text-primary"),
                            html.Span("System Status", className="fw-bold"),
                        ],
                        className="d-flex align-items-center"
                    ),
                    status_badge
                ],
                className="d-flex justify-content-between align-items-center"
            ),
            dbc.CardBody(
                [
                    dbc.ListGroup(status_items, className="border-0")
                ],
                className="p-0"
            )
        ],
        className="shadow-sm mb-4 border-0"
    )

def create_device_dropdown(devices):
    """Create dropdown for device selection"""
    options = []
    
    for device in devices:
        options.append({
            "label": f"{device['name']} ({device['id']})",
            "value": device['id']
        })
    
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="fas fa-microchip me-2 text-primary"),
                    html.Span("Select Device", className="fw-bold")
                ],
                className="d-flex align-items-center"
            ),
            dbc.CardBody(
                [
                    dcc.Dropdown(
                        id='device-dropdown',
                        options=options,
                        value=options[0]['value'] if options else None,
                        clearable=False,
                        className="border-0 shadow-sm",
                        optionHeight=50
                    )
                ]
            )
        ],
        className="shadow-sm mb-4 border-0"
    )

def create_time_range_selector():
    """Create time range selector for data visualization"""
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="fas fa-clock me-2 text-primary"),
                    html.Span("Time Range", className="fw-bold")
                ],
                className="d-flex align-items-center"
            ),
            dbc.CardBody(
                [
                    dbc.RadioItems(
                        id='time-range',
                        options=[
                            {'label': 'Last Hour', 'value': 1},
                            {'label': 'Last 24 Hours', 'value': 24},
                            {'label': 'Last 7 Days', 'value': 168},
                        ],
                        value=24,
                        inline=True,
                        className="d-flex justify-content-between mb-0"
                    )
                ]
            )
        ],
        className="shadow-sm mb-4 border-0"
    )

def create_sensor_graph(data_df=None, sensor_type="temperature"):
    """Create a graph for sensor data visualization"""
    # Set up titles and units based on sensor type
    title_text = f"{sensor_type.title()} Over Time"
    empty_title = f"No {sensor_type.title()} Data Available"
    
    units = {
        "temperature": "°C",
        "pressure": "kPa",
        "flow": "L/min"
    }.get(sensor_type, "")
    
    yaxis_title = f"{sensor_type.title()} ({units})" if units else sensor_type.title()
    
    # Set up colors based on sensor type
    colors = CHART_COLORS.get(sensor_type, ['#2563eb', '#93c5fd'])
    
    if data_df is None or data_df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=empty_title,
            xaxis_title="Time",
            yaxis_title=yaxis_title,
            template="plotly_white",
            plot_bgcolor=COLORS['card'],
            paper_bgcolor=COLORS['card'],
            font=dict(
                family="Segoe UI, Helvetica, Arial, sans-serif",
                color=COLORS['text'],
            ),
            title_font=dict(
                family="Segoe UI, Helvetica, Arial, sans-serif",
                color=COLORS['secondary'],
                size=16
            ),
            margin=dict(l=10, r=10, t=50, b=10),
            height=300
        )
    else:
        fig = px.line(
            data_df, 
            x='timestamp', 
            y='value',
            title=title_text,
            color_discrete_sequence=[colors[0]]
        )
        
        
        if len(data_df) > 1:
            min_val = data_df['value'].min() * 0.95
            fig.add_traces(
                go.Scatter(
                    x=data_df['timestamp'],
                    y=[min_val] * len(data_df),
                    fill='tonexty',
                    mode='none',
                    fillcolor=colors[1] + '40',  # Add transparency
                    hoverinfo='none',
                    showlegend=False
                )
            )
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title=yaxis_title,
            template="plotly_white",
            plot_bgcolor=COLORS['card'],
            paper_bgcolor=COLORS['card'],
            font=dict(
                family="Segoe UI, Helvetica, Arial, sans-serif",
                color=COLORS['text'],
            ),
            title_font=dict(
                family="Segoe UI, Helvetica, Arial, sans-serif",
                color=COLORS['secondary'],
                size=16
            ),
            margin=dict(l=10, r=10, t=50, b=10),
            height=300
        )
        
        # Improve line appearance
        fig.update_traces(
            line=dict(width=3),
            marker=dict(size=6)
        )
    
    icon_class = {
        "temperature": "fa-temperature-high",
        "pressure": "fa-tachometer-alt",
        "flow": "fa-water"
    }.get(sensor_type, "fa-chart-line")
    
    # Create the card
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className=f"fas {icon_class} me-2 text-primary"),
                    html.Span(f"{sensor_type.title()} Data", className="fw-bold")
                ],
                className="d-flex align-items-center"
            ),
            dbc.CardBody(
                [
                    dcc.Graph(
                        id=f'{sensor_type}-graph',
                        figure=fig,
                        config={
                            'displayModeBar': False,
                            'responsive': True
                        }
                    )
                ],
                className="p-2"
            )
        ],
        className="shadow-sm mb-4 border-0"
    )

def create_alert_table(alerts):
    """Create a table of recent alerts"""
    if not alerts:
        return dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.I(className="fas fa-bell me-2 text-primary"),
                        html.Span("Recent Alerts", className="fw-bold")
                    ],
                    className="d-flex align-items-center"
                ),
                dbc.CardBody(
                    [
                        html.Div(
                            [
                                html.I(className="fas fa-check-circle text-success fa-3x mb-3"),
                                html.P("No recent alerts", className="lead mb-0 text-center text-muted")
                            ],
                            className="text-center py-4"
                        )
                    ]
                )
            ],
            className="shadow-sm mb-4 border-0"
        )
    
    # Create table rows
    rows = []
    for alert in alerts:
        timestamp = datetime.fromisoformat(alert['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        
        severity_color = {
            "critical": "danger",
            "high": "warning",
            "medium": "primary",
            "low": "info"
        }.get(alert['severity'].lower(), "secondary")
        
        severity_icon = {
            "critical": "fa-exclamation-circle",
            "high": "fa-exclamation-triangle",
            "medium": "fa-info-circle",
            "low": "fa-info"
        }.get(alert['severity'].lower(), "fa-bell")
        
        rows.append(
            html.Tr(
                [
                    html.Td(timestamp, className="text-nowrap"),
                    html.Td(
                        html.Span(
                            alert['device_id'],
                            className="badge bg-light text-dark rounded-pill px-3 py-2"
                        )
                    ),
                    html.Td(alert['type']),
                    html.Td(
                        html.Span(
                            [
                                html.I(className=f"fas {severity_icon} me-1"),
                                alert['severity'].upper()
                            ],
                            className=f"badge bg-{severity_color} rounded-pill px-3 py-2"
                        )
                    ),
                    html.Td(alert['message'])
                ]
            )
        )
    
    table = dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Time", className="text-nowrap"),
                        html.Th("Device", className="text-nowrap"),
                        html.Th("Type", className="text-nowrap"),
                        html.Th("Severity", className="text-nowrap"),
                        html.Th("Message")
                    ],
                    className="table-light"
                )
            ),
            html.Tbody(rows)
        ],
        striped=True,
        hover=True,
        responsive=True,
        className="mb-0"
    )
    
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="fas fa-bell me-2 text-primary"),
                    html.Span("Recent Alerts", className="fw-bold"),
                    html.Span(
                        f"{len(alerts)} alerts",
                        className="badge bg-secondary rounded-pill ms-2"
                    )
                ],
                className="d-flex align-items-center"
            ),
            dbc.CardBody([table], className="p-0")
        ],
        className="shadow-sm mb-4 border-0"
    )

def create_device_control_card(device_id, device_type):
    """Create device control panel based on device type"""
    
    controls = []
    
    if device_type.lower() == "valve":
        controls = [
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Valve Position Control", className="fw-medium mb-3"),
                            html.Div(
                                [
                                    dbc.Button(
                                        [html.I(className="fas fa-unlock me-1"), "Open Valve"],
                                        id="open-valve-btn",
                                        color="success",
                                        className="me-2 shadow-sm"
                                    ),
                                    dbc.Button(
                                        [html.I(className="fas fa-lock me-1"), "Close Valve"],
                                        id="close-valve-btn",
                                        color="danger",
                                        className="shadow-sm"
                                    )
                                ],
                                className="d-flex mb-3"
                            ),
                            html.Div(
                                id="valve-status",
                                className="alert alert-info py-2 px-3"
                            )
                        ],
                        className="p-3 border rounded bg-light"
                    )
                ],
                className="mt-2"
            )
        ]
    elif device_type.lower() == "pump":
        controls = [
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Pump Speed Control", className="fw-medium mb-3"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Speed (%)", className="mb-2"),
                                            html.Div(
                                                dcc.Slider(
                                                    id="pump-speed-slider",
                                                    min=0,
                                                    max=100,
                                                    step=5,
                                                    value=50,
                                                    marks={0: '0', 25: '25', 50: '50', 75: '75', 100: '100'},
                                                    className="px-2"
                                                ),
                                                className="p-2 border rounded"
                                            )
                                        ],
                                        width=8
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Actions", className="mb-2"),
                                            html.Div(
                                                [
                                                    dbc.Button(
                                                        [html.I(className="fas fa-play me-1"), "Start"],
                                                        id="start-pump-btn",
                                                        color="success",
                                                        className="me-2 shadow-sm"
                                                    ),
                                                    dbc.Button(
                                                        [html.I(className="fas fa-stop me-1"), "Stop"],
                                                        id="stop-pump-btn",
                                                        color="danger",
                                                        className="shadow-sm"
                                                    )
                                                ],
                                                className="d-flex"
                                            )
                                        ],
                                        width=4
                                    )
                                ],
                                className="mb-3"
                            ),
                            html.Div(
                                id="pump-status",
                                className="alert alert-info py-2 px-3"
                            )
                        ],
                        className="p-3 border rounded bg-light"
                    )
                ],
                className="mt-2"
            )
        ]
    else:
        controls = [
            html.Div(
                html.P(
                    [
                        html.I(className="fas fa-info-circle me-2 text-info"),
                        f"No specific controls available for device type: {device_type}"
                    ],
                    className="mb-0 fst-italic"
                ),
                className="p-3 border rounded bg-light mt-2"
            )
        ]
    
    device_icon = {
        "valve": "fa-valve",
        "pump": "fa-pump-soap"
    }.get(device_type.lower(), "fa-microchip")
    
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className=f"fas {device_icon} me-2 text-primary"),
                    html.Span(f"Device Controls", className="fw-bold"),
                    html.Span(
                        device_id,
                        className="badge bg-light text-dark rounded-pill ms-2"
                    )
                ],
                className="d-flex align-items-center"
            ),
            dbc.CardBody(controls)
        ],
        className="shadow-sm mb-4 border-0"
    )