import dash
import json
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
import logging

logger = logging.getLogger(__name__)

def create_login_modal():
    """Create a login modal dialog"""
    return html.Div(
        [
            dbc.Modal(
                [
                    dbc.ModalHeader("Login"),
                    dbc.ModalBody(
                        [
                            dbc.Alert(
                                "Invalid username or password",
                                id="login-alert",
                                color="danger",
                                is_open=False,
                            ),
                            dbc.Form(
                                [
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Username", html_for="login-username"),
                                            dbc.Input(
                                                type="text", 
                                                id="login-username", 
                                                placeholder="Enter username"
                                            ),
                                        ]
                                    ),
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Password", html_for="login-password"),
                                            dbc.Input(
                                                type="password", 
                                                id="login-password", 
                                                placeholder="Enter password"
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Close", id="login-close", className="ml-auto"),
                            dbc.Button(
                                "Login", 
                                id="login-button", 
                                color="primary", 
                                className="ml-2"
                            ),
                        ]
                    ),
                ],
                id="login-modal",
                is_open=False,
            ),
        ]
    )

def create_register_modal():
    """Create a registration modal dialog"""
    return html.Div(
        [
            dbc.Modal(
                [
                    dbc.ModalHeader("Register New User"),
                    dbc.ModalBody(
                        [
                            dbc.Alert(
                                id="register-alert",
                                color="danger",
                                is_open=False,
                            ),
                            dbc.Form(
                                [
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Username", html_for="register-username"),
                                            dbc.Input(
                                                type="text", 
                                                id="register-username", 
                                                placeholder="Enter username"
                                            ),
                                        ]
                                    ),
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Email", html_for="register-email"),
                                            dbc.Input(
                                                type="email", 
                                                id="register-email", 
                                                placeholder="Enter email"
                                            ),
                                        ]
                                    ),
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Password", html_for="register-password"),
                                            dbc.Input(
                                                type="password", 
                                                id="register-password", 
                                                placeholder="Enter password"
                                            ),
                                        ]
                                    ),
                                    dbc.FormGroup(
                                        [
                                            dbc.Label("Role", html_for="register-role"),
                                            dbc.Select(
                                                id="register-role",
                                                options=[
                                                    {"label": "User", "value": "user"},
                                                    {"label": "Admin", "value": "admin"},
                                                ],
                                                value="user",
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Close", id="register-close", className="ml-auto"),
                            dbc.Button(
                                "Register", 
                                id="register-button", 
                                color="primary", 
                                className="ml-2"
                            ),
                        ]
                    ),
                ],
                id="register-modal",
                is_open=False,
            ),
        ]
    )

def create_auth_buttons():
    """Create buttons for the auth menu"""
    return html.Div(
        [
            dbc.Button("Login", id="open-login", color="primary", className="mr-2"),
            dbc.Button("Register", id="open-register", color="secondary"),
            dbc.Button(
                "Logout", 
                id="logout-button", 
                color="danger", 
                className="ml-2",
                style={"display": "none"}
            ),
        ],
        className="d-flex justify-content-end",
    )

def create_user_info():
    """Create user info display"""
    return html.Div(
        [
            html.Span("Not logged in", id="user-info", className="mr-2"),
        ],
        className="d-flex align-items-center mr-3",
    )

def create_auth_area():
    """Create the complete auth area with user info and buttons"""
    return html.Div(
        [
            create_user_info(),
            create_auth_buttons(),
            create_login_modal(),
            create_register_modal(),
            # Hidden div to store auth state
            html.Div(id="auth-state", style={"display": "none"}),
        ],
        className="d-flex justify-content-between align-items-center",
    )

def setup_auth_callbacks(app, data_handler):
    """Set up the callbacks for authentication components"""
    
    @app.callback(
        Output("login-modal", "is_open"),
        [
            Input("open-login", "n_clicks"),
            Input("login-close", "n_clicks"),
            Input("login-button", "n_clicks"),
        ],
        [State("login-modal", "is_open")],
    )
    def toggle_login_modal(n_open, n_close, n_login, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return is_open
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "open-login":
            return True
        if trigger_id in ["login-close", "login-button"]:
            return False
        return is_open

    @app.callback(
        Output("register-modal", "is_open"),
        [
            Input("open-register", "n_clicks"),
            Input("register-close", "n_clicks"),
            Input("register-button", "n_clicks"),
        ],
        [State("register-modal", "is_open")],
    )
    def toggle_register_modal(n_open, n_close, n_register, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return is_open
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "open-register":
            return True
        if trigger_id in ["register-close", "register-button"]:
            return False
        return is_open

    @app.callback(
        [
            Output("auth-state", "children"),
            Output("login-alert", "is_open"),
            Output("user-info", "children"),
            Output("open-login", "style"),
            Output("open-register", "style"),
            Output("logout-button", "style"),
        ],
        [Input("login-button", "n_clicks"), Input("logout-button", "n_clicks")],
        [
            State("login-username", "value"),
            State("login-password", "value"),
            State("auth-state", "children"),
        ],
    )
    def handle_login_logout(login_clicks, logout_clicks, username, password, auth_state):
        ctx = dash.callback_context
        if not ctx.triggered:
            # Default state - check if we're already logged in
            if auth_state:
                try:
                    auth_data = json.loads(auth_state)
                    return (
                        auth_state,
                        False,
                        f"Logged in as {auth_data['username']} ({auth_data['role']})",
                        {"display": "none"},
                        {"display": "none"},
                        {"display": "inline-block"},
                    )
                except:
                    pass
            
            return (
                "",
                False,
                "Not logged in",
                {"display": "inline-block"},
                {"display": "inline-block"},
                {"display": "none"},
            )
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if trigger_id == "login-button" and username and password:
            success, user_data = data_handler.login(username, password)
            if success and user_data:
                auth_data = {
                    "username": user_data.get("username"),
                    "role": user_data.get("role"),
                    "user_id": user_data.get("user_id"),
                    "logged_in": True,
                }
                return (
                    json.dumps(auth_data),
                    False,
                    f"Logged in as {auth_data['username']} ({auth_data['role']})",
                    {"display": "none"},
                    {"display": "none"},
                    {"display": "inline-block"},
                )
            else:
                return (
                    "",
                    True,
                    "Not logged in",
                    {"display": "inline-block"},
                    {"display": "inline-block"},
                    {"display": "none"},
                )
        
        elif trigger_id == "logout-button":
            data_handler.auth_token = None  # Clear the auth token
            return (
                "",
                False,
                "Not logged in",
                {"display": "inline-block"},
                {"display": "inline-block"},
                {"display": "none"},
            )
        
        # Default case - no change
        return (
            auth_state or "",
            False,
            "Not logged in" if not auth_state else f"Logged in",
            {"display": "inline-block"} if not auth_state else {"display": "none"},
            {"display": "inline-block"} if not auth_state else {"display": "none"},
            {"display": "none"} if not auth_state else {"display": "inline-block"},
        )

    @app.callback(
        [
            Output("register-alert", "children"),
            Output("register-alert", "is_open"),
            Output("register-alert", "color"),
        ],
        [Input("register-button", "n_clicks")],
        [
            State("register-username", "value"),
            State("register-email", "value"),
            State("register-password", "value"),
            State("register-role", "value"),
            State("auth-state", "children"),
        ],
    )
    def handle_registration(register_clicks, username, email, password, role, auth_state):
        if not register_clicks:
            return "", False, "danger"
        
        ctx = dash.callback_context
        if not ctx.triggered:
            return "", False, "danger"
        
        # Check if user is logged in and has permission to register
        auth_data = {}
        try:
            if auth_state:
                auth_data = json.loads(auth_state)
        except:
            return "You must be logged in as admin to register users", True, "danger"
        
        if not auth_data.get("logged_in") or auth_data.get("role") != "admin":
            return "Only admin users can register new accounts", True, "danger"
        
        if not username or not email or not password:
            return "All fields are required", True, "danger"
        
        # Try to register the user
        success, result = data_handler.register_user(username, email, password, role)
        if success:
            return "User registered successfully", True, "success"
        else:
            return f"Registration failed: {result}", True, "danger"