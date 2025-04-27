import json
import logging
import os
import signal
import sys
from datetime import datetime
import cherrypy
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from flask import Flask, redirect, request, session, url_for, Response, jsonify
import requests

# Get absolute path to config.json
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.json')

from config import load_config
CONFIG = load_config(config_path)
from data_handler import DataHandler
from mqtt_client import MQTTClient
import dashboard_components as components

# Setup logging
def setup_logging(config):
    log_level = getattr(logging, config["logging"]["level"])
    log_file = config["logging"]["file"]
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    cherrypy.log.screen = False
    
    return logging.getLogger("main")

# Create a directory for assets if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), 'assets'), exist_ok=True)

# Global variables for real-time data
latest_sensor_data = {}
latest_alerts = []

class DashboardService:
    def __init__(self):
        self.config = CONFIG
        self.logger = setup_logging(self.config)
        self.port = self.config["service"]["port"]
        self.refresh_interval = self.config.get("refresh_interval", 30000)  # Default to 30 seconds if not present
        self.account_manager_url = self.config.get("account_manager", {}).get("url", "http://localhost:8010")
        
        self.data_handler = DataHandler()
        self.mqtt_client = MQTTClient(
            on_sensor_data=self.handle_sensor_data,
            on_alert=self.handle_alert
        )
        
        # Initialize data
        self.devices = self.data_handler.get_all_devices()
        self.system_status = self.data_handler.get_system_status()
        self.alerts = self.data_handler.get_alerts()
        
        # Keep track of connected clients for real-time updates
        self.clients = set()
        
        # Setup Flask server
        self.server = Flask(__name__)
        self.server.secret_key = self.config.get("security", {}).get("secret_key", "supersecretkey")
        
        # Setup authentication routes
        self.setup_auth_routes()
        
        # Setup Dash app
        self.app = dash.Dash(
            __name__,
            server=self.server,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
            ],
            suppress_callback_exceptions=True,
            url_base_pathname='/dashboard/'
        )
        
        self.setup_layout()
        self.setup_callbacks()
        
        self.logger.info("Dashboard Service initialized")
    
    def setup_auth_routes(self):
        """Setup Flask routes for authentication"""
        @self.server.route('/')
        def index():
            return redirect('/login')
        
        @self.server.route('/login', methods=['GET'])
        def login_page():
            if 'token' in session:
                return redirect('/dashboard/')
            
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Smart Bolt Dashboard - Login</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                <style>
                    :root {
                        --primary-color: #2563eb;
                        --secondary-color: #0f172a;
                        --success-color: #16a34a;
                        --accent-color: #f59e0b;
                    }
                    
                    body {
                        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                        height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    }
                    
                    .login-container {
                        max-width: 450px;
                        width: 90%;
                        padding: 2.5rem;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
                    }
                    
                    .logo {
                        text-align: center;
                        margin-bottom: 2rem;
                    }
                    
                    .logo i {
                        font-size: 3rem;
                        color: var(--primary-color);
                        margin-bottom: 1rem;
                    }
                    
                    .logo h2 {
                        color: var(--secondary-color);
                        font-weight: 600;
                    }
                    
                    .logo p {
                        color: #64748b;
                        margin-top: 0.5rem;
                    }
                    
                    .card-header-tabs {
                        border-bottom: 2px solid #e2e8f0;
                        margin-bottom: 1.5rem;
                    }
                    
                    .form-label {
                        font-weight: 500;
                        color: #334155;
                    }
                    
                    .form-control {
                        padding: 0.75rem 1rem;
                        border-radius: 8px;
                        border: 1px solid #e2e8f0;
                        background-color: #f8fafc;
                        transition: all 0.2s ease;
                    }
                    
                    .form-control:focus {
                        border-color: var(--primary-color);
                        background-color: #fff;
                        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
                    }
                    
                    .input-group-text {
                        background-color: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                        color: #64748b;
                    }
                    
                    .btn-primary {
                        background-color: var(--primary-color);
                        border: none;
                        padding: 0.75rem;
                        font-weight: 600;
                        border-radius: 8px;
                        transition: all 0.2s;
                    }
                    
                    .btn-primary:hover {
                        background-color: #1d4ed8;
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
                    }
                    
                    .alert {
                        padding: 1rem;
                        border-radius: 8px;
                        margin-bottom: 1.5rem;
                    }
                    
                    .system-status {
                        text-align: center;
                        margin-top: 1.5rem;
                        font-size: 0.85rem;
                        color: #64748b;
                    }
                    
                    .system-status i {
                        color: var(--success-color);
                        margin-right: 0.5rem;
                    }

                    .register-link {
                        text-align: center;
                        margin-top: 1rem;
                        font-size: 0.9rem;
                    }
                    
                    .register-link a {
                        color: var(--primary-color);
                        text-decoration: none;
                    }
                    
                    .register-link a:hover {
                        text-decoration: underline;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="login-container">
                        <div class="logo">
                            <i class="fas fa-bolt-lightning"></i>
                            <h2>Smart Bolt Dashboard</h2>
                            <p>Enter your credentials to access the system</p>
                        </div>
                        
                        <div id="error-message" class="alert alert-danger d-none"></div>
                        
                        <form id="login-form" method="post" action="/login">
                            <div class="mb-4">
                                <label for="username" class="form-label">Username</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-user"></i></span>
                                    <input type="text" class="form-control" id="username" name="username" placeholder="Enter your username" required>
                                </div>
                            </div>
                            <div class="mb-4">
                                <label for="password" class="form-label">Password</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-lock"></i></span>
                                    <input type="password" class="form-control" id="password" name="password" placeholder="Enter your password" required>
                                </div>
                            </div>
                            <div class="d-grid mt-4">
                                <button type="submit" id="login-button" class="btn btn-primary">
                                    <span class="spinner-border spinner-border-sm d-none me-2" id="login-spinner" role="status" aria-hidden="true"></span>
                                    <span id="login-btn-text">Log In</span>
                                </button>
                            </div>
                        </form>
                        
                        <div class="register-link">
                            <p>Don't have an account? <a href="/register">Register</a></p>
                        </div>
                        
                        <div class="system-status mt-4">
                            <i class="fas fa-circle fa-sm"></i> System operational | Smart Bolt Monitoring
                        </div>
                    </div>
                </div>
                
                <script>
                    document.getElementById('login-form').addEventListener('submit', function(e) {
                        e.preventDefault();
                        
                        const username = document.getElementById('username').value;
                        const password = document.getElementById('password').value;
                        const loginButton = document.getElementById('login-button');
                        const loginSpinner = document.getElementById('login-spinner');
                        const loginBtnText = document.getElementById('login-btn-text');
                        const errorMessage = document.getElementById('error-message');
                        
                        // Clear previous error
                        errorMessage.classList.add('d-none');
                        
                        // Show loading state
                        loginButton.disabled = true;
                        loginSpinner.classList.remove('d-none');
                        loginBtnText.textContent = 'Authenticating...';
                        
                        fetch('/login', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                username: username,
                                password: password
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                loginBtnText.textContent = 'Success! Redirecting...';
                                window.location.href = '/dashboard/';
                            } else {
                                // Reset button
                                loginButton.disabled = false;
                                loginSpinner.classList.add('d-none');
                                loginBtnText.textContent = 'Log In';
                                
                                // Show error
                                errorMessage.textContent = data.message || 'Login failed';
                                errorMessage.classList.remove('d-none');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            
                            // Reset button
                            loginButton.disabled = false;
                            loginSpinner.classList.add('d-none');
                            loginBtnText.textContent = 'Log In';
                            
                            // Show error
                            errorMessage.textContent = 'An error occurred. Please try again.';
                            errorMessage.classList.remove('d-none');
                        });
                    });
                </script>
            </body>
            </html>
            '''
            
        @self.server.route('/register', methods=['GET'])
        def register_page():
            if 'token' in session:
                return redirect('/dashboard/')
            
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Smart Bolt Dashboard - Register</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                <style>
                    :root {
                        --primary-color: #2563eb;
                        --secondary-color: #0f172a;
                        --success-color: #16a34a;
                        --accent-color: #f59e0b;
                    }
                    
                    body {
                        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        padding: 2rem 0;
                    }
                    
                    .register-container {
                        max-width: 500px;
                        width: 90%;
                        padding: 2.5rem;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
                    }
                    
                    .logo {
                        text-align: center;
                        margin-bottom: 2rem;
                    }
                    
                    .logo i {
                        font-size: 3rem;
                        color: var(--primary-color);
                        margin-bottom: 1rem;
                    }
                    
                    .logo h2 {
                        color: var(--secondary-color);
                        font-weight: 600;
                    }
                    
                    .logo p {
                        color: #64748b;
                        margin-top: 0.5rem;
                    }
                    
                    .form-label {
                        font-weight: 500;
                        color: #334155;
                    }
                    
                    .form-control {
                        padding: 0.75rem 1rem;
                        border-radius: 8px;
                        border: 1px solid #e2e8f0;
                        background-color: #f8fafc;
                        transition: all 0.2s ease;
                    }
                    
                    .form-control:focus {
                        border-color: var (--primary-color);
                        background-color: #fff;
                        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
                    }
                    
                    .input-group-text {
                        background-color: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                        color: #64748b;
                    }
                    
                    .btn-primary {
                        background-color: var(--primary-color);
                        border: none;
                        padding: 0.75rem;
                        font-weight: 600;
                        border-radius: 8px;
                        transition: all 0.2s;
                    }
                    
                    .btn-primary:hover {
                        background-color: #1d4ed8;
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
                    }
                    
                    .alert {
                        padding: 1rem;
                        border-radius: 8px;
                        margin-bottom: 1.5rem;
                    }
                    
                    .login-link {
                        text-align: center;
                        margin-top: 1rem;
                        font-size: 0.9rem;
                    }
                    
                    .login-link a {
                        color: var(--primary-color);
                        text-decoration: none;
                    }
                    
                    .login-link a:hover {
                        text-decoration: underline;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="register-container">
                        <div class="logo">
                            <i class="fas fa-bolt-lightning"></i>
                            <h2>Smart Bolt Dashboard</h2>
                            <p>Create a new account</p>
                        </div>
                        
                        <div id="message" class="alert alert-danger d-none"></div>
                        
                        <form id="register-form" method="post" action="/register">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-user"></i></span>
                                    <input type="text" class="form-control" id="username" name="username" placeholder="Choose a username" required>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="email" class="form-label">Email Address</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-envelope"></i></span>
                                    <input type="email" class="form-control" id="email" name="email" placeholder="Enter your email" required>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-lock"></i></span>
                                    <input type="password" class="form-control" id="password" name="password" placeholder="Choose a password" required>
                                </div>
                            </div>
                            <div class="mb-4">
                                <label for="role" class="form-label">Role</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-user-tag"></i></span>
                                    <select class="form-control" id="role" name="role">
                                        <option value="user">User</option>
                                        <option value="admin">Admin</option>
                                    </select>
                                </div>
                            </div>
                            <div class="d-grid mt-4">
                                <button type="submit" id="register-button" class="btn btn-primary">
                                    <span class="spinner-border spinner-border-sm d-none me-2" id="register-spinner" role="status" aria-hidden="true"></span>
                                    <span id="register-btn-text">Register</span>
                                </button>
                            </div>
                        </form>
                        
                        <div class="login-link">
                            <p>Already have an account? <a href="/login">Log in</a></p>
                        </div>
                    </div>
                </div>
                
                <script>
                    document.getElementById('register-form').addEventListener('submit', function(e) {
                        e.preventDefault();
                        
                        const username = document.getElementById('username').value;
                        const email = document.getElementById('email').value;
                        const password = document.getElementById('password').value;
                        const role = document.getElementById('role').value;
                        const registerButton = document.getElementById('register-button');
                        const registerSpinner = document.getElementById('register-spinner');
                        const registerBtnText = document.getElementById('register-btn-text');
                        const messageEl = document.getElementById('message');
                        
                        // Clear previous message
                        messageEl.classList.add('d-none');
                        
                        // Show loading state
                        registerButton.disabled = true;
                        registerSpinner.classList.remove('d-none');
                        registerBtnText.textContent = 'Registering...';
                        
                        fetch('/register', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                username: username,
                                email: email,
                                password: password,
                                role: role
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                // Show success message
                                messageEl.textContent = 'Registration successful! Redirecting to login...';
                                messageEl.classList.remove('d-none', 'alert-danger');
                                messageEl.classList.add('alert-success');
                                registerBtnText.textContent = 'Success!';
                                
                                // Redirect to login page after a short delay
                                setTimeout(() => {
                                    window.location.href = '/login';
                                }, 2000);
                            } else {
                                // Reset button
                                registerButton.disabled = false;
                                registerSpinner.classList.add('d-none');
                                registerBtnText.textContent = 'Register';
                                
                                // Show error
                                messageEl.textContent = data.message || 'Registration failed';
                                messageEl.classList.remove('d-none');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            
                            // Reset button
                            registerButton.disabled = false;
                            registerSpinner.classList.add('d-none');
                            registerBtnText.textContent = 'Register';
                            
                            // Show error
                            messageEl.textContent = 'An error occurred. Please try again.';
                            messageEl.classList.remove('d-none');
                        });
                    });
                </script>
            </body>
            </html>
            '''
        
        @self.server.route('/login', methods=['POST'])
        def login():
            data = request.get_json()
            
            if not data or 'username' not in data or 'password' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Username and password are required'
                }), 400
            
            try:
                # Call account manager API to authenticate
                response = requests.post(
                    f"{self.account_manager_url}/login",
                    json={
                        'username': data['username'],
                        'password': data['password']
                    }
                )
                
                response_data = response.json()
                
                if response.status_code == 200 and response_data.get('status') == 'success':
                    # Store token in session
                    session['token'] = response_data['data']['token']
                    session['user'] = response_data['data']['user']
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Login successful'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': response_data.get('message', 'Login failed')
                    }), 401
            except Exception as e:
                self.logger.error(f"Login error: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'An error occurred during login'
                }), 500
        
        @self.server.route('/register', methods=['POST'])
        def register():
            data = request.get_json()
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid request data'
                }), 400
            
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }), 400
            
            try:
                # First try to log in as admin to get authentication token
                admin_login_response = requests.post(
                    f"{self.account_manager_url}/login",
                    json={
                        'username': 'admin',  # Default admin username
                        'password': 'admin123'  # Default admin password
                    }
                )
                
                if admin_login_response.status_code != 200:
                    return jsonify({
                        'status': 'error',
                        'message': 'Authentication required for registration. Please contact an administrator.'
                    }), 401
                
                admin_data = admin_login_response.json()
                if admin_data.get('status') != 'success' or 'token' not in admin_data.get('data', {}):
                    return jsonify({
                        'status': 'error',
                        'message': 'Authentication failed. Please contact an administrator.'
                    }), 401
                
                # Get the admin token for authorization
                admin_token = admin_data['data']['token']
                
                # Now call the register endpoint with admin authentication
                headers = {
                    'Authorization': f"Bearer {admin_token}"
                }
                
                register_response = requests.post(
                    f"{self.account_manager_url}/register",
                    headers=headers,
                    json={
                        'username': data['username'],
                        'email': data['email'],
                        'password': data['password'],
                        'role': data.get('role', 'user')  # Default to user role
                    }
                )
                
                register_data = register_response.json()
                
                if register_response.status_code == 200 and register_data.get('status') == 'success':
                    return jsonify({
                        'status': 'success',
                        'message': 'Registration successful'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': register_data.get('message', 'Registration failed')
                    }), register_response.status_code
            except Exception as e:
                self.logger.error(f"Registration error: {e}")
                return jsonify({
                    'status': 'error',
                    'message': f'An error occurred during registration: {str(e)}'
                }), 500
        
        @self.server.route('/logout')
        def logout():
            session.clear()
            return redirect('/login')
        
        # Add authentication middleware for dashboard routes
        @self.server.before_request
        def auth_middleware():
            # Skip auth for login page, register page and static files
            if (request.path == '/' or 
                request.path.startswith('/login') or 
                request.path.startswith('/register') or 
                request.path.startswith('/_dash-') or 
                request.path.startswith('/assets/')):
                return None
            
            # Check if user is authenticated
            if 'token' not in session:
                if request.path.startswith('/dashboard/'):
                    return redirect('/login')
                elif request.accept_mimetypes.accept_json:
                    return jsonify({
                        'status': 'error',
                        'message': 'Authentication required'
                    }), 401
                else:
                    return redirect('/login')
            
            # Verify token is valid
            try:
                response = requests.get(
                    f"{self.account_manager_url}/verify_token",
                    headers={'Authorization': f"Bearer {session['token']}"}
                )
                
                if response.status_code != 200:
                    session.clear()
                    return redirect('/login')
            except Exception as e:
                self.logger.error(f"Token verification error: {e}")
                session.clear()
                return redirect('/login')
    
    def setup_layout(self):
        """Set up the initial dashboard layout"""
        # Add custom CSS
        app_css = {
            'background-color': '#f1f5f9',
            'min-height': '100vh',
            'font-family': '"Segoe UI", Helvetica, Arial, sans-serif'
        }
        
        self.app.layout = html.Div([
            dcc.Store(id='devices-store', data=self.devices),
            dcc.Store(id='alerts-store', data=self.alerts),
            dcc.Store(id='selected-device-store', data=None),
            dcc.Interval(id='interval-component', interval=self.refresh_interval, n_intervals=0),
            dcc.Interval(id='clock-interval', interval=1000, n_intervals=0),
            
            # Loading component for page transitions
            dcc.Loading(
                id="loading-page",
                type="circle",
                color="#2563eb",
                children=[
                    # Header
                    components.create_header(),
                    
                    # Main content
                    dbc.Container([
                        # Quick stats row
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.I(className="fas fa-chart-line fa-2x text-primary"),
                                    html.Div([
                                        html.H6("Monitored Devices", className="mb-0 text-muted"),
                                        html.H4(f"{len(self.devices)}", className="mb-0 fw-bold")
                                    ], className="ms-3")
                                ], className="d-flex align-items-center p-3 bg-white rounded shadow-sm")
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.I(className="fas fa-bell fa-2x text-warning"),
                                    html.Div([
                                        html.H6("Active Alerts", className="mb-0 text-muted"),
                                        html.H4(f"{len(self.alerts)}", className="mb-0 fw-bold")
                                    ], className="ms-3")
                                ], className="d-flex align-items-center p-3 bg-white rounded shadow-sm")
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.I(className="fas fa-tachometer-alt fa-2x text-success"),
                                    html.Div([
                                        html.H6("System Health", className="mb-0 text-muted"),
                                        html.H4(f"{int(sum(self.system_status.values()) / len(self.system_status) * 100)}%", className="mb-0 fw-bold")
                                    ], className="ms-3")
                                ], className="d-flex align-items-center p-3 bg-white rounded shadow-sm")
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.I(className="fas fa-clock fa-2x text-info"),
                                    html.Div([
                                        html.H6("Last Update", className="mb-0 text-muted"),
                                        html.H4(datetime.now().strftime("%H:%M:%S"), className="mb-0 fw-bold")
                                    ], className="ms-3")
                                ], className="d-flex align-items-center p-3 bg-white rounded shadow-sm")
                            ], width=3)
                        ], className="mb-4"),
                        
                        # Main dashboard content
                        dbc.Row([
                            # Left column - Controls
                            dbc.Col([
                                components.create_system_status_card(self.system_status),
                                components.create_device_dropdown(self.devices),
                                components.create_time_range_selector(),
                                html.Div(id='device-control-container')
                            ], width=3),
                            
                            # Right column - Visualizations
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="fas fa-chart-area me-2 text-primary"),
                                        html.Span("Sensor Data Dashboard", className="fw-bold")
                                    ], className="d-flex align-items-center"),
                                    dbc.CardBody([
                                        dbc.Tabs([
                                            dbc.Tab(
                                                [
                                                    dbc.Row([
                                                        dbc.Col([
                                                            dcc.Loading(
                                                                id="loading-temp-graph",
                                                                type="default",
                                                                children=html.Div(id='temperature-graph-container')
                                                            )
                                                        ], width=12)
                                                    ]),
                                                    dbc.Row([
                                                        dbc.Col([
                                                            dcc.Loading(
                                                                id="loading-pressure-graph",
                                                                type="default",
                                                                children=html.Div(id='pressure-graph-container')
                                                            )
                                                        ], width=6),
                                                        dbc.Col([
                                                            dcc.Loading(
                                                                id="loading-flow-graph",
                                                                type="default",
                                                                children=html.Div(id='flow-graph-container')
                                                            )
                                                        ], width=6)
                                                    ])
                                                ],
                                                label="Sensor Data",
                                                tab_id="tab-sensor-data",
                                                label_class_name="fw-bold"
                                            ),
                                            dbc.Tab(
                                                [
                                                    dcc.Loading(
                                                        id="loading-alerts",
                                                        type="default",
                                                        children=html.Div(id='alerts-container')
                                                    )
                                                ],
                                                label="Alerts",
                                                tab_id="tab-alerts",
                                                label_class_name="fw-bold"
                                            )
                                        ], id="dashboard-tabs", active_tab="tab-sensor-data")
                                    ])
                                ], className="shadow-sm border-0")
                            ], width=9)
                        ])
                    ], fluid=True)
                ]
            )
        ], style=app_css)
    
    def setup_callbacks(self):
        """Set up Dash callbacks for interactivity"""
        
        # Update clock
        @self.app.callback(
            Output('live-clock', 'children'),
            Input('clock-interval', 'n_intervals')
        )
        def update_clock(n):
            return html.Div([
                html.Span(datetime.now().strftime("%H:%M:%S")),
                html.Div(datetime.now().strftime("%Y-%m-%d"), style={"fontSize": "0.8rem"})
            ])
        
        # Update device control panel when device is selected
        @self.app.callback(
            Output('device-control-container', 'children'),
            Output('selected-device-store', 'data'),
            Input('device-dropdown', 'value'),
            State('devices-store', 'data')
        )
        def update_device_controls(device_id, devices):
            if not device_id or not devices:
                return None, None
                
            device = next((d for d in devices if d['id'] == device_id), None)
            if not device:
                return None, None
                
            return components.create_device_control_card(device_id, device.get('type', 'unknown')), device
        
        # Update graphs based on selected device and time range
        @self.app.callback(
            Output('temperature-graph-container', 'children'),
            Output('pressure-graph-container', 'children'),
            Output('flow-graph-container', 'children'),
            Input('device-dropdown', 'value'),
            Input('time-range', 'value'),
            Input('interval-component', 'n_intervals')
        )
        def update_graphs(device_id, time_range, n_intervals):
            if not device_id:
                empty_graph = lambda sensor: components.create_sensor_graph(None, sensor)
                return empty_graph("temperature"), empty_graph("pressure"), empty_graph("flow")
            
            temperature_data = self.data_handler.get_sensor_data(device_id, "temperature", time_range)
            pressure_data = self.data_handler.get_sensor_data(device_id, "pressure", time_range)
            flow_data = self.data_handler.get_sensor_data(device_id, "flow", time_range)
            
            temperature_graph = components.create_sensor_graph(temperature_data, "temperature")
            pressure_graph = components.create_sensor_graph(pressure_data, "pressure")
            flow_graph = components.create_sensor_graph(flow_data, "flow")
            
            return temperature_graph, pressure_graph, flow_graph
        
        # Update alerts container
        @self.app.callback(
            Output('alerts-container', 'children'),
            Output('alerts-store', 'data'),
            Input('interval-component', 'n_intervals'),
            Input('time-range', 'value')
        )
        def update_alerts(n_intervals, time_range):
            alerts = self.data_handler.get_alerts(time_range)
            alert_table = components.create_alert_table(alerts)
            return alert_table, alerts
        
        # Valve control callbacks
        @self.app.callback(
            Output('valve-status', 'children'),
            Input('open-valve-btn', 'n_clicks'),
            Input('close-valve-btn', 'n_clicks'),
            State('device-dropdown', 'value'),
            prevent_initial_call=True
        )
        def control_valve(open_clicks, close_clicks, device_id):
            ctx = dash.callback_context
            if not ctx.triggered:
                return "Valve status: Unknown"
                
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == "open-valve-btn":
                success, response = self.data_handler.send_command(
                    device_id, "set_valve", {"position": "open"}
                )
                return f"Valve command sent: OPEN - {'Success' if success else 'Failed'}"
            else:
                success, response = self.data_handler.send_command(
                    device_id, "set_valve", {"position": "closed"}
                )
                return f"Valve command sent: CLOSED - {'Success' if success else 'Failed'}"
        
        # Pump control callbacks
        @self.app.callback(
            Output('pump-status', 'children'),
            Input('start-pump-btn', 'n_clicks'),
            Input('stop-pump-btn', 'n_clicks'),
            Input('pump-speed-slider', 'value'),
            State('device-dropdown', 'value'),
            prevent_initial_call=True
        )
        def control_pump(start_clicks, stop_clicks, speed, device_id):
            ctx = dash.callback_context
            if not ctx.triggered:
                return "Pump status: Unknown"
                
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == "start-pump-btn":
                success, response = self.data_handler.send_command(
                    device_id, "set_pump", {"state": "on", "speed": speed}
                )
                return f"Pump command sent: START at {speed}% - {'Success' if success else 'Failed'}"
            elif button_id == "stop-pump-btn":
                success, response = self.data_handler.send_command(
                    device_id, "set_pump", {"state": "off"}
                )
                return f"Pump command sent: STOP - {'Success' if success else 'Failed'}"
            else:  # slider change
                success, response = self.data_handler.send_command(
                    device_id, "set_pump", {"speed": speed}
                )
                return f"Pump speed set to {speed}% - {'Success' if success else 'Failed'}"
    
    def handle_sensor_data(self, data):
        """Handle incoming sensor data from MQTT"""
        global latest_sensor_data
        
        # Store latest sensor data
        device_id = data.get("device_id")
        if device_id:
            latest_sensor_data[device_id] = data
    
    def handle_alert(self, alert):
        """Handle incoming alert from MQTT"""
        global latest_alerts
        
        # Add alert to the list
        latest_alerts.append(alert)
        
        # Keep only the latest 100 alerts
        if len(latest_alerts) > 100:
            latest_alerts = latest_alerts[-100:]
    
    def start(self):
        """Start the dashboard service"""
        # Connect to MQTT broker
        self.mqtt_client.connect()
        
        # Start CherryPy server
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': self.port,
            'engine.autoreload.on': False
        })
        cherrypy.tree.graft(self.server, '/')
        cherrypy.engine.signals.subscribe()
        cherrypy.engine.start()
        
        self.logger.info(f"Dashboard service started on port {self.port}")
        
        # Keep the server running
        cherrypy.engine.block()
    
    def stop(self):
        """Stop the dashboard service"""
        # Disconnect from MQTT broker
        self.mqtt_client.disconnect()
        
        # Stop CherryPy server
        cherrypy.engine.exit()
        
        self.logger.info("Dashboard service stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C signal"""
    print("Shutting down...")
    dashboard_service.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start dashboard service
    dashboard_service = DashboardService()
    dashboard_service.start()