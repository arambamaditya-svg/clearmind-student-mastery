from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Use PostgreSQL on Vercel, fallback to SQLite locally
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # PostgreSQL mode (Vercel)
    def get_db_connection():
        return psycopg2.connect(DATABASE_URL)
    
    def init_db():
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id SERIAL PRIMARY KEY,
                subject TEXT,
                chapter_name TEXT,
                chapter_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                subject TEXT,
                chapter_id INTEGER,
                question_number INTEGER,
                question_text TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS student_progress (
                id SERIAL PRIMARY KEY,
                student_id TEXT,
                subject TEXT,
                chapter_id INTEGER,
                question_id INTEGER,
                done INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, subject, chapter_id, question_id)
            )
        ''')
        
        cur.execute("SELECT COUNT(*) FROM chapters")
        if cur.fetchone()[0] == 0:
            subjects = ['maths', 'physics', 'chemistry', 'biology']
            for subject in subjects:
                for chap_num in range(1, 11):
                    cur.execute('''
                        INSERT INTO chapters (subject, chapter_name, chapter_number)
                        VALUES (%s, %s, %s) RETURNING id
                    ''', (subject, f'Chapter {chap_num}', chap_num))
                    chapter_id = cur.fetchone()[0]
                    
                    for q_num in range(1, 5):
                        cur.execute('''
                            INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (subject, chapter_id, q_num, f'Question {q_num}', 'Answer will be added later'))
        
        conn.commit()
        cur.close()
        conn.close()
        print("PostgreSQL database ready")
    
    # PostgreSQL helper functions
    def get_chapters(subject):
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, chapter_number, chapter_name FROM chapters WHERE subject = %s ORDER BY chapter_number", (subject,))
        chapters = cur.fetchall()
        cur.close()
        conn.close()
        return chapters
    
    def get_questions_by_chapter(chapter_id):
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, question_number, question_text, answer FROM questions WHERE chapter_id = %s ORDER BY question_number", (chapter_id,))
        questions = cur.fetchall()
        cur.close()
        conn.close()
        return questions
    
    def get_student_progress_by_chapter(student_id, subject, chapter_id):
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT question_id, done FROM student_progress 
            WHERE student_id = %s AND subject = %s AND chapter_id = %s
        ''', (student_id, subject, chapter_id))
        progress = {row['question_id']: row['done'] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return progress
    
    def get_chapter_progress(student_id, subject, chapter_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE chapter_id = %s", (chapter_id,))
        total = cur.fetchone()[0]
        cur.execute('''
            SELECT COUNT(*) FROM student_progress 
            WHERE student_id = %s AND subject = %s AND chapter_id = %s AND done = 1
        ''', (student_id, subject, chapter_id))
        done = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {'total': total, 'done': done, 'percent': int(done/total*100) if total > 0 else 0}
    
    def get_all_chapters_progress(student_id, subject):
        chapters = get_chapters(subject)
        result = []
        for chap in chapters:
            progress = get_chapter_progress(student_id, subject, chap['id'])
            result.append({
                'id': chap['id'],
                'number': chap['chapter_number'],
                'name': chap['chapter_name'],
                'total': progress['total'],
                'done': progress['done'],
                'percent': progress['percent']
            })
        return result
    
    def update_progress(student_id, subject, chapter_id, question_id, done):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO student_progress (student_id, subject, chapter_id, question_id, done, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (student_id, subject, chapter_id, question_id)
            DO UPDATE SET done = %s, timestamp = %s
        ''', (student_id, subject, chapter_id, question_id, done, datetime.now(), done, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()

else:
    # SQLite mode (Local development)
    DB_PATH = 'mastery.db'
    
    import sqlite3
    
    def get_db_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                chapter_name TEXT,
                chapter_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                chapter_id INTEGER,
                question_number INTEGER,
                question_text TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chapter_id) REFERENCES chapters (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                subject TEXT,
                chapter_id INTEGER,
                question_id INTEGER,
                done INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, subject, chapter_id, question_id)
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM chapters")
        if cursor.fetchone()[0] == 0:
            subjects = ['maths', 'physics', 'chemistry', 'biology']
            for subject in subjects:
                for chap_num in range(1, 11):
                    cursor.execute('''
                        INSERT INTO chapters (subject, chapter_name, chapter_number)
                        VALUES (?, ?, ?)
                    ''', (subject, f'Chapter {chap_num}', chap_num))
                    chapter_id = cursor.lastrowid
                    
                    for q_num in range(1, 5):
                        cursor.execute('''
                            INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (subject, chapter_id, q_num, f'Question {q_num}', 'Answer will be added later'))
        
        conn.commit()
        conn.close()
        print("SQLite database ready")
    
    def get_chapters(subject):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, chapter_number, chapter_name FROM chapters WHERE subject = ? ORDER BY chapter_number", (subject,))
        chapters = cursor.fetchall()
        conn.close()
        return chapters
    
    def get_questions_by_chapter(chapter_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, question_number, question_text, answer FROM questions WHERE chapter_id = ? ORDER BY question_number", (chapter_id,))
        questions = cursor.fetchall()
        conn.close()
        return questions
    
    def get_student_progress_by_chapter(student_id, subject, chapter_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT question_id, done FROM student_progress 
            WHERE student_id = ? AND subject = ? AND chapter_id = ?
        ''', (student_id, subject, chapter_id))
        progress = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return progress
    
    def get_chapter_progress(student_id, subject, chapter_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions WHERE chapter_id = ?", (chapter_id,))
        total = cursor.fetchone()[0]
        cursor.execute('''
            SELECT COUNT(*) FROM student_progress 
            WHERE student_id = ? AND subject = ? AND chapter_id = ? AND done = 1
        ''', (student_id, subject, chapter_id))
        done = cursor.fetchone()[0]
        conn.close()
        return {'total': total, 'done': done, 'percent': int(done/total*100) if total > 0 else 0}
    
    def get_all_chapters_progress(student_id, subject):
        chapters = get_chapters(subject)
        result = []
        for chap in chapters:
            progress = get_chapter_progress(student_id, subject, chap[0])
            result.append({
                'id': chap[0],
                'number': chap[1],
                'name': chap[2],
                'total': progress['total'],
                'done': progress['done'],
                'percent': progress['percent']
            })
        return result
    
    def update_progress(student_id, subject, chapter_id, question_id, done):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO student_progress (student_id, subject, chapter_id, question_id, done, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, subject, chapter_id, question_id, done, datetime.now()))
        conn.commit()
        conn.close()

# Initialize database
init_db()

# ===== ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chapters/<subject>', methods=['POST'])
def get_chapters_data(subject):
    data = request.json
    student_id = data.get('student_id')
    chapters_progress = get_all_chapters_progress(student_id, subject)
    return jsonify({'chapters': chapters_progress})

@app.route('/api/chapter/<int:chapter_id>', methods=['POST'])
def get_chapter_data(chapter_id):
    data = request.json
    student_id = data.get('student_id')
    subject = data.get('subject')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT subject, chapter_name FROM chapters WHERE id = %s", (chapter_id,))
        chapter_info = cur.fetchone()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT subject, chapter_name FROM chapters WHERE id = ?", (chapter_id,))
        row = cur.fetchone()
        chapter_info = {'subject': row[0], 'chapter_name': row[1]} if row else None
        conn.close()
    
    questions = get_questions_by_chapter(chapter_id)
    progress = get_student_progress_by_chapter(student_id, subject, chapter_id)
    
    questions_data = []
    for q in questions:
        if DATABASE_URL:
            questions_data.append({
                'id': q['id'],
                'number': q['question_number'],
                'text': q['question_text'],
                'answer': q['answer'],
                'done': progress.get(q['id'], 0)
            })
        else:
            questions_data.append({
                'id': q[0],
                'number': q[1],
                'text': q[2],
                'answer': q[3],
                'done': progress.get(q[0], 0)
            })
    
    return jsonify({
        'chapter_id': chapter_id,
        'chapter_name': chapter_info['chapter_name'] if chapter_info else '',
        'questions': questions_data
    })

@app.route('/api/toggle', methods=['POST'])
def toggle_question():
    data = request.json
    student_id = data.get('student_id')
    subject = data.get('subject')
    chapter_id = data.get('chapter_id')
    question_id = data.get('question_id')
    done = data.get('done', 1)
    
    update_progress(student_id, subject, chapter_id, question_id, done)
    progress = get_chapter_progress(student_id, subject, chapter_id)
    
    return jsonify({
        'success': True,
        'done_count': progress['done'],
        'total': progress['total'],
        'percent': progress['percent']
    })

@app.route('/subject/<subject>')
def subject_page(subject):
    return render_template('subject.html', subject=subject)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/add_chapter', methods=['POST'])
def add_chapter():
    data = request.json
    subject = data.get('subject')
    chapter_name = data.get('chapter_name')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COALESCE(MAX(chapter_number), 0) FROM chapters WHERE subject = %s', (subject,))
        max_num = cur.fetchone()[0]
        cur.execute('''
            INSERT INTO chapters (subject, chapter_name, chapter_number)
            VALUES (%s, %s, %s) RETURNING id
        ''', (subject, chapter_name, max_num + 1))
        chapter_id = cur.fetchone()[0]
        for i in range(1, 5):
            cur.execute('''
                INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
                VALUES (%s, %s, %s, %s, %s)
            ''', (subject, chapter_id, i, f'Question {i}', 'Answer will be added later'))
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT MAX(chapter_number) FROM chapters WHERE subject = ?', (subject,))
        max_num = cur.fetchone()[0] or 0
        cur.execute('''
            INSERT INTO chapters (subject, chapter_name, chapter_number)
            VALUES (?, ?, ?)
        ''', (subject, chapter_name, max_num + 1))
        chapter_id = cur.lastrowid
        for i in range(1, 5):
            cur.execute('''
                INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
                VALUES (?, ?, ?, ?, ?)
            ''', (subject, chapter_id, i, f'Question {i}', 'Answer will be added later'))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/api/delete_chapter', methods=['POST'])
def delete_chapter():
    data = request.json
    chapter_id = data.get('id')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM questions WHERE chapter_id = %s", (chapter_id,))
        cur.execute("DELETE FROM chapters WHERE id = %s", (chapter_id,))
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM questions WHERE chapter_id = ?", (chapter_id,))
        cur.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/api/update_question', methods=['POST'])
def update_question():
    data = request.json
    question_id = data.get('id')
    question_text = data.get('question_text')
    answer = data.get('answer')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE questions SET question_text = %s, answer = %s WHERE id = %s
        ''', (question_text, answer, question_id))
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE questions SET question_text = ?, answer = ? WHERE id = ?
        ''', (question_text, answer, question_id))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/api/add_question', methods=['POST'])
def add_question():
    data = request.json
    chapter_id = data.get('chapter_id')
    question_text = data.get('question_text')
    answer = data.get('answer', '')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COALESCE(MAX(question_number), 0) FROM questions WHERE chapter_id = %s', (chapter_id,))
        max_num = cur.fetchone()[0]
        cur.execute('''
            INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
            SELECT subject, %s, %s, %s, %s FROM chapters WHERE id = %s
        ''', (chapter_id, max_num + 1, question_text, answer, chapter_id))
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT MAX(question_number) FROM questions WHERE chapter_id = ?', (chapter_id,))
        max_num = cur.fetchone()[0] or 0
        cur.execute('''
            INSERT INTO questions (subject, chapter_id, question_number, question_text, answer)
            SELECT subject, ?, ?, ?, ? FROM chapters WHERE id = ?
        ''', (chapter_id, max_num + 1, question_text, answer, chapter_id))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/api/delete_question', methods=['POST'])
def delete_question():
    data = request.json
    question_id = data.get('id')
    
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM questions WHERE id = %s", (question_id,))
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')