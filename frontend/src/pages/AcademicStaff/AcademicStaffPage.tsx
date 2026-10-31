import React, { useState, useEffect } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './AcademicStaffPage.css';

interface ProjectEligibility {
  id: number;
  student_name: string;
  student_reg_no: string;
  student_class: string;
  course_class_name?: string;
  course_class_code?: string;
  education_program: string;
  supervisor_name: string;
  topic_title_vi: string;
  initial_eligibility: 'PENDING' | 'ELIGIBLE' | 'INELIGIBLE' | 'FORCE_APPROVED' | 'DISQUALIFIED';
  ineligibility_reason: string;
  gpa_score: number | null;
  debt_credits: number;
  status: string;
}

interface CourseClassItem {
  id: number;
  class_code: string;
  class_name: string;
  program_type: string;
  program_display: string;
  student_count: number;
}

interface FinalGradeItem {
  project_id: number;
  student_id: number;
  registration_no: string;
  student_name: string;
  course_class_id: number | null;
  class_code: string;
  class_name: string;
  education_program: string;
  education_program_display: string;
  topic_title_vi: string;
  supervisor_name: string;
  reviewer_name: string;
  council_name: string;
  supervisor_score: number | null;
  reviewer_score: number | null;
  council_avg_score: number | null;
  final_score_10: number | null;
  final_score_4: number | null;
  final_letter_grade: string;
  classification: string;
  is_passed: boolean;
  is_deferred: boolean;
  deferral_reason: string;
  verdict: string;
  debt_credits: number;
  status: string;
}

interface GradeStats {
  total_students: number;
  passed_count: number;
  failed_count: number;
  deferred_count: number;
  pass_rate: number;
  average_score: number;
}

export const AcademicStaffPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'ELIGIBILITY' | 'FINAL_GRADES'>('ELIGIBILITY');
  const [batches, setBatches] = useState<any[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);

  // Tab 1: Eligibility states
  const [eligibilityProjects, setEligibilityProjects] = useState<ProjectEligibility[]>([]);
  const [loadingEligibility, setLoadingEligibility] = useState(false);
  const [filterEligibility, setFilterEligibility] = useState<string>('ALL');
  const [searchEligibility, setSearchEligibility] = useState<string>('');
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const [forceProject, setForceProject] = useState<ProjectEligibility | null>(null);
  const [forceReason, setForceReason] = useState<string>('');

  // Tab 2: Final Grades states
  const [classesList, setClassesList] = useState<CourseClassItem[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [finalGrades, setFinalGrades] = useState<FinalGradeItem[]>([]);
  const [gradeStats, setGradeStats] = useState<GradeStats | null>(null);
  const [loadingGrades, setLoadingGrades] = useState(false);
  const [searchGrade, setSearchGrade] = useState('');
  const [batchInfo, setBatchInfo] = useState<any>(null);
  const [showPrintModal, setShowPrintModal] = useState(false);

  // Fetch initial Batches
  const fetchBatches = async () => {
    try {
      const res = await apiClient.get('/admin/batches/');
      const list = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setBatches(list);
      if (list.length > 0 && !selectedBatchId) {
        setSelectedBatchId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load batches:', err);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  // Fetch Eligibility Projects
  const fetchEligibilityProjects = async () => {
    if (!selectedBatchId) return;
    try {
      setLoadingEligibility(true);
      const res = await apiClient.get(`/admin/projects/?batch_id=${selectedBatchId}`);
      setEligibilityProjects(Array.isArray(res.data) ? res.data : (res.data?.results || []));
    } catch (err) {
      console.error(err);
      setEligibilityProjects([]);
    } finally {
      setLoadingEligibility(false);
    }
  };

  // Fetch Final Grades by Class
  const fetchFinalGrades = async () => {
    if (!selectedBatchId) return;
    try {
      setLoadingGrades(true);
      let url = `/admin/academic-staff/final-grades/?batch_id=${selectedBatchId}`;
      if (selectedClassId) {
        url += `&class_id=${selectedClassId}`;
      }
      const res = await apiClient.get(url);
      setBatchInfo(res.data?.batch || null);
      setClassesList(res.data?.classes || []);
      setFinalGrades(res.data?.grades || []);
      setGradeStats(res.data?.stats || null);
    } catch (err) {
      console.error(err);
      setFinalGrades([]);
      setClassesList([]);
    } finally {
      setLoadingGrades(false);
    }
  };

  useEffect(() => {
    if (selectedBatchId) {
      if (activeTab === 'ELIGIBILITY') {
        fetchEligibilityProjects();
      } else {
        fetchFinalGrades();
      }
    }
  }, [selectedBatchId, activeTab, selectedClassId]);

  // Handle Import Eligibility
  const handleImportEligibility = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile || !selectedBatchId) return;
    try {
      setImporting(true);
      setImportResult(null);
      const formData = new FormData();
      formData.append('file', importFile);
      formData.append('batch_id', selectedBatchId.toString());

      const res = await apiClient.post('/admin/eligibility/import-excel/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportResult(res.data);
      fetchEligibilityProjects();
    } catch (err: any) {
      alert('Lỗi import file xét điều kiện: ' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(false);
    }
  };

  // Handle Force Approve
  const handleForceApproveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forceProject) return;
    try {
      await apiClient.post(`/admin/projects/${forceProject.id}/force-approve/`, {
        decision: 'FORCE_APPROVE',
        reason: forceReason.trim() || 'Khoa phê duyệt đặc cách theo đề xuất của Giáo vụ',
      });
      alert(`Đã duyệt đặc cách (Force Approve) cho sinh viên ${forceProject.student_reg_no}! Sinh viên được phép chuyển sang làm đồ án.`);
      setForceProject(null);
      setForceReason('');
      fetchEligibilityProjects();
    } catch (err: any) {
      alert('Lỗi đặc cách: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Disqualify
  const handleDisqualify = async (projId: number, regNo: string) => {
    const reason = prompt('Nhập lý do loại sinh viên này khỏi đợt đồ án:', 'Nợ quá số tín chỉ quy định (>= 10 tín chỉ)');
    if (reason === null) return;
    try {
      await apiClient.patch(`/admin/projects/${projId}/eligibility-decision/`, {
        decision: 'DISQUALIFY',
        reason: reason.trim(),
      });
      alert(`Đã loại sinh viên ${regNo} khỏi đợt đồ án.`);
      fetchEligibilityProjects();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Export Class Grades Excel
  const handleExportClassExcel = () => {
    if (!selectedBatchId) return;
    let url = `/admin/academic-staff/export-class-grades-excel/?batch_id=${selectedBatchId}`;
    if (selectedClassId) {
      url += `&class_id=${selectedClassId}`;
    }
    // Download via link
    const link = document.createElement('a');
    link.href = `${apiClient.defaults.baseURL || ''}${url}`;
    link.target = '_blank';
    link.download = `Bang_Diem_Do_An.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Handle Complete Batch
  const handleCompleteBatch = async () => {
    if (!selectedBatchId) return;
    const confirmMsg = 'Bạn có chắc chắn muốn hoàn tất đợt đồ án này? Sau khi hoàn tất, toàn bộ điểm và dữ liệu các lớp sẽ được khóa sổ chính thức.';
    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await apiClient.post('/admin/academic-staff/complete-batch/', {
        batch_id: selectedBatchId,
      });
      alert(res.data?.message || 'Đã hoàn tất đợt đồ án thành công!');
      fetchFinalGrades();
      fetchBatches();
    } catch (err: any) {
      alert('Lỗi hoàn tất đợt: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Handle Export Eligibility Report
  const handleExportEligibilityReport = async () => {
    if (!selectedBatchId) return;
    try {
      const res = await apiClient.get(`/admin/eligibility/export-excel/?batch_id=${selectedBatchId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Bao_Cao_Hau_Kiem_Hoc_Vu_Dot_${selectedBatchId}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      alert('Lỗi xuất báo cáo hậu kiểm: ' + (err.message || 'Lỗi server'));
    }
  };

  // Filtered Eligibility
  const filteredEligibility = eligibilityProjects.filter((p) => {
    if (filterEligibility !== 'ALL' && p.initial_eligibility !== filterEligibility) {
      return false;
    }
    if (searchEligibility.trim()) {
      const q = searchEligibility.toLowerCase();
      const matchName = (p.student_name || '').toLowerCase().includes(q);
      const matchReg = (p.student_reg_no || '').toLowerCase().includes(q);
      const matchTopic = (p.topic_title_vi || '').toLowerCase().includes(q);
      return matchName || matchReg || matchTopic;
    }
    return true;
  });

  const countEligible = eligibilityProjects.filter((p) => p.initial_eligibility === 'ELIGIBLE').length;
  const countIneligible = eligibilityProjects.filter((p) => p.initial_eligibility === 'INELIGIBLE').length;
  const countForceApproved = eligibilityProjects.filter((p) => p.initial_eligibility === 'FORCE_APPROVED').length;
  const countDisqualified = eligibilityProjects.filter((p) => p.initial_eligibility === 'DISQUALIFIED').length;

  // Filtered Final Grades
  const filteredGrades = finalGrades.filter((g) => {
    if (searchGrade.trim()) {
      const q = searchGrade.toLowerCase();
      const matchName = (g.student_name || '').toLowerCase().includes(q);
      const matchReg = (g.registration_no || '').toLowerCase().includes(q);
      const matchClass = (g.class_code || '').toLowerCase().includes(q);
      const matchTopic = (g.topic_title_vi || '').toLowerCase().includes(q);
      return matchName || matchReg || matchClass || matchTopic;
    }
    return true;
  });

  return (
    <AdminLayout>
      <div className="utc-academic-portal">
        {/* Top Header Bar */}
        <div className="utc-academic-header-bar">
          <div className="utc-academic-title-wrap">
            <h3>
              <span>💼</span> Phân Hệ Nghiệp Vụ Giáo Vụ Khoa CNTT UTC
              <span className="utc-academic-role-badge">🛡️ Role: Giáo Vụ (Academic Staff)</span>
            </h3>
            <p className="utc-academic-subtitle">
              Quản trị xét điều kiện làm đồ án tốt nghiệp theo số tín chỉ nợ & Tổng kết, xuất in danh sách điểm theo từng lớp học phần
            </p>
          </div>

          <div className="utc-academic-actions">
            <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>Đợt ĐATN:</label>
            <select
              value={selectedBatchId || ''}
              onChange={(e) => setSelectedBatchId(Number(e.target.value))}
              style={{ padding: '0.5rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontWeight: 600, fontSize: '0.86rem' }}
            >
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_code} - {b.batch_name} {b.is_closed ? '(Đã hoàn tất)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="utc-academic-tabs">
          <button
            className={`utc-academic-tab-btn ${activeTab === 'ELIGIBILITY' ? 'active' : ''}`}
            onClick={() => setActiveTab('ELIGIBILITY')}
          >
            <span>🛡️</span> 1. GĐ 4: Hậu Kiểm Điều Kiện Học Vụ (Nợ 0 TC)
          </button>
          <button
            className={`utc-academic-tab-btn ${activeTab === 'FINAL_GRADES' ? 'active' : ''}`}
            onClick={() => setActiveTab('FINAL_GRADES')}
          >
            <span>🎓</span> 2. GĐ 6: Tổng Kết Điểm &amp; Xuất In Theo Lớp (Cuối Kỳ)
          </button>
        </div>

        {/* TAB 1: ELIGIBILITY */}
        {activeTab === 'ELIGIBILITY' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Rule Banner */}
            <div className="utc-rule-banner">
              <strong>📌 Quy Chế Giai Đoạn 4: Hậu Kiểm Điều Kiện Học Vụ Trước Khi Bảo Vệ (Khoa CNTT - UTC):</strong>
              <div style={{ marginTop: '0.35rem' }}>
                • <strong>Sinh viên nợ tích lũy = 0 tín chỉ</strong>: Đủ điều kiện học vụ → Hệ thống xác nhận <strong>ĐỦ ĐIỀU KIỆN BẢO VỆ</strong> và chuyển sang Giai đoạn 5 (Hội đồng &amp; Xếp lịch bảo vệ).<br />
                • <strong>Sinh viên nợ tích lũy &gt; 0 tín chỉ</strong>: <strong>BẢO LƯU ĐỒ ÁN</strong> → Tự động chuyển trạng thái Bảo lưu đồ án (chờ đợt sau) hoặc chờ BCN Khoa xét duyệt đặc cách theo đơn.
              </div>
            </div>

            {/* Metrics Row */}
            <div className="utc-metrics-row">
              <div
                className={`utc-metric-box ${filterEligibility === 'ALL' ? 'active' : ''}`}
                onClick={() => setFilterEligibility('ALL')}
              >
                <span className="metric-label">Tổng Sinh Viên</span>
                <span className="metric-value">{eligibilityProjects.length}</span>
                <span className="metric-sub">Toàn bộ sinh viên trong đợt</span>
              </div>

              <div
                className={`utc-metric-box ${filterEligibility === 'ELIGIBLE' ? 'active' : ''}`}
                onClick={() => setFilterEligibility('ELIGIBLE')}
              >
                <span className="metric-label">Nợ = 0 TC (Đủ ĐK Bảo Vệ)</span>
                <span className="metric-value" style={{ color: '#16a34a' }}>{countEligible}</span>
                <span className="metric-sub">Đủ điều kiện ra Hội đồng bảo vệ (GĐ 5)</span>
              </div>

              <div
                className={`utc-metric-box ${filterEligibility === 'INELIGIBLE' ? 'active' : ''}`}
                onClick={() => setFilterEligibility('INELIGIBLE')}
              >
                <span className="metric-label">Nợ &gt; 0 TC (Bảo Lưu Đồ Án)</span>
                <span className="metric-value" style={{ color: '#dc2626' }}>{countIneligible}</span>
                <span className="metric-sub">Tự động chuyển bảo lưu đồ án</span>
              </div>

              <div
                className={`utc-metric-box ${filterEligibility === 'FORCE_APPROVED' ? 'active' : ''}`}
                onClick={() => setFilterEligibility('FORCE_APPROVED')}
              >
                <span className="metric-label">Đã Đặc Cách (Force Approve)</span>
                <span className="metric-value" style={{ color: '#2563eb' }}>{countForceApproved}</span>
                <span className="metric-sub">Khoa đã cho phép bảo vệ theo đơn</span>
              </div>

              <div
                className={`utc-metric-box ${filterEligibility === 'DISQUALIFIED' ? 'active' : ''}`}
                onClick={() => setFilterEligibility('DISQUALIFIED')}
              >
                <span className="metric-label">Bị Loại Khỏi Đợt</span>
                <span className="metric-value" style={{ color: '#64748b' }}>{countDisqualified}</span>
                <span className="metric-sub">Không đủ ĐK / Hủy kết quả</span>
              </div>
            </div>

            {/* Main Table Card */}
            <div className="utc-card-container">
              <div className="utc-card-header">
                <div>
                  <h4>Giai Đoạn 4: Danh Sách Hậu Kiểm Điều Kiện Bảo Vệ ({filteredEligibility.length})</h4>
                  <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                    Tiêu chuẩn: Nợ tích lũy 0 TC được ra Hội đồng bảo vệ; Nợ &gt; 0 TC tự động bảo lưu đồ án.
                  </span>
                </div>

                <div className="utc-search-filter-bar">
                  <input
                    type="text"
                    placeholder="Tìm theo MSSV, Họ tên, Đề tài..."
                    value={searchEligibility}
                    onChange={(e) => setSearchEligibility(e.target.value)}
                    className="utc-input-search"
                  />
                  <button
                    onClick={() => setShowImportModal(true)}
                    className="btn-primary-utc"
                  >
                    <span>📊</span> Import Điểm &amp; Nợ TC (Excel)
                  </button>
                  <button
                    onClick={handleExportEligibilityReport}
                    style={{ background: '#2563eb', color: '#fff', border: 'none', padding: '0.5rem 0.85rem', borderRadius: '7px', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                  >
                    <span>📥</span> Xuất Báo Cáo Hậu Kiểm (Excel)
                  </button>
                </div>
              </div>

              {loadingEligibility ? (
                <div style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b', fontWeight: 600 }}>
                  Đang tải danh sách hồ sơ...
                </div>
              ) : filteredEligibility.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b' }}>
                  Không tìm thấy sinh viên nào phù hợp với bộ lọc hiện tại.
                </div>
              ) : (
                <div className="utc-table-scroll">
                  <table className="utc-table">
                    <thead>
                      <tr>
                        <th>STT</th>
                        <th>MSSV</th>
                        <th>Sinh Viên</th>
                        <th>Lớp / Bộ Môn</th>
                        <th>Hệ ĐT</th>
                        <th style={{ textAlign: 'center' }}>Tín Chỉ Nợ (= 0 TC)</th>
                        <th>Kết Quả Hậu Kiểm GĐ 4</th>
                        <th>Trạng Thái ĐATN</th>
                        <th>Ghi Chú / Lý Do</th>
                        <th style={{ textAlign: 'center' }}>Thao Tác Giáo Vụ / Khoa</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredEligibility.map((p, idx) => {
                        const isOk = (p.debt_credits || 0) === 0;
                        return (
                          <tr key={p.id}>
                            <td style={{ color: '#64748b', textAlign: 'center' }}>{idx + 1}</td>
                            <td style={{ fontWeight: 700, color: '#003366' }}>{p.student_reg_no}</td>
                            <td>
                              <div style={{ fontWeight: 600 }}>{p.student_name}</div>
                              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{p.topic_title_vi || 'Chưa đăng ký đề tài'}</div>
                            </td>
                            <td>{p.student_class || 'CNTT'}</td>
                            <td>
                              <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>
                                {p.education_program === 'ENGINEER' ? '⚙️ Kỹ sư' : '🎓 Cử nhân'}
                              </span>
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <span className={isOk ? 'debt-highlight-ok' : 'debt-highlight-fail'}>
                                {p.debt_credits || 0} TC
                              </span>
                            </td>
                            <td>
                              {p.initial_eligibility === 'ELIGIBLE' && (
                                <span className="badge-green">✅ Đủ ĐK Bảo Vệ (0 TC)</span>
                              )}
                              {p.initial_eligibility === 'INELIGIBLE' && (
                                <span className="badge-red">⚠️ Bảo Lưu Đồ Án (Nợ &gt; 0 TC)</span>
                              )}
                              {p.initial_eligibility === 'FORCE_APPROVED' && (
                                <span className="badge-blue">⭐ Khoa Đặc Cách Bảo Vệ</span>
                              )}
                              {p.initial_eligibility === 'DISQUALIFIED' && (
                                <span className="badge-amber">🚫 Bị Loại Khỏi Đợt</span>
                              )}
                              {p.initial_eligibility === 'PENDING' && (
                                <span style={{ color: '#64748b', fontSize: '0.78rem' }}>⏳ Chưa hậu kiểm</span>
                              )}
                            </td>
                            <td>
                              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: p.status === 'IN_PROGRESS' ? '#16a34a' : '#64748b' }}>
                                {p.status === 'IN_PROGRESS' ? '🚀 Đang làm ĐA (Giao việc)' : p.status}
                              </span>
                            </td>
                            <td style={{ fontSize: '0.8rem', color: '#64748b', maxWidth: '200px' }}>
                              {p.ineligibility_reason || '—'}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                                {p.initial_eligibility === 'INELIGIBLE' && (
                                  <>
                                    <button
                                      onClick={() => setForceProject(p)}
                                      className="btn-success-utc btn-sm"
                                      title="Ban Chủ nhiệm Khoa phê duyệt đặc cách cho phép làm đồ án"
                                    >
                                      ⭐ Đặc Cách
                                    </button>
                                    <button
                                      onClick={() => handleDisqualify(p.id, p.student_reg_no)}
                                      className="btn-outline-utc btn-sm"
                                      style={{ color: '#dc2626', borderColor: '#fca5a5' }}
                                      title="Loại sinh viên này khỏi đợt đồ án"
                                    >
                                      🚫 Loại
                                    </button>
                                  </>
                                )}
                                {p.initial_eligibility === 'ELIGIBLE' && (
                                  <span style={{ fontSize: '0.75rem', color: '#16a34a', fontWeight: 700 }}>
                                    ✓ Đã cho phép làm ĐA
                                  </span>
                                )}
                                {p.initial_eligibility === 'FORCE_APPROVED' && (
                                  <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 700 }}>
                                    ✓ Đã đặc cách
                                  </span>
                                )}
                                {p.initial_eligibility === 'DISQUALIFIED' && (
                                  <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 700 }}>
                                    ✓ Đã loại
                                  </span>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: FINAL GRADES BY CLASS */}
        {activeTab === 'FINAL_GRADES' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Top Filter & Actions for Class */}
            <div className="utc-card-container">
              <div className="utc-card-header">
                <div>
                  <h4>Tổng Hợp Điểm Đồ Án Tốt Nghiệp Cuối Kỳ Theo Lớp Học Phần</h4>
                  <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                    Chọn từng lớp học phần để xem, xuất bảng điểm Excel và in biên bản điểm chính thức cho Giáo vụ
                  </span>
                </div>

                <div className="utc-academic-actions">
                  <button onClick={handleExportClassExcel} className="btn-success-utc">
                    <span>📥</span> Xuất File Excel Theo Lớp (.xlsx)
                  </button>
                  <button onClick={() => setShowPrintModal(true)} className="btn-primary-utc">
                    <span>🖨️</span> In Danh Sách Điểm (Chuẩn A4)
                  </button>
                  {batchInfo && !batchInfo.is_closed && (
                    <button onClick={handleCompleteBatch} className="btn-outline-utc" style={{ color: '#003366', borderColor: '#003366', fontWeight: 700 }}>
                      <span>🔒</span> Hoàn Tất Đợt Đồ Án
                    </button>
                  )}
                </div>
              </div>

              {/* Class Selector Bar */}
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', background: '#f8fafc', padding: '0.85rem 1rem', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1e293b' }}>Chọn Lớp Học Phần:</span>
                <select
                  value={selectedClassId || ''}
                  onChange={(e) => setSelectedClassId(e.target.value ? Number(e.target.value) : null)}
                  style={{ padding: '0.5rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontWeight: 600, fontSize: '0.86rem', minWidth: '260px' }}
                >
                  <option value="">-- Tất cả các lớp học phần ({classesList.length} lớp) --</option>
                  {classesList.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.class_code} - {c.class_name} ({c.student_count} SV)
                    </option>
                  ))}
                </select>

                <input
                  type="text"
                  placeholder="Lọc sinh viên, đề tài..."
                  value={searchGrade}
                  onChange={(e) => setSearchGrade(e.target.value)}
                  className="utc-input-search"
                  style={{ marginLeft: 'auto' }}
                />
              </div>

              {/* Stats Counters */}
              {gradeStats && (
                <div className="utc-metrics-row">
                  <div className="utc-metric-box">
                    <span className="metric-label">Tổng Sinh Viên</span>
                    <span className="metric-value">{gradeStats.total_students}</span>
                    <span className="metric-sub">Hồ sơ trong danh sách</span>
                  </div>
                  <div className="utc-metric-box">
                    <span className="metric-label">Đạt Bảo Vệ</span>
                    <span className="metric-value" style={{ color: '#16a34a' }}>{gradeStats.passed_count}</span>
                    <span className="metric-sub">Tỷ lệ đạt: {gradeStats.pass_rate}%</span>
                  </div>
                  <div className="utc-metric-box">
                    <span className="metric-label">Không Đạt</span>
                    <span className="metric-value" style={{ color: '#dc2626' }}>{gradeStats.failed_count}</span>
                    <span className="metric-sub">Điểm tổng kết &lt; 4.0</span>
                  </div>
                  <div className="utc-metric-box">
                    <span className="metric-label">Bảo Lưu Đồ Án</span>
                    <span className="metric-value" style={{ color: '#d97706' }}>{gradeStats.deferred_count}</span>
                    <span className="metric-sub">Được Khoa duyệt bảo lưu</span>
                  </div>
                  <div className="utc-metric-box">
                    <span className="metric-label">Điểm TB Hệ 10</span>
                    <span className="metric-value" style={{ color: '#003366' }}>{gradeStats.average_score}</span>
                    <span className="metric-sub">Thang điểm 10 UTC</span>
                  </div>
                </div>
              )}

              {/* Grades Table */}
              {loadingGrades ? (
                <div style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b', fontWeight: 600 }}>
                  Đang tải bảng điểm tổng kết...
                </div>
              ) : filteredGrades.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b' }}>
                  Chưa có dữ liệu điểm cho lớp hoặc đợt đã chọn.
                </div>
              ) : (
                <div className="utc-table-scroll">
                  <table className="utc-table">
                    <thead>
                      <tr>
                        <th>STT</th>
                        <th>Mã SV</th>
                        <th>Họ và Tên</th>
                        <th>Lớp Học Phần</th>
                        <th>Tên Đề Tài Tốt Nghiệp</th>
                        <th>GV Hướng Dẫn</th>
                        <th>GV Phản Biện</th>
                        <th>Hội Đồng</th>
                        <th style={{ textAlign: 'center' }}>Điểm GVHD</th>
                        <th style={{ textAlign: 'center' }}>Điểm GVPB</th>
                        <th style={{ textAlign: 'center' }}>Điểm HĐ</th>
                        <th style={{ textAlign: 'center' }}>Điểm Hệ 10</th>
                        <th style={{ textAlign: 'center' }}>Điểm Hệ 4</th>
                        <th style={{ textAlign: 'center' }}>Điểm Chữ</th>
                        <th>Xếp Loại</th>
                        <th style={{ textAlign: 'center' }}>Kết Luận</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredGrades.map((g, idx) => (
                        <tr key={g.project_id}>
                          <td style={{ textAlign: 'center', color: '#64748b' }}>{idx + 1}</td>
                          <td style={{ fontWeight: 700, color: '#003366' }}>{g.registration_no}</td>
                          <td style={{ fontWeight: 600 }}>{g.student_name}</td>
                          <td>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>{g.class_code || g.class_name}</span>
                          </td>
                          <td style={{ maxWidth: '280px', fontSize: '0.82rem' }}>{g.topic_title_vi}</td>
                          <td style={{ fontSize: '0.82rem' }}>{g.supervisor_name || '—'}</td>
                          <td style={{ fontSize: '0.82rem' }}>{g.reviewer_name || '—'}</td>
                          <td style={{ fontSize: '0.82rem' }}>{g.council_name || '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 600 }}>{g.supervisor_score !== null ? g.supervisor_score : '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 600 }}>{g.reviewer_score !== null ? g.reviewer_score : '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 600 }}>{g.council_avg_score !== null ? g.council_avg_score : '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 800, color: '#003366', fontSize: '0.95rem' }}>
                            {g.final_score_10 !== null ? g.final_score_10 : '—'}
                          </td>
                          <td style={{ textAlign: 'center', fontWeight: 700 }}>
                            {g.final_score_4 !== null ? g.final_score_4 : '—'}
                          </td>
                          <td style={{ textAlign: 'center', fontWeight: 800, color: '#0369a1' }}>
                            {g.final_letter_grade || '—'}
                          </td>
                          <td style={{ fontWeight: 600 }}>{g.classification || '—'}</td>
                          <td style={{ textAlign: 'center' }}>
                            {g.is_deferred ? (
                              <span className="badge-amber">Bảo Lưu</span>
                            ) : g.is_passed ? (
                              <span className="badge-green">Đạt</span>
                            ) : (
                              <span className="badge-red">Không Đạt</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* MODAL 1: IMPORT ELIGIBILITY EXCEL */}
        {showImportModal && (
          <div className="utc-modal-backdrop" onClick={() => setShowImportModal(false)}>
            <div className="utc-modal-window" onClick={(e) => e.stopPropagation()}>
              <div className="utc-modal-header">
                <h4>Import File Điểm / Số Tín Chỉ Nợ (Excel)</h4>
                <button className="utc-modal-close" onClick={() => setShowImportModal(false)}>&times;</button>
              </div>

              <form onSubmit={handleImportEligibility}>
                <div className="utc-modal-body">
                  <p style={{ fontSize: '0.88rem', color: '#475569', marginBottom: '1rem' }}>
                    Chọn tệp Excel chứa cột <strong>Mã SV (MSSV)</strong> và <strong>Số tín chỉ nợ</strong>. Hệ thống sẽ tự động cập nhật số tín chỉ nợ vào bảng Đồ án Tốt nghiệp và phân loại điều kiện học vụ theo quy định (&lt; 10 TC: Đủ ĐK; &ge; 10 TC: Không đủ ĐK).
                  </p>

                  <div style={{ marginBottom: '1.25rem' }}>
                    <label style={{ display: 'block', fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.4rem', color: '#1e293b' }}>
                      Chọn file Excel (.xlsx, .xls):
                    </label>
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      onChange={(e) => setImportFile(e.target.files ? e.target.files[0] : null)}
                      required
                      style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '8px' }}
                    />
                  </div>

                  {importResult && (
                    <div style={{ padding: '0.85rem', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', fontSize: '0.86rem', color: '#166534' }}>
                      <strong>Kết quả import:</strong><br />
                      • Tổng hồ sơ xử lý: {importResult.total_processed}<br />
                      • Đủ điều kiện (&lt;10 TC): <strong>{importResult.eligible_count}</strong><br />
                      • Không đủ điều kiện (&ge;10 TC): <strong>{importResult.ineligible_count}</strong>
                    </div>
                  )}
                </div>

                <div className="utc-modal-footer">
                  <button type="button" onClick={() => setShowImportModal(false)} className="btn-outline-utc">
                    Đóng
                  </button>
                  <button type="submit" disabled={importing || !importFile} className="btn-primary-utc">
                    {importing ? 'Đang xử lý...' : 'Bắt Đầu Import'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 2: FORCE APPROVE DIALOG */}
        {forceProject && (
          <div className="utc-modal-backdrop" onClick={() => setForceProject(null)}>
            <div className="utc-modal-window" onClick={(e) => e.stopPropagation()}>
              <div className="utc-modal-header">
                <h4>Khoa Phê Duyệt Đặc Cách (Force Approve)</h4>
                <button className="utc-modal-close" onClick={() => setForceProject(null)}>&times;</button>
              </div>

              <form onSubmit={handleForceApproveSubmit}>
                <div className="utc-modal-body">
                  <div style={{ background: '#eff6ff', padding: '0.85rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.86rem' }}>
                    <strong>Sinh viên:</strong> {forceProject.student_name} ({forceProject.student_reg_no})<br />
                    <strong>Tín chỉ nợ hiện tại:</strong> <span style={{ color: '#dc2626', fontWeight: 700 }}>{forceProject.debt_credits} TC</span> (&ge; 10 TC quy định)<br />
                    <strong>Đề tài:</strong> {forceProject.topic_title_vi || 'Chưa đăng ký'}
                  </div>

                  <div>
                    <label style={{ display: 'block', fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.4rem', color: '#1e293b' }}>
                      Lý do phê duyệt đặc cách của Ban Chủ nhiệm Khoa:
                    </label>
                    <textarea
                      rows={3}
                      value={forceReason}
                      onChange={(e) => setForceReason(e.target.value)}
                      placeholder="Ví dụ: Khoa phê duyệt đặc cách theo đơn giải trình, cam kết trả nợ học phần song song..."
                      required
                      style={{ width: '100%', padding: '0.6rem', border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '0.85rem' }}
                    />
                  </div>
                </div>

                <div className="utc-modal-footer">
                  <button type="button" onClick={() => setForceProject(null)} className="btn-outline-utc">
                    Hủy Bỏ
                  </button>
                  <button type="submit" className="btn-success-utc">
                    ⭐ Xác Nhận Đặc Cách (Cho Làm ĐA)
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 3: PRINT PREVIEW MODAL */}
        {showPrintModal && (
          <div className="utc-modal-backdrop" onClick={() => setShowPrintModal(false)}>
            <div className="utc-modal-print-window" onClick={(e) => e.stopPropagation()}>
              <div className="utc-modal-header">
                <h4>Bản In Danh Sách Điểm Đồ Án Tốt Nghiệp Theo Chuẩn UTC (Khổ Giấy A4)</h4>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button onClick={() => window.print()} className="btn-primary-utc btn-sm">
                    🖨️ In Ngay
                  </button>
                  <button className="utc-modal-close" onClick={() => setShowPrintModal(false)}>&times;</button>
                </div>
              </div>

              <div className="utc-modal-body" style={{ background: '#f8fafc' }}>
                <div className="utc-print-sheet">
                  {/* Banner */}
                  <div className="print-header-grid">
                    <div className="print-univ-side">
                      TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI<br />
                      KHOA CÔNG NGHỆ THÔNG TIN<br />
                      ***
                    </div>
                    <div className="print-nation-side">
                      CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br />
                      Độc lập - Tự do - Hạnh phúc<br />
                      ***
                    </div>
                  </div>

                  {/* Title */}
                  <div className="print-doc-title">
                    BẢNG TỔNG HỢP ĐIỂM ĐỒ ÁN TỐT NGHIỆP
                  </div>
                  <div className="print-doc-sub">
                    {selectedClassId && classesList.find((c) => c.id === selectedClassId)
                      ? `Lớp: ${classesList.find((c) => c.id === selectedClassId)?.class_code} - ${classesList.find((c) => c.id === selectedClassId)?.class_name}`
                      : 'Toàn bộ các lớp học phần trong đợt'}{' '}
                    | Đợt: {batchInfo?.batch_name || 'ĐATN UTC'}
                  </div>

                  {/* Table */}
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th>STT</th>
                        <th>Mã SV</th>
                        <th>Họ và Tên</th>
                        <th>Lớp</th>
                        <th>Tên Đề Tài Tốt Nghiệp</th>
                        <th>GV Hướng Dẫn</th>
                        <th>Điểm GVHD</th>
                        <th>Điểm GVPB</th>
                        <th>Điểm HĐ</th>
                        <th>Điểm Hệ 10</th>
                        <th>Điểm Chữ</th>
                        <th>Xếp Loại</th>
                        <th>Kết Luận</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredGrades.map((g, i) => (
                        <tr key={g.project_id}>
                          <td style={{ textAlign: 'center' }}>{i + 1}</td>
                          <td style={{ fontWeight: 'bold' }}>{g.registration_no}</td>
                          <td>{g.student_name}</td>
                          <td>{g.class_code}</td>
                          <td style={{ fontSize: '0.78rem' }}>{g.topic_title_vi}</td>
                          <td>{g.supervisor_name}</td>
                          <td style={{ textAlign: 'center' }}>{g.supervisor_score ?? '—'}</td>
                          <td style={{ textAlign: 'center' }}>{g.reviewer_score ?? '—'}</td>
                          <td style={{ textAlign: 'center' }}>{g.council_avg_score ?? '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 'bold' }}>{g.final_score_10 ?? '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 'bold' }}>{g.final_letter_grade || '—'}</td>
                          <td>{g.classification || '—'}</td>
                          <td style={{ textAlign: 'center', fontWeight: 'bold' }}>{g.verdict}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Stats */}
                  {gradeStats && (
                    <div className="print-stat-row">
                      Thống kê: Tổng số {gradeStats.total_students} sinh viên | Đạt: {gradeStats.passed_count} ({gradeStats.pass_rate}%) | Không đạt: {gradeStats.failed_count} | Bảo lưu: {gradeStats.deferred_count} | Điểm trung bình: {gradeStats.average_score}/10
                    </div>
                  )}

                  {/* Signatures */}
                  <div style={{ textAlign: 'right', fontStyle: 'italic', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
                    Hà Nội, ngày {new Date().getDate()} tháng {new Date().getMonth() + 1} năm {new Date().getFullYear()}
                  </div>

                  <div className="print-sign-grid">
                    <div className="print-sign-box">
                      NGƯỜI LẬP BẢNG<br />
                      (Giáo vụ Khoa CNTT)
                      <div className="print-sign-space"></div>
                      (Ký và ghi rõ họ tên)
                    </div>

                    <div className="print-sign-box">
                      TRƯỜNG BỘ MÔN
                      <div className="print-sign-space"></div>
                      (Ký và ghi rõ họ tên)
                    </div>

                    <div className="print-sign-box">
                      TRƯỞNG KHOA CNTT
                      <div className="print-sign-space"></div>
                      (Ký và ghi rõ họ tên)
                    </div>
                  </div>
                </div>
              </div>

              <div className="utc-modal-footer">
                <button onClick={() => setShowPrintModal(false)} className="btn-outline-utc">
                  Đóng
                </button>
                <button onClick={() => window.print()} className="btn-primary-utc">
                  🖨️ In Trang Điểm Này
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
