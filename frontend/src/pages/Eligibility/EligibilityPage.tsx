import React, { useState, useEffect } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './EligibilityPage.css';

interface ProjectEligibility {
  id: number;
  student_name: string;
  student_reg_no: string;
  student_class: string;
  education_program: string;
  supervisor_name: string;
  topic_title_vi: string;
  initial_eligibility: 'PENDING' | 'ELIGIBLE' | 'INELIGIBLE' | 'FORCE_APPROVED' | 'DISQUALIFIED';
  ineligibility_reason: string;
  gpa_score: number | null;
  debt_credits: number;
}

export const EligibilityPage: React.FC = () => {
  const [batches, setBatches] = useState<any[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [projects, setProjects] = useState<ProjectEligibility[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  // Import Modal
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  // Force Approve Modal
  const [forceProject, setForceProject] = useState<ProjectEligibility | null>(null);
  const [forceReason, setForceReason] = useState('');

  const fetchBatches = async () => {
    try {
      const res = await apiClient.get('/admin/batches/');
      const list = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setBatches(list);
      if (list.length > 0 && !selectedBatchId) {
        setSelectedBatchId(list[0].id);
      }
    } catch (err) {
      console.error(err);
      setBatches([]);
    }
  };

  const fetchProjects = async () => {
    if (!selectedBatchId) return;
    try {
      setLoading(true);
      const res = await apiClient.get(`/admin/projects/?batch_id=${selectedBatchId}`);
      setProjects(Array.isArray(res.data) ? res.data : (res.data?.results || []));
    } catch (err) {
      console.error(err);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  useEffect(() => {
    if (selectedBatchId) {
      fetchProjects();
    }
  }, [selectedBatchId]);

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
      fetchProjects();
    } catch (err: any) {
      alert('Lỗi import: ' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(false);
    }
  };

  const handleForceApproveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forceProject) return;

    try {
      await apiClient.post(`/admin/projects/${forceProject.id}/force-approve/`, {
        decision: 'FORCE_APPROVE',
        reason: forceReason.trim() || 'Khoa phê duyệt đặc cách theo đơn giải trình',
      });
      alert(`Đã Force Approve đặc cách cho SV ${forceProject.student_reg_no} làm đồ án!`);
      setForceProject(null);
      setForceReason('');
      fetchProjects();
    } catch (err: any) {
      alert('Lỗi đặc cách: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleBulkForceApproveIneligible = async () => {
    const ineligibles = projects.filter((p) => p.initial_eligibility === 'INELIGIBLE');
    if (ineligibles.length === 0) {
      alert('Không có sinh viên nào ở trạng thái Không đủ điều kiện.');
      return;
    }
    if (!window.confirm(`Bạn có chắc chắn muốn Force Approve đặc cách cho toàn bộ ${ineligibles.length} sinh viên không đủ điều kiện được làm đồ án tốt nghiệp?`)) {
      return;
    }
    try {
      for (const p of ineligibles) {
        await apiClient.post(`/admin/projects/${p.id}/force-approve/`, {
          decision: 'FORCE_APPROVE',
          reason: 'Khoa phê duyệt đặc cách tập trung cho đợt đồ án',
        });
      }
      alert(`Đã Force Approve thành công cho ${ineligibles.length} sinh viên!`);
      fetchProjects();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDisqualify = async (projId: number, regNo: string) => {
    const reason = prompt('Nhập lý do loại sinh viên này khỏi đợt đồ án:', 'Không đủ điều kiện học vụ theo quy định');
    if (reason === null) return;

    try {
      await apiClient.patch(`/admin/projects/${projId}/eligibility-decision/`, {
        decision: 'DISQUALIFY',
        reason: reason.trim(),
      });
      alert(`Đã loại sinh viên ${regNo} khỏi đợt đồ án.`);
      fetchProjects();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleExportEligibility = async () => {
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
      alert('Lỗi xuất file báo cáo hậu kiểm: ' + (err.message || 'Lỗi server'));
    }
  };

  const filtered = projects.filter((p) => {
    if (filterStatus === 'ALL') return true;
    return p.initial_eligibility === filterStatus;
  });

  const countEligible = projects.filter((p) => p.initial_eligibility === 'ELIGIBLE').length;
  const countIneligible = projects.filter((p) => p.initial_eligibility === 'INELIGIBLE').length;
  const countForceApproved = projects.filter((p) => p.initial_eligibility === 'FORCE_APPROVED').length;
  const countDisqualified = projects.filter((p) => p.initial_eligibility === 'DISQUALIFIED').length;

  return (
    <AdminLayout>
      <div className="utc-eligibility-portal">
        {/* Header Bar */}
        <div className="utc-eligibility-header-bar">
          <div className="utc-eligibility-header-info">
            <h3>Giai Đoạn 4: Hậu Kiểm Điều Kiện Học Vụ Trước Khi Bảo Vệ (Quy chế Nợ = 0 TC)</h3>
            <p>
              <strong>Quy chế UTC:</strong> Sau khi GVHD hoàn thành chấm điểm quá trình, Giáo vụ khoa hậu kiểm điều kiện học vụ:
              Sinh viên nợ tích lũy <strong>0 tín chỉ</strong> mới đủ điều kiện bảo vệ. Sinh viên nợ &gt; 0 tín chỉ tự động chuyển trạng thái <strong>Bảo lưu đồ án</strong> (chờ đợt sau).
            </p>
          </div>

          <div className="utc-header-actions">
            <select
              value={selectedBatchId || ''}
              onChange={(e) => setSelectedBatchId(Number(e.target.value))}
              className="utc-batch-dropdown"
            >
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_code} - {b.batch_name}
                </option>
              ))}
            </select>

            <button onClick={() => setShowImportModal(true)} className="utc-btn-emerald">
              <span>📊</span> Import Điểm &amp; Nợ TC (Excel)
            </button>

            <button onClick={handleExportEligibility} className="utc-btn-blue" style={{ background: '#2563eb', color: '#fff', border: 'none', padding: '0.55rem 0.9rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <span>📥</span> Xuất Báo Cáo Hậu Kiểm (Excel)
            </button>

            {countIneligible > 0 && (
              <button
                onClick={handleBulkForceApproveIneligible}
                className="utc-btn-force-bulk"
                title="Đặc cách cho tất cả sinh viên không đủ điều kiện học vụ trong đợt"
              >
                <span>⭐</span> Force Approve Tất Cả ({countIneligible})
              </button>
            )}
          </div>
        </div>

        {/* Metric Cards */}
        <div className="utc-elig-metrics-grid">
          <div
            className={`utc-elig-card ${filterStatus === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterStatus('ALL')}
          >
            <span className="card-label">Tổng Sinh Viên</span>
            <span className="card-num">{projects.length}</span>
            <span className="card-sub">Toàn bộ sinh viên trong đợt</span>
          </div>

          <div
            className={`utc-elig-card ${filterStatus === 'ELIGIBLE' ? 'active' : ''}`}
            onClick={() => setFilterStatus('ELIGIBLE')}
          >
            <span className="card-label">Nợ = 0 TC (Đủ ĐK Bảo Vệ)</span>
            <span className="card-num text-emerald">{countEligible}</span>
            <span className="card-sub">Đủ điều kiện ra Hội đồng bảo vệ (GĐ 5)</span>
          </div>

          <div
            className={`utc-elig-card ${filterStatus === 'INELIGIBLE' ? 'active' : ''}`}
            onClick={() => setFilterStatus('INELIGIBLE')}
          >
            <span className="card-label">Nợ &gt; 0 TC (Bảo Lưu Đồ Án)</span>
            <span className="card-num text-amber">{countIneligible}</span>
            <span className="card-sub">Tự động bảo lưu đồ án (chờ đợt sau)</span>
          </div>

          <div
            className={`utc-elig-card ${filterStatus === 'FORCE_APPROVED' ? 'active' : ''}`}
            onClick={() => setFilterStatus('FORCE_APPROVED')}
          >
            <span className="card-label">Khoa Đặc Cách (Force Approve)</span>
            <span className="card-num text-blue">{countForceApproved}</span>
            <span className="card-sub">Được đặc cách bảo vệ theo đơn</span>
          </div>

          <div
            className={`utc-elig-card ${filterStatus === 'DISQUALIFIED' ? 'active' : ''}`}
            onClick={() => setFilterStatus('DISQUALIFIED')}
          >
            <span className="card-label">Bị Loại Khỏi Đợt</span>
            <span className="card-num text-red">{countDisqualified}</span>
            <span className="card-sub">Không đạt / Hủy kết quả</span>
          </div>
        </div>

        {/* Projects Table */}
        <div className="utc-elig-table-card">
          <div className="utc-elig-table-head">
            <h4>Danh Sách Xét Duyệt Điều Kiện ({filtered.length})</h4>
            <span className="text-muted">Nhấn "Force Approve" để đặc cách hoặc "Loại Khỏi Đợt"</span>
          </div>

          {loading ? (
            <div className="utc-loading-text">Đang tải danh sách...</div>
          ) : filtered.length === 0 ? (
            <div className="utc-empty-text">Chưa có dữ liệu xét duyệt. Hãy nhấn Import Excel.</div>
          ) : (
            <div className="utc-table-container">
              <table className="utc-custom-table">
                <thead>
                  <tr>
                    <th>MSSV</th>
                    <th>Sinh Viên</th>
                    <th>Hệ ĐT</th>
                    <th>GPA Tích Lũy</th>
                    <th>Tín Chỉ Nợ (Quy chế = 0 TC)</th>
                    <th>Kết Quả Hậu Kiểm GĐ 4</th>
                    <th>Lý Do / Ghi Chú Học Vụ</th>
                    <th>Quyết Định Của Khoa</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.id}>
                      <td className="font-bold">{p.student_reg_no}</td>
                      <td>
                        <div className="font-semibold">{p.student_name}</div>
                        <div className="text-xs text-muted">{p.student_class}</div>
                      </td>
                      <td>
                        <span className={`utc-tag-edu ${p.education_program === 'ENGINEER' ? 'edu-ks' : 'edu-cn'}`}>
                          {p.education_program === 'ENGINEER' ? '⚙️ Kỹ sư' : '🎓 Cử nhân'}
                        </span>
                      </td>
                      <td className="font-bold text-center">{p.gpa_score !== null ? p.gpa_score : '—'}</td>
                      <td className="text-center">
                        <span className={`font-bold ${(p.debt_credits || 0) === 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                          {p.debt_credits || 0} TC
                        </span>
                        <div className="text-xs text-muted">
                          {(p.debt_credits || 0) === 0 ? '✓ Nợ 0 TC (Đủ ĐK)' : `⚠ Nợ ${p.debt_credits} TC (> 0)`}
                        </div>
                      </td>
                      <td>
                        <span className={`utc-elig-pill pill-${(p.initial_eligibility || 'pending').toLowerCase()}`}>
                          {p.initial_eligibility === 'ELIGIBLE'
                            ? '✅ Đủ ĐK Bảo Vệ (0 TC)'
                            : p.initial_eligibility === 'FORCE_APPROVED'
                            ? '⭐ Khoa Đặc Cách Bảo Vệ'
                            : p.initial_eligibility === 'DISQUALIFIED'
                            ? '🚫 Bị Loại Khỏi Đợt'
                            : p.initial_eligibility === 'INELIGIBLE'
                            ? '⚠️ Bảo Lưu Đồ Án (Nợ > 0 TC)'
                            : '⏳ Chưa Hậu Kiểm'}
                        </span>
                      </td>
                      <td style={{ maxWidth: '250px' }}>
                        <span className="text-sm text-slate-700">{p.ineligibility_reason || '—'}</span>
                      </td>
                      <td>
                        <div className="utc-action-btn-group">
                          {p.initial_eligibility !== 'ELIGIBLE' && p.initial_eligibility !== 'FORCE_APPROVED' && (
                            <>
                              <button
                                onClick={() => {
                                  setForceProject(p);
                                  setForceReason(p.ineligibility_reason ? `Đặc cách: ${p.ineligibility_reason}` : 'Khoa phê duyệt đặc cách theo đơn giải trình');
                                }}
                                className="utc-btn-sm-force"
                                data-testid="force-approve-btn"
                                title="Cho phép đặc cách làm đồ án (Force Approve)"
                              >
                                ⭐ Force Approve
                              </button>
                              {p.initial_eligibility !== 'DISQUALIFIED' && (
                                <button
                                  onClick={() => handleDisqualify(p.id, p.student_reg_no)}
                                  className="utc-btn-sm-disqualify"
                                  title="Loại sinh viên khỏi đợt đồ án"
                                >
                                  ✕ Loại
                                </button>
                              )}
                            </>
                          )}
                          {p.initial_eligibility === 'ELIGIBLE' && (
                            <span className="text-xs text-emerald-600 font-bold">✅ Đủ ĐK (GĐ5)</span>
                          )}
                          {p.initial_eligibility === 'FORCE_APPROVED' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span className="text-xs text-blue-600 font-bold">⭐ Đã đặc cách (GĐ5)</span>
                              <button
                                onClick={() => {
                                  setForceProject(p);
                                  setForceReason(p.ineligibility_reason || 'Khoa phê duyệt đặc cách theo đơn giải trình');
                                }}
                                className="utc-btn-sm-subtle"
                                title="Cập nhật thông tin đặc cách"
                              >
                                Sửa
                              </button>
                            </div>
                          )}
                          {p.initial_eligibility === 'DISQUALIFIED' && (
                            <span className="text-xs text-red-600 font-bold">🚫 Đã loại</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* MODAL 1: IMPORT EXCEL */}
        {showImportModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card">
              <div className="utc-modal-head">
                <h4>📊 Import Điểm Tích Lũy & Xét Điều Kiện Làm ĐATN</h4>
                <button onClick={() => setShowImportModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleImportEligibility}>
                <div className="utc-form-group">
                  <label>Chọn File Excel Điểm Tích Lũy:</label>
                  <input
                    type="file"
                    accept=".xlsx, .xls"
                    required
                    onChange={(e) => setImportFile(e.target.files ? e.target.files[0] : null)}
                    className="utc-input"
                  />
                  <small style={{ color: '#64748b', display: 'block', marginTop: '0.4rem' }}>
                    File Excel chứa các cột: MSSV, Điểm tích lũy (GPA), Số tín chỉ nợ, Kết luận điều kiện.
                  </small>
                </div>

                {importResult && (
                  <div className="utc-alert-box">
                    <strong>Kết quả rà soát:</strong>
                    <div>Đã xử lý: {importResult.total_processed} sinh viên</div>
                    <div style={{ color: '#059669' }}>Đủ điều kiện: {importResult.eligible_count}</div>
                    <div style={{ color: '#d97706' }}>Không đủ điều kiện: {importResult.ineligible_count}</div>
                  </div>
                )}

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowImportModal(false)} className="utc-btn-cancel">Đóng</button>
                  <button type="submit" disabled={importing} className="utc-btn-emerald">
                    {importing ? 'Đang phân tích...' : 'Bắt Đầu Import & Xét Duyệt'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 2: FORCE APPROVE */}
        {forceProject && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card">
              <div className="utc-modal-head">
                <h4>⭐ Quyết Định Force Approve (Đặc Cách Cho Làm Đồ Án)</h4>
                <button onClick={() => setForceProject(null)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleForceApproveSubmit}>
                <div className="utc-form-group">
                  <p>Sinh viên: <strong>{forceProject.student_name}</strong> ({forceProject.student_reg_no})</p>
                  <p>Lý do không đạt ban đầu: <span className="text-red font-bold">{forceProject.ineligibility_reason}</span></p>
                </div>

                <div className="utc-form-group">
                  <label>Lý do Khoa chấp thuận đặc cách (Lưu hồ sơ kiểm toán):</label>
                  <textarea
                    rows={4}
                    required
                    placeholder="VD: Sinh viên đã có đơn cam kết trả nợ học phần trong kỳ phụ; Đã được phê duyệt giải trình đặc cách..."
                    value={forceReason}
                    onChange={(e) => setForceReason(e.target.value)}
                    className="utc-input"
                  />
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setForceProject(null)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" className="utc-btn-primary">Xác Nhận Force Approve</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
