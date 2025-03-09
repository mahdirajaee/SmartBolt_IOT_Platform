/**
 * Authentication Module for Smart IoT Bolt Dashboard with Firebase
 */

// Firebase configuration with the updated API key
const firebaseConfig = {
    apiKey: "AIzaSyDurWCMYf7LdUYpZBBvSXexg9JYiCU39RA",
    authDomain: "smart-bolt-iot-platform.firebaseapp.com",
    projectId: "smart-bolt-iot-platform",
    storageBucket: "smart-bolt-iot-platform.appspot.com",
    messagingSenderId: "752431114855",
    appId: "1:752431114855:web:7a6fd27c54ddbde93c6a3e"
};
  
// User info storage key
const USER_INFO_KEY = 'user_info';

// Initialize Firebase
let firebaseInitialized = false;
let auth;

function initFirebase() {
  if (!firebaseInitialized) {
    try {
      console.log("Initializing Firebase...");
      firebase.initializeApp(firebaseConfig);
      auth = firebase.auth();
      firebaseInitialized = true;
      console.log("Firebase initialized successfully");
    } catch (error) {
      console.error("Firebase initialization error:", error);
      throw error;
    }
  }
}

/**
 * Initialize the authentication module
 */
function initAuth() {
  // Initialize Firebase
  initFirebase();
  
  console.log("Setting up auth state listener...");
  
  // Set up auth state listener
  auth.onAuthStateChanged((user) => {
    console.log("Auth state changed:", user ? `User ${user.email} authenticated` : "No authenticated user");
    
    if (user) {
      // User is signed in
      saveUserInfo(user);
      console.log("Current location:", window.location.pathname);
      
      // If on login page, redirect to dashboard
      if (window.location.pathname === '/' || 
          window.location.pathname.includes('index.html') || 
          window.location.pathname.endsWith('/')) {
        console.log("Redirecting to dashboard...");
        window.location.href = 'dashboard.html';
      }
    } else {
      // User is signed out
      console.log("Not authenticated. Current location:", window.location.pathname);
      
      // If not on login page, redirect to login
      if (!window.location.pathname.includes('index.html') && 
          window.location.pathname !== '/' && 
          !window.location.pathname.endsWith('/')) {
        console.log("Redirecting to login page...");
        window.location.href = 'index.html';
      }
    }
  });
}

/**
 * Initialize the login page functionality
 */
function initLoginPage() {
  console.log("Initializing login page...");
  
  // Initialize Firebase
  initFirebase();
  
  // Toggle between login and register forms
  const tabBtns = document.querySelectorAll('.tab-btn');
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  
  if (!tabBtns.length || !loginForm || !registerForm) {
    console.error("Login page elements not found");
    return;
  }
  
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      if (btn.dataset.tab === 'login') {
        loginForm.classList.add('active-form');
        registerForm.classList.remove('active-form');
      } else {
        registerForm.classList.add('active-form');
        loginForm.classList.remove('active-form');
      }
    });
  });
  
  // Setup password visibility toggle
  const togglePasswordBtns = document.querySelectorAll('.toggle-password');
  togglePasswordBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const input = this.previousElementSibling;
      const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
      input.setAttribute('type', type);
      this.classList.toggle('fa-eye');
      this.classList.toggle('fa-eye-slash');
    });
  });
  
  // Handle login form submission
  if (loginForm) {
    loginForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      const rememberMe = document.getElementById('remember')?.checked || false;
      
      if (!email || !password) {
        showLoginError("Email and password are required");
        return;
      }
      
      // Show loading state
      const loginBtn = this.querySelector('.btn-login');
      const loginBtnText = loginBtn.querySelector('span');
      const loginBtnSpinner = loginBtn.querySelector('.spinner');
      
      loginBtnText.classList.add('hidden');
      loginBtnSpinner.classList.remove('hidden');
      
      try {
        console.log("Attempting to sign in user:", email);
        
        // Set persistence based on remember me option
        const persistence = rememberMe ? 
          firebase.auth.Auth.Persistence.LOCAL : 
          firebase.auth.Auth.Persistence.SESSION;
          
        await auth.setPersistence(persistence);
        
        // Sign in with Firebase
        const userCredential = await auth.signInWithEmailAndPassword(email, password);
        console.log("Login successful!");
        
        // Success - redirect will happen automatically via onAuthStateChanged
      } catch (error) {
        console.error('Login error:', error);
        showLoginError(error.message || 'Login failed. Please check your credentials.');
      } finally {
        // Reset button state
        loginBtnText.classList.remove('hidden');
        loginBtnSpinner.classList.add('hidden');
      }
    });
  }
  
  // Handle register form submission
  if (registerForm) {
    registerForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const email = document.getElementById('reg-email').value;
      const password = document.getElementById('reg-password').value;
      const confirmPassword = document.getElementById('reg-confirm-password').value;
      
      // Validate passwords match
      if (password !== confirmPassword) {
        showLoginError('Passwords do not match', 'register');
        return;
      }
      
      // Show loading state
      const registerBtn = this.querySelector('.btn-register');
      const registerBtnText = registerBtn.querySelector('span');
      const registerBtnSpinner = registerBtn.querySelector('.spinner');
      
      registerBtnText.classList.add('hidden');
      registerBtnSpinner.classList.remove('hidden');
      
      try {
        console.log("Attempting to create user:", email);
        
        // Create user with Firebase
        await auth.createUserWithEmailAndPassword(email, password);
        console.log("User created successfully");
        
        // Send email verification
        const user = auth.currentUser;
        await user.sendEmailVerification();
        
        // Show success message and switch to login
        showLoginSuccess('Registration successful! Please verify your email and then log in.', 'register');
        document.querySelector('.tab-btn[data-tab="login"]').click();
      } catch (error) {
        console.error('Registration error:', error);
        showLoginError(error.message || 'Registration failed. Please try again.', 'register');
      } finally {
        // Reset button state
        registerBtnText.classList.remove('hidden');
        registerBtnSpinner.classList.add('hidden');
      }
    });
  }
  
  // Setup particles background
  initParticles();
  
  console.log("Login page initialization complete");
}

/**
 * Initialize particles animation for login background
 */
function initParticles() {
  const particlesContainer = document.getElementById('particles');
  if (!particlesContainer) return;
  
  // Create particles
  const particleCount = 50;
  
  for (let i = 0; i < particleCount; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    
    // Random position
    const posX = Math.random() * 100;
    const posY = Math.random() * 100;
    
    // Random size
    const size = Math.random() * 5 + 2;
    
    // Random opacity
    const opacity = Math.random() * 0.5 + 0.1;
    
    // Random animation duration
    const duration = Math.random() * 20 + 10;
    
    // Set styles
    particle.style.left = `${posX}%`;
    particle.style.top = `${posY}%`;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    particle.style.opacity = opacity;
    particle.style.animation = `particleAnimation ${duration}s linear infinite`;
    particle.style.animationDelay = `${Math.random() * 10}s`;
    
    particlesContainer.appendChild(particle);
  }
}

/**
 * Show login error message
 * @param {string} message - Error message to display
 * @param {string} form - Form type ('login' or 'register')
 */
function showLoginError(message, form = 'login') {
  const alertContainer = document.getElementById('login-alert');
  
  if (alertContainer) {
    alertContainer.innerHTML = `
      <div class="alert alert-error">
        <i class="fas fa-exclamation-circle"></i>
        ${message}
      </div>
    `;
    
    alertContainer.classList.add('show');
    
    // Hide after 5 seconds
    setTimeout(() => {
      alertContainer.classList.remove('show');
    }, 5000);
  }
}

/**
 * Show login success message
 * @param {string} message - Success message to display
 * @param {string} form - Form type ('login' or 'register')
 */
function showLoginSuccess(message, form = 'login') {
  const alertContainer = document.getElementById('login-alert');
  
  if (alertContainer) {
    alertContainer.innerHTML = `
      <div class="alert alert-success">
        <i class="fas fa-check-circle"></i>
        ${message}
      </div>
    `;
    
    alertContainer.classList.add('show');
    
    // Hide after 5 seconds
    setTimeout(() => {
      alertContainer.classList.remove('show');
    }, 5000);
  }
}

/**
 * Log out the current user
 */
async function logout() {
  try {
    // Initialize Firebase if not already
    initFirebase();
    
    // Sign out from Firebase
    await auth.signOut();
    console.log("User signed out successfully");
    
    // Clear any stored user info
    localStorage.removeItem(USER_INFO_KEY);
    sessionStorage.removeItem(USER_INFO_KEY);
    
    // Redirect will be handled by onAuthStateChanged
  } catch (error) {
    console.error('Logout error:', error);
    window.location.href = 'index.html'; // Fallback redirect
  }
}

/**
 * Save user information to storage
 * @param {Object} user - Firebase user object
 */
function saveUserInfo(user) {
  // Get additional user info if available
  const userInfo = {
    uid: user.uid,
    email: user.email,
    emailVerified: user.emailVerified,
    displayName: user.displayName || user.email.split('@')[0],
    photoURL: user.photoURL,
    role: 'user' // Default role
  };
  
  // Store in localStorage for persistence
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
  console.log("User info saved to localStorage:", userInfo);
}

/**
 * Check if user is authenticated
 * @returns {boolean} - Whether the user is authenticated
 */
function isAuthenticated() {
  // Initialize Firebase if not already
  initFirebase();
  
  // Return current auth state
  return auth.currentUser !== null;
}

/**
 * Get the current authentication token (Firebase ID token)
 * @returns {Promise<string|null>} - The current authentication token or null if not authenticated
 */
async function getAuthToken() {
  // Initialize Firebase if not already
  initFirebase();
  
  if (!isAuthenticated()) {
    return null;
  }
  
  try {
    // Get Firebase ID token
    return await auth.currentUser.getIdToken(true);
  } catch (error) {
    console.error('Error getting auth token:', error);
    return null;
  }
}

/**
 * Get the current user information
 * @returns {Object|null} - The current user information or null if not authenticated
 */
function getCurrentUser() {
  // Initialize Firebase if not already
  initFirebase();
  
  if (!isAuthenticated()) {
    return null;
  }
  
  const userInfo = localStorage.getItem(USER_INFO_KEY);
  
  if (!userInfo) {
    return auth.currentUser ? {
      uid: auth.currentUser.uid,
      email: auth.currentUser.email,
      displayName: auth.currentUser.displayName || auth.currentUser.email.split('@')[0],
      role: 'user' // Default role
    } : null;
  }
  
  try {
    return JSON.parse(userInfo);
  } catch (e) {
    console.error('Error parsing user info:', e);
    return null;
  }
}

/**
 * Update user interface with current user information
 */
function updateUserInterface() {
  const user = getCurrentUser();
  
  if (!user) {
    console.log("No user found to update UI");
    return;
  }
  
  // Update user name and role in the interface
  const userNameElements = document.querySelectorAll('.user-name');
  const userRoleElements = document.querySelectorAll('.user-role');
  
  userNameElements.forEach(element => {
    element.textContent = user.displayName || user.email;
  });
  
  userRoleElements.forEach(element => {
    element.textContent = user.role || 'User';
  });
  
  console.log("User interface updated with user info");
}

// Set up event listeners for logout buttons
document.addEventListener('DOMContentLoaded', function() {
  const logoutBtns = document.querySelectorAll('#logout-btn, #user-logout-btn');
  
  logoutBtns.forEach(btn => {
    if (btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        logout();
      });
    }
  });
});

// Export auth functions
window.authService = {
  initAuth,
  initLoginPage,
  logout,
  isAuthenticated,
  getAuthToken,
  getCurrentUser,
  updateUserInterface
};