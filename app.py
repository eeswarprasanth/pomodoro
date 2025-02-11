import os
import json
from flask import Flask, render_template, request ,send_from_directory, redirect, session, url_for
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai
import markdown

os.environ["GOOGLE_API_KEY"] = "AIzaSyCcWZCBDhEWLhu5zFBf7vn00bS3VXbA1Lk"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}
app.config['SECRET_KEY'] = 'my_simple_secret_key_123'
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


@app.route("/")
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("landing"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and users[username] == password:
            session["username"] = username
            return redirect(url_for("landing"))
        return "Invalid credentials. Try again."
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            return "Username already exists."
        users[username] = password
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/landing")
def landing():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("landing.html")

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

@app.route('/journal')
def journal():
    # Placeholder route for Journal (coming soon)
    return "<h1>Journal Coming Soon!</h1>"

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)