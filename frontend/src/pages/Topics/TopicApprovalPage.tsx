import React, { useState, useEffect } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './TopicApprovalPage.css';

interface ProjectTopic {
  id: number;
  student_name: string;
  student_reg_no: string;
  student_class: string;
  education_program: string;
  supervisor_name: string;
  topic_title_vi: string;
  topic_title_en: string;
  topic_review_status: 'DRAFT' | 'GV_CONFIRMED' | 'APPROVED' | 'REVISION_REQUIRED';
  topic_revision_notes: string;
  status: string;
}

export const TopicApprovalPage: React.FC = () => {
  const [batches, setBatches] = useState<any[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [projects, setProjects] = useState<ProjectTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

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



  const handleDownloadOutline = async (projId: number, regNo: string) => {
    try {
      const res = await apiClient.get(`/admin/projects/${projId}/download-outline/`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Phieu_giao_de_tai_${regNo}.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Lỗi tải phiếu giao đề tài!');
    }
  };

  const filteredProjects = projects.filter((p) => {
    if (statusFilter === 'ALL') return true;
    return p.topic_review_status === statusFilter;
  });

  const countPending = projects.filter((p) => p.topic_review_status === 'GV_CONFIRMED').length;
  const countApproved = projects.filter((p) => p.topic_review_status === 'APPROVED').length;
  const countRevision = projects.filter((p) => p.topic_review_status === 'REVISION_REQUIRED').length;
  const countDraft = projects.filter((p) => p.topic_review_status === 'DRAFT').length;

  return (
    <AdminLayout>
      <div className="utc-topics-portal">
        {/* Header Bar */}
        <div className="utc-topics-header-bar">
          <div className="utc-topics-header-info">
            <h3>Giai Đoạn 2: Danh Sách & Giám Sát Đề Tài & Đề Cương ĐATN</h3>
            <p>Theo chuẩn yeucau.md: Sinh viên đăng ký tên & mục tiêu đề tài ➔ GVHD trực tiếp thẩm định & duyệt đề tài. Sinh viên hoàn thiện đề cương theo mẫu Template và xuất file PDF để GVHD duyệt trên hệ thống.</p>
          </div>

          <div className="utc-batch-select-group">
            <label>🎯 Chọn Đợt ĐATN:</label>
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
          </div>
        </div>

        {/* Status Counters */}
        <div className="utc-topic-stats-grid">
          <div
            className={`utc-topic-stat-box ${statusFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setStatusFilter('ALL')}
          >
            <span className="stat-title">Tất cả đề tài</span>
            <span className="stat-number">{projects.length}</span>
          </div>

          <div
            className={`utc-topic-stat-box ${statusFilter === 'GV_CONFIRMED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('GV_CONFIRMED')}
          >
            <span className="stat-title">GVHD đã xác nhận</span>
            <span className="stat-number text-amber">{countPending}</span>
          </div>

          <div
            className={`utc-topic-stat-box ${statusFilter === 'APPROVED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('APPROVED')}
          >
            <span className="stat-title">Đề tài hợp lệ</span>
            <span className="stat-number text-emerald">{countApproved}</span>
          </div>

          <div
            className={`utc-topic-stat-box ${statusFilter === 'REVISION_REQUIRED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('REVISION_REQUIRED')}
          >
            <span className="stat-title">Cần hoàn thiện</span>
            <span className="stat-number text-red">{countRevision}</span>
          </div>

          <div
            className={`utc-topic-stat-box ${statusFilter === 'DRAFT' ? 'active' : ''}`}
            onClick={() => setStatusFilter('DRAFT')}
          >
            <span className="stat-title">Đang soạn nháp</span>
            <span className="stat-number text-slate">{countDraft}</span>
          </div>
        </div>

        {/* Projects Table */}
        <div className="utc-topic-table-card">
          <div className="utc-topic-table-head">
            <h4>Danh sách Đề tài đồ án tốt nghiệp ({filteredProjects.length})</h4>
            <span className="text-muted">Theo dõi danh mục đề tài chính thức do GVHD và SV đăng ký</span>
          </div>

          {loading ? (
            <div className="utc-loading-text">Đang tải danh sách đề tài...</div>
          ) : filteredProjects.length === 0 ? (
            <div className="utc-empty-text">Không có đề tài nào phù hợp với bộ lọc.</div>
          ) : (
            <div className="utc-table-container">
              <table className="utc-custom-table">
                <thead>
                  <tr>
                    <th>MSSV</th>
                    <th>Sinh Viên</th>
                    <th>Hệ ĐT</th>
                    <th>GV Hướng Dẫn</th>
                    <th>Tên Đề Tài Tốt Nghiệp</th>
                    <th>Trạng Thái Đề Tài</th>
                    <th>Tài Liệu / Đề Cương</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProjects.map((p) => (
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
                      <td>
                        <span className="font-medium text-slate-800">{p.supervisor_name}</span>
                      </td>
                      <td style={{ maxWidth: '320px' }}>
                        <div className="font-semibold text-slate-900">{p.topic_title_vi}</div>
                        {p.topic_title_en && <div className="text-xs text-muted italic">{p.topic_title_en}</div>}
                        {p.topic_revision_notes && (
                          <div className="utc-revision-note-box">
                            <strong>Ghi chú:</strong> {p.topic_revision_notes}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`utc-topic-badge badge-${(p.topic_review_status || 'draft').toLowerCase()}`}>
                          {p.topic_review_status === 'APPROVED'
                            ? '✅ Đề Tài Hợp Lệ'
                            : p.topic_review_status === 'GV_CONFIRMED'
                            ? '✓ GVHD Đã Xác Nhận'
                            : p.topic_review_status === 'REVISION_REQUIRED'
                            ? '⚠️ Cần Hoàn Thiện'
                            : '📝 Bản Nháp (Draft)'}
                        </span>
                      </td>
                      <td>
                        <div className="utc-action-btn-group">
                          <button
                            onClick={() => handleDownloadOutline(p.id, p.student_reg_no)}
                            className="utc-btn-sm-outline"
                            title="Tải phiếu giao đề tài Word (.docx)"
                          >
                            📄 Xuất Phiếu Giao ĐT
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  );
};
