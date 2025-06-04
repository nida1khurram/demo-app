# streamlit run main.py
from datetime import datetime
import os
import streamlit as st
import pandas as pd
import numpy as np
from hashlib import md5, sha256
import json
from PIL import Image
import base64

# Initialize or load the CSV file
CSV_FILE = "fees_data.csv"
USER_DB_FILE = "users.json"

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

def initialize_files():
    """Initialize all required files"""
    initialize_csv()
    initialize_user_db()

def initialize_user_db():
    """Initialize the user database with admin if it doesn't exist"""
    if not os.path.exists(USER_DB_FILE):
        # Create default admin user (username: admin, password: admin123)
        default_admin = {
            "admin": {
                "password": hash_password("admin123"),
                "is_admin": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        with open(USER_DB_FILE, 'w') as f:
            json.dump(default_admin, f)

def hash_password(password):
    """Hash a password for storing"""
    return sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    return stored_password == sha256(provided_password.encode('utf-8')).hexdigest()

def authenticate_user(username, password):
    """Authenticate a user"""
    try:
        with open(USER_DB_FILE, 'r') as f:
            users = json.load(f)
        
        if username in users:
            if verify_password(users[username]['password'], password):
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.session_state.is_admin = users[username].get('is_admin', False)
                return True
        return False
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False

def create_user(username, password, is_admin=False):
    """Create a new user account"""
    try:
        if os.path.exists(USER_DB_FILE):
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
        else:
            users = {}
        
        if username in users:
            return False, "Username already exists"
        
        users[username] = {
            "password": hash_password(password),
            "is_admin": is_admin,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(USER_DB_FILE, 'w') as f:
            json.dump(users, f)
        
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def initialize_csv():
    """Initialize the CSV file with proper columns if it doesn't exist"""
    if not os.path.exists(CSV_FILE):
        columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month", 
            "Monthly Fee", "Annual Charges", "Admission Fee", 
            "Received Amount", "Date", "Signature", "Entry Timestamp"
        ]
        pd.DataFrame(columns=columns).to_csv(CSV_FILE, index=False)
    else:
        # Ensure existing CSV has all required columns
        try:
            df = pd.read_csv(CSV_FILE)
            expected_columns = [
                "ID", "Student Name", "Class Category", "Class Section", "Month", 
                "Monthly Fee", "Annual Charges", "Admission Fee", 
                "Received Amount", "Date", "Signature", "Entry Timestamp"
            ]
            
            # Add any missing columns
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = np.nan
            
            # Save back with all columns
            df.to_csv(CSV_FILE, index=False)
        except Exception as e:
            st.error(f"Error initializing CSV: {str(e)}")
            # Create fresh file if corrupted
            pd.DataFrame(columns=expected_columns).to_csv(CSV_FILE, index=False)

def generate_student_id(student_name, class_category):
    """Generate a unique 8-character ID based on student name and class"""
    unique_str = f"{student_name}_{class_category}".encode('utf-8')
    return md5(unique_str).hexdigest()[:8].upper()

def save_to_csv(data):
    """Save data to CSV with proper validation"""
    try:
        # Read existing data
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.DataFrame(columns=data.keys())
        
        # Convert to DataFrame and append
        new_df = pd.DataFrame([data])
        df = pd.concat([df, new_df], ignore_index=True)
        
        # Save back to CSV
        df.to_csv(CSV_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def load_data():
    """Load data from CSV with robust error handling"""
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    
    try:
        # Read CSV with error handling
        try:
            df = pd.read_csv(CSV_FILE)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except pd.errors.ParserError:
            df = pd.read_csv(CSV_FILE, error_bad_lines=False)
        
        # Ensure all expected columns exist
        expected_columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month", 
            "Monthly Fee", "Annual Charges", "Admission Fee", 
            "Received Amount", "Date", "Signature", "Entry Timestamp"
        ]
        
        for col in expected_columns:
            if col not in df.columns:
                df[col] = np.nan
        
        # Convert dates to datetime objects but keep original formatting
        try:
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%m-%Y')
        except:
            # If parsing fails, keep original date string
            pass
        
        try:
            df['Entry Timestamp'] = pd.to_datetime(df['Entry Timestamp']).dt.strftime('%d-%m-%Y %H:%M')
        except:
            # If parsing fails, keep original timestamp string
            pass
        
        return df.dropna(how='all')  # Remove completely empty rows
    
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def update_data(updated_df):
    """Update the CSV file with the modified DataFrame"""
    try:
        updated_df.to_csv(CSV_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error updating data: {str(e)}")
        return False

def format_currency(val):
    """Format currency with Pakistani Rupees symbol and thousand separators"""
    try:
        return f"Rs. {int(val):,}" if not pd.isna(val) and val != 0 else "Rs. 0"
    except:
        return "Rs. 0"

def style_row(row):
    """Apply styling to DataFrame rows based on payment status"""
    today = datetime.now()
    is_between_1st_and_10th = 1 <= today.day <= 10
    styles = [''] * len(row)
    
    if is_between_1st_and_10th:
        if row['Monthly Fee'] == 0:
            styles[0] = 'color: red'
        else:
            styles[0] = 'color: green'
    return styles

def home_page():
    """Display beautiful home page with logo"""
    st.set_page_config(page_title="School Fees Management", layout="wide", page_icon="🏫")
    
    # Custom CSS for styling
    st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .title-text {
        font-size: 3.5rem !important;
        font-weight: 700 !important;
        color: #2c3e50 !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    .subtitle-text {
        font-size: 1.5rem !important;
        font-weight: 400 !important;
        color: #7f8c8d !important;
        text-align: center;
        margin-bottom: 2rem !important;
    }
    .feature-card {
        background-color: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
        height: 100%;
    }
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
    }
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #3498db;
    }
    .feature-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #2c3e50;
    }
    .feature-desc {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    .login-btn {
        background: linear-gradient(135deg, #3498db 0%, #2c3e50 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.5rem 1.5rem !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-top: 2rem !important;
    }
    .circle-container {
        display: flex;
        justify-content: center;
        margin-bottom: 1.5rem;
    }
    .circle {
        width: 200px;
        height: 200px;
        border-radius: 50%;
        background-color: white;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
    }
    .circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Logo and title
    st.markdown('<div class="circle-container">', unsafe_allow_html=True)
    
    try:
        # Try to load local flower.jpg
        with open("flower.jpg", "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        img_html = f'<img src="data:image/jpeg;base64,{img_base64}" alt="School Logo">'
    except:
        # Fallback to placeholder if image not found
        img_html = '<div style="color: gray; text-align: center; padding: 20px;">School Logo</div>'
    
    st.markdown(
        f"""
        <div class="circle">
            {img_html}
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h1 class="title-text">School Fees Management System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Streamline your school\'s fee collection and tracking process</p>', unsafe_allow_html=True)
    
    # Features section
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <h3 class="feature-title">Fee Collection</h3>
            <p class="feature-desc">Easily record and track student fee payments with a simple, intuitive interface.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3 class="feature-title">Reports</h3>
            <p class="feature-desc">Generate detailed reports on fee collection, outstanding payments, and student records.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3 class="feature-title">Secure Access</h3>
            <p class="feature-desc">Role-based authentication ensures only authorized staff can access sensitive data.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Login button
    st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
    if st.button("Get Started / Login", key="home_login_btn", help="Click to login to the system"):
        st.session_state.show_login = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 3rem; color: #7f8c8d; font-size: 0.8rem;">
        <p>© 2023 School Fees Management System | Developed with ❤️ for educational institutions</p>
    </div>
    """, unsafe_allow_html=True)

def login_page():
    """Display login page and handle authentication"""
    st.title("🔒 School Fees Management - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if authenticate_user(username, password):
                st.success(f"Welcome {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def user_management():
    """Admin interface for user management"""
    st.header("👥 User Management")
    
    with st.expander("➕ Create New User"):
        with st.form("create_user_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password", key="new_pass")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pass")
            is_admin = st.checkbox("Admin User")
            show_password = st.checkbox("Show Password")
            
            if show_password:
                st.text(f"Password will be: {new_password if new_password else '[not set]'}")
            
            submit = st.form_submit_button("Create User")
            
            if submit:
                if not new_username or not new_password:
                    st.error("Username and password are required!")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message = create_user(new_username, new_password, is_admin)
                    if success:
                        st.success(message)
                        st.info(f"User '{new_username}' created with password: {new_password}")
                    else:
                        st.error(message)

    with st.expander("👀 View All Users"):
        try:
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
            
            user_data = []
            for username, details in users.items():
                user_data.append({
                    "Username": username,
                    "Admin": "Yes" if details.get('is_admin', False) else "No",
                    "Created At": details.get('created_at', "Unknown")
                })
            
            user_df = pd.DataFrame(user_data)
            st.dataframe(user_df)
            
            # Add delete user functionality
            st.subheader("Delete User")
            if not user_df.empty:
                user_to_delete = st.selectbox(
                    "Select User to Delete",
                    user_df['Username'].tolist(),
                    key="delete_user_select"
                )
                
                if st.button("🗑️ Delete User", key="delete_user_btn"):
                    if user_to_delete == st.session_state.current_user:
                        st.error("You cannot delete your own account!")
                    elif user_to_delete == "admin":
                        st.error("Cannot delete the default admin account!")
                    else:
                        try:
                            with open(USER_DB_FILE, 'r') as f:
                                users = json.load(f)
                            
                            if user_to_delete in users:
                                del users[user_to_delete]
                                
                                with open(USER_DB_FILE, 'w') as f:
                                    json.dump(users, f)
                                
                                st.success(f"User '{user_to_delete}' deleted successfully!")
                                st.rerun()
                            else:
                                st.error("User not found!")
                        except Exception as e:
                            st.error(f"Error deleting user: {str(e)}")
            
        except Exception as e:
            st.error(f"Error loading users: {str(e)}")

    # Password reset functionality
    with st.expander("🔑 Reset Password"):
        try:
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
            
            users_list = list(users.keys())
            selected_user = st.selectbox("Select User", users_list)
            
            with st.form("reset_password_form"):
                new_password = st.text_input("New Password", type="password", key="reset_pass")
                confirm_password = st.text_input("Confirm Password", type="password", key="reset_confirm")
                show_password = st.checkbox("Show New Password")
                
                if show_password:
                    st.text(f"New password will be: {new_password if new_password else '[not set]'}")
                
                reset_btn = st.form_submit_button("Reset Password")
                
                if reset_btn:
                    if not new_password:
                        st.error("Password cannot be empty!")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match!")
                    else:
                        users[selected_user]['password'] = hash_password(new_password)
                        with open(USER_DB_FILE, 'w') as f:
                            json.dump(users, f)
                        st.success(f"Password for {selected_user} reset successfully!")
                        st.info(f"New password: {new_password}")
        except Exception as e:
            st.error(f"Error resetting password: {str(e)}")

def main_app():
    """Main application after login"""
    st.set_page_config(page_title="School Fees Management", layout="wide")
    st.title("📚 School Fees Management System")
    
    if st.session_state.is_admin:
        st.sidebar.write(f"Logged in as Admin: {st.session_state.current_user}")
    else:
        st.sidebar.write(f"Logged in as: {st.session_state.current_user}")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.session_state.show_login = False
        st.rerun()
    
    # Define menu options based on user role
    if st.session_state.is_admin:
        menu_options = ["Enter Fees", "View All Records", "Paid & Unpaid Students Record", "Student Yearly Report", "User Management", "Set Monthly Fees"]
    else:
        menu_options = ["Enter Fees"]  # Non-admin users can only access Enter Fees
    
    menu = st.sidebar.selectbox("Menu", menu_options)
    
    CLASS_CATEGORIES = [
        "Nursery", "KGI", "KGII", 
        "Class 1", "Class 2", "Class 3", "Class 4", "Class 5",
        "Class 6", "Class 7", "Class 8", "Class 9", "Class 10 (Matric)"
    ]
    
    months = [
        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
    ]
    
    if menu == "Enter Fees":
        st.header("➕ Enter Fee Details")
        
        with st.form("fee_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input("Student Name*", placeholder="Full name")
            with col2:
                class_category = st.selectbox("Class Category*", CLASS_CATEGORIES)
                class_section = st.text_input("Class Section", placeholder="A, B, etc. (if applicable)")
            
            # Load existing data to check paid months
            df = load_data()
            
            # Get paid months for this student if they exist
            paid_months = []
            if student_name and class_category:
                student_records = df[(df['Student Name'] == student_name) & 
                                   (df['Class Category'] == class_category)]
                paid_months = student_records['Month'].unique().tolist()
            
            # Filter out paid months from available options
            available_months = [m for m in months if m not in paid_months]
            
            if not available_months:
                st.warning("This student has already paid fees for all months!")
                selected_month = None
            else:
                selected_month = st.selectbox("Select Month*", available_months)
            
            col3, col4 = st.columns(2)
            with col3:
                # Get the standard monthly fee for this class if set by admin
                monthly_fee = 0
                if os.path.exists("monthly_fees.json"):
                    with open("monthly_fees.json", "r") as f:
                        monthly_fees = json.load(f)
                        monthly_fee = monthly_fees.get(class_category, 0)
                
                # Display monthly fee (editable only by admin)
                if st.session_state.is_admin:
                    monthly_fee = st.number_input("Monthly Fee", min_value=0, value=monthly_fee, key="monthly_fee")
                else:
                    st.text_input("Monthly Fee", value=format_currency(monthly_fee), disabled=True)
                
                annual_charges = st.number_input("Annual Charges", min_value=0, value=0, key="annual_charges")
            with col4:
                admission_fee = st.number_input("Admission Fee", min_value=0, value=0, key="admission_fee")
                # Calculate total amount (only monthly fee should be included in the total)
                total_amount = monthly_fee  # Only monthly fee goes in the total
                st.text_input("Monthly Amount", value=format_currency(total_amount), disabled=True)
                received_amount = st.number_input("Received Amount*", min_value=0, value=total_amount, key="received_amount")
            
            payment_date = st.date_input("Payment Date", value=datetime.now())
            signature = st.text_input("Received By (Signature)*", placeholder="Your name")
            
            submitted = st.form_submit_button("💾 Save Fee Record")
            
            if submitted:
                if not student_name or not class_category or not signature or not selected_month:
                    st.error("Please fill all required fields (*)")
                else:
                    student_id = generate_student_id(student_name, class_category)
                    fee_data = {
                        "ID": student_id,
                        "Student Name": student_name,
                        "Class Category": class_category,
                        "Class Section": class_section,
                        "Month": selected_month,
                        "Monthly Fee": monthly_fee,
                        "Annual Charges": annual_charges,
                        "Admission Fee": admission_fee,
                        "Received Amount": received_amount,
                        "Date": payment_date.strftime("%Y-%m-%d"),
                        "Signature": signature,
                        "Entry Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if save_to_csv(fee_data):
                        st.success("✅ Fee record saved successfully!")
                        st.balloons()
    
    elif menu == "Set Monthly Fees":
        if st.session_state.is_admin:
            st.header("💰 Set Standard Monthly Fees by Class")
            
            # Load existing fees if they exist
            if os.path.exists("monthly_fees.json"):
                with open("monthly_fees.json", "r") as f:
                    monthly_fees = json.load(f)
            else:
                monthly_fees = {category: 0 for category in CLASS_CATEGORIES}
            
            # Create a form to set fees for each class
            with st.form("monthly_fees_form"):
                st.write("Set the standard monthly fee for each class:")
                
                # Create two columns for better layout
                col1, col2 = st.columns(2)
                
                fee_values = {}
                for i, category in enumerate(CLASS_CATEGORIES):
                    # Alternate between columns
                    if i % 2 == 0:
                        with col1:
                            fee_values[category] = st.number_input(
                                f"{category} Fee",
                                min_value=0,
                                value=monthly_fees.get(category, 0),
                                key=f"fee_{category}"
                            )
                    else:
                        with col2:
                            fee_values[category] = st.number_input(
                                f"{category} Fee",
                                min_value=0,
                                value=monthly_fees.get(category, 0),
                                key=f"fee_{category}"
                            )
                
                submitted = st.form_submit_button("💾 Save Monthly Fees")
                
                if submitted:
                    # Save the fees to a JSON file
                    with open("monthly_fees.json", "w") as f:
                        json.dump(fee_values, f)
                    st.success("✅ Monthly fees saved successfully!")
        else:
            st.warning("⚠️ You don't have permission to access this page")
    
    elif menu == "View All Records":
        if st.session_state.is_admin:
            st.header("👀 View All Fee Records")
            
            df = load_data()
            if df.empty:
                st.info("No fee records found")
            else:
                # Create tabs for each class category
                tabs = st.tabs(["All Records"] + CLASS_CATEGORIES)
                
                with tabs[0]:
                    st.subheader("All Fee Records")
                    
                    with st.expander("📝 Edit/Delete Records", expanded=False):
                        st.write("Select a record to edit or delete:")
                        
                        edit_index = st.selectbox(
                            "Select Record",
                            options=df.index,
                            format_func=lambda x: f"{df.loc[x, 'Student Name']} - {df.loc[x, 'Class Category']} - {df.loc[x, 'Month']}"
                        )
                        
                        with st.form("edit_form"):
                            record = df.loc[edit_index]
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                edit_name = st.text_input("Student Name", value=record['Student Name'])
                                edit_class = st.selectbox("Class Category", CLASS_CATEGORIES, index=CLASS_CATEGORIES.index(record['Class Category']))
                                edit_section = st.text_input("Class Section", value=record['Class Section'])
                                edit_month = st.selectbox("Month", months, index=months.index(record['Month']))
                            with col2:
                                edit_monthly_fee = st.number_input("Monthly Fee", value=record['Monthly Fee'])
                                edit_annual_charges = st.number_input("Annual Charges", value=record['Annual Charges'])
                                edit_admission_fee = st.number_input("Admission Fee", value=record['Admission Fee'])
                                edit_received = st.number_input("Received Amount", value=record['Received Amount'])
                            
                            # Handle date parsing
                            try:
                                edit_date_value = datetime.strptime(record['Date'], '%d-%m-%Y')
                            except:
                                try:
                                    edit_date_value = datetime.strptime(record['Date'], '%Y-%m-%d')
                                except:
                                    edit_date_value = datetime.now()
                            
                            edit_date = st.date_input("Payment Date", value=edit_date_value)
                            edit_signature = st.text_input("Received By (Signature)", value=record['Signature'])
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                update_btn = st.form_submit_button("🔄 Update Record")
                            with col2:
                                delete_btn = st.form_submit_button("🗑️ Delete Record")
                            
                            if update_btn:
                                df.loc[edit_index, 'Student Name'] = edit_name
                                df.loc[edit_index, 'Class Category'] = edit_class
                                df.loc[edit_index, 'Class Section'] = edit_section
                                df.loc[edit_index, 'Month'] = edit_month
                                df.loc[edit_index, 'Monthly Fee'] = edit_monthly_fee
                                df.loc[edit_index, 'Annual Charges'] = edit_annual_charges
                                df.loc[edit_index, 'Admission Fee'] = edit_admission_fee
                                df.loc[edit_index, 'Received Amount'] = edit_received
                                df.loc[edit_index, 'Date'] = edit_date.strftime('%d-%m-%Y')
                                df.loc[edit_index, 'Signature'] = edit_signature
                                df.loc[edit_index, 'Entry Timestamp'] = datetime.now().strftime('%d-%m-%Y %H:%M')
                                
                                if update_data(df):
                                    st.success("✅ Record updated successfully!")
                                    st.rerun()
                            
                            if delete_btn:
                                df = df.drop(index=edit_index)
                                if update_data(df):
                                    st.success("✅ Record deleted successfully!")
                                    st.rerun()
                    
                    # Display styled dataframe
                    st.dataframe(
                        df.style.apply(style_row, axis=1).format({
                            'Monthly Fee': format_currency,
                            'Annual Charges': format_currency,
                            'Admission Fee': format_currency,
                            'Received Amount': format_currency
                        }),
                        use_container_width=True
                    )
                
                for i, category in enumerate(CLASS_CATEGORIES, start=1):
                    with tabs[i]:
                        st.subheader(f"{category} Records")
                        class_df = df[df['Class Category'] == category]
                        
                        if not class_df.empty:
                            st.dataframe(
                                class_df.style.apply(style_row, axis=1).format({
                                    'Monthly Fee': format_currency,
                                    'Annual Charges': format_currency,
                                    'Admission Fee': format_currency,
                                    'Received Amount': format_currency
                                }),
                                use_container_width=True
                            )
                            
                            st.subheader("Summary")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Students", class_df['Student Name'].nunique())
                            with col2:
                                st.metric("Total Received", format_currency(class_df['Received Amount'].sum()))
                            with col3:
                                unpaid = class_df[class_df['Monthly Fee'] == 0]['Student Name'].nunique()
                                st.metric("Unpaid Students", unpaid, delta_color="inverse")
                            
                            st.write("Monthly Collection:")
                            monthly_summary = class_df.groupby('Month')['Received Amount'].sum().reset_index()
                            st.bar_chart(monthly_summary.set_index('Month'))
                
                st.divider()
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download All Records as CSV",
                    data=csv,
                    file_name="all_fee_records.csv",
                    mime="text/csv"
                )
        else:
            st.warning("⚠️ You don't have permission to access this page")

    elif menu == "Paid & Unpaid Students Record":
        if st.session_state.is_admin:
            st.header("✅ Paid & ❌ Unpaid Students Record")
            df = load_data()
            
            if df.empty:
                st.info("No fee records found")
            else:
                # Calculate outstanding amount for each record
                df['Outstanding'] = df['Monthly Fee'] - df['Received Amount']
                
                # Get all unique students
                all_students = df[['ID', 'Student Name', 'Class Category']].drop_duplicates()
                
                # Get all months in the academic year
                MONTHS = ["APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", 
                         "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"]
                
                # Create a DataFrame with all possible student-month combinations
                all_combinations = pd.DataFrame([
                    (student['ID'], student['Student Name'], student['Class Category'], month)
                    for _, student in all_students.iterrows()
                    for month in MONTHS
                ], columns=['ID', 'Student Name', 'Class Category', 'Month'])
                
                # Merge with actual payments
                merged = pd.merge(all_combinations, 
                                 df[['ID', 'Month', 'Monthly Fee', 'Received Amount', 'Outstanding']],
                                 on=['ID', 'Month'], 
                                 how='left')
                
                # Get each student's standard monthly fee (first recorded fee)
                student_fees = df.groupby('ID')['Monthly Fee'].first().reset_index()
                merged = pd.merge(merged, student_fees, on='ID', how='left')
                
                # Calculate payment status
                merged['Status'] = 'Unpaid'
                merged.loc[merged['Outstanding'] <= 0, 'Status'] = 'Paid'
                merged.loc[merged['Outstanding'].isna() & (merged['Monthly Fee_y'] > 0), 'Outstanding'] = merged['Monthly Fee_y']
                
                # Create tabs for each month
                tabs = st.tabs(MONTHS)
                
                for i, month in enumerate(MONTHS):
                    with tabs[i]:
                        month_data = merged[merged['Month'] == month].copy()
                        
                        if not month_data.empty:
                            # Calculate summary stats
                            total_students = len(month_data)
                            paid_students = len(month_data[month_data['Status'] == 'Paid'])
                            unpaid_students = total_students - paid_students
                            total_outstanding = month_data[month_data['Status'] == 'Unpaid']['Monthly Fee_y'].sum()
                            
                            # Display summary metrics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Students", total_students)
                            with col2:
                                st.metric("Paid Students", paid_students)
                            with col3:
                                st.metric("Unpaid Students", unpaid_students, 
                                          delta=f"Rs. {int(total_outstanding):,}" if total_outstanding > 0 else None)
                            
                            # Display the data with color coding
                            def color_status(val):
                                color = 'green' if val == 'Paid' else 'red'
                                return f'color: {color}'
                            
                            display_df = month_data[['Student Name', 'Class Category', 'Monthly Fee_y', 'Received Amount', 'Outstanding', 'Status']]
                            display_df = display_df.rename(columns={
                                'Monthly Fee_y': 'Monthly Fee',
                                'Received Amount': 'Amount Paid',
                                'Outstanding': 'Balance Due'
                            })
                            
                            st.dataframe(
                                display_df.style.format({
                                    'Monthly Fee': format_currency,
                                    'Amount Paid': format_currency,
                                    'Balance Due': format_currency
                                }).applymap(color_status, subset=['Status']),
                                use_container_width=True
                            )
                            
                            # Download button for this month's data
                            csv = display_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label=f"📥 Download {month} Data",
                                data=csv,
                                file_name=f"{month.lower()}_payment_status.csv",
                                mime="text/csv"
                            )
                
                # Overall summary across all months
                st.subheader("🎯 Overall Payment Status")
                
                # Calculate unpaid months per student
                student_summary = merged.groupby(['ID', 'Student Name', 'Class Category'])['Status'].apply(
                    lambda x: (x == 'Unpaid').sum()
                ).reset_index()
                student_summary.columns = ['ID', 'Student Name', 'Class Category', 'Unpaid Months']
                
                # Calculate total outstanding per student
                student_outstanding = merged[merged['Status'] == 'Unpaid'].groupby(
                    ['ID', 'Student Name', 'Class Category']
                )['Monthly Fee_y'].sum().reset_index()
                student_outstanding.columns = ['ID', 'Student Name', 'Class Category', 'Total Outstanding']
                
                # Merge the data
                student_summary = pd.merge(student_summary, student_outstanding, 
                                         on=['ID', 'Student Name', 'Class Category'],
                                         how='left').fillna(0)
                
                # Display summary
                st.dataframe(
                    student_summary.style.format({'Total Outstanding': format_currency}),
                    use_container_width=True
                )
                
                # Download all data
                csv = merged[['Student Name', 'Class Category', 'Month', 'Monthly Fee_y', 
                             'Received Amount', 'Outstanding', 'Status']]\
                      .rename(columns={'Monthly Fee_y': 'Monthly Fee'})\
                      .to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Complete Payment Records",
                    data=csv,
                    file_name="complete_payment_records.csv",
                    mime="text/csv"
                )
        
    elif menu == "Student Yearly Report":
        if st.session_state.is_admin:
            st.header("📊 Student Yearly Fee Report")
            
            df = load_data()
            if df.empty:
                st.info("No fee records found")
            else:
                # Step 1: Show all classes with records
                all_classes = sorted(df['Class Category'].unique())
                selected_class = st.selectbox("Select Class", all_classes, key="class_selector")
                
                # Step 2: Show all students in selected class
                class_students = sorted(df[df['Class Category'] == selected_class]['Student Name'].unique())
                
                if not class_students:
                    st.warning(f"No students found in {selected_class}")
                else:
                    selected_student = st.selectbox("Select Student", class_students, key="student_selector")
                    
                    # Step 3: Show yearly report for selected student
                    student_data = df[(df['Student Name'] == selected_student) & 
                                    (df['Class Category'] == selected_class)]
                    
                    if student_data.empty:
                        st.warning(f"No records found for {selected_student} in {selected_class}")
                    else:
                        # Display student info
                        st.subheader(f"Yearly Report for {selected_student}")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Class:** {selected_class}")
                        with col2:
                            section = student_data.iloc[0]['Class Section'] if 'Class Section' in student_data.columns else 'N/A'
                            st.write(f"**Section:** {section if pd.notna(section) else 'N/A'}")
                        
                        # Yearly summary
                        st.subheader("Fee Summary")
                        
                        # Calculate totals
                        total_monthly_fee = student_data['Monthly Fee'].sum()
                        annual_charges = student_data['Annual Charges'].sum()  # Sum of all annual charges
                        admission_fee = student_data['Admission Fee'].sum()  # Sum of all admission fees
                        total_received = student_data['Received Amount'].sum()
                        
                        # Display totals
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Monthly Fee", format_currency(total_monthly_fee))
                        with col2:
                            st.metric("Annual Charges", format_currency(annual_charges))
                        with col3:
                            st.metric("Admission Fee", format_currency(admission_fee))
                        with col4:
                            st.metric("Total Received", format_currency(total_received))
                        
                        # Display total fees breakdown
                        st.write("### Total Fees Breakdown")
                        st.write(f"- **Monthly Fees:** {format_currency(total_monthly_fee)}")
                        st.write(f"- **Annual Charges:** {format_currency(annual_charges)}")
                        st.write(f"- **Admission Fees:** {format_currency(admission_fee)}")
                        st.write(f"- **Total Fees Due:** {format_currency(total_monthly_fee + annual_charges + admission_fee)}")
                        st.write(f"- **Total Amount Received:** {format_currency(total_received)}")
                        st.write(f"- **Balance Due:** {format_currency((total_monthly_fee + annual_charges + admission_fee) - total_received)}")
                        
                        # Monthly fee details
                        st.subheader("Monthly Fee Details")
                        
                        all_months = [
                            "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                            "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
                        ]
                        
                        monthly_report = pd.DataFrame({'Month': all_months})
                        monthly_data = student_data.groupby('Month').agg({
                            'Monthly Fee': 'sum',
                            'Annual Charges': 'sum',
                            'Admission Fee': 'sum',
                            'Received Amount': 'sum'
                        }).reset_index()
                        
                        monthly_report = monthly_report.merge(monthly_data, on='Month', how='left').fillna(0)
                        monthly_report['Status'] = monthly_report.apply(
                            lambda row: 'Paid' if row['Monthly Fee'] > 0 else 'Unpaid', 
                            axis=1
                        )
                        
                        def color_unpaid(val):
                            if val == 'Unpaid':
                                return 'color: red'
                            return ''
                        
                        st.dataframe(
                            monthly_report.style
                            .applymap(color_unpaid, subset=['Status'])
                            .format({
                                'Monthly Fee': format_currency,
                                'Annual Charges': format_currency,
                                'Admission Fee': format_currency,
                                'Received Amount': format_currency
                            }),
                            use_container_width=True
                        )
                        
                        # Visualizations
                        st.subheader("Payment Trends")
                        st.line_chart(monthly_report.set_index('Month')[['Monthly Fee', 'Received Amount']])
                        
                        # Download student report
                        st.divider()
                        csv = monthly_report.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Student Report",
                            data=csv,
                            file_name=f"{selected_student}_fee_report.csv",
                            mime="text/csv"
                        )
        else:
            st.warning("⚠️ You don't have permission to access this page")

    elif menu == "User Management":
        if st.session_state.is_admin:
            user_management()
        else:
            st.warning("⚠️ You don't have permission to access this page")

def main():
    initialize_files()
    
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False
    
    if not st.session_state.authenticated:
        if st.session_state.show_login:
            login_page()
        else:
            home_page()
    else:
        main_app()

if __name__ == "__main__":
    main()