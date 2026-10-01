import { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, MapPin, Briefcase, Building, User, LogOut } from 'lucide-react';
import './App.css';

function App() {
  const [jobs, setJobs] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('home'); // 'home' hoặc 'login'
  
  // Form state đăng nhập
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  // Lấy danh sách tin tuyển dụng thật từ Backend (PostgreSQL) khi mở trang
  useEffect(() => {
    axios.get('http://localhost:8000/tin-tuyen-dung/danh-sach')
      .then((response) => {
        setJobs(response.data); // Nhận dữ liệu thật từ database lên giao diện
      })
      .catch((err) => {
        console.log("Không thể kết nối lấy danh sách việc làm:", err);
      });
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await axios.post('http://localhost:8000/auth/login', { email, password });
      setUser(response.data.user_info);
      setActiveTab('home');
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng nhập thất bại!');
    }
  };

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', backgroundColor: '#f8f9fa', minHeight: '100vh', margin: 0 }}>
      
      {/* 1. HEADER (Navbar chuẩn ITviec/TopCV) */}
      <header style={{ background: '#ffffff', borderBottom: '1px solid #e2e8f0', padding: '15px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '30px' }}>
          <h2 style={{ color: '#00b14f', margin: 0, cursor: 'pointer' }} onClick={() => setActiveTab('home')}>
            🚀 IT Jobs Platform
          </h2>
          <nav style={{ display: 'flex', gap: '20px', fontWeight: 500, color: '#4a5568' }}>
            <span style={{ cursor: 'pointer' }} onClick={() => setActiveTab('home')}>Việc Làm IT</span>
            <span style={{ cursor: 'pointer' }}>Công Ty Hàng Đầu</span>
            <span style={{ cursor: 'pointer' }}>Dành Cho Nhà Tuyển Dụng</span>
          </nav>
        </div>

        <div>
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <span style={{ fontWeight: 600, color: '#2d3748' }}><User size={16}/> {user.full_name || user.email}</span>
              <button onClick={() => setUser(null)} style={{ background: '#fed7d7', color: '#c53030', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <LogOut size={14}/> Đăng xuất
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => setActiveTab('login')} style={{ background: 'transparent', border: '1px solid #00b14f', color: '#00b14f', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                Đăng Nhập
              </button>
              <button style={{ background: '#00b14f', border: 'none', color: 'white', padding: '8px 16px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                Đăng Ký
              </button>
            </div>
          )}
        </div>
      </header>

      {/* 2. NỘI DUNG THAY ĐỔI THEO TAB */}
      {activeTab === 'login' ? (
        /* Form Đăng Nhập */
        <div style={{ maxWidth: '400px', margin: '60px auto', background: 'white', padding: '30px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
          <h2 style={{ textAlign: 'center', color: '#2d3748', marginBottom: '20px' }}>Đăng Nhập Hệ Thống</h2>
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            <div>
              <label style={{ fontSize: '14px', fontWeight: 500 }}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #cbd5e0', boxSizing: 'border-box' }} />
            </div>
            <div>
              <label style={{ fontSize: '14px', fontWeight: 500 }}>Mật khẩu</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #cbd5e0', boxSizing: 'border-box' }} />
            </div>
            <button type="submit" style={{ padding: '12px', background: '#00b14f', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', marginTop: '10px' }}>
              Đăng Nhập
            </button>
          </form>
          {error && <p style={{ color: 'red', fontSize: '14px', textAlign: 'center', marginTop: '15px' }}>{error}</p>}
        </div>
      ) : (
        /* Trang Chủ: Hero Banner + Danh sách việc làm */
        <div>
          {/* Hero Banner Tìm Kiếm (Đặc trưng TopCV/ITviec) */}
          <div style={{ background: 'linear-gradient(135deg, #1a365d 0%, #2a4365 100%)', padding: '50px 20px', textAlign: 'center', color: 'white' }}>
            <h1 style={{ margin: '0 0 10px 0', fontSize: '32px' }}>1,000+ Việc Làm IT Hàng Đầu Cho Bạn</h1>
            <p style={{ color: '#cbd5e0', marginBottom: '30px' }}>Tìm kiếm cơ hội việc làm Data Engineering, Backend, Frontend phù hợp nhất</p>
            
            <div style={{ maxWidth: '800px', margin: '0 auto', background: 'white', padding: '10px', borderRadius: '8px', display: 'flex', gap: '10px', boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}>
              <div style={{ display: 'flex', alignItems: 'center', flex: 1, paddingLeft: '10px', gap: '10px' }}>
                <Search color="#a0aec0" size={20}/>
                <input 
                  type="text" 
                  placeholder="Nhập tên kỹ năng, vị trí, công ty..." 
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{ border: 'none', outline: 'none', width: '100%', fontSize: '15px' }}
                />
              </div>
              <button style={{ background: '#00b14f', color: 'white', border: 'none', padding: '12px 25px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', fontSize: '15px' }}>
                Tìm Kiếm
              </button>
            </div>
          </div>

          {/* Danh Sách Tin Tuyển Dụng */}
          <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }}>
            <h3 style={{ borderLeft: '4px solid #00b14f', paddingLeft: '10px', color: '#2d3748', marginBottom: '20px' }}>
              Việc Làm IT Nổi Bật
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '15px' }}>
              {jobs.map((job) => (
                <div key={job.id} style={{ background: 'white', padding: '20px', borderRadius: '8px', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'all 0.2s', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
                  <div>
                    <h4 style={{ margin: '0 0 8px 0', color: '#2b6cb0', fontSize: '18px' }}>{job.tieu_de}</h4>
                    <p style={{ margin: '0 0 10px 0', color: '#4a5568', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Building size={14}/> {job.ten_cong_ty}
                    </p>
                    <p style={{ margin: 0, color: '#718096', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <MapPin size={14}/> {job.dia_chi}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ background: '#c6f6d5', color: '#22543d', padding: '6px 12px', borderRadius: '20px', fontWeight: 600, fontSize: '14px', display: 'inline-block', marginBottom: '10px' }}>
                      ${job.luong_min} - ${job.luong_max}
                    </span><br/>
                    <button style={{ background: '#2b6cb0', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>
                      Ứng Tuyển Ngay
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;