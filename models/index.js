const path = require('path');
const { Sequelize, DataTypes, Op } = require('sequelize');

const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: path.join(__dirname, '..', 'qlsv.db'),
  logging: false,
});

const VaiTroEnum = {
  SINHVIEN: 'SINHVIEN',
  GIAOVIEN: 'GIAOVIEN',
};

const TaiKhoan = sequelize.define('TaiKhoan', {
  username: {
    type: DataTypes.STRING(50),
    primaryKey: true,
  },
  password: {
    type: DataTypes.STRING(255),
    allowNull: false,
  },
  vai_tro: {
    type: DataTypes.ENUM(VaiTroEnum.SINHVIEN, VaiTroEnum.GIAOVIEN),
    allowNull: false,
  },
}, {
  tableName: 'tai_khoan',
  timestamps: false,
});

const SinhVien = sequelize.define('SinhVien', {
  ma_sv: {
    type: DataTypes.STRING(50),
    primaryKey: true,
  },
  ho_ten: {
    type: DataTypes.STRING(100),
    allowNull: false,
  },
  ngay_sinh: {
    type: DataTypes.DATEONLY,
  },
  lop: {
    type: DataTypes.STRING(50),
  },
  khoa: {
    type: DataTypes.STRING(100),
  },
  email: {
    type: DataTypes.STRING(150),
    unique: true,
  },
  location: {
    type: DataTypes.STRING(200),
  },
}, {
  tableName: 'sinh_vien',
  timestamps: false,
});

const MonHoc = sequelize.define('MonHoc', {
  ma_mh: {
    type: DataTypes.STRING(50),
    primaryKey: true,
  },
  ten_mh: {
    type: DataTypes.STRING(100),
    allowNull: false,
  },
  so_tin_chi: {
    type: DataTypes.INTEGER,
    allowNull: false,
  },
}, {
  tableName: 'mon_hoc',
  timestamps: false,
});

const KetQua = sequelize.define('KetQua', {
  ma_sv: {
    type: DataTypes.STRING(50),
    primaryKey: true,
  },
  ma_mh: {
    type: DataTypes.STRING(50),
    primaryKey: true,
  },
  diem_thi: {
    type: DataTypes.FLOAT,
    allowNull: false,
  },
}, {
  tableName: 'ket_qua',
  timestamps: false,
});

const ThongBao = sequelize.define('ThongBao', {
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  tieu_de: {
    type: DataTypes.STRING(200),
    allowNull: false,
  },
  noi_dung: {
    type: DataTypes.TEXT,
    allowNull: false,
  },
  ngay_gui: {
    type: DataTypes.DATE,
    defaultValue: Sequelize.literal('CURRENT_TIMESTAMP'),
  },
  ma_gv: {
    type: DataTypes.STRING(50),
    allowNull: false,
  },
  lop_nhan: {
    type: DataTypes.STRING(50),
    allowNull: false,
  },
}, {
  tableName: 'thong_bao',
  timestamps: false,
});

TaiKhoan.hasOne(SinhVien, {
  foreignKey: 'ma_sv',
  sourceKey: 'username',
  onDelete: 'CASCADE',
  hooks: true,
});
SinhVien.belongsTo(TaiKhoan, {
  foreignKey: 'ma_sv',
  targetKey: 'username',
});

SinhVien.hasMany(KetQua, {
  foreignKey: 'ma_sv',
  onDelete: 'CASCADE',
  hooks: true,
});
KetQua.belongsTo(SinhVien, {
  foreignKey: 'ma_sv',
});

MonHoc.hasMany(KetQua, {
  foreignKey: 'ma_mh',
  onDelete: 'CASCADE',
  hooks: true,
});
KetQua.belongsTo(MonHoc, {
  foreignKey: 'ma_mh',
});

TaiKhoan.hasMany(ThongBao, {
  foreignKey: 'ma_gv',
  sourceKey: 'username',
});
ThongBao.belongsTo(TaiKhoan, {
  foreignKey: 'ma_gv',
  targetKey: 'username',
});

async function initDatabase() {
  await sequelize.sync();

  const existingTeacher = await TaiKhoan.findByPk('giaovien01');
  if (!existingTeacher) {
    const bcrypt = require('bcryptjs');
    const hashed = await bcrypt.hash('admin@123', 10);
    await TaiKhoan.create({
      username: 'giaovien01',
      password: hashed,
      vai_tro: VaiTroEnum.GIAOVIEN,
    });
  }
}

module.exports = {
  sequelize,
  Op,
  VaiTroEnum,
  TaiKhoan,
  SinhVien,
  MonHoc,
  KetQua,
  ThongBao,
  initDatabase,
};
