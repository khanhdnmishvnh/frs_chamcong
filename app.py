import os
import sqlite3
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from calendar import monthrange
from flask import render_template_string

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Tạo thư mục uploads nếu chưa tồn tại
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Kết nối và tạo cơ sở dữ liệu
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
# Tạo bảng Employees với EmployeeCode
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Employees (
            EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
            EmployeeCode TEXT UNIQUE NOT NULL,
            FullName TEXT NOT NULL,
            FaceID TEXT UNIQUE NOT NULL,
            FaceImagePath TEXT NOT NULL,
            DepartmentID INTEGER,
            RemainingLeaveDays INTEGER DEFAULT 0,
            FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
        )
    ''')
    # Tạo bảng Departments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Departments (
            DepartmentID INTEGER PRIMARY KEY AUTOINCREMENT,
            DepartmentName TEXT NOT NULL
        )
    ''')

    # Tạo bảng Employees với thông tin nhân viên và đường dẫn ảnh khuôn mặt
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Employees (
            EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
            FullName TEXT NOT NULL,
            FaceID TEXT UNIQUE NOT NULL,
            FaceImagePath TEXT NOT NULL,
            DepartmentID INTEGER,
            FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
        )
    ''')

    # Tạo bảng Attendance để lưu dữ liệu chấm công
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            AttendanceID INTEGER PRIMARY KEY AUTOINCREMENT,
            EmployeeID INTEGER NOT NULL,
            CheckInTime TEXT,
            CheckOutTime TEXT,
            Date TEXT NOT NULL,
            Status TEXT NOT NULL,
            CheckinImagePath TEXT,
            CheckoutImagePath TEXT,
            FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID)
        )
    ''')

    # Tạo bảng Users để quản lý đăng nhập
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            EmployeeID INTEGER,
            FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID)
        )
    ''')

    # Tạo thư mục uploads nếu chưa tồn tại để lưu ảnh khuôn mặt nhân viên
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    conn.commit()
    conn.close()
from werkzeug.utils import secure_filename  # Dùng để bảo mật tên file ảnh khi tải lên

# Route để thêm nhân viên
def generate_employee_code():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Lấy EmployeeCode mới nhất
    cursor.execute("SELECT EmployeeCode FROM Employees ORDER BY EmployeeID DESC LIMIT 1")
    last_code = cursor.fetchone()
    
    conn.close()
    
    if last_code and last_code[0]:
        last_number = int(last_code[0][2:])  # Lấy số từ "NV01"
        new_code = f"NV{last_number + 1:02d}"  # Tạo mã mới, ví dụ: "NV02"
    else:
        new_code = "NV01"  # Nếu chưa có nhân viên nào, bắt đầu từ NV01
    
    return new_code

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        employee_code = generate_employee_code()  # Sinh mã EmployeeCode tự động
        full_name = request.form['full_name']
        department_id = request.form['department_id']
        contact_info = request.form['contact_info']  # Lấy dữ liệu địa chỉ nhân viên
        
        # Tạo FaceID duy nhất
        face_id = f"face_{int(datetime.timestamp(datetime.now()))}"
        
        # Kiểm tra và lưu ảnh khuôn mặt
        image_paths = []
        files = request.files.getlist('face_images')
        for file in files:
            if file:
                filename = secure_filename(f"{face_id}_{len(image_paths) + 1}.jpg")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_paths.append(f"uploads/{filename}")
        
        if len(image_paths) < 80:
            flash('Cần ít nhất 80 ảnh để đăng ký khuôn mặt!', 'danger')
            return redirect(url_for('add_employee'))
        
        face_image_path = image_paths[0]  # Chọn ảnh đầu tiên làm ảnh đại diện
        
        # Thêm nhân viên vào database
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Employees (EmployeeCode, FullName, FaceID, FaceImagePath, DepartmentID, ContactInfo) 
            VALUES (?, ?, ?, ?, ?, ?)''', 
            (employee_code, full_name, face_id, face_image_path, department_id, contact_info))
        conn.commit()
        conn.close()
        
        flash(f'Nhân viên {full_name} đã được thêm với mã {employee_code}!', 'success')
        return redirect(url_for('add_employee'))
    
    # Lấy danh sách phòng ban
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DepartmentID, DepartmentName FROM Departments')
    departments = cursor.fetchall()
    conn.close()
    
    return render_template('add_employee.html', departments=departments)

    # Thêm dữ liệu mẫu
    hashed_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
    
    # Thêm phòng ban
    cursor.execute('INSERT OR IGNORE INTO Departments (DepartmentName) VALUES (?)', ('Kinh doanh',))
    cursor.execute('INSERT OR IGNORE INTO Departments (DepartmentName) VALUES (?)', ('Nhân sự',))

    # Thêm nhân viên
    cursor.execute('INSERT OR IGNORE INTO Employees (FullName, FaceID, FaceImagePath, DepartmentID, RemainingLeaveDays) VALUES (?, ?, ?, ?, ?)',
                   ('Đỗ Ngọc Khánh', 'face_001', 'faces/emp1.jpg', 1, 3))

    # Thêm người dùng
    cursor.execute('INSERT OR IGNORE INTO Users (Username, Password, EmployeeID) VALUES (?, ?, ?)',
                   ('admin', hashed_password, 1))

    # Thêm dữ liệu chấm công mẫu cho tháng 3/2025
    for day in range(1, 16):  # 01/03/2025 đến 15/03/2025
        date_str = f'2025-03-{day:02d}'
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        day_of_week = date_obj.weekday()
        if day_of_week == 5 or day_of_week == 6:  # Thứ 7, Chủ nhật
            cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                           (1, None, None, date_str, 'Weekend'))
        else:
            cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                           (1, f'2025-03-{day:02d} 08:00:00', f'2025-03-{day:02d} 17:00:00', date_str, 'OnTime'))
    
    # Thêm các trường hợp đặc biệt
    cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                   (1, None, None, '2025-03-18', 'P'))  # Không chấm công cả vào và ra
    cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                   (1, '2025-03-19 08:00:00', None, '2025-03-19', 'Q2'))  # Quên chấm công lúc ra
    cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                   (1, None, '2025-03-20 17:00:00', '2025-03-20', 'Q1'))  # Quên chấm công lúc vào
    cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                   (1, '2025-03-21 08:30:00', '2025-03-21 17:00:00', '2025-03-21', 'M'))  # Đi làm muộn
    cursor.execute('INSERT OR IGNORE INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status) VALUES (?, ?, ?, ?, ?)',
                   (1, '2025-03-22 08:00:00', '2025-03-22 16:30:00', '2025-03-22', 'S'))  # Về sớm

    conn.commit()
    conn.close()

init_db()

def check_login(username, password):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Password FROM Users WHERE Username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0]):
        return True
    return False

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if check_login(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('face_recognition'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/face_recognition', methods=['GET', 'POST'])
def face_recognition():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        flash('Chưa tích hợp mô hình nhận diện. Vui lòng kiểm tra lại!', 'info')
        return redirect(url_for('attendance_history'))
    return render_template('face_recognition.html')

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
    return render_template('attendance_history.html', departments=departments, 
                          month_filter=month_filter, year_filter=year_filter)

# API để lấy danh sách chấm công dạng lịch
@app.route('/api/attendance_calendar', methods=['GET'])
def get_attendance_calendar():
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
        employee_id, date, status, checkin_time, checkout_time, checkin_image, checkout_image = record
        if employee_id not in attendance_dict:
            attendance_dict[employee_id] = {}
        attendance_dict[employee_id][date] = {
            'status': status,
            'checkin_time': checkin_time,
            'checkout_time': checkout_time,
            'checkin_image': checkin_image,
            'checkout_image': checkout_image
        }

    calendar_data = []
    for idx, employee in enumerate(employees, 1):
        employee_id, full_name, remaining_leave_days = employee
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
            if day_of_week == 5 or day_of_week == 6:  # Thứ 7, Chủ nhật
                status = 'Weekend'
            else:
                if employee_id in attendance_dict and date_str in attendance_dict[employee_id]:
                    status_data = attendance_dict[employee_id][date_str]
                    status = status_data['status']
                    checkin_time = status_data['checkin_time']
                    checkout_time = status_data['checkout_time']
                    checkin_image = status_data['checkin_image']
                    checkout_image = status_data['checkout_image']
                    if status == 'OnTime' or status == 'M' or status == 'S':
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
            'employee_id': employee_id,
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

# API để lấy chi tiết ngày công
@app.route('/api/attendance_detail', methods=['GET'])
def get_attendance_detail():
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
        full_name, checkin_time, checkout_time, date, status, checkin_image, checkout_image = record
        return jsonify({
            'success': True,
            'full_name': full_name,
            'date': date,
            'status': status,
            'checkin_time': checkin_time,
            'checkout_time': checkout_time,
            'checkin_image': url_for('static', filename=checkin_image) if checkin_image else None,
            'checkout_image': url_for('static', filename=checkout_image) if checkout_image else None
        })
    return jsonify({'success': False, 'message': 'No data found'})

# API để chấm công thủ công từ popup
@app.route('/api/manual_checkin_popup', methods=['POST'])
def manual_checkin_popup():
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

    # Chuyển đổi giờ thành định dạng đầy đủ
    full_date = datetime.strptime(date, '%Y-%m-%d')
    if checkin_time:
        checkin_datetime = full_date.replace(hour=int(checkin_time.split(':')[0]), minute=int(checkin_time.split(':')[1]), second=0)
        checkin_time = checkin_datetime.strftime('%Y-%m-%d %H:%M:%S')
    if checkout_time:
        checkout_datetime = full_date.replace(hour=int(checkout_time.split(':')[0]), minute=int(checkout_time.split(':')[1]), second=0)
        checkout_time = checkout_datetime.strftime('%Y-%m-%d %H:%M:%S')

    # Xác định trạng thái cuối cùng dựa trên thời gian
    final_status = status
    if status == 'OnTime':
        checkin_diff = (datetime.strptime(checkin_time, '%Y-%m-%d %H:%M:%S') - datetime.strptime(f'{date} 08:00:00', '%Y-%m-%d %H:%M:%S')).total_seconds() / 60
        checkout_diff = (datetime.strptime(f'{date} 17:00:00', '%Y-%m-%d %H:%M:%S') - datetime.strptime(checkout_time, '%Y-%m-%d %H:%M:%S')).total_seconds() / 60
        if checkin_diff > 0:
            final_status = 'M'
        elif checkout_diff > 0:
            final_status = 'S'

    # Lưu ảnh minh chứng nếu có
    evidence_image_path = None
    if evidence_image:
        filename = f"evidence_{employee_id}_{date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        evidence_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        evidence_image_path = f"uploads/{filename}"

    # Kiểm tra xem bản ghi đã tồn tại chưa
    cursor.execute('SELECT AttendanceID FROM Attendance WHERE EmployeeID = ? AND Date = ?', (employee_id, date))
    existing_record = cursor.fetchone()

    if existing_record:
        cursor.execute('''
            UPDATE Attendance SET CheckInTime = ?, CheckOutTime = ?, Status = ?, EvidenceImagePath = ?, ModifiedBy = ?, ModifiedAt = ?
            WHERE EmployeeID = ? AND Date = ?
        ''', (checkin_time, checkout_time, final_status, evidence_image_path, session['username'], 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), employee_id, date))
    else:
        cursor.execute('''
            INSERT INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status, EvidenceImagePath, ModifiedBy, ModifiedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, checkin_time, checkout_time, date, final_status, evidence_image_path, 
              session['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Chấm công thủ công thành công'})

@app.route('/manual_checkin', methods=['GET', 'POST'])
def manual_checkin():
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
            INSERT INTO Attendance (EmployeeID, CheckInTime, CheckOutTime, Date, Status, CheckinImagePath, CheckoutImagePath, ModifiedBy, ModifiedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, checkin_time, checkout_time, date, status, checkin_image, checkout_image, modified_by, modified_at))
        
        conn.commit()
        conn.close()
        flash('Chấm công thủ công thành công!', 'success')
        return redirect(url_for('attendance_history'))

    conn.close()
    return render_template('manual_checkin.html', employees=employees)

@app.route('/report', methods=['GET', 'POST'])
def report():
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

    cursor.execute(f'''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status, a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Employees e
        LEFT JOIN Attendance a ON e.EmployeeID = a.EmployeeID
        {where_clause}
        ORDER BY a.Date DESC
    ''')
    detailed_records = cursor.fetchall()

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

@app.route('/delete_attendance/<int:attendance_id>', methods=['POST'])
def delete_attendance(attendance_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Attendance WHERE AttendanceID = ?', (attendance_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Xóa bản ghi thành công!'})

@app.route('/update_manual_checkin/<int:attendance_id>', methods=['GET', 'POST'])
def update_manual_checkin(attendance_id):
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
            UPDATE Attendance SET CheckInTime = ?, CheckOutTime = ?, Date = ?, CheckinImagePath = ?, CheckoutImagePath = ?, ModifiedBy = ?, ModifiedAt = ?
            WHERE AttendanceID = ?
        ''', (checkin_time, checkout_time, date, checkin_image, checkout_image, modified_by, modified_at, attendance_id))
        conn.commit()
        conn.close()
        flash('Cập nhật chấm công thủ công thành công!', 'success')
        return redirect(url_for('attendance_history'))

    cursor.execute('''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status, a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        WHERE a.AttendanceID = ?
    ''', (attendance_id,))
    record = cursor.fetchone()
    conn.close()
    return render_template(' Nawupdate_manual_checkin.html', record=record)

@app.route('/attendance_detail/<int:attendance_id>')
def attendance_detail(attendance_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.AttendanceID, e.FullName, a.CheckInTime, a.CheckOutTime, a.Date, a.Status, a.CheckinImagePath, a.CheckoutImagePath, a.ModifiedBy, a.ModifiedAt
        FROM Attendance a
        JOIN Employees e ON a.EmployeeID = e.EmployeeID
        WHERE a.AttendanceID = ?
    ''', (attendance_id,))
    record = cursor.fetchone()
    conn.close()

    if record:
        html = render_template_string('''
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div class="space-y-4">
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-user text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Tên nhân viên</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[1] }}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-clock text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian vào</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[2] or 'N/A' }}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-clock text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian ra</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[3] or 'N/A' }}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-calendar-alt text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Ngày</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[4] }}</p>
                        </div>
                    </div>
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
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-user-edit text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Cập nhật bởi</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[8] or 'N/A' }}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-calendar-check text-indigo-500"></i>
                        <div>
                            <p class="text-sm text-gray-500">Thời gian cập nhật</p>
                            <p class="text-lg font-semibold text-gray-800">{{ record[9] or 'N/A' }}</p>
                        </div>
                    </div>
                </div>
                <div class="space-y-6">
                    <div>
                        <p class="text-sm text-gray-500 mb-2">Ảnh vào</p>
                        {% if record[6] %}
                            <img src="{{ url_for('static', filename=record[6]) }}" alt="Ảnh vào" class="w-full h-48 object-cover rounded-lg shadow-md">
                        {% else %}
                            <div class="w-full h-48 flex items-center justify-center bg-gray-100 rounded-lg shadow-md">
                                <p class="text-gray-500">Không có ảnh</p>
                            </div>
                        {% endif %}
                    </div>
                    <div>
                        <p class="text-sm text-gray-500 mb-2">Ảnh ra</p>
                        {% if record[7] %}
                            <img src="{{ url_for('static', filename=record[7]) }}" alt="Ảnh ra" class="w-full h-48 object-cover rounded-lg shadow-md">
                        {% else %}
                            <div class="w-full h-48 flex items-center justify-center bg-gray-100 rounded-lg shadow-md">
                                <p class="text-gray-500">Không có ảnh</p>
                            </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        ''', record=record)
        return html
    return "Không tìm thấy bản ghi!"

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)