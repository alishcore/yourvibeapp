import streamlit as st

st.set_page_config(
    page_title="MusicU", 
    page_icon="🎵",                    
)
import json
import os
import google.generativeai as genai
from supabase import create_client, Client
from datetime import datetime


import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


if not GEMINI_API_KEY:
    st.error("🚨 **Google Gemini API Key Not Found!**")
    st.warning("Please set GEMINI_API_KEY in Streamlit secrets or environment variables.")
    st.stop()


if not GEMINI_API_KEY or "your-api-key-here" in GEMINI_API_KEY:
    st.error("🚨 **Google Gemini API Key Not Found!**")
    st.warning("""
        Please add your Google Gemini API key to the `config.py` file.
        
        **How to fix this:**
        1. Go to https://ai.google.dev/
        2. Create a free Google account if needed
        3. Get your free API key (no billing required!)
        4. Paste the key into the `GEMINI_API_KEY` variable in `config.py`.
    """)
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

try:
    if SUPABASE_URL and SUPABASE_KEY and "your-supabase-url" not in SUPABASE_URL and "your-supabase-key" not in SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        supabase = None
except Exception as e:
    supabase = None
    st.error("🚨 **Supabase Connection Failed!**")
    st.warning(f"""
        **What this means:** The app could not connect to your Supabase database.
        
        **Possible Reasons:**
        1.  The `SUPABASE_URL` or `SUPABASE_KEY` might be incorrect.
        2.  Your Supabase project might be paused.
        3.  There might be a network issue.

        **How to fix this:**
        1.  Double-check your Supabase URL and Key in your project settings.
        2.  Ensure they are set correctly as environment variables.
        3.  Visit your Supabase dashboard to ensure your project is active.
        
        **Error Details:** `{e}`
    """)

def setup_database():
    """Setup database table if it doesn't exist"""
    try:
        if supabase:
            supabase.rpc('exec', {'query': '''
                CREATE TABLE IF NOT EXISTS user_vibes (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    mood TEXT,
                    genre TEXT,
                    energy_level TEXT,
                    aesthetic_keywords TEXT[],
                    suggested_music TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                
                ALTER TABLE user_vibes ENABLE ROW LEVEL SECURITY;
                
                CREATE POLICY IF NOT EXISTS "Users can view own vibes" ON user_vibes
                    FOR SELECT USING (auth.uid() = user_id);
                    
                CREATE POLICY IF NOT EXISTS "Users can insert own vibes" ON user_vibes
                    FOR INSERT WITH CHECK (auth.uid() = user_id);
            '''}).execute()
    except Exception as e:
        print(f"Database setup failed: {e}")

def register_user(email, password, name):
    """Register a new user"""
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name
                }
            }
        })
        return response
    except Exception as e:
        raise Exception(f"Registration failed: {e}")

def login_user(email, password):
    """Login existing user"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response
    except Exception as e:
        raise Exception(f"Login failed: {e}")

def logout_user():
    """Logout current user"""
    try:
        supabase.auth.sign_out()
        if 'user' in st.session_state:
            del st.session_state['user']
        if 'user_email' in st.session_state:
            del st.session_state['user_email']
    except Exception as e:
        print(f"Logout error: {e}")

def save_vibe_to_history(user_id, description, vibe_data):
    """Save user's music vibe to history"""
    try:
        if supabase:
            supabase.table('user_vibes').insert({
                'user_id': user_id,
                'description': description,
                'mood': vibe_data.get('mood'),
                'genre': vibe_data.get('genre'),
                'energy_level': vibe_data.get('energy_level'),
                'aesthetic_keywords': vibe_data.get('aesthetic_keywords'),
                'suggested_music': vibe_data.get('suggested_music'),
                'created_at': datetime.now().isoformat()
            }).execute()
    except Exception as e:
        print(f"Failed to save vibe: {e}")

def get_user_history(user_id):
    """Get user's vibe history"""
    try:
        if supabase:
            response = supabase.table('user_vibes').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(10).execute()
            return response.data
        return []
    except Exception as e:
        print(f"Failed to get history: {e}")
        return []

def generate_music_vibe(description):
    """
    Generate music vibe based on user description using Google Gemini
    """
    try:
        prompt = f"""Given the following description of a person, suggest:
1. Mood
2. Music genre
3. Energy level (low, medium, high)
4. Aesthetic keywords (3-5)
5. A matching artist or song

Description: "{description}"

Please respond with a JSON object in this exact format:
{{
    "mood": "string",
    "genre": "string", 
    "energy_level": "string",
    "aesthetic_keywords": ["string1", "string2", "string3"],
    "suggested_music": "string"
}}"""

        system_instruction = "You are a music expert who can analyze personality descriptions and suggest matching music vibes. Always respond with valid JSON."
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"},
            system_instruction=system_instruction
        )
        
        response = model.generate_content(prompt)
        
        content = response.text
        if content is None:
            raise Exception("No content received from AI response")
        result = json.loads(content)
        return result
        
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse AI response: {e}")
    except Exception as e:
        raise Exception(f"Failed to generate music vibe: {e}")

def display_vibe_result(vibe_data):
    """
    Display the generated vibe result with clean, modern styling
    """
    st.markdown('<div class="vibe-result-container">', unsafe_allow_html=True)
    
    # Animated header
    st.markdown('''
        <div class="vibe-header">
            <div class="pulse-animation">🎵</div>
            <h2>Your Musical Vibe</h2>
            <div class="pulse-animation">🎶</div>
        </div>
    ''', unsafe_allow_html=True)
    
    # Main vibe card
    st.markdown('<div class="vibe-card">', unsafe_allow_html=True)
    
    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f'''
            <div class="vibe-item mood-item">
                <div class="vibe-icon">🎭</div>
                <div class="vibe-content">
                    <h4>Mood</h4>
                    <p>{vibe_data.get('mood', 'Unknown')}</p>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="vibe-item genre-item">
                <div class="vibe-icon">🎸</div>
                <div class="vibe-content">
                    <h4>Genre</h4>
                    <p>{vibe_data.get('genre', 'Unknown')}</p>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        energy = vibe_data.get('energy_level', 'Unknown')
        energy_emoji = {"low": "🔋", "medium": "🔋🔋", "high": "🔋🔋🔋"}.get(energy.lower(), "🔋")
        st.markdown(f'''
            <div class="vibe-item energy-item">
                <div class="vibe-icon">⚡</div>
                <div class="vibe-content">
                    <h4>Energy Level</h4>
                    <p>{energy_emoji} {energy.title()}</p>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        keywords = vibe_data.get('aesthetic_keywords', [])
        keywords_html = ""
        if keywords:
            keywords_html = "".join([f'<span class="keyword-tag">{keyword}</span>' for keyword in keywords])
        else:
            keywords_html = '<span class="keyword-tag">No keywords</span>'
        
        st.markdown(f'''
            <div class="vibe-item keywords-item">
                <div class="vibe-icon">✨</div>
                <div class="vibe-content">
                    <h4>Aesthetic Keywords</h4>
                    <div class="keywords-container">
                        {keywords_html}
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        suggested = vibe_data.get('suggested_music', 'No suggestion available')
        youtube_query = suggested.replace(' ', '+').replace('-', '+')
        youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"
        
        st.markdown(f'''
            <div class="vibe-item music-item">
                <div class="vibe-icon">🎼</div>
                <div class="vibe-content">
                    <h4>Suggested Music</h4>
                    <p>{suggested}</p>
                    <a href="{youtube_url}" target="_blank" class="listen-btn">
                        <span class="btn-icon">🎵</span>
                        Listen Now
                    </a>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)

def show_auth_page():
    """Display login/register page"""
    st.markdown('''
        <div class="auth-container">
            <div class="auth-header">
                <h1 class="main-title">🎵 You in a Song</h1>
                <p class="main-subtitle">Discover your personalized music vibe using AI</p>
            </div>
        </div>
    ''', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        st.markdown('<div class="auth-form">', unsafe_allow_html=True)
        st.markdown("### Welcome Back!")
        email = st.text_input("📧 Email", key="login_email", placeholder="Enter your email")
        password = st.text_input("🔒 Password", type="password", key="login_password", placeholder="Enter your password")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🚀 Login", type="primary", use_container_width=True):
                if email and password:
                    try:
                        if supabase:
                            response = login_user(email, password)
                            if response.user:
                                st.session_state['user'] = response.user
                                st.session_state['user_email'] = email
                                st.success("Login successful!")
                                st.rerun()
                            else:
                                st.error("Login failed. Please check your credentials.")
                        else:
                            st.error("Database connection not available. Please try guest mode.")
                    except Exception as e:
                        st.error(f"Login error: {str(e)}")
                else:
                    st.error("Please enter both email and password")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="auth-form">', unsafe_allow_html=True)
        st.markdown("### Join the Music Community!")
        name = st.text_input("👤 Full Name", key="register_name", placeholder="Enter your full name")
        email = st.text_input("📧 Email", key="register_email", placeholder="Enter your email")
        password = st.text_input("🔒 Password", type="password", key="register_password", placeholder="Enter your password")
        confirm_password = st.text_input("🔒 Confirm Password", type="password", key="register_confirm", placeholder="Confirm your password")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🎉 Register", type="primary", use_container_width=True):
                if name and email and password and confirm_password:
                    if password == confirm_password:
                        if len(password) >= 6:
                            try:
                                if supabase:
                                    response = register_user(email, password, name)
                                    if response.user:
                                        st.success("Registration successful! Please check your email to verify your account.")
                                        st.info("After verification, you can login with your credentials.")
                                    else:
                                        st.error("Registration failed. Please try again.")
                                else:
                                    st.error("Database connection not available.")
                            except Exception as e:
                                st.error(f"Registration error: {str(e)}")
                        else:
                            st.error("Password must be at least 6 characters long")
                    else:
                        st.error("Passwords do not match")
                else:
                    st.error("Please fill in all fields")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🎵 Continue as Guest", type="secondary", use_container_width=True):
            st.session_state['guest_mode'] = True
            st.rerun()

def show_user_history():
    """Display user's vibe history"""
    if 'user' in st.session_state and supabase:
        st.markdown('''
            <div class="history-section">
                <h3 class="section-title">
                    <span class="section-icon">📚</span>
                    Your Music Vibe History
                </h3>
            </div>
        ''', unsafe_allow_html=True)
        
        history = get_user_history(st.session_state['user'].id)
        
        if history:
            for i, vibe in enumerate(history[:5]):  # Show last 5 vibes
                with st.expander(f"🎵 {vibe['mood']} - {vibe['genre']} ({vibe['created_at'][:10]})", expanded=False):
                    st.markdown('<div class="history-item">', unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**📝 Description:** {vibe['description']}")
                        st.markdown(f"**🎭 Mood:** {vibe['mood']}")
                        st.markdown(f"**🎸 Genre:** {vibe['genre']}")
                    with col2:
                        st.markdown(f"**⚡ Energy:** {vibe['energy_level']}")
                        if vibe['aesthetic_keywords']:
                            keywords = " • ".join(vibe['aesthetic_keywords'])
                            st.markdown(f"**✨ Keywords:** {keywords}")
                        st.markdown(f"**🎼 Music:** {vibe['suggested_music']}")
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('''
                <div class="empty-history">
                    <div class="empty-icon">🎵</div>
                    <p>No music vibes saved yet.</p>
                    <p>Generate your first one below!</p>
                </div>
            ''', unsafe_allow_html=True)

def main():
    """
    Main application function with authentication
    """
    # Check if user is logged in or in guest mode
    if 'user' not in st.session_state and 'guest_mode' not in st.session_state:
        show_auth_page()
        return
    
    # Enhanced Custom CSS
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;700&display=swap');
    
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    .main .block-container {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem auto;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
    }
    
    /* Typography */
    .main-title {
        font-family: 'Playfair Display', serif;
        font-size: 4rem;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .main-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 1.3rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    .section-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.5rem;
        font-weight: 600;
        color: #333;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-icon {
        font-size: 1.8rem;
    }
    
    /* Auth Container */
    .auth-container {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .auth-header {
        padding: 2rem 0;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border-radius: 15px;
        margin-bottom: 2rem;
    }
    
    .auth-form {
        background: rgba(255, 255, 255, 0.8);
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    }
    
    /* Vibe Result Styling */
    .vibe-result-container {
        margin: 2rem 0;
    }
    
    .vibe-header {
        text-align: center;
        margin-bottom: 2rem;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 1rem;
    }
    
    .vibe-header h2 {
        font-family: 'Playfair Display', serif;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
    }
    
    .pulse-animation {
        font-size: 2rem;
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    .vibe-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 2.5rem;
        box-shadow: 0 20px 40px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .vibe-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, rgba(255,255,255,0.1) 0%, transparent 50%, rgba(255,255,255,0.1) 100%);
        pointer-events: none;
    }
    
    .vibe-item {
        background: rgba(255, 255, 255, 0.15);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .vibe-item:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        background: rgba(255, 255, 255, 0.25);
    }
    
    .vibe-item:last-child {
        margin-bottom: 0;
    }
    
    .vibe-icon {
        font-size: 2rem;
        min-width: 2rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .vibe-content {
        flex: 1;
    }
    
    .vibe-content h4 {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        font-weight: 600;
        color: white;
        margin: 0 0 0.5rem 0;
    }
    
    .vibe-content p {
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        color: rgba(255, 255, 255, 0.9);
        margin: 0;
        font-weight: 400;
    }
    
    .keywords-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    
    .keyword-tag {
        background: rgba(255, 255, 255, 0.2);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 500;
        border: 1px solid rgba(255, 255, 255, 0.3);
        transition: all 0.3s ease;
    }
    
    .keyword-tag:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: scale(1.05);
    }
    
    .listen-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
        color: white;
        padding: 0.7rem 1.5rem;
        border-radius: 25px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
        margin-top: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 5px 15px rgba(255, 107, 107, 0.3);
    }
    
    .listen-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(255, 107, 107, 0.4);
        text-decoration: none;
        color: white;
    }
    
    .btn-icon {
        font-size: 1rem;
    }
    
    /* History Section */
    .history-section {
        margin-bottom: 2rem;
    }
    
    .history-item {
        background: rgba(102, 126, 234, 0.05);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .empty-history {
        text-align: center;
        padding: 3rem;
        background: rgba(102, 126, 234, 0.05);
        border-radius: 15px;
        margin: 2rem 0;
    }
    
    .empty-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    .empty-history p {
        color: #666;
        font-size: 1.1rem;
        margin: 0.5rem 0;
    }
    
    /* Form Styling */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid rgba(102, 126, 234, 0.3);
        padding: 0.75rem;
        font-size: 1rem;
        transition: all 0.3s ease;
        background: rgba(255, 255, 255, 0.9);
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    .stTextArea > div > div > textarea {
        border-radius: 15px;
        border: 2px solid rgba(102, 126, 234, 0.3);
        padding: 1rem;
        font-size: 1rem;
        background: rgba(255, 255, 255, 0.9);
        transition: all 0.3s ease;
        font-family: 'Inter', sans-serif;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Button Styling */
    .stButton > button {
        border-radius: 25px;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        font-family: 'Inter', sans-serif;
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
        color: #2d3436;
    }
    
    .stButton > button[kind="secondary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(255, 234, 167, 0.4);
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        background: rgba(102, 126, 234, 0.1);
        border: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        background: rgba(102, 126, 234, 0.1);
        border-radius: 10px;
        padding: 1rem;
        font-weight: 500;
    }
    
    /* Alert Styling */
    .stAlert {
        border-radius: 10px;
        border: none;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* Spinner Styling */
    .stSpinner {
        text-align: center;
        padding: 2rem;
    }
    
    /* Footer Styling */
    .footer {
        text-align: center;
        color: #888;
        font-style: italic;
        margin-top: 3rem;
        padding: 2rem;
        background: rgba(102, 126, 234, 0.05);
        border-radius: 15px;
        font-family: 'Inter', sans-serif;
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2.5rem;
        }
        
        .main-subtitle {
            font-size: 1.1rem;
        }
        
        .vibe-header h2 {
            font-size: 2rem;
        }
        
        .vibe-card {
            padding: 1.5rem;
        }
        
        .vibe-item {
            padding: 1rem;
        }
        
        .main .block-container {
            padding: 1rem;
        }
    }
    
    /* Loading Animation */
    .loading-animation {
        display: inline-block;
        width: 2rem;
        height: 2rem;
        border: 3px solid rgba(102, 126, 234, 0.3);
        border-radius: 50%;
        border-top-color: #667eea;
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    /* Gradient Text Animation */
    .gradient-text {
        background: linear-gradient(45deg, #667eea, #764ba2, #667eea);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradientShift 3s ease infinite;
    }
    
    @keyframes gradientShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }
    
    /* Hover Effects */
    .hover-lift {
        transition: all 0.3s ease;
    }
    
    .hover-lift:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(102, 126, 234, 0.1);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
    }
    
    /* Additional CSS for new elements */
    .app-header {
        margin-bottom: 2rem;
    }
    
    .welcome-text {
        color: #333;
    }
    
    .wave-emoji {
        animation: wave 2s ease-in-out infinite;
        display: inline-block;
    }
    
    @keyframes wave {
        0%, 100% { transform: rotate(0deg); }
        25% { transform: rotate(20deg); }
        75% { transform: rotate(-20deg); }
    }
    
    .guest-badge {
        background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
        color: #2d3436;
        padding: 0.2rem 0.8rem;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 0.5rem;
        display: inline-block;
    }
    
    .section-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
        margin: 2rem 0;
        border-radius: 1px;
    }
    
    .input-section {
        margin-bottom: 1.5rem;
    }
    
    .example-btn-container {
        display: flex;
        align-items: flex-end;
        height: 100%;
        padding-bottom: 1.5rem;
    }
    
    .textarea-container {
        position: relative;
    }
    
    .generate-section {
        margin: 2rem 0;
    }
    
    .error-message, .warning-message, .success-message {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        font-weight: 500;
    }
    
    .error-message {
        background: rgba(255, 107, 107, 0.1);
        color: #d63031;
        border: 1px solid rgba(255, 107, 107, 0.3);
    }
    
    .warning-message {
        background: rgba(255, 234, 167, 0.3);
        color: #e17055;
        border: 1px solid rgba(255, 234, 167, 0.5);
    }
    
    .success-message {
        background: rgba(0, 184, 148, 0.1);
        color: #00b894;
        border: 1px solid rgba(0, 184, 148, 0.3);
    }
    
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 3rem 2rem;
        background: rgba(102, 126, 234, 0.05);
        border-radius: 15px;
        margin: 2rem 0;
    }
    
    .loading-text {
        color: #667eea;
        font-size: 1.1rem;
        margin-top: 1rem;
        font-weight: 500;
    }
    
    .copy-section {
        text-align: center;
        margin: 2rem 0;
    }
    
    .copy-title {
        color: #333;
        font-size: 1.2rem;
        margin-bottom: 1rem;
    }
    
    .error-card, .warning-card {
        background: white;
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem 0;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        border-left: 4px solid;
    }
    
    .error-card {
        border-left-color: #d63031;
    }
    
    .warning-card {
        border-left-color: #e17055;
    }
    
    .error-header, .warning-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    
    .error-header h3, .warning-header h3 {
        margin: 0;
        color: #333;
    }
    
    .error-content, .warning-content {
        color: #666;
        line-height: 1.6;
    }
    
    .error-steps {
        background: rgba(102, 126, 234, 0.05);
        padding: 1rem;
        border-radius: 10px;
        margin-top: 1rem;
    }
    
    .error-steps h4 {
        color: #333;
        margin-bottom: 0.5rem;
    }
    
    .error-steps ol {
        margin: 0;
        padding-left: 1.5rem;
    }
    
    .error-steps li {
        margin-bottom: 0.5rem;
    }
    
    .error-steps a {
        color: #667eea;
        text-decoration: none;
        font-weight: 500;
    }
    
    .error-steps a:hover {
        text-decoration: underline;
    }
    
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding: 2rem;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border-radius: 15px;
    }
    
    .footer-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
    }
    
    .footer-icon {
        font-size: 2rem;
        animation: pulse 2s ease-in-out infinite;
    }
    
    .footer-content p {
        color: #666;
        font-size: 1.1rem;
        margin: 0;
    }
    
    .footer-links {
        color: #888;
        font-size: 0.9rem;
        font-style: italic;
    }
    
    /* Enhanced Mobile Responsiveness */
    @media (max-width: 768px) {
        .footer-content {
            gap: 0.5rem;
        }
        
        .footer-content p {
            font-size: 1rem;
        }
        
        .footer-links {
            font-size: 0.8rem;
        }
        
        .loading-container {
            padding: 2rem 1rem;
        }
        
        .error-card, .warning-card {
            padding: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)
