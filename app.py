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

# Secure Gemini API key usage
# Import credentials from config file
try:
    from config import GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY
except ImportError:
    st.error("🚨 **Configuration File Not Found!**")
    st.warning("Please create a `config.py` file and add your API keys.")
    st.stop()

# Secure Gemini API key usage
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
            # Try to create the table (will be ignored if exists)
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

# Authentication functions
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
    st.markdown('<div class="vibe-card">', unsafe_allow_html=True)
    st.markdown('<h2 style="text-align: center; margin-bottom: 2rem;">🎵 Your Musical Vibe</h2>', unsafe_allow_html=True)
    
    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="vibe-item">', unsafe_allow_html=True)
        st.markdown("**🎭 Mood**")
        st.markdown(f"<span style='font-size: 1.2rem; font-style: italic;'>{vibe_data.get('mood', 'Unknown')}</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="vibe-item">', unsafe_allow_html=True)
        st.markdown("**🎸 Genre**") 
        st.markdown(f"<span style='font-size: 1.2rem; font-style: italic;'>{vibe_data.get('genre', 'Unknown')}</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="vibe-item">', unsafe_allow_html=True)
        st.markdown("**⚡ Energy Level**")
        energy = vibe_data.get('energy_level', 'Unknown')
        energy_emoji = {"low": "🔋", "medium": "🔋🔋", "high": "🔋🔋🔋"}.get(energy.lower(), "🔋")
        st.markdown(f"<span style='font-size: 1.2rem; font-style: italic;'>{energy_emoji} {energy.title()}</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="vibe-item">', unsafe_allow_html=True)
        st.markdown("**✨ Aesthetic Keywords**")
        keywords = vibe_data.get('aesthetic_keywords', [])
        if keywords:
            keywords_text = " • ".join(keywords)
            st.markdown(f"<span style='font-size: 1.2rem; font-style: italic;'>{keywords_text}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='font-size: 1.2rem; font-style: italic;'>No keywords available</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="vibe-item">', unsafe_allow_html=True)
        st.markdown("**🎼 Suggested Music**")
        suggested = vibe_data.get('suggested_music', 'No suggestion available')
        # Create YouTube search link
        youtube_query = suggested.replace(' ', '+').replace('-', '+')
        youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"
        st.markdown(f'<span style="font-size: 1.2rem; font-style: italic;">{suggested}</span> <a href="{youtube_url}" target="_blank" class="youtube-link">🎵 Listen</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_auth_page():
    """Display login/register page"""
    st.markdown('<h1 class="main-header">🎵 You in a Song</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Please login or register to save your music vibes</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.markdown("### 🔐 Login to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
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
    
    with tab2:
        st.markdown("### 📝 Create New Account")
        name = st.text_input("Full Name", key="register_name")
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm")
        
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
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🎵 Continue as Guest", type="secondary", use_container_width=True):
            st.session_state['guest_mode'] = True
            st.rerun()

def show_user_history():
    """Display user's vibe history"""
    if 'user' in st.session_state and supabase:
        st.markdown('<h3 class="section-header">📚 Your Music Vibe History</h3>', unsafe_allow_html=True)
        
        history = get_user_history(st.session_state['user'].id)
        
        if history:
            for i, vibe in enumerate(history[:5]):  # Show last 5 vibes
                with st.expander(f"🎵 {vibe['mood']} - {vibe['genre']} ({vibe['created_at'][:10]})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Description:** {vibe['description']}")
                        st.write(f"**Mood:** {vibe['mood']}")
                        st.write(f"**Genre:** {vibe['genre']}")
                    with col2:
                        st.write(f"**Energy:** {vibe['energy_level']}")
                        if vibe['aesthetic_keywords']:
                            keywords = " • ".join(vibe['aesthetic_keywords'])
                            st.write(f"**Keywords:** {keywords}")
                        st.write(f"**Music:** {vibe['suggested_music']}")
        else:
            st.info("No music vibes saved yet. Generate your first one below!")

def main():
    """
    Main application function with authentication
    """
    # Check if user is logged in or in guest mode
    if 'user' not in st.session_state and 'guest_mode' not in st.session_state:
        show_auth_page()
        return
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .section-header {
        background: linear-gradient(90deg, #ff6b6b, #ffa500);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: bold;
        font-size: 1.3rem;
        margin-bottom: 1rem;
    }
    .vibe-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    .vibe-item {
        background: transparent;
        padding: 1rem 0;
        margin: 0.8rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        font-size: 1.1rem;
    }
    .vibe-item:last-child {
        border-bottom: none;
    }
    .youtube-link {
        background: #ff0000;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        text-decoration: none;
        font-size: 0.9rem;
        margin-left: 0.5rem;
        display: inline-block;
    }
    .youtube-link:hover {
        background: #cc0000;
        color: white;
        text-decoration: none;
    }
    .generate-btn {
        background: linear-gradient(45deg, #ff6b6b, #ffa500);
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.8rem 2rem;
        border-radius: 25px;
        font-size: 1.1rem;
    }
    .stTextArea > div > div > textarea {
        border-radius: 15px;
        border: 2px solid #e0e0e0;
        padding: 1rem;
        font-size: 1rem;
    }
    .footer {
        text-align: center;
        color: #888;
        font-style: italic;
        margin-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # App header with user info
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown('<h1 class="main-header">🎵 You in a Song</h1>', unsafe_allow_html=True)
        if 'user' in st.session_state:
            user_name = st.session_state['user'].user_metadata.get('name', 'User')
            st.markdown(f'<p class="subtitle">Welcome back, {user_name}! 🎶</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="subtitle">Discover your personalized music vibe using AI (Guest Mode)</p>', unsafe_allow_html=True)
    
    with col3:
        if 'user' in st.session_state:
            if st.button("🚪 Logout", type="secondary"):
                logout_user()
                st.rerun()
        elif 'guest_mode' in st.session_state:
            if st.button("🔐 Login", type="secondary"):
                del st.session_state['guest_mode']
                st.rerun()
    
    # Show user history if logged in
    if 'user' in st.session_state:
        show_user_history()
        st.markdown("---")
    
    # Description input with styling
    st.markdown('<h3 class="section-header">📝 Tell us about yourself</h3>', unsafe_allow_html=True)
    
    # Sample description functionality
    col1, col2 = st.columns([3, 1])
    
    # Initialize example in session state if not present
    if "example_description" not in st.session_state:
        st.session_state.example_description = ""
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Add some spacing
        if st.button("💡 Try an Example", type="secondary", use_container_width=True):
            example_descriptions = [
                "I'm an energetic person who loves early morning runs and coffee. I'm always planning my next adventure and have an optimistic view of the world.",
                "I'm introspective and enjoy quiet evenings with books and tea. I find beauty in simple moments and often feel nostalgic about the past.",
                "I'm a social butterfly who thrives in creative environments. I love vibrant colors, spontaneous plans, and making people laugh.",
                "I'm a night owl who finds inspiration in city lights and jazz clubs. I'm passionate about art and have a sophisticated, mysterious personality."
            ]
            import random
            st.session_state.example_description = random.choice(example_descriptions)
    
    with col1:
        user_description = st.text_area(
            "Describe yourself or someone else (2-3 sentences):",
            value=st.session_state.example_description,
            placeholder="I'm a creative person who loves rainy days and reading poetry. I often find myself daydreaming about distant places and have a melancholic but hopeful outlook on life...",
            height=100,
            key="description_input"
        )
    
    # Generate button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        generate_button = st.button("🎵 Generate Vibe", type="primary", use_container_width=True)
    
    # Process generation
    if generate_button:
        if not user_description.strip():
            st.error("⚠️ Please enter a description before generating your vibe!")
            return
        
        if len(user_description.strip().split()) < 10:
            st.warning("💭 Try adding a bit more detail to get a better music vibe recommendation!")
        
        # Show loading spinner
        with st.spinner("🎼 Analyzing your vibe and finding the perfect musical match..."):
            try:
                # Generate music vibe
                vibe_result = generate_music_vibe(user_description)
                
                # Save to history if logged in
                if 'user' in st.session_state and supabase:
                    save_vibe_to_history(st.session_state['user'].id, user_description, vibe_result)
                
                # Display result
                display_vibe_result(vibe_result)
                
                # Add copy functionality (bonus feature)
                result_text = f"""Your Musical Vibe:
Mood: {vibe_result.get('mood', 'Unknown')}
Genre: {vibe_result.get('genre', 'Unknown')}
Energy Level: {vibe_result.get('energy_level', 'Unknown')}
Aesthetic Keywords: {', '.join(vibe_result.get('aesthetic_keywords', []))}
Suggested Music: {vibe_result.get('suggested_music', 'Unknown')}"""
                
                st.markdown("---")
                if st.button("📋 Copy Result to Clipboard"):
                    st.code(result_text, language=None)
                    st.success("✅ Result copied! You can now paste it anywhere.")
                
            except Exception as e:
                error_message = str(e)
                if "api_key" in error_message.lower() or "unauthorized" in error_message.lower() or "permission" in error_message.lower():
                    st.error("🔑 **Google Gemini API Key Issue**")
                    st.warning("""
                    **What this means:** There's an issue with your Google Gemini API key.
                    
                    **How to fix this:**
                    1. Go to https://ai.google.dev/
                    2. Create a free Google account if needed
                    3. Get your free API key (no billing required!)
                    4. Google Gemini offers generous free usage limits
                    
                    **Note:** Google Gemini is FREE to use with good daily limits.
                    """)
                elif "quota" in error_message.lower() or "limit" in error_message.lower():
                    st.error("📊 **Daily Limit Reached**")
                    st.info("You've reached today's free usage limit. Try again tomorrow or upgrade for higher limits.")
                else:
                    st.error(f"😞 Oops! Something went wrong: {error_message}")
                    st.info("💡 Please check your internet connection and try again. If the problem persists, the AI service might be temporarily unavailable.")
    
    # Footer with styling
    st.markdown("---")
    st.markdown('<p class="footer">Powered by Google Gemini (Free!) ✨</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
