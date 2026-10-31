import React, { useState, useEffect } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './DefenseManagementPage.css';

interface ProjectAdmin {
  id: number;
  student: number;
  student_name: string;
  student_reg_no: string;
  student_class: string;
  education_program?: string;
  supervisor_name: string;
  reviewer_name: string;
  council: number | null;
  council_name: string;
  topic_title_vi: string;
  status: string;
  supervisor_defense_confirmed?: boolean;
  final_academic_eligibility?: string;
  final_academic_notes?: string;
  deferral_status?: string;
  deferral_reason?: string;
  supervisor_score: number | null;
  reviewer_score: number | null;
  final_score_10: number | null;
  final_score_4: number | null;
  final_letter_grade: string;
  is_passed: boolean;
}

export const DefenseManagementPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'grades' | 'deferral'>('grades');
  const [batches, setBatches] = useState<any[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [councils, setCouncils] = useState<any[]>([]);
  const [selectedCouncilId, setSelectedCouncilId] = useState<string>('');
  const [projects, setProjects] = useState<ProjectAdmin[]>([]);
  const [loading, setLoading] = useState(true);

  // Import Final Academic Modal
  const [showImportFinalModal, setShowImportFinalModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

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

  const fetchData = async () => {
    if (!selectedBatchId) return;
    try {
      setLoading(true);
      let url = `/admin/projects/?batch_id=${selectedBatchId}`;
      if (selectedCouncilId) {
        url += `&council_id=${selectedCouncilId}`;
      }

      const [counRes, projRes] = await Promise.all([
        apiClient.get(`/admin/councils/?batch_id=${selectedBatchId}`),
        apiClient.get(url),
      ]);
      setCouncils(Array.isArray(counRes.data) ? counRes.data : (counRes.data?.results || []));
      setProjects(Array.isArray(projRes.data) ? projRes.data : (projRes.data?.results || []));
    } catch (err) {
      console.error(err);
      setCouncils([]);
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
      fetchData();
    }
  }, [selectedBatchId, selectedCouncilId]);

  const handleDownloadToTrinhDocx = async () => {
    if (!selectedCouncilId) {
      alert('Vui lòng chọn một Hội đồng cụ thể để xuất Tờ trình Word!');
      return;
    }
    try {
      const res = await apiClient.get(`/admin/export/to-trinh-word/?council_id=${selectedCouncilId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `To_trinh_Hoi_dong_${selectedCouncilId}.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Lỗi tải file Tờ trình: ' + JSON.stringify(err));
    }
  };

  const handleDownloadBienBanExcel = async () => {
    if (!selectedCouncilId) {
      alert('Vui lòng chọn một Hội đồng cụ thể để xuất Biên bản chấm điểm Excel!');
      return;
    }
    try {
      const res = await apiClient.get(`/admin/export/bien-ban-excel/?council_id=${selectedCouncilId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Bien_ban_cham_diem_HD_${selectedCouncilId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Lỗi tải file Bảng điểm Excel: ' + JSON.stringify(err));
    }
  };

  const handleDownloadBienBanPdf = async () => {
    if (!selectedCouncilId) {
      alert('Vui lòng chọn một Hội đồng cụ thể để xuất Biên bản họp bảo vệ PDF!');
      return;
    }
    try {
      const res = await apiClient.get(`/admin/councils/${selectedCouncilId}/export-minutes-pdf/`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Bien_ban_HD_${selectedCouncilId}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('Lỗi tải file Biên bản PDF: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDownloadFinalSummaryExcel = async () => {
    if (!selectedBatchId) return;
    try {
      const res = await apiClient.get(`/admin/export/final-summary-excel/?batch_id=${selectedBatchId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Bao_cao_du_lieu_cuoi_ky_Dot_${selectedBatchId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Lỗi xuất báo cáo cuối kỳ!');
    }
  };

  const handleFinalizeCouncilScores = async () => {
    if (!selectedCouncilId) {
      alert('Vui lòng chọn một Hội đồng cụ thể để chốt điểm!');
      return;
    }
    if (!confirm('Xác nhận Hội đồng chấm thi đã hoàn thành và CHỐT ĐIỂM chính thức? Sau khi chốt, điểm số sẽ được khóa.')) return;
    try {
      const res = await apiClient.post(`/admin/councils/${selectedCouncilId}/finalize-scores/`);
      alert(res.data?.message || 'Đã chốt điểm thành công!');
      fetchData();
    } catch (err: any) {
      alert('Lỗi chốt điểm: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCloseBatch = async () => {
    if (!selectedBatchId) return;
    if (!confirm('Khoa xác nhận HOÀN TẤT VÀ KẾT THÚC ĐỢT ĐỒ ÁN TỐT NGHIỆP? Toàn bộ hồ sơ sẽ được lưu trữ.')) return;
    try {
      const res = await apiClient.post(`/admin/batches/${selectedBatchId}/close/`);
      alert(res.data?.message || 'Đã kết thúc đợt thành công!');
      fetchBatches();
      fetchData();
    } catch (err: any) {
      alert('Lỗi kết thúc đợt: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleImportFinalAcademic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile || !selectedBatchId) return;

    try {
      setImporting(true);
      setImportResult(null);
      const formData = new FormData();
      formData.append('file', importFile);
      formData.append('batch_id', selectedBatchId.toString());

      const res = await apiClient.post('/admin/final-academic/import-excel/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportResult(res.data);
      fetchData();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(false);
    }
  };

  const handleDeferralDecision = async (projId: number, decision: 'APPROVE_DEFERRAL' | 'REJECT_DEFERRAL', regNo: string) => {
    const isApprove = decision === 'APPROVE_DEFERRAL';
    const reasonPrompt = isApprove
      ? prompt(`Nhập ghi chú duyệt đơn bảo lưu cho SV ${regNo}:`, 'Đủ điều kiện bảo lưu theo quy chế đào tạo')
      : prompt(`Nhập lý do từ chối bảo lưu cho SV ${regNo} (Loại khỏi đợt):`, 'Không đạt yêu cầu bảo lưu');

    if (reasonPrompt === null) return;

    try {
      const res = await apiClient.patch(`/admin/projects/${projId}/deferral-decision/`, {
        decision: decision,
        reason: reasonPrompt,
      });
      alert(res.data?.message || 'Xử lý thành công!');
      fetchData();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.message));
    }
  };

  const deferralCandidates = projects.filter(
    (p) =>
      p.deferral_status === 'REQUESTED' ||
      p.deferral_status === 'APPROVED' ||
      p.final_academic_eligibility === 'INELIGIBLE'
  );

  return (
    <AdminLayout>
      <div className="utc-defense-portal">
        {/* Navigation Tabs */}
        <div className="utc-subnav-tabs">
          <button
            className={`utc-subnav-btn ${activeTab === 'grades' ? 'active' : ''}`}
            onClick={() => setActiveTab('grades')}
          >
            📊 Điểm Số, Biên Bản & Tổng Hợp
          </button>
          <button
            className={`utc-subnav-btn ${activeTab === 'deferral' ? 'active' : ''}`}
            onClick={() => setActiveTab('deferral')}
          >
            📋 Rà Soát Học Vụ & Nhánh Bảo Lưu ({deferralCandidates.length})
          </button>
        </div>

        {/* Header Bar */}
        <div className="utc-defense-header-bar">
          <div className="utc-defense-filters-group">
            <div className="utc-defense-filter-item">
              <label>Đợt ĐATN:</label>
              <select
                value={selectedBatchId || ''}
                onChange={(e) => setSelectedBatchId(Number(e.target.value))}
                className="utc-form-select"
              >
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.batch_code} - {b.batch_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="utc-defense-filter-item">
              <label>Lọc Hội Đồng:</label>
              <select
                value={selectedCouncilId}
                onChange={(e) => setSelectedCouncilId(e.target.value)}
                className="utc-form-select"
              >
                <option value="">-- Tất cả Hội đồng --</option>
                {councils.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.council_name} ({c.defense_room || 'Phòng ?'})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="utc-defense-actions-group">
            <button
              onClick={handleDownloadToTrinhDocx}
              disabled={!selectedCouncilId}
              className="utc-btn-blue-outline"
              title="Xuất Tờ trình thành lập Hội đồng Word chuẩn UTC"
            >
              <span>📄</span> Xuất Tờ Trình Word
            </button>

            <button
              onClick={handleDownloadBienBanExcel}
              disabled={!selectedCouncilId}
              className="utc-btn-emerald-outline"
              title="Xuất file Biên bản chấm điểm Excel của Hội đồng"
            >
              <span>📊</span> Bảng Điểm HĐ (Excel)
            </button>

            <button
              onClick={handleDownloadBienBanPdf}
              disabled={!selectedCouncilId}
              className="utc-btn-red-outline"
              style={{ background: '#fff', border: '1px solid #ef4444', color: '#dc2626', padding: '0.5rem 0.85rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '5px' }}
              title="Xuất Biên bản họp bảo vệ PDF có chữ ký điện tử"
            >
              <span>📑</span> Biên Bản Bảo Vệ (PDF)
            </button>

            <button
              onClick={handleFinalizeCouncilScores}
              disabled={!selectedCouncilId}
              className="utc-btn-amber"
              title="Hội đồng xác nhận chốt điểm chính thức"
            >
              <span>🔒</span> HĐ Xác Nhận Chốt Điểm
            </button>

            <button
              onClick={handleDownloadFinalSummaryExcel}
              className="utc-btn-emerald"
              title="Xuất toàn bộ dữ liệu cuối kỳ phục vụ ký số và lưu trữ"
            >
              <span>📑</span> Xuất Dữ Liệu Cuối Kỳ (Ký)
            </button>

            <button
              onClick={handleCloseBatch}
              className="utc-btn-red"
              title="Khoa hoàn tất và kết thúc đợt đồ án"
            >
              <span>🏁</span> Kết Thúc Đợt Đồ Án
            </button>
          </div>
        </div>

        {/* TAB 1: GRADES & COUNCIL SUMMARY */}
        {activeTab === 'grades' && (
          <div className="utc-defense-table-card">
            <div className="utc-panel-head">
              <h4>Bảng Tổng Hợp Điểm Bảo Vệ & Xếp Loại Đồ Án Tốt Nghiệp ({projects.length})</h4>
              <span className="text-muted">Tổng hợp tự động: Điểm GVHD (40%), Điểm Phản biện (20%), Điểm Hội đồng (40%)</span>
            </div>

            {loading ? (
              <div className="utc-loading-text">Đang tải dữ liệu điểm...</div>
            ) : projects.length === 0 ? (
              <div className="utc-empty-text">Không có đồ án nào trong bộ lọc này.</div>
            ) : (
              <div className="utc-table-container">
                <table className="utc-custom-table">
                  <thead>
                    <tr>
                      <th>MSSV</th>
                      <th>Sinh Viên</th>
                      <th>Hội Đồng</th>
                      <th>GV Hướng Dẫn</th>
                      <th>GV Phản Biện</th>
                      <th>Điểm GVHD</th>
                      <th>Điểm GVPB</th>
                      <th>Tổng Hệ 10</th>
                      <th>Hệ 4</th>
                      <th>Điểm Chữ</th>
                      <th>Kết Luận</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projects.map((proj) => {
                      const isDeferred = proj.deferral_status === 'APPROVED';
                      return (
                        <tr key={proj.id} style={{ backgroundColor: isDeferred ? '#fffbeb' : undefined }}>
                          <td className="font-bold">{proj.student_reg_no}</td>
                          <td>
                            <div className="font-semibold">{proj.student_name}</div>
                            <div className="text-xs text-muted">{proj.student_class}</div>
                          </td>
                          <td>{proj.council_name || '—'}</td>
                          <td>{proj.supervisor_name}</td>
                          <td>{proj.reviewer_name || '—'}</td>
                          <td className="text-center font-bold">{proj.supervisor_score !== null ? proj.supervisor_score : '—'}</td>
                          <td className="text-center font-bold">{proj.reviewer_score !== null ? proj.reviewer_score : '—'}</td>
                          <td className="text-center font-bold text-blue-700">
                            {isDeferred ? '—' : proj.final_score_10 !== null ? proj.final_score_10 : '—'}
                          </td>
                          <td className="text-center font-bold">
                            {isDeferred ? '—' : proj.final_score_4 !== null ? proj.final_score_4 : '—'}
                          </td>
                          <td className="text-center font-bold">
                            {isDeferred ? '—' : proj.final_letter_grade || '—'}
                          </td>
                          <td>
                            {isDeferred ? (
                              <span className="utc-badge-deferral">BẢO LƯU</span>
                            ) : proj.is_passed ? (
                              <span className="utc-badge-pass">ĐẠT</span>
                            ) : proj.final_score_10 !== null ? (
                              <span className="utc-badge-fail">KHÔNG ĐẠT</span>
                            ) : (
                              <span className="utc-badge-pending">Chờ chấm</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: DEFERRAL & FINAL ACADEMIC STATUS */}
        {activeTab === 'deferral' && (
          <div className="utc-defense-table-card">
            <div className="utc-panel-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h4>Nhánh Bảo Lưu & Rà Soát Học Vụ Cuối (Bước 36, 37 & 43)</h4>
                <span className="text-muted">
                  Nếu không đủ điều kiện học vụ hoặc không đủ khả năng bảo vệ: Khoa duyệt đơn Bảo lưu $\rightarrow$ Lưu hồ sơ và kết thúc; Không duyệt $\rightarrow$ Loại khỏi đợt
                </span>
              </div>
              <button onClick={() => setShowImportFinalModal(true)} className="utc-btn-emerald">
                <span>📊</span> Import Kiểm Tra Học Vụ Cuối (Excel)
              </button>
            </div>

            <div className="utc-table-container">
              <table className="utc-custom-table">
                <thead>
                  <tr>
                    <th>MSSV</th>
                    <th>Sinh Viên</th>
                    <th>GV Xác Nhận BV</th>
                    <th>Điều Kiện Học Vụ Cuối</th>
                    <th>Trạng Thái Bảo Lưu</th>
                    <th>Lý Do / Ghi Chú</th>
                    <th>Quyết Định Của Khoa</th>
                  </tr>
                </thead>
                <tbody>
                  {deferralCandidates.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-6 text-slate-500">
                        Không có sinh viên nào rơi vào diện bảo lưu hoặc nợ học vụ cuối.
                      </td>
                    </tr>
                  ) : (
                    deferralCandidates.map((proj) => (
                      <tr key={proj.id}>
                        <td className="font-bold">{proj.student_reg_no}</td>
                        <td>{proj.student_name}</td>
                        <td>
                          <span className={`utc-pill ${proj.supervisor_defense_confirmed ? 'pill-green' : 'pill-amber'}`}>
                            {proj.supervisor_defense_confirmed ? 'Đủ khả năng BV' : 'Chưa xác nhận'}
                          </span>
                        </td>
                        <td>
                          <span className={`utc-pill ${proj.final_academic_eligibility === 'ELIGIBLE' ? 'pill-green' : 'pill-red'}`}>
                            {proj.final_academic_eligibility === 'ELIGIBLE' ? 'Đủ ĐK Học Vụ' : 'Nợ CĐR / Học phí'}
                          </span>
                        </td>
                        <td>
                          <span className={`utc-deferral-status status-${(proj.deferral_status || 'none').toLowerCase()}`}>
                            {proj.deferral_status === 'APPROVED'
                              ? '✅ Đã Duyệt Bảo Lưu'
                              : proj.deferral_status === 'REJECTED'
                              ? '🚫 Từ Chối Bảo Lưu (Loại)'
                              : '⏳ Đơn Xin Bảo Lưu'}
                          </span>
                        </td>
                        <td style={{ maxWidth: '250px' }}>
                          <span className="text-xs text-slate-700">{proj.deferral_reason || proj.final_academic_notes || '—'}</span>
                        </td>
                        <td>
                          <div className="utc-action-btn-group">
                            {proj.deferral_status !== 'APPROVED' && (
                              <button
                                onClick={() => handleDeferralDecision(proj.id, 'APPROVE_DEFERRAL', proj.student_reg_no)}
                                className="utc-btn-sm-approve"
                                title="Khoa duyệt bảo lưu -> Lưu hồ sơ và kết thúc"
                              >
                                ✓ Duyệt Bảo Lưu
                              </button>
                            )}
                            {proj.deferral_status !== 'REJECTED' && (
                              <button
                                onClick={() => handleDeferralDecision(proj.id, 'REJECT_DEFERRAL', proj.student_reg_no)}
                                className="utc-btn-sm-reject"
                                title="Từ chối bảo lưu -> Loại khỏi đợt"
                              >
                                ✕ Loại Khỏi Đợt
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* MODAL: IMPORT FINAL ACADEMIC */}
        {showImportFinalModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card">
              <div className="utc-modal-head">
                <h4>📊 Import Rà Soát Điều Kiện Học Vụ Cuối (Bước 36 & 37)</h4>
                <button onClick={() => setShowImportFinalModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleImportFinalAcademic}>
                <div className="utc-form-group">
                  <label>Chọn File Excel Rà Soát Học Vụ:</label>
                  <input
                    type="file"
                    accept=".xlsx, .xls"
                    required
                    onChange={(e) => setImportFile(e.target.files ? e.target.files[0] : null)}
                    className="utc-input"
                  />
                  <small style={{ color: '#64748b', display: 'block', marginTop: '0.4rem' }}>
                    File Excel kiểm tra chuẩn đầu ra ngoại ngữ, công nợ học phí và điều kiện bảo vệ.
                  </small>
                </div>

                {importResult && (
                  <div className="utc-alert-box">
                    <strong>Kết quả rà soát:</strong>
                    <div>Đã kiểm tra: {importResult.total} sinh viên</div>
                    <div style={{ color: '#059669' }}>Đủ điều kiện: {importResult.eligible_count}</div>
                    <div style={{ color: '#dc2626' }}>Không đủ ĐK (Chuyển bảo lưu): {importResult.ineligible_count}</div>
                  </div>
                )}

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowImportFinalModal(false)} className="utc-btn-cancel">Đóng</button>
                  <button type="submit" disabled={importing} className="utc-btn-emerald">
                    {importing ? 'Đang phân tích...' : 'Bắt Đầu Import & Rà Soát'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
