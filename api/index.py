def convert_10_to_4_scale(diem_10):
    """
    Hàm trợ giúp đề xuất: Chuyển điểm 10 sang điểm 4.
    (Dựa trên thang điểm tín chỉ thông thường)
    """
    if diem_10 >= 8.5:
        return 4.0  # A
    elif diem_10 >= 8.0:
        return 3.5  # B+
    elif diem_10 >= 7.0:
        return 3.0  # B
    elif diem_10 >= 6.5:
        return 2.5  # C+
    elif diem_10 >= 5.5:
        return 2.0  # C
    elif diem_10 >= 5.0:
        return 1.5  # D+
    elif diem_10 >= 4.0:
        return 1.0  # D
    else:
        return 0.0  # F
# === THÊM HÀM HELPER PHÂN LOẠI GPA (HỆ 10) ===
def classify_gpa_10(gpa):
    if gpa >= 9.0:
        return "Xuất sắc"
    elif gpa >= 8.0:
        return "Giỏi"
    elif gpa >= 6.5:
        return "Khá"
    elif gpa >= 5.0:
        return "Trung bình"
    else:
        return "Yếu"
# ===============================================
import os
import enum
import pandas as pd
import io
from flask import send_file
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
# from sqlalchemy_utils import ENUMType # <-- DÒNG NÀY ĐÃ BỊ XÓA
from sqlalchemy.sql import func, case, literal_column
from sqlalchemy import select, and_ # Cần cho các truy vấn phức tạp
from functools import wraps # Dùng để tạo decorator kiểm tra vai trò

# --- 1. CẤU HÌNH ỨNG DỤNG ---

basedir = os.path.abspath(os.path.dirname(__file__))

# === THAY THẾ DÒNG app = Flask(__name__) BẰNG KHỐI CODE NÀY ===

# Tính toán đường dẫn thư mục gốc (cha của thư mục 'api')
project_root = os.path.abspath(os.path.join(basedir, '..'))
# Tạo đường dẫn đầy đủ đến thư mục templates và static
template_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(project_root, 'static')

# Khởi tạo Flask và chỉ định vị trí thư mục templates, static
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Cập nhật đường dẫn CSDL để sử dụng project_root (Quan trọng!)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(project_root, 'qlsv.db')


# Khóa bí mật để bảo vệ session
app.config['SECRET_KEY'] = 'mot-khoa-bi-mat-rat-manh-theo-yeu-cau-bao-mat'
# Cấu hình đường dẫn CSDL SQLite
project_root = os.path.abspath(os.path.join(basedir, '..'))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(project_root, 'qlsv.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)

# Cấu hình: Nếu người dùng chưa đăng nhập, chuyển hướng đến trang 'login'
login_manager.login_view = 'login' # 
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'info' # CSS class cho thông báo (nếu dùng Bootstrap)


# --- 2. ĐỊNH NGHĨA MODEL (CSDL) ---
# Tuân thủ chặt chẽ đặc tả CSDL 

# Dùng Enum cho VaiTro như đặc tả 
class VaiTroEnum(enum.Enum):
    SINHVIEN = 'SINHVIEN'
    GIAOVIEN = 'GIAOVIEN'

# 2.1. Bảng TaiKhoan 
class TaiKhoan(UserMixin, db.Model):
    __tablename__ = 'tai_khoan'
    username = db.Column(db.String(50), primary_key=True) # 
    password = db.Column(db.String(255), nullable=False) # 
    
    # === ĐÃ SỬA LỖI IMPORT TẠI ĐÂY ===
    # Đã thay thế ENUMType bằng db.Enum 
    vai_tro = db.Column(db.Enum(VaiTroEnum), nullable=False) 

    # Triển khai UserMixin cho Flask-Login
    def get_id(self):
        return self.username

    # Hàm băm mật khẩu (dùng bcrypt như yêu cầu) 
    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    # Hàm kiểm tra mật khẩu
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

# 2.2. Bảng SinhVien 
class SinhVien(db.Model):
    __tablename__ = 'sinh_vien'
    ma_sv = db.Column(db.String(50), db.ForeignKey('tai_khoan.username', ondelete='CASCADE'), primary_key=True)
    ho_ten = db.Column(db.String(100), nullable=False)
    ngay_sinh = db.Column(db.Date)
    lop = db.Column(db.String(50))
    khoa = db.Column(db.String(100))
    
    # === CẬP NHẬT MỚI ===
    email = db.Column(db.String(150), unique=True, nullable=True)
    location = db.Column(db.String(200), nullable=True) # (Địa chỉ/Vị trí)
    # ====================

    # Định nghĩa quan hệ 1-1 với TaiKhoan
    # Khi xóa SinhVien, 'tai_khoan' liên quan cũng bị xóa (cascade)
    tai_khoan = db.relationship('TaiKhoan', backref=db.backref('sinh_vien', uselist=False, cascade='all, delete-orphan'), foreign_keys=[ma_sv])
    
    # Quan hệ 1-N với KetQua
    # Khi xóa SinhVien, các bản ghi KetQua cũng bị xóa (theo logic yêu cầu )
    ket_qua_list = db.relationship('KetQua', backref='sinh_vien', lazy=True, cascade='all, delete-orphan', foreign_keys='KetQua.ma_sv')


# 2.3. Bảng MonHoc 
class MonHoc(db.Model):
    __tablename__ = 'mon_hoc'
    ma_mh = db.Column(db.String(50), primary_key=True)
    ten_mh = db.Column(db.String(100), nullable=False)
    so_tin_chi = db.Column(db.Integer, nullable=False)
    
    # Quan hệ 1-N với KetQua
    ket_qua_list = db.relationship('KetQua', backref='mon_hoc', lazy=True, cascade='all, delete-orphan', foreign_keys='KetQua.ma_mh')


# 2.4. Bảng KetQua 
class KetQua(db.Model):
    __tablename__ = 'ket_qua'
    # Khóa chính tổng hợp (MaSV, MaMH) 
    # ondelete='CASCADE' để khi xóa SinhVien hoặc MonHoc, điểm cũng bị xóa.
    ma_sv = db.Column(db.String(50), db.ForeignKey('sinh_vien.ma_sv', ondelete='CASCADE'), primary_key=True)
    ma_mh = db.Column(db.String(50), db.ForeignKey('mon_hoc.ma_mh', ondelete='CASCADE'), primary_key=True)
    diem_thi = db.Column(db.Float, nullable=False)

# 2.5. Bảng ThongBao (Chức năng MỚI)
class ThongBao(db.Model):
    __tablename__ = 'thong_bao'
    id = db.Column(db.Integer, primary_key=True)
    tieu_de = db.Column(db.String(200), nullable=False)
    noi_dung = db.Column(db.Text, nullable=False)
    ngay_gui = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Giáo viên nào đã gửi?
    ma_gv = db.Column(db.String(50), db.ForeignKey('tai_khoan.username'), nullable=False)
    
    # Gửi cho Lớp nào?
    lop_nhan = db.Column(db.String(50), nullable=False)

    # Quan hệ (Relationship) để dễ dàng truy cập thông tin người gửi
    nguoi_gui = db.relationship('TaiKhoan', backref='thong_bao_da_gui', foreign_keys=[ma_gv])

# --- 3. LOGIC XÁC THỰC VÀ PHÂN QUYỀN ---

# Hàm này giúp Flask-Login lấy thông tin user từ session 
@login_manager.user_loader
def load_user(user_id):
    # user_id ở đây chính là username
    return TaiKhoan.query.get(user_id)

# Decorator tự định nghĩa để kiểm tra VaiTro (Middleware) 
def role_required(vai_tro_enum):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.vai_tro != vai_tro_enum:
                # Nếu sai vai trò, trả về lỗi 403 Forbidden
                abort(403) 
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.errorhandler(403)
def forbidden_page(e):
    # Trang thông báo lỗi khi truy cập sai vai trò
    return render_template('403.html'), 403


# --- 4. CÁC ROUTE (CHỨC NĂNG) ---

# === ĐÃ SỬA LỖI INDENTATION TẠI ĐÂY ===
# Thêm route cho trang chủ (/) để chuyển hướng đến /login
@app.route('/')
def home():
    return redirect(url_for('login'))
# =======================================

# 4.1. Chức năng Chung (Public) 
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu đã đăng nhập, chuyển hướng ngay
    if current_user.is_authenticated:
        if current_user.vai_tro == VaiTroEnum.SINHVIEN:
            return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Logic tìm kiếm và xác thực 
        user = TaiKhoan.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Đăng nhập thành công, tạo session 
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            
            # Phân luồng chuyển hướng dựa trên VaiTro 
            if user.vai_tro == VaiTroEnum.SINHVIEN:
                return redirect(url_for('student_dashboard'))
            elif user.vai_tro == VaiTroEnum.GIAOVIEN:
                return redirect(url_for('admin_dashboard'))
        else:
            # Logic xử lý lỗi 
            flash('Sai tên đăng nhập hoặc mật khẩu.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required # Chỉ người đã đăng nhập mới được đăng xuất
def logout():
    logout_user() # Xóa session 
    flash('Bạn đã đăng xuất.', 'success')
    return redirect(url_for('login'))


# 4.2. Chức năng của Sinh viên 

# === ĐÃ SỬA LỖI: THÊM LOGIC LẤY THÔNG BÁO ===
@app.route('/student/dashboard')
@login_required
@role_required(VaiTroEnum.SINHVIEN) # 
def student_dashboard():
    # Chào mừng 
    sinh_vien = SinhVien.query.get(current_user.username)
    
    # Logic MỚI: Lấy thông báo cho lớp của sinh viên
    notifications = []
    if sinh_vien and sinh_vien.lop:
        notifications = ThongBao.query.filter_by(
            lop_nhan=sinh_vien.lop
        ).order_by(
            ThongBao.ngay_gui.desc() # Sắp xếp mới nhất lên đầu
        ).limit(10).all() # Chỉ lấy 10 thông báo gần nhất

    return render_template('student_dashboard.html', sinh_vien=sinh_vien, notifications=notifications)

@app.route('/student/profile', methods=['GET', 'POST']) # <-- THÊM METHODS
@login_required
@role_required(VaiTroEnum.SINHVIEN)
def student_profile():
    # Lấy thông tin cá nhân 
    sinh_vien = SinhVien.query.get_or_404(current_user.username)
    
    if request.method == 'POST':
        # YÊU CẦU MỚI: Cho phép sinh viên sửa thông tin
        try:
            # Lấy dữ liệu từ form
            # SV không được sửa MaSV, Lớp, Khoa (chỉ admin mới được)
            sinh_vien.ho_ten = request.form.get('ho_ten')
            sinh_vien.ngay_sinh = db.func.date(request.form.get('ngay_sinh'))
            sinh_vien.email = request.form.get('email')
            sinh_vien.location = request.form.get('location')
            
            db.session.commit()
            flash('Cập nhật thông tin cá nhân thành công!', 'success')
            return redirect(url_for('student_profile'))
            
        except Exception as e:
            db.session.rollback()
            # Xử lý lỗi nếu email bị trùng
            if 'UNIQUE constraint failed: sinh_vien.email' in str(e):
                 flash('Lỗi: Email này đã được sử dụng bởi một tài khoản khác.', 'danger')
            else:
                flash(f'Lỗi khi cập nhật thông tin: {e}', 'danger')
            
    # Trang GET (hoặc khi POST bị lỗi)
    return render_template('student_profile.html', sv=sinh_vien)

@app.route('/student/grades')
@login_required
@role_required(VaiTroEnum.SINHVIEN)
def student_grades():
    # Lấy bảng điểm 
    ma_sv = current_user.username
    
    # Query join 3 bảng (KetQua, MonHoc) để lấy thông tin 
    results = db.session.query(
        MonHoc.ma_mh,
        MonHoc.ten_mh,
        MonHoc.so_tin_chi,
        KetQua.diem_thi
    ).join(
        KetQua, MonHoc.ma_mh == KetQua.ma_mh
    ).filter(
        KetQua.ma_sv == ma_sv
    ).order_by(MonHoc.ma_mh).all() # Sắp xếp theo mã môn
    
    # Logic tính GPA (thang 10) VÀ GPA (thang 4) MỚI
    total_points_10 = 0
    total_points_4 = 0
    total_credits = 0
    
    # Dữ liệu cho biểu đồ
    chart_labels = [] # Trục hoành (Mã môn)
    chart_data = [] # Trục tung (Điểm 10)

    for row in results:
        # Tính điểm cho GPA
        diem_he_4 = convert_10_to_4_scale(row.diem_thi)
        total_points_10 += row.diem_thi * row.so_tin_chi
        total_points_4 += diem_he_4 * row.so_tin_chi
        total_credits += row.so_tin_chi
        
        # Thêm dữ liệu cho biểu đồ
        chart_labels.append(row.ma_mh) # Trục hoành là Mã Môn
        chart_data.append(row.diem_thi) # Trục tung là Điểm 10

    gpa_10 = (total_points_10 / total_credits) if total_credits > 0 else 0.0
    gpa_4 = (total_points_4 / total_credits) if total_credits > 0 else 0.0
    
    return render_template(
        'student_grades.html', 
        results=results, 
        gpa_10=gpa_10,
        gpa_4=gpa_4,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

# 4.3. Chức năng của Giáo viên 

@app.route('/admin/dashboard')
@login_required
@role_required(VaiTroEnum.GIAOVIEN) # 
def admin_dashboard():
    # Thống kê nhanh 
    total_sv = SinhVien.query.count()
    total_mh = MonHoc.query.count()
    return render_template('admin_dashboard.html', total_sv=total_sv, total_mh=total_mh)

@app.route('/admin/students')
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_manage_students():
    # Lấy các tham số tìm kiếm/lọc từ URL (request.args cho phương thức GET)
    search_ma_sv = request.args.get('ma_sv', '')
    search_ho_ten = request.args.get('ho_ten', '')
    filter_lop = request.args.get('lop', '')
    filter_khoa = request.args.get('khoa', '')

    # Bắt đầu với một truy vấn cơ bản
    query = SinhVien.query

    # Áp dụng các bộ lọc động 
    if search_ma_sv:
        # Dùng .ilike() để tìm kiếm không phân biệt chữ hoa/thường
        query = query.filter(SinhVien.ma_sv.ilike(f'%{search_ma_sv}%'))
    if search_ho_ten:
        query = query.filter(SinhVien.ho_ten.ilike(f'%{search_ho_ten}%'))
    if filter_lop:
        # Lọc chính xác theo Lớp
        query = query.filter(SinhVien.lop == filter_lop)
    if filter_khoa:
        # Lọc chính xác theo Khoa
        query = query.filter(SinhVien.khoa == filter_khoa)

    # Thực thi truy vấn sau khi đã áp dụng các bộ lọc
    students = query.order_by(SinhVien.ma_sv).all() # Sắp xếp theo MaSV

    # Lấy danh sách Lớp và Khoa (duy nhất) để điền vào dropdown lọc
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]]

    khoa_tuples = db.session.query(SinhVien.khoa).distinct().order_by(SinhVien.khoa).all()
    danh_sach_khoa = [khoa[0] for khoa in khoa_tuples if khoa[0]]

    # Trả về template với danh sách sinh viên đã lọc và các danh sách để lọc
    return render_template(
        'admin_manage_students.html', 
        students=students,
        danh_sach_lop=danh_sach_lop,
        danh_sach_khoa=danh_sach_khoa,
        # Gửi lại các giá trị tìm kiếm để hiển thị trên form
        search_params={
            'ma_sv': search_ma_sv,
            'ho_ten': search_ho_ten,
            'lop': filter_lop,
            'khoa': filter_khoa
        }
    )
@app.route('/admin/students/add', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_add_student():
    if request.method == 'POST':
        # Lấy dữ liệu form 
        ma_sv = request.form.get('ma_sv')
        ho_ten = request.form.get('ho_ten')
        ngay_sinh = request.form.get('ngay_sinh')
        lop = request.form.get('lop')
        khoa = request.form.get('khoa')
        
        # Validate: MaSV không được trùng 
        existing_user = TaiKhoan.query.get(ma_sv)
        if existing_user:
            flash('Lỗi: Mã sinh viên đã tồn tại.', 'danger') # 
            return redirect(url_for('admin_add_student'))

        try:
            # Logic quan trọng: Tự động tạo TaiKhoan 
            
            # 1. Tạo TaiKhoan
            default_password = f"{ma_sv}@123" # 
            new_account = TaiKhoan(
                username=ma_sv, # 
                vai_tro=VaiTroEnum.SINHVIEN # 
            )
            new_account.set_password(default_password) # Băm mật khẩu 
            
            # 2. Tạo SinhVien
            new_student = SinhVien(
                ma_sv=ma_sv,
                ho_ten=ho_ten,
                ngay_sinh=db.func.date(ngay_sinh), # Chuyển string sang Date
                lop=lop,
                khoa=khoa
                # (Lưu ý: Form thêm thủ công này không có location/email,
                # chúng sẽ là NULL, điều này là bình thường)
            )
            
            # 3. Lưu vào CSDL
            db.session.add(new_account)
            db.session.add(new_student)
            db.session.commit()
            
            flash('Thêm sinh viên và tài khoản thành công!', 'success') # 
            return redirect(url_for('admin_manage_students'))

        except Exception as e:
            db.session.rollback() # Hoàn tác nếu có lỗi
            flash(f'Đã xảy ra lỗi: {e}', 'danger')
            return redirect(url_for('admin_add_student'))
            
    return render_template('admin_add_student.html')
# === KẾT THÚC HÀM CẦN DÁN ===

@app.route('/admin/students/edit/<ma_sv>', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_edit_student(ma_sv):
    # Lấy sinh viên từ CSDL, nếu không tìm thấy sẽ báo lỗi 404
    sv = SinhVien.query.get_or_404(ma_sv)
    
    if request.method == 'POST':
        # Cập nhật thông tin 
        try:
            sv.ho_ten = request.form.get('ho_ten')
            sv.ngay_sinh = db.func.date(request.form.get('ngay_sinh'))
            sv.lop = request.form.get('lop')
            sv.khoa = request.form.get('khoa')
            
            db.session.commit()
            flash('Cập nhật thông tin sinh viên thành công!', 'success')
            return redirect(url_for('admin_manage_students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật: {e}', 'danger')
            
    # Tải trang (GET) và hiển thị thông tin cũ của sinh viên
    return render_template('admin_edit_student.html', sv=sv)


@app.route('/admin/students/delete/<ma_sv>', methods=['POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_delete_student(ma_sv):
    # 
    sv = SinhVien.query.get_or_404(ma_sv)
    
    try:
        # Quan trọng: Đặc tả yêu cầu xóa cả TaiKhoan và KetQua liên quan 
        # Chúng ta đã cấu hình 'cascade' trong Model (Bước 1),
        # vì vậy chỉ cần xóa 'SinhVien', CSDL sẽ tự động xóa
        # 'TaiKhoan' và 'KetQua' liên quan.
        
        db.session.delete(sv)
        db.session.commit()
        flash('Đã xóa sinh viên và tài khoản liên quan thành công!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa sinh viên: {e}', 'danger')
        
    return redirect(url_for('admin_manage_students'))


# ===============================================
# === 4.4. CHỨC NĂNG QUẢN LÝ MÔN HỌC (CRUD) ===
# ===============================================

@app.route('/admin/courses')
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_manage_courses():
    # Xem danh sách môn học 
    courses = MonHoc.query.all()
    return render_template('admin_manage_courses.html', courses=courses)


@app.route('/admin/courses/add', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_add_course():
    if request.method == 'POST':
        ma_mh = request.form.get('ma_mh')
        ten_mh = request.form.get('ten_mh')
        so_tin_chi = request.form.get('so_tin_chi')

        # Validate: MaMH không trùng 
        existing = MonHoc.query.get(ma_mh)
        if existing:
            flash('Lỗi: Mã môn học đã tồn tại.', 'danger')
            return redirect(url_for('admin_add_course'))
            
        try:
            new_course = MonHoc(
                ma_mh=ma_mh,
                ten_mh=ten_mh,
                so_tin_chi=int(so_tin_chi)
            )
            db.session.add(new_course)
            db.session.commit()
            flash('Thêm môn học mới thành công!', 'success')
            return redirect(url_for('admin_manage_courses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi thêm môn học: {e}', 'danger')
    
    return render_template('admin_add_course.html')


@app.route('/admin/courses/edit/<ma_mh>', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_edit_course(ma_mh):
    course = MonHoc.query.get_or_404(ma_mh)
    
    if request.method == 'POST':
        # Cập nhật thông tin 
        try:
            course.ten_mh = request.form.get('ten_mh')
            course.so_tin_chi = int(request.form.get('so_tin_chi'))
            
            db.session.commit()
            flash('Cập nhật môn học thành công!', 'success')
            return redirect(url_for('admin_manage_courses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật: {e}', 'danger')
            
    # Tải trang (GET) với thông tin môn học
    return render_template('admin_edit_course.html', course=course)


@app.route('/admin/courses/delete/<ma_mh>', methods=['POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_delete_course(ma_mh):
    # 
    course = MonHoc.query.get_or_404(ma_mh)
    try:
        # (Lưu ý: Xóa môn học cũng sẽ xóa điểm (KetQua) liên quan
        # do chúng ta đã cài đặt 'cascade' trong Model MonHoc)
        db.session.delete(course)
        db.session.commit()
        flash('Đã xóa môn học thành công!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa môn học: {e}', 'danger')
        
    return redirect(url_for('admin_manage_courses'))


# ===============================================
# === 4.5. CHỨC NĂNG QUẢN LÝ ĐIỂM (CRUD) ===
# ===============================================

@app.route('/admin/grades', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_manage_grades():
    # Bước 1: Cung cấp dropdown để chọn Lớp và Môn học
    
    # Lấy danh sách các lớp học (không trùng lặp)
    # db.session.query(SinhVien.lop).distinct() trả về một list các tuple,
    # ví dụ: [('Lớp A',), ('Lớp B',)]
    # Chúng ta chuyển nó thành list các string: ['Lớp A', 'Lớp B']
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]] # Lọc bỏ các giá trị None/trống

    # Lấy danh sách môn học
    danh_sach_mon_hoc = MonHoc.query.order_by(MonHoc.ten_mh).all()

    if request.method == 'POST':
        # Khi giáo viên chọn xong và nhấn "Hiển thị", form sẽ submit đến chính nó (POST)
        # Chúng ta lấy 2 giá trị đã chọn...
        selected_lop = request.form.get('lop')
        selected_mh = request.form.get('ma_mh')

        # ... và chuyển hướng đến trang Nhập điểm (Bước 2)
        if selected_lop and selected_mh:
            return redirect(url_for('admin_enter_grades', lop=selected_lop, ma_mh=selected_mh))

    # Nếu là 'GET' (lần đầu vào trang), chỉ hiển thị 2 dropdown
    return render_template(
        'admin_manage_grades.html',
        danh_sach_lop=danh_sach_lop,
        danh_sach_mon_hoc=danh_sach_mon_hoc
    )


@app.route('/admin/grades/enter/<lop>/<ma_mh>', methods=['GET'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_enter_grades(lop, ma_mh):
    # Bước 2: Hiển thị danh sách SV và ô nhập điểm
    
    # Lấy thông tin môn học để hiển thị tiêu đề
    mon_hoc = MonHoc.query.get_or_404(ma_mh)
    
    # Lấy danh sách sinh viên thuộc lớp đã chọn
    sinh_vien_list = SinhVien.query.filter_by(lop=lop).order_by(SinhVien.ma_sv).all()
    
    if not sinh_vien_list:
        flash(f'Không tìm thấy sinh viên nào trong lớp {lop}.', 'warning')
        return redirect(url_for('admin_manage_grades'))

    # Tối ưu: Lấy điểm *hiện có* của tất cả SV trong lớp này cho môn này
    # Bằng cách này, chúng ta không cần query CSDL N lần trong vòng lặp
    diem_hien_co_raw = KetQua.query.filter(
        KetQua.ma_mh == ma_mh,
        KetQua.ma_sv.in_([sv.ma_sv for sv in sinh_vien_list])
    ).all()
    
    # Chuyển list điểm thành một dictionary để truy cập nhanh
    # Ví dụ: {'sv001': 8.5, 'sv003': 7.0}
    diem_hien_co_dict = {kq.ma_sv: kq.diem_thi for kq in diem_hien_co_raw}

    # Gắn điểm hiện có vào từng sinh viên để hiển thị trên form
    # Chúng ta sẽ tạo một list mới để gửi ra template
    danh_sach_nhap_diem = []
    for sv in sinh_vien_list:
        danh_sach_nhap_diem.append({
            'ma_sv': sv.ma_sv,
            'ho_ten': sv.ho_ten,
            'diem_thi': diem_hien_co_dict.get(sv.ma_sv) # Lấy điểm, nếu chưa có thì là None
        })

    return render_template(
        'admin_enter_grades.html',
        lop=lop,
        mon_hoc=mon_hoc,
        danh_sach_nhap_diem=danh_sach_nhap_diem
    )


@app.route('/admin/grades/save', methods=['POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_save_grades():
    # Bước 3: Nhận dữ liệu và lưu hàng loạt
    try:
        ma_mh = request.form.get('ma_mh')
        lop = request.form.get('lop') # Lấy lại để redirect nếu cần
        
        # request.form chứa tất cả dữ liệu gửi lên.
        # Ví dụ: {'ma_mh': 'IT101', 'lop': 'Lop A', 'diem_sv001': '8.5', 'diem_sv002': '', 'diem_sv003': '7'}
        
        updated_count = 0
        created_count = 0

        # Logic INSERT hoặc UPDATE
        for key, value in request.form.items():
            # Key có dạng 'diem_MaSV', ví dụ: 'diem_sv001'
            if key.startswith('diem_'):
                ma_sv = key.split('_', 1)[1] # Lấy MaSV từ key
                
                # Nếu ô điểm bị bỏ trống, bỏ qua, không lưu
                if value == '':
                    continue 

                try:
                    diem_thi_float = float(value)
                    # Validate điểm (ví dụ: 0-10)
                    if not (0 <= diem_thi_float <= 10):
                        raise ValueError("Điểm phải nằm trong khoảng 0-10")
                except ValueError:
                    flash(f'Lỗi: Điểm "{value}" của SV {ma_sv} không hợp lệ. Bỏ qua.', 'danger')
                    continue

                # Kiểm tra xem điểm đã tồn tại (UPDATE) hay chưa (INSERT)
                existing_grade = KetQua.query.get((ma_sv, ma_mh))
                
                if existing_grade:
                    # UPDATE
                    existing_grade.diem_thi = diem_thi_float
                    updated_count += 1
                else:
                    # INSERT
                    new_grade = KetQua(
                        ma_sv=ma_sv,
                        ma_mh=ma_mh,
                        diem_thi=diem_thi_float
                    )
                    db.session.add(new_grade)
                    created_count += 1
        
        db.session.commit()
        flash(f'Lưu điểm thành công! (Cập nhật: {updated_count}, Thêm mới: {created_count})', 'success')
        return redirect(url_for('admin_manage_grades'))

    except Exception as e:
        db.session.rollback()
        flash(f'Đã xảy ra lỗi nghiêm trọng khi lưu điểm: {e}', 'danger')
        # Trả về trang chọn lớp/môn ban đầu
        return redirect(url_for('admin_manage_grades'))

# ========================================================
# === 4.6. CHỨC NĂNG BÁO CÁO & THỐNG KÊ ===
# ========================================================

# Hàm trợ giúp (helper) để tính GPA cho một truy vấn (query)
# GPA = Sum(DiemThi * SoTinChi) / Sum(SoTinChi)
def calculate_gpa_expression():
    """Trả về biểu thức SQLAlchemy (column expression) để tính GPA."""
    # Tính tổng (Điểm * Tín chỉ)
    total_points = func.sum(KetQua.diem_thi * MonHoc.so_tin_chi)
    
    # Tính tổng Tín chỉ
    total_credits = func.sum(MonHoc.so_tin_chi)
    
    # Trả về biểu thức GPA, xử lý trường hợp chia cho 0 (nếu SV chưa có tín chỉ nào)
    # case() giống như 'CASE WHEN total_credits > 0 THEN ... ELSE 0 END' trong SQL
    return case(
        (total_credits > 0, total_points / total_credits),
        else_ = 0.0
    ).label("gpa")

def calculate_gpa_4_expression():
    """Trả về biểu thức SQLAlchemy để tính GPA 4.0."""
    
    # Dùng hàm convert_10_to_4_scale đã viết ở lần trước,
    # nhưng chuyển đổi sang cú pháp 'case' của SQLAlchemy
    diem_he_4 = case(
        (KetQua.diem_thi >= 8.5, 4.0),
        (KetQua.diem_thi >= 8.0, 3.5),
        (KetQua.diem_thi >= 7.0, 3.0),
        (KetQua.diem_thi >= 6.5, 2.5),
        (KetQua.diem_thi >= 5.5, 2.0),
        (KetQua.diem_thi >= 5.0, 1.5),
        (KetQua.diem_thi >= 4.0, 1.0),
        else_=0.0
    )
    
    total_points_4 = func.sum(diem_he_4 * MonHoc.so_tin_chi)
    total_credits = func.sum(MonHoc.so_tin_chi)
    
    return case(
        (total_credits > 0, total_points_4 / total_credits),
        else_=0.0
    ).label("gpa_4")

@app.route('/admin/reports')
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_reports_index():
    # Trang chính hiển thị các liên kết đến các báo cáo
    return render_template('admin_reports_index.html')


# === Báo cáo 1: SV có GPA > 8.0 ===
@app.route('/admin/reports/high_gpa')
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_report_high_gpa():
    # Mốc điểm GPA cao (theo thang 10) 
    GPA_THRESHOLD = 8.0
    
    gpa_10_expression = calculate_gpa_expression()
    gpa_4_expression = calculate_gpa_4_expression() # <-- GỌI HÀM MỚI
    
    results = db.session.query(
        SinhVien.ma_sv,
        SinhVien.ho_ten,
        SinhVien.lop,
        gpa_10_expression, # Đổi tên cho rõ ràng
        gpa_4_expression   # <-- THÊM GPA 4.0 VÀO QUERY
    ).join(
        KetQua, SinhVien.ma_sv == KetQua.ma_sv
    ).join(
        MonHoc, KetQua.ma_mh == MonHoc.ma_mh
    ).group_by(
        SinhVien.ma_sv, SinhVien.ho_ten, SinhVien.lop
    ).having(
        gpa_10_expression > GPA_THRESHOLD # Vẫn lọc theo GPA 10
    ).order_by(
        gpa_10_expression.desc() # Sắp xếp GPA giảm dần
    ).all()

    # Hiển thị bảng kết quả
    # === THÊM LOGIC ĐẾM PHÂN LOẠI CHO BIỂU ĐỒ ===
    category_counts = {"Yếu": 0, "Trung bình": 0, "Khá": 0, "Giỏi": 0, "Xuất sắc": 0}
    # Chỉ đếm dựa trên kết quả đã lọc (results)
    for row in results:
        category = classify_gpa_10(row.gpa) # Dùng GPA hệ 10 để phân loại
        if category in category_counts:
            category_counts[category] += 1
            
    # Chuẩn bị dữ liệu cho Chart.js
    chart_labels = list(category_counts.keys())
    chart_data = list(category_counts.values())
    # =============================================

    # Hiển thị bảng kết quả VÀ dữ liệu biểu đồ
    return render_template(
        'admin_report_high_gpa.html', 
        results=results, 
        threshold=GPA_THRESHOLD,
        chart_labels=chart_labels, # <-- Gửi labels cho template
        chart_data=chart_data     # <-- Gửi data count cho template
    )
        

# === Báo cáo 2: SV chưa thi môn X ===
@app.route('/admin/reports/missing_grade', methods=['GET']) # Dùng GET với query param
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_report_missing_grade():
    danh_sach_mon_hoc = MonHoc.query.order_by(MonHoc.ten_mh).all()
    selected_mh_id = request.args.get('ma_mh') # Lấy MaMH từ URL (ví dụ: ?ma_mh=IT101)
    
    results = []
    selected_mon_hoc = None

    if selected_mh_id:
        selected_mon_hoc = MonHoc.query.get(selected_mh_id)
        
        # Logic: Tìm tất cả sinh viên 
        # KHÔNG CÓ (NOT IN) bản ghi (MaSV, MaMH_X) trong bảng KetQua.
        
        # 1. Tạo một subquery (truy vấn con) để lấy TẤT CẢ MaSV đã thi môn này.
        subquery_sv_da_thi = select(KetQua.ma_sv).where(KetQua.ma_mh == selected_mh_id)
        
        # 2. Truy vấn chính: Lấy TẤT CẢ SinhVien
        #    mà MaSV KHÔNG NẰM TRONG (NOT IN) kết quả của truy vấn con.
        results = SinhVien.query.where(
            SinhVien.ma_sv.notin_(subquery_sv_da_thi)
        ).order_by(SinhVien.lop, SinhVien.ma_sv).all()

    # Cung cấp dropdown chọn MonHoc
    return render_template(
        'admin_report_missing_grade.html',
        danh_sach_mon_hoc=danh_sach_mon_hoc,
        selected_mon_hoc=selected_mon_hoc,
        results=results
    )


# === Báo cáo 3: Thống kê điểm trung bình Lớp ===
# === REPLACE the old admin_report_class_gpa function with this ===
@app.route('/admin/reports/class_gpa', methods=['GET'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_report_class_gpa():
    # Lấy danh sách Lớp
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]]

    selected_lop = request.args.get('lop') # Lấy Lớp từ URL

    lop_gpa_10 = None
    lop_gpa_4 = None
    chart_labels = []
    chart_data = []

    if selected_lop:
        # --- Logic tính GPA trung bình của LỚP (Cả hệ 10 và hệ 4) ---

        # 1. Tạo subquery tính GPA 10 cho TỪNG SINH VIÊN trong lớp
        gpa_10_expression = calculate_gpa_expression()
        subquery_gpa_10_sv = db.session.query(
            SinhVien.ma_sv.label('sv_id'), # Đặt tên label để dễ truy cập
            gpa_10_expression # GPA 10 của 1 SV
        ).join(
            KetQua, SinhVien.ma_sv == KetQua.ma_sv
        ).join(
            MonHoc, KetQua.ma_mh == MonHoc.ma_mh
        ).filter(
            SinhVien.lop == selected_lop
        ).group_by(
            SinhVien.ma_sv
        ).subquery()

        # 2. Tạo subquery tính GPA 4 cho TỪNG SINH VIÊN trong lớp
        gpa_4_expression = calculate_gpa_4_expression()
        subquery_gpa_4_sv = db.session.query(
            SinhVien.ma_sv.label('sv_id'),
            gpa_4_expression # GPA 4 của 1 SV
        ).join(
            KetQua, SinhVien.ma_sv == KetQua.ma_sv
        ).join(
            MonHoc, KetQua.ma_mh == MonHoc.ma_mh
        ).filter(
            SinhVien.lop == selected_lop
        ).group_by(
            SinhVien.ma_sv
        ).subquery()

        # 3. Tính TRUNG BÌNH (AVG) của các GPA từ subquery
        avg_gpa_10_result = db.session.query(func.avg(subquery_gpa_10_sv.c.gpa)).scalar()
        avg_gpa_4_result = db.session.query(func.avg(subquery_gpa_4_sv.c.gpa_4)).scalar()

        lop_gpa_10 = avg_gpa_10_result if avg_gpa_10_result else 0.0
        lop_gpa_4 = avg_gpa_4_result if avg_gpa_4_result else 0.0

        # --- Logic đếm phân loại sinh viên cho biểu đồ ---
        # Lấy GPA 10 của từng sinh viên trong lớp (từ subquery đã tạo)
        student_gpas = db.session.query(subquery_gpa_10_sv.c.gpa).all()

        category_counts = {"Yếu": 0, "Trung bình": 0, "Khá": 0, "Giỏi": 0, "Xuất sắc": 0}
        if student_gpas:
            for gpa_tuple in student_gpas:
                # gpa_tuple[0] là giá trị GPA 10
                category = classify_gpa_10(gpa_tuple[0])
                if category in category_counts:
                    category_counts[category] += 1

        # Chuẩn bị dữ liệu cho Chart.js (chỉ lấy loại có SV > 0)
        chart_labels = [label for label, count in category_counts.items() if count > 0]
        chart_data = [count for label, count in category_counts.items() if count > 0]


    # Cung cấp dropdown chọn Lop và gửi dữ liệu GPA, biểu đồ
    return render_template(
        'admin_report_class_gpa.html',
        danh_sach_lop=danh_sach_lop,
        selected_lop=selected_lop,
        lop_gpa_10=lop_gpa_10,
        lop_gpa_4=lop_gpa_4,        # <-- Thêm GPA 4
        chart_labels=chart_labels, # <-- Thêm chart labels
        chart_data=chart_data      # <-- Thêm chart data
    )
# =========================================================

# ========================================================
# === 4.7. CHỨC NĂNG GỬI THÔNG BÁO (MỚI) ===
# ========================================================

@app.route('/admin/notify', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_send_notification():
    # Lấy danh sách lớp để gửi (tương tự trang Nhập điểm)
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]]

    if request.method == 'POST':
        try:
            lop_nhan = request.form.get('lop_nhan')
            tieu_de = request.form.get('tieu_de')
            noi_dung = request.form.get('noi_dung')

            if not lop_nhan or not tieu_de or not noi_dung:
                flash('Vui lòng điền đầy đủ Lớp, Tiêu đề và Nội dung.', 'danger')
                return redirect(url_for('admin_send_notification'))

            # Tạo thông báo mới
            new_notification = ThongBao(
                tieu_de=tieu_de,
                noi_dung=noi_dung,
                ma_gv=current_user.username, # Người gửi là giáo viên hiện tại
                lop_nhan=lop_nhan
            )
            
            db.session.add(new_notification)
            db.session.commit()
            
            flash(f'Gửi thông báo đến lớp {lop_nhan} thành công!', 'success')
            return redirect(url_for('admin_send_notification'))

        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi gửi thông báo: {e}', 'danger')

    return render_template('admin_send_notification.html', danh_sach_lop=danh_sach_lop)

# ========================================================
# === 4.8. CHỨC NĂNG NHẬP EXCEL HÀNG LOẠT (ĐÃ SỬA LỖI NaT) ===
# ========================================================
@app.route('/admin/import_students', methods=['GET', 'POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN) # <-- Đã sửa lỗi GIAOIAOVIEN thành GIAOVIEN
def admin_import_students():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Không có tệp nào được chọn.', 'danger')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('Chưa chọn tệp.', 'danger')
            return redirect(request.url)

        if file and file.filename.endswith(('.xls', '.xlsx')):
            try:
                # 1. Đọc file Excel
                df = pd.read_excel(file)

                # 2. Validate các cột bắt buộc
                required_columns = ['ma_sinh_vien', 'ten_sinh_vien', 'password', 'role']
                if not all(col in df.columns for col in required_columns):
                    flash(f'Lỗi: File Excel phải chứa các cột: {", ".join(required_columns)}', 'danger')
                    return redirect(request.url)

                created_count = 0
                errors = []

                # 3. Duyệt qua từng dòng trong Excel
                for index, row in df.iterrows():
                    ma_sv = str(row['ma_sinh_vien'])
                    ten_sv = str(row['ten_sinh_vien'])
                    password = str(row['password'])
                    role_str = str(row['role']).upper()

                    # Kiểm tra vai trò
                    if role_str != 'SINHVIEN':
                        errors.append(f'Dòng {index+2}: Vai trò "{role_str}" không hợp lệ, chỉ chấp nhận "SINHVIEN". Bỏ qua.')
                        continue

                    # Kiểm tra trùng MaSV 
                    existing_user = TaiKhoan.query.get(ma_sv)
                    if existing_user:
                        errors.append(f'Dòng {index+2}: Mã SV "{ma_sv}" đã tồn tại. Bỏ qua.')
                        continue

                    # 4. Tạo TaiKhoan (Tự động băm mật khẩu) 
                    new_account = TaiKhoan(
                        username=ma_sv,
                        vai_tro=VaiTroEnum.SINHVIEN
                    )
                    new_account.set_password(password)

                    # === PHẦN SỬA LỖI NaT & NaN (QUAN TRỌNG!) ===
                    # 5. Tạo SinhVien (Xử lý cẩn thận giá trị NaN/NaT từ Pandas)

                    # Lấy giá trị, nếu là NaN (hoặc NaT) thì chuyển thành None (SQL NULL)
                    lop_val = row.get('lop', None)
                    khoa_val = row.get('khoa', None)
                    email_val = row.get('email', None)
                    location_val = row.get('location', None)
                    ngay_sinh_val = row.get('ngay_sinh', None)

                    # Dòng này kiểm tra nếu ngay_sinh_val là NaT thì gán None, ngược lại mới chuyển thành datetime
                    ngay_sinh_final = None if pd.isna(ngay_sinh_val) else pd.to_datetime(ngay_sinh_val)

                    new_student = SinhVien(
                        ma_sv=ma_sv,
                        ho_ten=ten_sv,

                        # pd.isna() kiểm tra cả NaN (float) và NaT (datetime)
                        lop = None if pd.isna(lop_val) else str(lop_val),
                        khoa = None if pd.isna(khoa_val) else str(khoa_val),
                        email = None if pd.isna(email_val) else str(email_val),
                        location = None if pd.isna(location_val) else str(location_val),
                        ngay_sinh = ngay_sinh_final # <-- SỬ DỤNG GIÁ TRỊ ĐÃ XỬ LÝ
                    )
                    # === KẾT THÚC PHẦN SỬA LỖI ===

                    db.session.add(new_account)
                    db.session.add(new_student)
                    created_count += 1

                # 6. Lưu tất cả vào CSDL
                db.session.commit()

                flash(f'Nhập file thành công! Đã thêm mới {created_count} sinh viên.', 'success')
                # Hiển thị các lỗi (nếu có)
                for error in errors:
                    flash(error, 'warning')

            except Exception as e:
                db.session.rollback() # Hoàn tác nếu có lỗi
                flash(f'Đã xảy ra lỗi nghiêm trọng khi đọc file: {e}', 'danger')

            return redirect(url_for('admin_manage_students'))

    return render_template('admin_import_students.html')

# ========================================================
# === 4.9. CHỨC NĂNG XUẤT ĐIỂM EXCEL THEO LỚP (MỚI) ===
# ========================================================

@app.route('/admin/export_grades', methods=['GET'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_export_grades():
    """Trang hiển thị dropdown để chọn Lớp."""
    # Lấy danh sách lớp
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]]
    
    return render_template('admin_export_grades.html', danh_sach_lop=danh_sach_lop)


@app.route('/admin/export/perform', methods=['POST'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_perform_export():
    """Xử lý logic và trả về file Excel."""
    try:
        selected_lop = request.form.get('lop')
        if not selected_lop:
            flash('Vui lòng chọn một lớp.', 'danger')
            return redirect(url_for('admin_export_grades'))

        # 1. Tìm tất cả sinh viên trong lớp đã chọn
        students_in_class = SinhVien.query.filter_by(lop=selected_lop).all()
        if not students_in_class:
            flash(f'Không tìm thấy sinh viên nào trong lớp {selected_lop}.', 'warning')
            return redirect(url_for('admin_export_grades'))

        student_ids = [sv.ma_sv for sv in students_in_class]

        # 2. Lấy TẤT CẢ điểm của các sinh viên này
        #    Join với SinhVien (lấy HoTen) và MonHoc (lấy TenMH)
        query_results = db.session.query(
            SinhVien.ma_sv,
            SinhVien.ho_ten,
            MonHoc.ma_mh,
            MonHoc.ten_mh,
            KetQua.diem_thi
        ).join(
            KetQua, SinhVien.ma_sv == KetQua.ma_sv
        ).join(
            MonHoc, KetQua.ma_mh == MonHoc.ma_mh
        ).filter(
            SinhVien.ma_sv.in_(student_ids)
        ).all()

        if not query_results:
            flash(f'Không tìm thấy dữ liệu điểm nào cho lớp {selected_lop}.', 'warning')
            return redirect(url_for('admin_export_grades'))

        # 3. Chuyển dữ liệu "dài" sang DataFrame của Pandas
        df_long = pd.DataFrame(query_results, columns=['Mã SV', 'Họ tên', 'Mã MH', 'Tên Môn học', 'Điểm thi'])

        # 4. Dùng PIVOT để tạo bảng điểm...
        df_pivot = df_long.pivot_table(
            index=['Mã SV', 'Họ tên'],
            columns=['Mã MH', 'Tên Môn học'], # <-- Đây là nguyên nhân tạo MultiIndex
            values='Điểm thi'
        )
        
        # Reset index để 'Mã SV' và 'Họ tên' trở thành cột
        df_pivot = df_pivot.reset_index()

        # === SỬA LỖI: FLATTEN (LÀM PHẲNG) MULTIINDEX COLUMNS ===
        # Lỗi xảy ra vì to_excel không hỗ trợ index=False với MultiIndex columns.
        # Chúng ta sẽ chuyển các cột (tuple) thành (string).
        # Ví dụ: ('Mã SV', '') -> 'Mã SV'
        # Ví dụ: ('TEL1343', 'Cơ sở dữ liệu') -> 'TEL1343 (Cơ sở dữ liệu)'
        
        new_columns = []
        for col in df_pivot.columns:
            if col[1]: # Nếu phần tử thứ 2 (Tên MH) tồn tại (vd: 'Cơ sở dữ liệu')
                new_columns.append(f"{col[0]} ({col[1]})") # Kết quả: 'TEL1343 (Cơ sở dữ liệu)'
            else: # Ngược lại (là cột 'Mã SV' hoặc 'Họ tên', col[1] là rỗng)
                new_columns.append(col[0])
        
        df_pivot.columns = new_columns
        # === KẾT THÚC SỬA LỖI ===

        # 5. Tạo file Excel trong bộ nhớ
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Bây giờ df_pivot không còn MultiIndex columns,
            # nên index=False sẽ hoạt động bình thường
            df_pivot.to_excel(writer, sheet_name=f'Diem_Lop_{selected_lop}', index=False)
        output.seek(0) # Đưa con trỏ về đầu file
        
        # 6. Trả file về cho người dùng
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'BangDiem_Lop_{selected_lop}.xlsx'
        )

    except Exception as e:
        flash(f'Đã xảy ra lỗi khi xuất file: {e}', 'danger')
        return redirect(url_for('admin_export_grades'))

# ========================================================
# === 4.9. CHỨC NĂNG XUẤT EXCEL DANH SÁCH SV (MỚI) ===
# ========================================================
@app.route('/admin/export_students_excel')
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_export_students_excel():
    try:
        # SAO CHÉP Y HỆT LOGIC LỌC TỪ HÀM admin_manage_students 
        search_ma_sv = request.args.get('ma_sv', '')
        search_ho_ten = request.args.get('ho_ten', '')
        filter_lop = request.args.get('lop', '')
        filter_khoa = request.args.get('khoa', '')

        query = SinhVien.query
        if search_ma_sv:
            query = query.filter(SinhVien.ma_sv.ilike(f'%{search_ma_sv}%'))
        if search_ho_ten:
            query = query.filter(SinhVien.ho_ten.ilike(f'%{search_ho_ten}%'))
        if filter_lop:
            query = query.filter(SinhVien.lop == filter_lop)
        if filter_khoa:
            query = query.filter(SinhVien.khoa == filter_khoa)

        students = query.order_by(SinhVien.ma_sv).all()
        
        if not students:
            flash('Không có dữ liệu sinh viên nào để xuất.', 'warning')
            return redirect(url_for('admin_manage_students'))

        # 2. Chuyển danh sách đối tượng (object) sang list dictionary
        data_for_df = []
        for sv in students:
            data_for_df.append({
                'Mã SV': sv.ma_sv,
                'Họ tên': sv.ho_ten,
                'Ngày sinh': sv.ngay_sinh,
                'Lớp': sv.lop,
                'Khoa': sv.khoa,
                'Email': sv.email,
                'Địa chỉ (Location)': sv.location
            })
        
        # 3. Tạo DataFrame và file Excel
        df = pd.DataFrame(data_for_df)
        
        # Định dạng lại cột Ngày sinh cho đẹp
        if 'Ngày sinh' in df.columns:
            df['Ngày sinh'] = pd.to_datetime(df['Ngày sinh']).dt.strftime('%d-%m-%Y')

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='DanhSachSinhVien', index=False)
        output.seek(0)
        
        # 4. Trả file về cho người dùng
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='DanhSachSinhVien_Filtered.xlsx'
        )

    except Exception as e:
        flash(f'Đã xảy ra lỗi khi xuất file: {e}', 'danger')
        return redirect(url_for('admin_manage_students'))

# --- 5. KHỞI CHẠY ỨNG DỤNG ---

if __name__ == '__main__':
    with app.app_context():
        # Tạo tất cả các bảng nếu chưa tồn tại
        db.create_all() 
        
        # *** Logic tạo tài khoản GIAOVIEN mẫu (Chạy 1 lần) ***
        # 
        if not TaiKhoan.query.filter_by(username='giaovien01').first():
            print("Tạo tài khoản giáo viên mẫu...")
            admin_user = TaiKhoan(
                username='giaovien01',
                vai_tro=VaiTroEnum.GIAOVIEN
            )
            admin_user.set_password('admin@123') # Mật khẩu ví dụ
            db.session.add(admin_user)
            db.session.commit()
            print("Tạo xong. Username: giaovien01, Password: admin@123")
            
    app.run(debug=True) # debug=True để tự động khởi động lại