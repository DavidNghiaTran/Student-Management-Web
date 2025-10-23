import os
import enum
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

app = Flask(__name__)
# Khóa bí mật để bảo vệ session
app.config['SECRET_KEY'] = 'mot-khoa-bi-mat-rat-manh-theo-yeu-cau-bao-mat'
# Cấu hình đường dẫn CSDL SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'qlsv.db')
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
    # Quan hệ 1-1: MaSV là PK và cũng là FK tham chiếu đến TaiKhoan(username) 
    # ondelete='CASCADE' để khi xóa TaiKhoan, SinhVien cũng bị xóa
    ma_sv = db.Column(db.String(50), db.ForeignKey('tai_khoan.username', ondelete='CASCADE'), primary_key=True)
    ho_ten = db.Column(db.String(100), nullable=False)
    ngay_sinh = db.Column(db.Date)
    lop = db.Column(db.String(50))
    khoa = db.Column(db.String(100))

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

@app.route('/student/dashboard')
@login_required
@role_required(VaiTroEnum.SINHVIEN) # 
def student_dashboard():
    # Chào mừng 
    # Lấy thông tin từ bảng SinhVien dựa trên MaSV (là current_user.username)
    sinh_vien = SinhVien.query.get(current_user.username)
    return render_template('student_dashboard.html', sinh_vien=sinh_vien)

@app.route('/student/profile')
@login_required
@role_required(VaiTroEnum.SINHVIEN)
def student_profile():
    # Lấy thông tin cá nhân (chỉ đọc) 
    sinh_vien = SinhVien.query.get(current_user.username)
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
    ).all()
    
    # Logic tính GPA (thang 10) 
    total_points = 0
    total_credits = 0
    for row in results:
        total_points += row.diem_thi * row.so_tin_chi
        total_credits += row.so_tin_chi
        
    gpa = (total_points / total_credits) if total_credits > 0 else 0.0
    
    return render_template('student_grades.html', results=results, gpa=gpa)

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
    # Xem danh sách sinh viên 
    # (Chưa làm phân trang và tìm kiếm, sẽ làm ở bước sau) 
    students = SinhVien.query.all()
    return render_template('admin_manage_students.html', students=students)

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
            )
            
            # 3. Lưu vào CSDL
            # Do quan hệ 1-1 và FK, ta phải add TaiKhoan trước
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

# ... (code cũ của hàm admin_add_student giữ nguyên) ...

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

    # Đây là một truy vấn phức tạp:
    # 1. Join SinhVien, KetQua, MonHoc
    # 2. Group by (gom nhóm) theo từng SinhVien (MaSV, HoTen, Lop)
    # 3. Tính GPA cho mỗi nhóm
    # 4. Lọc (having) các nhóm có GPA > 8.0
    
    gpa_expression = calculate_gpa_expression()
    
    results = db.session.query(
        SinhVien.ma_sv,
        SinhVien.ho_ten,
        SinhVien.lop,
        gpa_expression # Sử dụng biểu thức GPA đã định nghĩa
    ).join(
        KetQua, SinhVien.ma_sv == KetQua.ma_sv
    ).join(
        MonHoc, KetQua.ma_mh == MonHoc.ma_mh
    ).group_by(
        SinhVien.ma_sv, SinhVien.ho_ten, SinhVien.lop
    ).having(
        gpa_expression > GPA_THRESHOLD # Lọc sau khi group by
    ).order_by(
        gpa_expression.desc() # Sắp xếp GPA giảm dần
    ).all()

    # Hiển thị bảng kết quả
    return render_template('admin_report_high_gpa.html', results=results, threshold=GPA_THRESHOLD)


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
@app.route('/admin/reports/class_gpa', methods=['GET'])
@login_required
@role_required(VaiTroEnum.GIAOVIEN)
def admin_report_class_gpa():
    # Lấy danh sách Lớp (tương tự trang Nhập điểm)
    lop_hoc_tuples = db.session.query(SinhVien.lop).distinct().order_by(SinhVien.lop).all()
    danh_sach_lop = [lop[0] for lop in lop_hoc_tuples if lop[0]]
    
    selected_lop = request.args.get('lop') # Lấy Lớp từ URL
    
    lop_gpa = None

    if selected_lop:
        # Logic tính GPA trung bình của LỚP
        # 1. Join 3 bảng
        # 2. Lọc (filter) theo Lớp đã chọn
        # 3. Group by (gom nhóm) theo Lớp
        # 4. Tính GPA trung bình của nhóm đó
        
        gpa_expression = calculate_gpa_expression()

        # Truy vấn này tính GPA cho *từng sinh viên* TRONG LỚP ĐÓ
        # Chúng ta cần tính GPA của cả lớp (trung bình của các GPA)
        
        # Bước 1: Tạo subquery tính GPA cho TỪNG SINH VIÊN trong lớp
        subquery_gpa_sv = db.session.query(
            SinhVien.ma_sv,
            gpa_expression # GPA của 1 SV
        ).join(
            KetQua, SinhVien.ma_sv == KetQua.ma_sv
        ).join(
            MonHoc, KetQua.ma_mh == MonHoc.ma_mh
        ).filter(
            SinhVien.lop == selected_lop # Lọc theo lớp
        ).group_by(
            SinhVien.ma_sv
        ).subquery() # Biến thành truy vấn con

        # Bước 2: Truy vấn chính: Tính TRUNG BÌNH (AVG) của các GPA từ truy vấn con
        # Dùng func.avg() để tính trung bình
        result = db.session.query(
            func.avg(subquery_gpa_sv.c.gpa) # .c.gpa là truy cập cột gpa từ subquery
        ).scalar() # .scalar() để lấy 1 giá trị duy nhất
        
        lop_gpa = result if result else 0.0

    # Cung cấp dropdown chọn Lop
    return render_template(
        'admin_report_class_gpa.html',
        danh_sach_lop=danh_sach_lop,
        selected_lop=selected_lop,
        lop_gpa=lop_gpa
    )

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