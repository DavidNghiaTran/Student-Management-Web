# Hệ thống Quản lý Sinh viên & Điểm thi (Node.js)

Ứng dụng web quản lý sinh viên, môn học, điểm thi và thông báo được xây dựng lại hoàn toàn bằng **Node.js + Express** sử dụng **Sequelize** làm ORM và **SQLite** làm cơ sở dữ liệu mặc định. Giao diện HTML/CSS gốc được giữ nguyên và kết xuất bằng **Nunjucks** (cú pháp giống Jinja2).

## 🚀 Tính năng nổi bật
- **Xác thực & Phân quyền**: Đăng nhập với vai trò Sinh viên/Giáo viên, bảo vệ route bằng session và middleware.
- **Sinh viên**:
  - Xem bảng điều khiển với thông tin cá nhân, thông báo theo lớp.
  - Chỉnh sửa thông tin (họ tên, ngày sinh, email, địa chỉ).
  - Xem bảng điểm, biểu đồ điểm và GPA (thang 10 & 4).
- **Giáo viên**:
  - CRUD Sinh viên, tự sinh tài khoản và mật khẩu mặc định khi tạo mới.
  - CRUD Môn học.
  - Nhập điểm hàng loạt theo lớp/môn; hệ thống tự động thêm/sửa điểm.
  - Báo cáo: sinh viên GPA cao, sinh viên chưa thi môn, GPA trung bình lớp (kèm biểu đồ phân loại).
  - Gửi thông báo tới từng lớp.
  - Nhập danh sách sinh viên từ Excel, xuất bảng điểm theo lớp, xuất danh sách sinh viên đã lọc.

## 🛠️ Công nghệ
- **Backend**: Node.js, Express, Sequelize, SQLite.
- **View engine**: Nunjucks (cú pháp Jinja giữ nguyên templates cũ).
- **Auth**: express-session, bcryptjs, connect-flash.
- **Xử lý Excel**: multer (upload), xlsx (đọc), exceljs (ghi).

## 📦 Cài đặt & Khởi chạy
```bash
# Cài đặt phụ thuộc
npm install

# Khởi chạy development server
npm run dev
# hoặc
npm start
```
Ứng dụng chạy tại `http://localhost:5000`.

## 🔑 Tài khoản mặc định
Lần chạy đầu tiên sẽ tự sinh tài khoản giáo viên:
- Username: `giaovien01`
- Password: `admin@123`

Sau khi đăng nhập bạn có thể nhập dữ liệu sinh viên/môn học hoặc import từ Excel để trải nghiệm đầy đủ các tính năng.
