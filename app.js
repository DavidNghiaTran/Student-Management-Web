const express = require('express');
const path = require('path');
const session = require('express-session');
const flash = require('connect-flash');
const bcrypt = require('bcryptjs');
const multer = require('multer');
const fs = require('fs');
const xlsx = require('xlsx');
const ExcelJS = require('exceljs');
const nunjucks = require('nunjucks');
const { format } = require('date-fns');

const {
  sequelize,
  Op,
  VaiTroEnum,
  TaiKhoan,
  SinhVien,
  MonHoc,
  KetQua,
  ThongBao,
  initDatabase,
} = require('./models');

const app = express();
const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}
const upload = multer({ dest: uploadDir });

// Configure Nunjucks
const env = nunjucks.configure(path.join(__dirname, 'templates'), {
  autoescape: true,
  express: app,
});

env.addFilter('formatDate', (value, fmt) => {
  if (!value) return '';
  try {
    const dateValue = value instanceof Date ? value : new Date(value);
    return format(dateValue, fmt);
  } catch (err) {
    return '';
  }
});

env.addFilter('formatDateTime', (value, fmt) => {
  if (!value) return '';
  try {
    const dateValue = value instanceof Date ? value : new Date(value);
    return format(dateValue, fmt);
  } catch (err) {
    return '';
  }
});

env.addFilter('tojson', (value) => {
  try {
    return JSON.stringify(value ?? null);
  } catch (err) {
    return 'null';
  }
});

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'static')));

app.use(session({
  secret: 'mot-khoa-bi-mat-rat-manh-theo-yeu-cau-bao-mat',
  resave: false,
  saveUninitialized: false,
}));
app.use(flash());

app.use(async (req, res, next) => {
  res.locals.current_user = req.session.user || null;
  res.locals.flash_messages = req.flash();
  res.locals.get_flashed_messages = ({ with_categories = false } = {}) => {
    const flashes = res.locals.flash_messages || {};
    if (!with_categories) {
      return Object.values(flashes).flat();
    }
    const result = [];
    for (const [category, messages] of Object.entries(flashes)) {
      for (const msg of messages) {
        result.push([category, msg]);
      }
    }
    return result;
  };
  next();
});

const routePaths = {
  home: '/',
  login: '/login',
  logout: '/logout',
  student_dashboard: '/student/dashboard',
  student_profile: '/student/profile',
  student_grades: '/student/grades',
  admin_dashboard: '/admin/dashboard',
  admin_manage_students: '/admin/students',
  admin_add_student: '/admin/students/add',
  admin_edit_student: { path: '/admin/students/edit/:ma_sv', params: ['ma_sv'] },
  admin_delete_student: { path: '/admin/students/delete/:ma_sv', params: ['ma_sv'] },
  admin_manage_courses: '/admin/courses',
  admin_add_course: '/admin/courses/add',
  admin_edit_course: { path: '/admin/courses/edit/:ma_mh', params: ['ma_mh'] },
  admin_delete_course: { path: '/admin/courses/delete/:ma_mh', params: ['ma_mh'] },
  admin_manage_grades: '/admin/grades',
  admin_enter_grades: { path: '/admin/grades/enter/:lop/:ma_mh', params: ['lop', 'ma_mh'] },
  admin_save_grades: '/admin/grades/save',
  admin_reports_index: '/admin/reports',
  admin_report_high_gpa: '/admin/reports/high_gpa',
  admin_report_missing_grade: '/admin/reports/missing_grade',
  admin_report_class_gpa: '/admin/reports/class_gpa',
  admin_send_notification: '/admin/notify',
  admin_import_students: '/admin/import_students',
  admin_export_grades: '/admin/export_grades',
  admin_perform_export: '/admin/export/perform',
  admin_export_students_excel: '/admin/export_students_excel',
};

app.use((req, res, next) => {
  res.locals.url_for = (name, params = {}) => {
    if (name === 'static') {
      const filename = params.filename || '';
      return `/static/${filename}`;
    }
    const target = routePaths[name];
    if (!target) return '#';
    let pathValue = '';
    let usedKeys = [];
    if (typeof target === 'string') {
      pathValue = target;
    } else if (target && typeof target === 'object' && target.path) {
      pathValue = target.path;
      usedKeys = target.params || [];
      for (const key of usedKeys) {
        const value = params[key];
        if (value === undefined) {
          return '#';
        }
        pathValue = pathValue.replace(`:${key}`, encodeURIComponent(value));
      }
    }
    const queryParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (usedKeys.includes(key)) continue;
      if (value === undefined || value === null || value === '') continue;
      if (Array.isArray(value)) {
        value.forEach((item) => queryParams.append(key, item));
      } else {
        queryParams.append(key, value);
      }
    }
    const queryString = queryParams.toString();
    return queryString ? `${pathValue}?${queryString}` : pathValue;
  };
  next();
});

function ensureAuthenticated(req, res, next) {
  if (!req.session.user) {
    req.flash('info', 'Vui lòng đăng nhập để truy cập trang này.');
    return res.redirect('/login');
  }
  next();
}

function roleRequired(role) {
  return (req, res, next) => {
    if (!req.session.user) {
      req.flash('info', 'Vui lòng đăng nhập để truy cập trang này.');
      return res.redirect('/login');
    }
    if (req.session.user.vai_tro !== role) {
      return res.status(403).render('403.html');
    }
    next();
  };
}

function convert10To4Scale(score) {
  if (score >= 8.5) return 4.0;
  if (score >= 8.0) return 3.5;
  if (score >= 7.0) return 3.0;
  if (score >= 6.5) return 2.5;
  if (score >= 5.5) return 2.0;
  if (score >= 5.0) return 1.5;
  if (score >= 4.0) return 1.0;
  return 0.0;
}

function classifyGPA10(gpa) {
  if (gpa >= 9.0) return 'Xuất sắc';
  if (gpa >= 8.0) return 'Giỏi';
  if (gpa >= 6.5) return 'Khá';
  if (gpa >= 5.0) return 'Trung bình';
  return 'Yếu';
}

app.get('/', (req, res) => {
  res.redirect('/login');
});

app.get('/login', (req, res) => {
  if (req.session.user) {
    if (req.session.user.vai_tro === VaiTroEnum.SINHVIEN) {
      return res.redirect('/student/dashboard');
    }
    return res.redirect('/admin/dashboard');
  }
  res.render('login.html');
});

app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const user = await TaiKhoan.findByPk(username);
  if (!user) {
    req.flash('danger', 'Sai tên đăng nhập hoặc mật khẩu.');
    return res.redirect('/login');
  }

  const match = await bcrypt.compare(password, user.password);
  if (!match) {
    req.flash('danger', 'Sai tên đăng nhập hoặc mật khẩu.');
    return res.redirect('/login');
  }

  req.session.user = {
    username: user.username,
    vai_tro: user.vai_tro,
  };
  req.flash('success', 'Đăng nhập thành công!');

  if (user.vai_tro === VaiTroEnum.SINHVIEN) {
    return res.redirect('/student/dashboard');
  }
  return res.redirect('/admin/dashboard');
});

app.get('/logout', ensureAuthenticated, (req, res) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

app.get('/student/dashboard', ensureAuthenticated, roleRequired(VaiTroEnum.SINHVIEN), async (req, res) => {
  const student = await SinhVien.findByPk(req.session.user.username, {
    raw: true,
  });
  let notifications = [];
  if (student && student.lop) {
    notifications = await ThongBao.findAll({
      where: { lop_nhan: student.lop },
      order: [['ngay_gui', 'DESC']],
      limit: 10,
      raw: true,
    });
  }
  res.render('student_dashboard.html', { sinh_vien: student, notifications });
});

app.route('/student/profile')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.SINHVIEN))
  .get(async (req, res) => {
    const sv = await SinhVien.findByPk(req.session.user.username, { raw: true });
    res.render('student_profile.html', { sv });
  })
  .post(async (req, res) => {
    try {
      const sv = await SinhVien.findByPk(req.session.user.username);
      if (!sv) {
        req.flash('danger', 'Không tìm thấy sinh viên.');
        return res.redirect('/student/profile');
      }
      sv.ho_ten = req.body.ho_ten;
      sv.ngay_sinh = req.body.ngay_sinh || null;
      sv.email = req.body.email || null;
      sv.location = req.body.location || null;
      await sv.save();
      req.flash('success', 'Cập nhật thông tin cá nhân thành công!');
    } catch (error) {
      if (error.name === 'SequelizeUniqueConstraintError') {
        req.flash('danger', 'Lỗi: Email này đã được sử dụng bởi một tài khoản khác.');
      } else {
        req.flash('danger', `Lỗi khi cập nhật thông tin: ${error.message}`);
      }
    }
    res.redirect('/student/profile');
  });

app.get('/student/grades', ensureAuthenticated, roleRequired(VaiTroEnum.SINHVIEN), async (req, res) => {
  const ma_sv = req.session.user.username;
  const grades = await KetQua.findAll({
    where: { ma_sv },
    include: [{ model: MonHoc, required: true }],
    order: [[MonHoc, 'ma_mh', 'ASC']],
  });

  let totalPoints10 = 0;
  let totalPoints4 = 0;
  let totalCredits = 0;
  const chart_labels = [];
  const chart_data = [];

  const results = grades.map((grade) => {
    const row = grade.get({ plain: true });
    const subject = grade.MonHoc.get({ plain: true });
    const diem_he_4 = convert10To4Scale(row.diem_thi);
    totalPoints10 += row.diem_thi * subject.so_tin_chi;
    totalPoints4 += diem_he_4 * subject.so_tin_chi;
    totalCredits += subject.so_tin_chi;
    chart_labels.push(subject.ma_mh);
    chart_data.push(row.diem_thi);
    return {
      ma_mh: subject.ma_mh,
      ten_mh: subject.ten_mh,
      so_tin_chi: subject.so_tin_chi,
      diem_thi: row.diem_thi,
    };
  });

  const gpa_10 = totalCredits > 0 ? totalPoints10 / totalCredits : 0;
  const gpa_4 = totalCredits > 0 ? totalPoints4 / totalCredits : 0;

  res.render('student_grades.html', {
    results,
    gpa_10,
    gpa_4,
    chart_labels,
    chart_data,
  });
});

app.get('/admin/dashboard', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const total_sv = await SinhVien.count();
  const total_mh = await MonHoc.count();
  res.render('admin_dashboard.html', { total_sv, total_mh });
});

app.get('/admin/students', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const search_ma_sv = req.query.ma_sv || '';
  const search_ho_ten = req.query.ho_ten || '';
  const filter_lop = req.query.lop || '';
  const filter_khoa = req.query.khoa || '';

  const where = {};
  if (search_ma_sv) {
    where.ma_sv = { [Op.like]: `%${search_ma_sv}%` };
  }
  if (search_ho_ten) {
    where.ho_ten = { [Op.like]: `%${search_ho_ten}%` };
  }
  if (filter_lop) {
    where.lop = filter_lop;
  }
  if (filter_khoa) {
    where.khoa = filter_khoa;
  }

  const students = await SinhVien.findAll({
    where,
    order: [['ma_sv', 'ASC']],
    raw: true,
  });

  const lop_hoc_tuples = await SinhVien.findAll({
    attributes: [[sequelize.fn('DISTINCT', sequelize.col('lop')), 'lop']],
    order: [[sequelize.col('lop'), 'ASC']],
    raw: true,
  });
  const danh_sach_lop = lop_hoc_tuples.map((row) => row.lop).filter(Boolean);

  const khoa_tuples = await SinhVien.findAll({
    attributes: [[sequelize.fn('DISTINCT', sequelize.col('khoa')), 'khoa']],
    order: [[sequelize.col('khoa'), 'ASC']],
    raw: true,
  });
  const danh_sach_khoa = khoa_tuples.map((row) => row.khoa).filter(Boolean);

  res.render('admin_manage_students.html', {
    students,
    danh_sach_lop,
    danh_sach_khoa,
    search_params: {
      ma_sv: search_ma_sv,
      ho_ten: search_ho_ten,
      lop: filter_lop,
      khoa: filter_khoa,
    },
  });
});

app.route('/admin/students/add')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get((req, res) => {
    res.render('admin_add_student.html');
  })
  .post(async (req, res) => {
    const { ma_sv, ho_ten, ngay_sinh, lop, khoa } = req.body;
    const existing = await TaiKhoan.findByPk(ma_sv);
    if (existing) {
      req.flash('danger', 'Lỗi: Mã sinh viên đã tồn tại.');
      return res.redirect('/admin/students/add');
    }

    try {
      const password = `${ma_sv}@123`;
      const hashed = await bcrypt.hash(password, 10);
      await sequelize.transaction(async (transaction) => {
        await TaiKhoan.create({
          username: ma_sv,
          password: hashed,
          vai_tro: VaiTroEnum.SINHVIEN,
        }, { transaction });
        await SinhVien.create({
          ma_sv,
          ho_ten,
          ngay_sinh: ngay_sinh || null,
          lop,
          khoa,
        }, { transaction });
      });
      req.flash('success', 'Thêm sinh viên và tài khoản thành công!');
    } catch (error) {
      req.flash('danger', `Đã xảy ra lỗi: ${error.message}`);
    }
    res.redirect('/admin/students');
  });

app.route('/admin/students/edit/:ma_sv')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get(async (req, res) => {
    const sv = await SinhVien.findByPk(req.params.ma_sv, { raw: true });
    if (!sv) {
      return res.status(404).render('403.html');
    }
    res.render('admin_edit_student.html', { sv });
  })
  .post(async (req, res) => {
    try {
      const sv = await SinhVien.findByPk(req.params.ma_sv);
      if (!sv) {
        return res.status(404).render('403.html');
      }
      sv.ho_ten = req.body.ho_ten;
      sv.ngay_sinh = req.body.ngay_sinh || null;
      sv.lop = req.body.lop;
      sv.khoa = req.body.khoa;
      await sv.save();
      req.flash('success', 'Cập nhật thông tin sinh viên thành công!');
    } catch (error) {
      req.flash('danger', `Lỗi khi cập nhật: ${error.message}`);
    }
    res.redirect('/admin/students');
  });

app.post('/admin/students/delete/:ma_sv', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  try {
    const sv = await SinhVien.findByPk(req.params.ma_sv);
    if (sv) {
      await sequelize.transaction(async (transaction) => {
        await sv.destroy({ transaction });
        await TaiKhoan.destroy({ where: { username: req.params.ma_sv }, transaction });
      });
      req.flash('success', 'Đã xóa sinh viên và tài khoản liên quan thành công!');
    }
  } catch (error) {
    req.flash('danger', `Lỗi khi xóa sinh viên: ${error.message}`);
  }
  res.redirect('/admin/students');
});

app.get('/admin/courses', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const courses = await MonHoc.findAll({ order: [['ma_mh', 'ASC']], raw: true });
  res.render('admin_manage_courses.html', { courses });
});

app.route('/admin/courses/add')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get((req, res) => {
    res.render('admin_add_course.html');
  })
  .post(async (req, res) => {
    try {
      await MonHoc.create({
        ma_mh: req.body.ma_mh,
        ten_mh: req.body.ten_mh,
        so_tin_chi: parseInt(req.body.so_tin_chi, 10),
      });
      req.flash('success', 'Thêm môn học thành công!');
      res.redirect('/admin/courses');
    } catch (error) {
      req.flash('danger', `Lỗi khi thêm môn học: ${error.message}`);
      res.redirect('/admin/courses/add');
    }
  });

app.route('/admin/courses/edit/:ma_mh')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get(async (req, res) => {
    const course = await MonHoc.findByPk(req.params.ma_mh, { raw: true });
    if (!course) {
      return res.status(404).render('403.html');
    }
    res.render('admin_edit_course.html', { course });
  })
  .post(async (req, res) => {
    try {
      const course = await MonHoc.findByPk(req.params.ma_mh);
      if (!course) {
        return res.status(404).render('403.html');
      }
      course.ten_mh = req.body.ten_mh;
      course.so_tin_chi = parseInt(req.body.so_tin_chi, 10);
      await course.save();
      req.flash('success', 'Cập nhật môn học thành công!');
    } catch (error) {
      req.flash('danger', `Lỗi khi cập nhật: ${error.message}`);
    }
    res.redirect('/admin/courses');
  });

app.post('/admin/courses/delete/:ma_mh', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  try {
    const course = await MonHoc.findByPk(req.params.ma_mh);
    if (course) {
      await course.destroy();
      req.flash('success', 'Đã xóa môn học thành công!');
    }
  } catch (error) {
    req.flash('danger', `Lỗi khi xóa môn học: ${error.message}`);
  }
  res.redirect('/admin/courses');
});

app.route('/admin/grades')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get(async (req, res) => {
    const lop_hoc_tuples = await SinhVien.findAll({
      attributes: [[sequelize.fn('DISTINCT', sequelize.col('lop')), 'lop']],
      order: [[sequelize.col('lop'), 'ASC']],
      raw: true,
    });
    const danh_sach_lop = lop_hoc_tuples.map((row) => row.lop).filter(Boolean);
    const danh_sach_mon_hoc = await MonHoc.findAll({ order: [['ten_mh', 'ASC']], raw: true });
    res.render('admin_manage_grades.html', { danh_sach_lop, danh_sach_mon_hoc });
  })
  .post(async (req, res) => {
    const selected_lop = req.body.lop;
    const selected_mh = req.body.ma_mh;
    if (selected_lop && selected_mh) {
      return res.redirect(`/admin/grades/enter/${encodeURIComponent(selected_lop)}/${encodeURIComponent(selected_mh)}`);
    }
    req.flash('danger', 'Vui lòng chọn lớp và môn học.');
    res.redirect('/admin/grades');
  });

app.get('/admin/grades/enter/:lop/:ma_mh', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const { lop, ma_mh } = req.params;
  const mon_hoc = await MonHoc.findByPk(ma_mh, { raw: true });
  if (!mon_hoc) {
    req.flash('danger', 'Không tìm thấy môn học.');
    return res.redirect('/admin/grades');
  }
  const sinh_vien_list = await SinhVien.findAll({
    where: { lop },
    order: [['ma_sv', 'ASC']],
    raw: true,
  });
  if (sinh_vien_list.length === 0) {
    req.flash('warning', `Không tìm thấy sinh viên nào trong lớp ${lop}.`);
    return res.redirect('/admin/grades');
  }
  const ids = sinh_vien_list.map((sv) => sv.ma_sv);
  const existingGrades = await KetQua.findAll({
    where: {
      ma_sv: { [Op.in]: ids },
      ma_mh,
    },
    raw: true,
  });
  const gradeMap = new Map(existingGrades.map((item) => [`${item.ma_sv}`, item.diem_thi]));
  const danh_sach_nhap_diem = sinh_vien_list.map((sv) => ({
    ma_sv: sv.ma_sv,
    ho_ten: sv.ho_ten,
    diem_thi: gradeMap.get(sv.ma_sv) ?? null,
  }));
  res.render('admin_enter_grades.html', { lop, mon_hoc, danh_sach_nhap_diem });
});

app.post('/admin/grades/save', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const { ma_mh, lop } = req.body;
  let updated = 0;
  let created = 0;
  try {
    const entries = Object.entries(req.body);
    for (const [key, value] of entries) {
      if (!key.startsWith('diem_')) continue;
      const ma_sv = key.slice(5);
      if (!value) continue;
      const diem = parseFloat(value);
      if (Number.isNaN(diem) || diem < 0 || diem > 10) {
        req.flash('danger', `Lỗi: Điểm "${value}" của SV ${ma_sv} không hợp lệ. Bỏ qua.`);
        continue;
      }
      const [grade, createdFlag] = await KetQua.findOrCreate({
        where: { ma_sv, ma_mh },
        defaults: { diem_thi: diem },
      });
      if (!createdFlag) {
        grade.diem_thi = diem;
        await grade.save();
        updated += 1;
      } else {
        created += 1;
      }
    }
    req.flash('success', `Lưu điểm thành công! (Cập nhật: ${updated}, Thêm mới: ${created})`);
  } catch (error) {
    req.flash('danger', `Đã xảy ra lỗi nghiêm trọng khi lưu điểm: ${error.message}`);
  }
  res.redirect('/admin/grades');
});

app.get('/admin/reports', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), (req, res) => {
  res.render('admin_reports_index.html');
});

app.get('/admin/reports/high_gpa', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const GPA_THRESHOLD = 8.0;
  const query = `
    SELECT sv.ma_sv, sv.ho_ten, sv.lop,
      SUM(kq.diem_thi * mh.so_tin_chi) / SUM(mh.so_tin_chi) AS gpa,
      SUM(
        CASE
          WHEN kq.diem_thi >= 8.5 THEN 4.0
          WHEN kq.diem_thi >= 8.0 THEN 3.5
          WHEN kq.diem_thi >= 7.0 THEN 3.0
          WHEN kq.diem_thi >= 6.5 THEN 2.5
          WHEN kq.diem_thi >= 5.5 THEN 2.0
          WHEN kq.diem_thi >= 5.0 THEN 1.5
          WHEN kq.diem_thi >= 4.0 THEN 1.0
          ELSE 0.0
        END * mh.so_tin_chi
      ) / SUM(mh.so_tin_chi) AS gpa_4
    FROM sinh_vien sv
    JOIN ket_qua kq ON sv.ma_sv = kq.ma_sv
    JOIN mon_hoc mh ON kq.ma_mh = mh.ma_mh
    GROUP BY sv.ma_sv, sv.ho_ten, sv.lop
    HAVING gpa > :threshold
    ORDER BY gpa DESC
  `;
  const [results] = await sequelize.query(query, {
    replacements: { threshold: GPA_THRESHOLD },
  });
  const category_counts = { Yếu: 0, 'Trung bình': 0, 'Khá': 0, 'Giỏi': 0, 'Xuất sắc': 0 };
  for (const row of results) {
    const category = classifyGPA10(row.gpa);
    if (category_counts[category] !== undefined) {
      category_counts[category] += 1;
    }
  }
  const chart_labels = Object.keys(category_counts);
  const chart_data = Object.values(category_counts);
  res.render('admin_report_high_gpa.html', {
    results,
    threshold: GPA_THRESHOLD,
    chart_labels,
    chart_data,
  });
});

app.get('/admin/reports/missing_grade', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const danh_sach_mon_hoc = await MonHoc.findAll({ order: [['ten_mh', 'ASC']], raw: true });
  const selected_mh_id = req.query.ma_mh;
  let selected_mon_hoc = null;
  let results = [];
  if (selected_mh_id) {
    selected_mon_hoc = await MonHoc.findByPk(selected_mh_id, { raw: true });
    const missingQuery = `
      SELECT sv.* FROM sinh_vien sv
      WHERE NOT EXISTS (
        SELECT 1 FROM ket_qua kq
        WHERE kq.ma_sv = sv.ma_sv AND kq.ma_mh = :ma_mh
      )
      ORDER BY sv.lop, sv.ma_sv
    `;
    const [rows] = await sequelize.query(missingQuery, {
      replacements: { ma_mh: selected_mh_id },
    });
    results = rows;
  }
  res.render('admin_report_missing_grade.html', {
    danh_sach_mon_hoc,
    selected_mon_hoc,
    results,
  });
});

app.get('/admin/reports/class_gpa', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const lop_hoc_tuples = await SinhVien.findAll({
    attributes: [[sequelize.fn('DISTINCT', sequelize.col('lop')), 'lop']],
    order: [[sequelize.col('lop'), 'ASC']],
    raw: true,
  });
  const danh_sach_lop = lop_hoc_tuples.map((row) => row.lop).filter(Boolean);
  const selected_lop = req.query.lop;
  let lop_gpa_10 = null;
  let lop_gpa_4 = null;
  let chart_labels = [];
  let chart_data = [];
  if (selected_lop) {
    const gpaQuery = `
      SELECT sv.ma_sv,
        SUM(kq.diem_thi * mh.so_tin_chi) / SUM(mh.so_tin_chi) AS gpa,
        SUM(
          CASE
            WHEN kq.diem_thi >= 8.5 THEN 4.0
            WHEN kq.diem_thi >= 8.0 THEN 3.5
            WHEN kq.diem_thi >= 7.0 THEN 3.0
            WHEN kq.diem_thi >= 6.5 THEN 2.5
            WHEN kq.diem_thi >= 5.5 THEN 2.0
            WHEN kq.diem_thi >= 5.0 THEN 1.5
            WHEN kq.diem_thi >= 4.0 THEN 1.0
            ELSE 0.0
          END * mh.so_tin_chi
        ) / SUM(mh.so_tin_chi) AS gpa_4
      FROM sinh_vien sv
      JOIN ket_qua kq ON sv.ma_sv = kq.ma_sv
      JOIN mon_hoc mh ON kq.ma_mh = mh.ma_mh
      WHERE sv.lop = :lop
      GROUP BY sv.ma_sv
    `;
    const [rows] = await sequelize.query(gpaQuery, {
      replacements: { lop: selected_lop },
    });
    if (rows.length > 0) {
      const totalGPA10 = rows.reduce((sum, row) => sum + (row.gpa || 0), 0);
      const totalGPA4 = rows.reduce((sum, row) => sum + (row.gpa_4 || 0), 0);
      lop_gpa_10 = totalGPA10 / rows.length;
      lop_gpa_4 = totalGPA4 / rows.length;
      const category_counts = { Yếu: 0, 'Trung bình': 0, 'Khá': 0, 'Giỏi': 0, 'Xuất sắc': 0 };
      for (const row of rows) {
        const category = classifyGPA10(row.gpa);
        if (category_counts[category] !== undefined) {
          category_counts[category] += 1;
        }
      }
      chart_labels = Object.keys(category_counts).filter((label) => category_counts[label] > 0);
      chart_data = chart_labels.map((label) => category_counts[label]);
    } else {
      lop_gpa_10 = 0;
      lop_gpa_4 = 0;
      chart_labels = [];
      chart_data = [];
    }
  }
  res.render('admin_report_class_gpa.html', {
    danh_sach_lop,
    selected_lop,
    lop_gpa_10,
    lop_gpa_4,
    chart_labels,
    chart_data,
  });
});

app.route('/admin/notify')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get(async (req, res) => {
    const lop_hoc_tuples = await SinhVien.findAll({
      attributes: [[sequelize.fn('DISTINCT', sequelize.col('lop')), 'lop']],
      order: [[sequelize.col('lop'), 'ASC']],
      raw: true,
    });
    const danh_sach_lop = lop_hoc_tuples.map((row) => row.lop).filter(Boolean);
    res.render('admin_send_notification.html', { danh_sach_lop });
  })
  .post(async (req, res) => {
    const { lop_nhan, tieu_de, noi_dung } = req.body;
    if (!lop_nhan || !tieu_de || !noi_dung) {
      req.flash('danger', 'Vui lòng điền đầy đủ Lớp, Tiêu đề và Nội dung.');
      return res.redirect('/admin/notify');
    }
    try {
      await ThongBao.create({
        lop_nhan,
        tieu_de,
        noi_dung,
        ma_gv: req.session.user.username,
      });
      req.flash('success', `Gửi thông báo đến lớp ${lop_nhan} thành công!`);
    } catch (error) {
      req.flash('danger', `Lỗi khi gửi thông báo: ${error.message}`);
    }
    res.redirect('/admin/notify');
  });

app.route('/admin/import_students')
  .all(ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN))
  .get((req, res) => {
    res.render('admin_import_students.html');
  })
  .post(upload.single('file'), async (req, res) => {
    if (!req.file) {
      req.flash('danger', 'Không có tệp nào được chọn.');
      return res.redirect('/admin/import_students');
    }
    if (!req.file.originalname.match(/\.(xls|xlsx)$/i)) {
      req.flash('danger', 'Vui lòng chọn tệp Excel (.xls hoặc .xlsx).');
      try {
        fs.unlinkSync(req.file.path);
      } catch (err) {
        // ignore cleanup errors
      }
      return res.redirect('/admin/import_students');
    }
    try {
      const workbook = xlsx.readFile(req.file.path, { cellDates: true });
      const sheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[sheetName];
      const rows = xlsx.utils.sheet_to_json(worksheet);
      const required = ['ma_sinh_vien', 'ten_sinh_vien', 'password', 'role'];
      for (const field of required) {
        if (!rows.length || !Object.prototype.hasOwnProperty.call(rows[0], field)) {
          throw new Error(`File Excel phải chứa các cột: ${required.join(', ')}`);
        }
      }
      let created_count = 0;
      const errors = [];
      const parseDateValue = (value) => {
        if (!value) return null;
        if (value instanceof Date && !Number.isNaN(value.getTime())) {
          return value.toISOString().split('T')[0];
        }
        if (typeof value === 'number' && xlsx.SSF && typeof xlsx.SSF.parse_date_code === 'function') {
          const parsed = xlsx.SSF.parse_date_code(value);
          if (parsed) {
            const jsDate = new Date(Date.UTC(parsed.y, parsed.m - 1, parsed.d));
            if (!Number.isNaN(jsDate.getTime())) {
              return jsDate.toISOString().split('T')[0];
            }
          }
        }
        const parsedDate = new Date(value);
        if (!Number.isNaN(parsedDate.getTime())) {
          return parsedDate.toISOString().split('T')[0];
        }
        return null;
      };

      for (let index = 0; index < rows.length; index += 1) {
        const row = rows[index];
        const ma_sv = String(row.ma_sinh_vien);
        const ten_sv = String(row.ten_sinh_vien);
        const password = String(row.password);
        const role = String(row.role || '').toUpperCase();
        if (role !== VaiTroEnum.SINHVIEN) {
          errors.push(`Dòng ${index + 2}: Vai trò "${role}" không hợp lệ, chỉ chấp nhận "SINHVIEN". Bỏ qua.`);
          continue;
        }
        const existing = await TaiKhoan.findByPk(ma_sv);
        if (existing) {
          errors.push(`Dòng ${index + 2}: Mã SV "${ma_sv}" đã tồn tại. Bỏ qua.`);
          continue;
        }
        const hashed = await bcrypt.hash(password, 10);
        const toStringOrNull = (value) => {
          if (value === undefined || value === null) return null;
          if (value instanceof Date) return value.toISOString().split('T')[0];
          if (typeof value === 'string' && value.trim() === '') return null;
          return String(value);
        };
        try {
          await sequelize.transaction(async (transaction) => {
            await TaiKhoan.create({
              username: ma_sv,
              password: hashed,
              vai_tro: VaiTroEnum.SINHVIEN,
            }, { transaction });
            await SinhVien.create({
              ma_sv,
              ho_ten: ten_sv,
              lop: toStringOrNull(row.lop),
              khoa: toStringOrNull(row.khoa),
              email: toStringOrNull(row.email),
              location: toStringOrNull(row.location),
              ngay_sinh: parseDateValue(row.ngay_sinh),
            }, { transaction });
          });
          created_count += 1;
        } catch (err) {
          errors.push(`Dòng ${index + 2}: ${err.message}`);
        }
      }
      req.flash('success', `Nhập file thành công! Đã thêm mới ${created_count} sinh viên.`);
      errors.forEach((message) => req.flash('warning', message));
    } catch (error) {
      req.flash('danger', `Đã xảy ra lỗi nghiêm trọng khi đọc file: ${error.message}`);
    } finally {
      if (req.file) {
        try {
          fs.unlinkSync(req.file.path);
        } catch (err) {
          // ignore cleanup errors
        }
      }
    }
    res.redirect('/admin/students');
  });

app.get('/admin/export_grades', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const lop_hoc_tuples = await SinhVien.findAll({
    attributes: [[sequelize.fn('DISTINCT', sequelize.col('lop')), 'lop']],
    order: [[sequelize.col('lop'), 'ASC']],
    raw: true,
  });
  const danh_sach_lop = lop_hoc_tuples.map((row) => row.lop).filter(Boolean);
  res.render('admin_export_grades.html', { danh_sach_lop });
});

app.post('/admin/export/perform', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const selected_lop = req.body.lop;
  if (!selected_lop) {
    req.flash('danger', 'Vui lòng chọn một lớp.');
    return res.redirect('/admin/export_grades');
  }
  const students = await SinhVien.findAll({
    where: { lop: selected_lop },
    raw: true,
  });
  if (students.length === 0) {
    req.flash('warning', `Không tìm thấy sinh viên nào trong lớp ${selected_lop}.`);
    return res.redirect('/admin/export_grades');
  }
  const studentIds = students.map((sv) => sv.ma_sv);
  const gradeRows = await KetQua.findAll({
    where: { ma_sv: { [Op.in]: studentIds } },
    include: [{ model: MonHoc, required: true }],
  });
  const courseSet = new Map();
  for (const row of gradeRows) {
    const course = row.MonHoc.get({ plain: true });
    courseSet.set(course.ma_mh, course.ten_mh);
  }
  const courses = Array.from(courseSet.entries());
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet(`Diem_Lop_${selected_lop}`);
  const header = ['Mã SV', 'Họ tên'];
  for (const [ma_mh, ten_mh] of courses) {
    header.push(`${ma_mh} (${ten_mh})`);
  }
  sheet.addRow(header);
  const gradeMap = new Map();
  for (const row of gradeRows) {
    const data = row.get({ plain: true });
    const key = data.ma_sv;
    if (!gradeMap.has(key)) {
      gradeMap.set(key, new Map());
    }
    gradeMap.get(key).set(data.ma_mh, data.diem_thi);
  }
  for (const sv of students) {
    const row = [sv.ma_sv, sv.ho_ten];
    const map = gradeMap.get(sv.ma_sv) || new Map();
    for (const [ma_mh] of courses) {
      row.push(map.has(ma_mh) ? map.get(ma_mh) : '');
    }
    sheet.addRow(row);
  }
  const buffer = await workbook.xlsx.writeBuffer();
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', `attachment; filename=BangDiem_Lop_${selected_lop}.xlsx`);
  res.send(Buffer.from(buffer));
});

app.get('/admin/export_students_excel', ensureAuthenticated, roleRequired(VaiTroEnum.GIAOVIEN), async (req, res) => {
  const search_ma_sv = req.query.ma_sv || '';
  const search_ho_ten = req.query.ho_ten || '';
  const filter_lop = req.query.lop || '';
  const filter_khoa = req.query.khoa || '';

  const where = {};
  if (search_ma_sv) {
    where.ma_sv = { [Op.like]: `%${search_ma_sv}%` };
  }
  if (search_ho_ten) {
    where.ho_ten = { [Op.like]: `%${search_ho_ten}%` };
  }
  if (filter_lop) {
    where.lop = filter_lop;
  }
  if (filter_khoa) {
    where.khoa = filter_khoa;
  }

  const students = await SinhVien.findAll({
    where,
    order: [['ma_sv', 'ASC']],
    raw: true,
  });
  if (students.length === 0) {
    req.flash('warning', 'Không có dữ liệu sinh viên nào để xuất.');
    return res.redirect('/admin/students');
  }
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('DanhSachSinhVien');
  sheet.addRow(['Mã SV', 'Họ tên', 'Ngày sinh', 'Lớp', 'Khoa', 'Email', 'Địa chỉ (Location)']);
  for (const sv of students) {
    const ngaySinh = sv.ngay_sinh ? format(new Date(sv.ngay_sinh), 'dd-MM-yyyy') : '';
    sheet.addRow([
      sv.ma_sv,
      sv.ho_ten,
      ngaySinh,
      sv.lop || '',
      sv.khoa || '',
      sv.email || '',
      sv.location || '',
    ]);
  }
  const buffer = await workbook.xlsx.writeBuffer();
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', 'attachment; filename=DanhSachSinhVien_Filtered.xlsx');
  res.send(Buffer.from(buffer));
});

app.use((req, res) => {
  res.status(404).render('403.html');
});

const PORT = process.env.PORT || 5000;

initDatabase().then(() => {
  app.listen(PORT, () => {
    console.log(`Server is running at http://localhost:${PORT}`);
  });
}).catch((error) => {
  console.error('Failed to initialize database:', error);
});
