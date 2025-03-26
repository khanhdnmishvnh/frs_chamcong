import os
import sqlite3
import re
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from calendar import monthrange
from flask import render_template_string

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Tạo thư mục uploads nếu chưa có
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

###############################################################################
# Hàm kiểm tra chuỗi có phải bcrypt-hash không
###############################################################################
def is_bcrypt_hash(text):
    return bool(re.match(r'^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$', text))

###############################################################################
# Khởi tạo DB
###############################################################################
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Departments (
            DepartmentID INTEGER PRIMARY KEY AUTOINCREMENT,
            DepartmentName TEXT NOT NULL
        )
    ''')

    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("DROP TABLE IF EXISTS Employees;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Employees (
            EmployeeID TEXT PRIMARY KEY,
            FullName TEXT NOT NULL,
            ContactInfo TEXT NOT NULL,
            FaceImagePath TEXT NOT NULL,
            DepartmentID INTEGER,
            RemainingLeaveDays INTEGER DEFAULT 0,
            FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            EmployeeID TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            AttendanceID INTEGER PRIMARY KEY AUTOINCREMENT,
            EmployeeID TEXT NOT NULL,
            CheckInTime TEXT,
            CheckOutTime TEXT,
            Date TEXT NOT NULL,
            Status TEXT NOT NULL,
            CheckinImagePath TEXT,
            CheckoutImagePath TEXT,
            EvidenceImagePath TEXT,
            ModifiedBy TEXT,
            ModifiedAt TEXT
        )
    ''')

    # Mẫu phòng ban
    cursor.execute("SELECT COUNT(*) FROM Departments")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO Departments (DepartmentName) VALUES (?)", ('Kinh doanh',))
        cursor.execute("INSERT INTO Departments (DepartmentName) VALUES (?)", ('Nhân sự',))

    # Mẫu nhân viên
    cursor.execute("SELECT COUNT(*) FROM Employees")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO Employees (EmployeeID, FullName, ContactInfo, FaceImagePath, DepartmentID, RemainingLeaveDays)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("NV001", "Nguyễn Văn A", "0901234567", "uploads/default1.jpg", 1, 5))

    # Mẫu user admin (bcrypt)
    cursor.execute("SELECT COUNT(*) FROM Users")
    if cursor.fetchone()[0] == 0:
        hashed_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
        hashed_password_text = hashed_password.decode('utf-8')
        cursor.execute('''
            INSERT INTO Users (Username, Password)
            VALUES (?, ?)
        ''', ("admin", hashed_password_text))

    conn.commit()
    conn.close()

init_db()

###############################################################################
# Fallback check_login
###############################################################################
def check_login(username, password):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT Password FROM Users WHERE Username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row:
        stored_pw = row[0]
        if is_bcrypt_hash(stored_pw):
            return bcrypt.checkpw(password.encode('utf-8'), stored_pw.encode('utf-8'))
        else:
            return (password == stored_pw)
    return False

###############################################################################
# LOGIN ( '/' và '/login' dùng chung )
###############################################################################
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if check_login(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('employee_list'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'danger')
    return render_template('login.html')

###############################################################################
# EMPLOYEE LIST
###############################################################################
@app.route('/employee_list')
def employee_list():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.EmployeeID, e.FullName, e.ContactInfo, e.FaceImagePath, d.DepartmentName
        FROM Employees e
        LEFT JOIN Departments d ON e.DepartmentID = d.DepartmentID
    ''')
    employees = cursor.fetchall()
    conn.close()
    return render_template('employee_list.html', employees=employees)

###############################################################################
# LOGOUT
###############################################################################
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

###############################################################################
#region ADD_EMPLOYEE
###############################################################################
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        employee_id   = request.form['employee_id']
        full_name     = request.form['full_name']
        department_id = request.form['department_id']
        contact_info  = request.form['contact_info']

        import json, base64
        from werkzeug.utils import secure_filename

        face_images_json = request.form.get('face_images', '[]')
        face_images_list = json.loads(face_images_json)
        image_paths = []

        # Decode và ghi file ảnh
        for idx, base64_img in enumerate(face_images_list):
            if not base64_img:
                continue
            header, data = base64_img.split(',', 1)
            img_bytes = base64.b64decode(data)
            filename = f"{secure_filename(employee_id)}_{idx}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
            image_paths.append(f"uploads/{filename}")

        if len(image_paths) < 1:
            flash('Vui lòng chụp ít nhất 1 ảnh khuôn mặt!', 'danger')
            return redirect(url_for('add_employee'))

        face_image_path = image_paths[0]

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO Employees (EmployeeID, FullName, FaceImagePath, ContactInfo, DepartmentID, RemainingLeaveDays)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_id, full_name, face_image_path, contact_info, department_id, 0))
            conn.commit()
        except sqlite3.IntegrityError:
            # Nếu trùng mã nhân viên => báo lỗi
            flash('Mã nhân viên đã tồn tại, vui lòng nhập mã khác!', 'danger')
            conn.rollback()
            conn.close()
            return redirect(url_for('add_employee'))

        conn.close()
        flash('Thêm nhân viên thành công!', 'success')
        return redirect(url_for('employee_list'))

    # GET => hiển thị form
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DepartmentID, DepartmentName FROM Departments')
    departments = cursor.fetchall()
    conn.close()
    return render_template('add_employee.html', departments=departments)
###############################################################################
#endregion ADD_EMPLOYEE
###############################################################################


###############################################################################
# EDIT EMPLOYEE (mới thêm)
###############################################################################
@app.route('/edit_employee/<string:id>', methods=['GET', 'POST'])
def edit_employee(id):
    """
    Sửa thông tin nhân viên. Bổ sung tính năng chụp 80 ảnh.
    Nếu user chụp ảnh mới => update FaceImagePath. Nếu không => giữ ảnh cũ.
    """

    # Kiểm tra đăng nhập
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Mở kết nối DB
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # ========================== SỬA TỪ ĐÂY ==========================
    if request.method == 'POST':
        # Lấy dữ liệu form
        employee_id_form = request.form['employee_id']   # user có thể thay ID nếu bạn cho phép
        full_name       = request.form['full_name']
        contact_info    = request.form['contact_info']
        department_id   = request.form['department_id']

        # Chuẩn bị decode ảnh base64
        import json, base64
        from werkzeug.utils import secure_filename

        face_images_json = request.form.get('face_images', '[]')
        face_images_list = json.loads(face_images_json)  # Mảng base64
        image_paths = []

        # Nếu user có chụp ảnh => decode, ghi file
        for idx, base64_img in enumerate(face_images_list):
            if not base64_img:
                continue
            header, data = base64_img.split(',', 1)
            img_bytes = base64.b64decode(data)
            filename = f"{secure_filename(id)}_{idx}.jpg"  # id = EmployeeID cũ
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
            image_paths.append(f"uploads/{filename}")

        # Nếu có ảnh mới => update FaceImagePath = ảnh đầu
        if len(image_paths) > 0:
            face_image_path = image_paths[0]
            cursor.execute('''
                UPDATE Employees
                SET EmployeeID=?, FullName=?, ContactInfo=?, DepartmentID=?, FaceImagePath=?
                WHERE EmployeeID=?
            ''', (employee_id_form, full_name, contact_info, department_id, face_image_path, id))
        else:
            # Không chụp => giữ FaceImagePath cũ
            cursor.execute('''
                UPDATE Employees
                SET EmployeeID=?, FullName=?, ContactInfo=?, DepartmentID=?
                WHERE EmployeeID=?
            ''', (employee_id_form, full_name, contact_info, department_id, id))

        conn.commit()
        conn.close()

        flash('Cập nhật nhân viên thành công!', 'success')
        return redirect(url_for('employee_list'))

    else:
        # GET => Lấy thông tin cũ
        cursor.execute('''
            SELECT EmployeeID, FullName, ContactInfo, DepartmentID, FaceImagePath
            FROM Employees
            WHERE EmployeeID=?
        ''', (id,))
        emp = cursor.fetchone()

        # Lấy phòng ban
        cursor.execute('SELECT DepartmentID, DepartmentName FROM Departments')
        departments = cursor.fetchall()
        conn.close()
        # ========================== ĐẾN ĐÂY ==========================

        if not emp:
            flash('Không tìm thấy nhân viên để sửa!', 'danger')
            return redirect(url_for('employee_list'))

        # Render template edit_employee.html
        # emp = (EmployeeID, FullName, ContactInfo, DepartmentID, FaceImagePath)
        # departments = [(DeptID, DeptName), ...]
        return render_template('edit_employee.html', emp=emp, departments=departments)

###############################################################################
# FACE RECOGNITION
###############################################################################
@app.route('/face_recognition', methods=['GET', 'POST'])
def face_recognition():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        flash('Chưa tích hợp mô hình nhận diện. Vui lòng kiểm tra lại!', 'info')
        return redirect(url_for('attendance_history'))
    return render_template('face_recognition.html')

###############################################################################
# ATTENDANCE HISTORY
###############################################################################
@app.route('/attendance_history')
def attendance_history():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT DepartmentID, DepartmentName FROM Departments')
    departments = cursor.fetchall()

    current_month = datetime.now().month
    current_year = datetime.now().year
    month_filter = request.args.get('month_filter', str(current_month))
    year_filter = request.args.get('year_filter', str(current_year))

    conn.close()
    return render_template('attendance_history.html',
                           departments=departments,
                           month_filter=month_filter,
                           year_filter=year_filter)

###############################################################################
# API: ATTENDANCE CALENDAR
###############################################################################
@app.route('/api/attendance_calendar', methods=['GET'])
def get_attendance_calendar():
    """Trả về JSON danh sách chấm công dạng lịch."""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    month_filter = int(request.args.get('month_filter', datetime.now().month))
    year_filter = int(request.args.get('year_filter', datetime.now().year))

    num_days_in_month = monthrange(year_filter, month_filter)[1]
    start_date = f'{year_filter}-{month_filter:02d}-01'
    end_date = f'{year_filter}-{month_filter:02d}-{num_days_in_month}'

    cursor.execute('SELECT EmployeeID, FullName, RemainingLeaveDays FROM Employees')
    employees = cursor.fetchall()

    cursor.execute('''
        SELECT a.EmployeeID, a.Date, a.Status, a.CheckInTime, a.CheckOutTime, a.CheckinImagePath, a.CheckoutImagePath
        FROM Attendance a
        WHERE a.Date BETWEEN ? AND ?
    ''', (start_date, end_date))
    attendance_records = cursor.fetchall()

    attendance_dict = {}
    for record in attendance_records:
        emp_id, date, status, checkin_time, checkout_time, checkin_image, checkout_image = record
        if emp_id not in attendance_dict:
            attendance_dict[emp_id] = {}
        attendance_dict[emp_id][date] = {
            'status': status,
            'checkin_time': checkin_time,
            'checkout_time': checkout_time,
            'checkin_image': checkin_image,
            'checkout_image': checkout_image
        }

    calendar_data = []
    for idx, emp in enumerate(employees, 1):
        emp_id, full_name, remaining_leave_days = emp
        paid_days = 0
        days = []
        for day in range(1, num_days_in_month + 1):
            date_str = f'{year_filter}-{month_filter:02d}-{day:02d}'
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day_of_week = date_obj.weekday()

            status = ''
            checkin_time = None
            checkout_time = None
            checkin_image = None
            checkout_image = None
            if day_of_week in [5, 6]:  # T7, CN
                status = 'Weekend'
            else:
                if emp_id in attendance_dict and date_str in attendance_dict[emp_id]:
                    st = attendance_dict[emp_id][date_str]
                    status = st['status']
                    checkin_time = st['checkin_time']
                    checkout_time = st['checkout_time']
                    checkin_image = st['checkin_image']
                    checkout_image = st['checkout_image']
                    if status in ['OnTime', 'M', 'S']:
                        paid_days += 1
                else:
                    status = 'P'

            days.append({
                'date': date_str,
                'status': status,
                'checkin_time': checkin_time,
                'checkout_time': checkout_time,
                'checkin_image': checkin_image,
                'checkout_image': checkout_image
            })

        calendar_data.append({
            'stt': idx,
            'employee_id': emp_id,
            'full_name': full_name,
            'remaining_leave_days': remaining_leave_days,
            'paid_days': paid_days,
            'days': days
        })

    conn.close()

    return jsonify({
        'success': True,
        'start_date': start_date,
        'end_date': end_date,
        'num_days': num_days_in_month,
        'calendar_data': calendar_data
    })


###############################################################################
# API: ATTENDANCE DETAIL
###############################################################################
@app.route('/api/attendance_detail', methods=['GET'])
def get_attendance_detail():
    """Trả về JSON chi tiết 1 ngày công của 1 nhân viên."""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    employee_id = request.args.get('employee_id')
    date = request.args.get('date')

    cursor.execute('''
        SELECT e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status, a.CheckinImagePath, a.CheckoutImagePath
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        WHERE a.EmployeeID = ? AND a.Date = ?
    ''', (employee_id, date))
    record = cursor.fetchone()
    conn.close()

    if record:
        (full_name, checkin_time, checkout_time,
         date_str, status, checkin_image, checkout_image) = record
        return jsonify({
            'success': True,
            'full_name': full_name,
            'date': date_str,
            'status': status,
            'checkin_time': checkin_time,
            'checkout_time': checkout_time,
            'checkin_image': url_for('static', filename=checkin_image) if checkin_image else None,
            'checkout_image': url_for('static', filename=checkout_image) if checkout_image else None
        })
    return jsonify({'success': False, 'message': 'No data found'})


###############################################################################
# API: MANUAL CHECKIN POPUP
###############################################################################
@app.route('/api/manual_checkin_popup', methods=['POST'])
def manual_checkin_popup():
    """Chấm công thủ công từ popup."""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    employee_id = request.form['employee_id']
    date = request.form['date']
    checkin_time = request.form['checkin_time']
    checkout_time = request.form['checkout_time']
    evidence_image = request.files.get('evidence_image')
    status = request.form['status']

    # Chuyển đổi giờ sang format đầy đủ
    full_date = datetime.strptime(date, '%Y-%m-%d')
    if checkin_time:
        hh, mm = map(int, checkin_time.split(':'))
        checkin_time = full_date.replace(hour=hh, minute=mm, second=0).strftime('%Y-%m-%d %H:%M:%S')
    if checkout_time:
        hh, mm = map(int, checkout_time.split(':'))
        checkout_time = full_date.replace(hour=hh, minute=mm, second=0).strftime('%Y-%m-%d %H:%M:%S')

    # Xác định trạng thái
    final_status = status
    if status == 'OnTime':
        # Kiểm tra đi muộn hoặc về sớm
        c_in_diff = (datetime.strptime(checkin_time, '%Y-%m-%d %H:%M:%S')
                     - datetime.strptime(f'{date} 08:00:00', '%Y-%m-%d %H:%M:%S')).total_seconds() / 60
        c_out_diff = (datetime.strptime(f'{date} 17:00:00', '%Y-%m-%d %H:%M:%S')
                      - datetime.strptime(checkout_time, '%Y-%m-%d %H:%M:%S')).total_seconds() / 60
        if c_in_diff > 0:
            final_status = 'M'
        elif c_out_diff > 0:
            final_status = 'S'

    # Lưu ảnh evidence
    evidence_image_path = None
    if evidence_image:
        filename = f"evidence_{employee_id}_{date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        evidence_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        evidence_image_path = f"uploads/{filename}"

    # Kiểm tra record Attendance
    cursor.execute('SELECT AttendanceID FROM Attendance WHERE EmployeeID = ? AND Date = ?', (employee_id, date))
    existing = cursor.fetchone()

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if existing:
        cursor.execute('''
            UPDATE Attendance
            SET CheckInTime=?, CheckOutTime=?, Status=?, EvidenceImagePath=?,
                ModifiedBy=?, ModifiedAt=?
            WHERE EmployeeID=? AND Date=?
        ''', (checkin_time, checkout_time, final_status, evidence_image_path,
              session['username'], now_str, employee_id, date))
    else:
        cursor.execute('''
            INSERT INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status,
                                    EvidenceImagePath, ModifiedBy, ModifiedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, checkin_time, checkout_time, date, final_status,
              evidence_image_path, session['username'], now_str))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Chấm công thủ công thành công'})


###############################################################################
# MANUAL CHECKIN (form)
###############################################################################
@app.route('/manual_checkin', methods=['GET', 'POST'])
def manual_checkin():
    """Chấm công thủ công qua form. Yêu cầu đăng nhập."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT EmployeeID, FullName FROM Employees')
    employees = cursor.fetchall()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        checkin_time = request.form['checkin_time']
        checkout_time = request.form['checkout_time']
        date = request.form['date']
        status = 'OnTime'
        checkin_image = request.form.get('checkin_image', '')
        checkout_image = request.form.get('checkout_image', '')
        modified_by = session['username']
        modified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status,
                                    CheckinImagePath, CheckoutImagePath, ModifiedBy, ModifiedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, checkin_time, checkout_time, date, status,
              checkin_image, checkout_image, modified_by, modified_at))
        
        conn.commit()
        conn.close()
        flash('Chấm công thủ công thành công!', 'success')
        return redirect(url_for('attendance_history'))

    conn.close()
    return render_template('manual_checkin.html', employees=employees)


###############################################################################
# REPORT
###############################################################################
@app.route('/report', methods=['GET', 'POST'])
def report():
    """Báo cáo thống kê. Yêu cầu đăng nhập."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT DepartmentID, DepartmentName FROM Departments')
    departments = cursor.fetchall()
    cursor.execute('SELECT EmployeeID, FullName FROM Employees')
    employees = cursor.fetchall()

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    department_filter = 'all'
    employee_filter = 'all'

    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        department_filter = request.form.get('department_filter', 'all')
        employee_filter = request.form.get('employee_filter', 'all')

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else start_date
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else end_date

    start_date_str = start_date.strftime('%Y-%m-%d') if start_date else datetime.now().date().strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d') if end_date else datetime.now().date().strftime('%Y-%m-%d')

    cursor.execute('SELECT COUNT(*) FROM Employees')
    total_employees = cursor.fetchone()[0]

    where_clause = f"WHERE a.Date BETWEEN '{start_date_str}' AND '{end_date_str}'"
    if department_filter != 'all':
        where_clause += f" AND e.DepartmentID = {department_filter}"
    if employee_filter != 'all':
        where_clause += f" AND a.EmployeeID = {employee_filter}"

    # Thống kê chung
    cursor.execute(f'''
        SELECT COUNT(*) as total_days,
               SUM(CASE WHEN a.Status = 'OnTime' THEN 1 ELSE 0 END) as on_time,
               SUM(CASE WHEN a.Status = 'M' THEN 1 ELSE 0 END) as late,
               SUM(CASE WHEN a.Status = 'P' THEN 1 ELSE 0 END) as absent
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        {where_clause}
    ''')
    overview_stats = cursor.fetchone()
    total_days = overview_stats[0] or 0
    on_time_days = overview_stats[1] or 0
    late_days = overview_stats[2] or 0
    absent_days = overview_stats[3] or 0

    on_time_rate = (on_time_days / total_days * 100) if total_days > 0 else 0
    late_rate = (late_days / total_days * 100) if total_days > 0 else 0
    absent_rate = (absent_days / total_days * 100) if total_days > 0 else 0

    # Thống kê theo nhân viên
    cursor.execute(f'''
        SELECT e.EmployeeID, e.FullName,
               COUNT(a.Date) as total_days,
               SUM(CASE WHEN a.CheckInTime IS NOT NULL AND a.CheckOutTime IS NOT NULL 
                        THEN strftime('%s', a.CheckOutTime) - strftime('%s', a.CheckInTime) 
                        ELSE 0 END) / 3600.0 as total_hours,
               SUM(CASE WHEN a.Status = 'OnTime' THEN 1 ELSE 0 END) as on_time,
               SUM(CASE WHEN a.Status = 'M' THEN 1 ELSE 0 END) as late,
               SUM(CASE WHEN a.Status = 'S' THEN 1 ELSE 0 END) as early_leave,
               SUM(CASE WHEN a.Status = 'P' THEN 1 ELSE 0 END) as absent,
               SUM(CASE WHEN a.Status IN ('Q1', 'Q2') THEN 1 ELSE 0 END) as manual
        FROM Employees e
        LEFT JOIN Attendance a ON e.EmployeeID = a.EmployeeID
        {where_clause}
        GROUP BY e.EmployeeID, e.FullName
    ''')
    employee_stats = cursor.fetchall()

    # Chi tiết bản ghi
    cursor.execute(f'''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status,
               a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Employees e
        LEFT JOIN Attendance a ON e.EmployeeID = a.EmployeeID
        {where_clause}
        ORDER BY a.Date DESC
    ''')
    detailed_records = cursor.fetchall()

    # Thống kê theo phòng ban
    cursor.execute(f'''
        SELECT d.DepartmentName,
               COUNT(a.Date) as total_days,
               SUM(CASE WHEN a.Status = 'OnTime' THEN 1 ELSE 0 END) as on_time,
               SUM(CASE WHEN a.Status = 'M' THEN 1 ELSE 0 END) as late,
               SUM(CASE WHEN a.Status = 'P' THEN 1 ELSE 0 END) as absent
        FROM Departments d
        LEFT JOIN Employees e ON d.DepartmentID = e.DepartmentID
        LEFT JOIN Attendance a ON e.EmployeeID = a.EmployeeID
        {where_clause}
        GROUP BY d.DepartmentID, d.DepartmentName
    ''')
    department_stats = cursor.fetchall()

    conn.close()

    has_data = bool(employee_stats or detailed_records or department_stats)

    return render_template('report.html', 
                           departments=departments,
                           employees=employees,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           department_filter=department_filter,
                           employee_filter=employee_filter,
                           total_employees=total_employees,
                           on_time_rate=on_time_rate,
                           late_rate=late_rate,
                           absent_rate=absent_rate,
                           employee_stats=employee_stats,
                           detailed_records=detailed_records,
                           department_stats=department_stats,
                           has_data=has_data)


###############################################################################
# DELETE ATTENDANCE
###############################################################################
@app.route('/delete_attendance/<int:attendance_id>', methods=['POST'])
def delete_attendance(attendance_id):
    """Xóa bản ghi Attendance theo ID."""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Attendance WHERE AttendanceID = ?', (attendance_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Xóa bản ghi thành công!'})


###############################################################################
# UPDATE MANUAL CHECKIN
###############################################################################
@app.route('/update_manual_checkin/<int:attendance_id>', methods=['GET', 'POST'])
def update_manual_checkin(attendance_id):
    """Cập nhật chấm công thủ công."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        checkin_time = request.form['checkin_time']
        checkout_time = request.form['checkout_time']
        date = request.form['date']
        checkin_image = request.form.get('checkin_image', '')
        checkout_image = request.form.get('checkout_image', '')
        modified_by = session['username']
        modified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            UPDATE Attendance
            SET CheckInTime=?, CheckOutTime=?, Date=?, CheckinImagePath=?, CheckoutImagePath=?,
                ModifiedBy=?, ModifiedAt=?
            WHERE AttendanceID=?
        ''', (checkin_time, checkout_time, date, checkin_image, checkout_image,
              modified_by, modified_at, attendance_id))
        conn.commit()
        conn.close()
        flash('Cập nhật chấm công thủ công thành công!', 'success')
        return redirect(url_for('attendance_history'))

    cursor.execute('''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status,
               a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        WHERE a.AttendanceID=?
    ''', (attendance_id,))
    record = cursor.fetchone()
    conn.close()
    return render_template('Nawupdate_manual_checkin.html', record=record)


###############################################################################
# ATTENDANCE DETAIL
###############################################################################
@app.route('/attendance_detail/<int:attendance_id>')
def attendance_detail(attendance_id):
    """Xem chi tiết 1 bản ghi Attendance."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status,
               a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        WHERE a.AttendanceID=?
    ''', (attendance_id,))
    record = cursor.fetchone()
    conn.close()

    if record:
        html = render_template_string('''
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div class="space-y-4">
                    <!-- Info block -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-user text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Tên nhân viên</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[1] }}</p>
                        </div>
                    </div>
                    <!-- Checkin -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-clock text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian vào</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[2] or 'N/A' }}</p>
                        </div>
                    </div>
                    <!-- Checkout -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-clock text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian ra</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[3] or 'N/A' }}</p>
                        </div>
                    </div>
                    <!-- Date -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-calendar-alt text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Ngày</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[4] }}</p>
                        </div>
                    </div>
                    <!-- Status -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-info-circle text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Trạng thái</p>
                            <p class="text-lg font-semibold">
                                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium
                                    {% if record[5] == 'OnTime' %}bg-green-100 text-green-800 bg-opacity-70
                                    {% elif record[5] == 'M' %}bg-red-100 text-red-800 bg-opacity-70
                                    {% elif record[5] == 'S' %}bg-yellow-100 text-yellow-800 bg-opacity-70
                                    {% elif record[5] == 'P' %}bg-gray-100 text-gray-800 bg-opacity-70
                                    {% else %}bg-purple-100 text-purple-800 bg-opacity-70{% endif %}">
                                    {{ record[5] }}
                                </span>
                            </p>
                        </div>
                    </div>
                    <!-- ModifiedBy -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-user-edit text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Cập nhật bởi</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[8] or 'N/A' }}</p>
                        </div>
                    </div>
                    <!-- ModifiedAt -->
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-calendar-check text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian cập nhật</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[9] or 'N/A' }}</p>
                        </div>
                    </div>
                </div>
                <!-- Images -->
                <div class="space-y-6">
                    <div>
                        <p class="text-sm text-gray-500 mb-2">Ảnh vào</p>
                        {% if record[6] %}
                            <img src="{{ url_for('static', filename=record[6]) }}" alt=\"Ảnh vào\"
                                 class=\"w-full h-48 object-cover rounded-lg shadow-md\">
                        {% else %}
                            <div class=\"w-full h-48 flex items-center justify-center bg-gray-100 rounded-lg shadow-md\">
                                <p class=\"text-gray-500\">Không có ảnh</p>
                            </div>
                        {% endif %}
                    </div>
                    <div>
                        <p class=\"text-sm text-gray-500 mb-2\">Ảnh ra</p>
                        {% if record[7] %}
                            <img src=\"{{ url_for('static', filename=record[7]) }}\" alt=\"Ảnh ra\"
                                 class=\"w-full h-48 object-cover rounded-lg shadow-md\">
                        {% else %}
                            <div class=\"w-full h-48 flex items-center justify-center bg-gray-100 rounded-lg shadow-md\">
                                <p class=\"text-gray-500\">Không có ảnh</p>
                            </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        ''', record=record)
        return html

    return "Không tìm thấy bản ghi!"

###############################################################################
# DELETE EMPLOYEE
###############################################################################
@app.route('/delete_employee/<string:id>', methods=['POST'])
def delete_employee(id):
    """Xóa nhân viên theo EmployeeID (TEXT)."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Employees WHERE EmployeeID = ?", (id,))
    conn.commit()
    conn.close()
    flash("Xóa nhân viên thành công!", "success")
    return redirect(url_for('employee_list'))

###############################################################################
# MAIN
###############################################################################
if __name__ == '__main__':
    app.run(debug=True)