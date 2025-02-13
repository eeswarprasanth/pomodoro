import os
import json
from flask import Flask, render_template, request ,send_from_directory, redirect, session, url_for, g, abort
import sqlite3
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai

os.environ["GOOGLE_API_KEY"] = "Enter-your-api-key"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}
app.config['SECRET_KEY'] = 'my_simple_secret_key_123'
DATABASE = os.path.join(app.root_path, "database.db")
users = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join(page.extract_text() for page in pdf.pages)
        return text
    elif ext == 'docx':
        doc = docx.Document(file_path)
        text = ' '.join(para.text for para in doc.paragraphs)
        return text
    elif ext == 'txt':
        with open(file_path, 'r') as file:
            return file.read()
    return None

def generate_open_questions(input_text):
    prompt = f"""
    You are an AI assistant. Based on the following document context, generate exactly 5 open-ended questions that test the understanding of the content.
    Return the questions as a JSON array of strings. Do not include any markdown formatting, code fences, or additional text.
    Document:
    {input_text}
    """
    response = model.generate_content(prompt).text.strip()
    # Remove code fences or markdown formatting if present
    if response.startswith("```"):
        lines = response.splitlines()
        lines = [line for line in lines if not line.startswith("```")]
        response = "\n".join(lines).strip()
    try:
        questions = json.loads(response)
        if isinstance(questions, list) and len(questions) == 5:
            return questions
    except Exception:
        # Fallback: split by newlines, remove any extraneous placeholder text, and select the first 5 items
        questions = [q.strip() for q in response.split('\n') if q.strip()]
        questions = [q for q in questions if not q.lower().startswith("type your answer here")]
        return questions[:5]
    return []


def evaluate_answers(doc_text, qas):
    qa_str = "\n".join([f"Question: {qa['question']}\nAnswer: {qa['answer']}" for qa in qas])
    prompt = f"""
    You are an expert evaluator. Given the following document context:
    {doc_text}
    And the following questions with the user's answers:
    {qa_str}
    For each question, evaluate the answer in terms of correctness, completeness, and clarity. Additionally, assign an accuracy score between 0 and 100 that represents how accurately the answer addresses the question based on the document context give less scores if the answer is not accurate or if the answer is out of context and irrelevant answers.
    Provide your evaluation in the following format for each question:
    Question: <question text>
    Accuracy Score: <score out of 100>
    Feedback: <detailed feedback>
    """
    evaluation = model.generate_content(prompt).text.strip()
    return evaluation


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # enable dict-like access to rows
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # Create journals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        db.commit()

# Initialize the database when the app starts
init_db()



@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("landing"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        cursor = db.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user and user["password"] == password:  # Use hashed passwords in production
            session.clear()  # Clear any existing session data
            session["user_id"] = user["id"]
            session.permanent = False  # Ensure the session cookie is not permanent
            return redirect(url_for("landing"))
        return "Invalid credentials. Try again."
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
        except sqlite3.IntegrityError:
            return "Username already exists."
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/landing")
def landing():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cursor = db.execute("SELECT username FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()
    username = user["username"] if user else "User"
    return render_template("landing.html", username=username)


@app.route("/journal", methods=["GET", "POST"])
def journal():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user_id = session["user_id"]
    if request.method == "POST":
        content = request.form["content"]
        db.execute("INSERT INTO journals (user_id, content) VALUES (?, ?)", (user_id, content))
        db.commit()
        return redirect(url_for("journal"))
    # Retrieve journal entries for the current user
    cursor = db.execute("SELECT id, content, created_at FROM journals WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    journals = cursor.fetchall()
    return render_template("journal.html", journals=journals)

@app.route("/journal/delete/<int:journal_id>", methods=["POST"])
def delete_journal(journal_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user_id = session["user_id"]
    # Ensure the journal belongs to the current user
    cursor = db.execute("SELECT id FROM journals WHERE id = ? AND user_id = ?", (journal_id, user_id))
    journal = cursor.fetchone()
    if journal is None:
        abort(404)
    db.execute("DELETE FROM journals WHERE id = ?", (journal_id,))
    db.commit()
    return redirect(url_for("journal"))

@app.route("/journal/edit/<int:journal_id>", methods=["GET", "POST"])
def edit_journal(journal_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user_id = session["user_id"]
    # Ensure the journal belongs to the current user
    cursor = db.execute("SELECT id, content FROM journals WHERE id = ? AND user_id = ?", (journal_id, user_id))
    journal = cursor.fetchone()
    if journal is None:
        abort(404)
    if request.method == "POST":
        new_content = request.form["content"]
        db.execute("UPDATE journals SET content = ? WHERE id = ?", (new_content, journal_id))
        db.commit()
        return redirect(url_for("journal"))
    return render_template("edit_journal.html", journal=journal)

@app.route('/generate', methods=['POST'])
def generate_questions():
    if 'file' not in request.files:
        return "No file part"
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        text = extract_text_from_file(file_path)
        if text:
            questions = generate_open_questions(text)
            return render_template('questions.html', questions=questions, doc_text=text)
    return "Invalid file format or error extracting text."

@app.route('/evaluate', methods=['POST'])
def evaluate():
    doc_text = request.form.get('doc_text')
    qas = []
    for i in range(1, 6):
        question = request.form.get(f'question{i}')
        answer = request.form.get(f'answer{i}')
        qas.append({'question': question, 'answer': answer})
    evaluation_result = evaluate_answers(doc_text, qas)
    return render_template('evaluation.html', evaluation=evaluation_result)

@app.route('/quiz')
def quiz():
    # This route loads the Quiz app landing page (quiz_index.html)
    return render_template('quiz_index.html')

@app.route('/pomodoro')
def pomodoro():
    # Serve the Pomodoro clock index page from the static folder
    return send_from_directory('static/pomodoro', 'index.html')

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
