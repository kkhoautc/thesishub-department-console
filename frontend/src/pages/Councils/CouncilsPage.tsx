import React, { useState, useEffect } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './CouncilsPage.css';

interface CouncilMember {
  id: number;
  user: number;
  role: string;
  external_institution: string;
  lecturer_name: string;
  academic_title: string;
}

interface DefenseCouncil {
  id: number;
  batch: number;
  council_number: number;
  council_name: string;
  session_date: string | null;
  session_time: string;
  defense_room: string;
  is_finalized?: boolean;
  members: CouncilMember[];
  project_count: number;
  validity_info?: {
    is_valid: boolean;
    chair_count: number;
    secretary_count: number;
    member_count: number;
    total_count: number;
    expected_formula: string;
  };
}

export const CouncilsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'councils' | 'schedule'>('councils');
  const [batches, setBatches] = useState<any[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [councils, setCouncils] = useState<DefenseCouncil[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [assignResult, setAssignResult] = useState<any>(null);

  // Create Council Form (1 Chủ tịch, 2 Thư ký, 2 Ủy viên)
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [councilNumber, setCouncilNumber] = useState(1);
  const [councilName, setCouncilName] = useState('');
  const [defenseRoom, setDefenseRoom] = useState('');
  const [sessionDate, setSessionDate] = useState('');
  const [sessionTime, setSessionTime] = useState('MORNING');
  const [selectedMembers, setSelectedMembers] = useState<Array<{ user_id: number; role: string; external_institution?: string }>>([]);

  // Auto Schedule Modal
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [slotDuration, setSlotDuration] = useState(40);
  const [morningStart, setMorningStart] = useState('08:00');
  const [afternoonStart, setAfternoonStart] = useState('13:30');
  const [scheduling, setScheduling] = useState(false);

  // Manual Override Reviewer Modal
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideProj, setOverrideProj] = useState<any>(null);
  const [overrideCouncilId, setOverrideCouncilId] = useState<number | ''>('');
  const [overrideReviewerId, setOverrideReviewerId] = useState<number | ''>('');

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
      const [counRes, userRes, projRes] = await Promise.all([
        apiClient.get(`/admin/councils/?batch_id=${selectedBatchId}`),
        apiClient.get('/admin/users/?user_type=supervisor'),
        apiClient.get(`/admin/projects/?batch_id=${selectedBatchId}`),
      ]);
      setCouncils(Array.isArray(counRes.data) ? counRes.data : (counRes.data?.results || []));
      const userList = Array.isArray(userRes.data) ? userRes.data : (userRes.data?.users || userRes.data?.results || []);
      setUsers(userList);
      setProjects(Array.isArray(projRes.data) ? projRes.data : (projRes.data?.results || []));
    } catch (err) {
      console.error(err);
      setCouncils([]);
      setUsers([]);
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
  }, [selectedBatchId]);

  const handleAutoAssignReviewers = async () => {
    if (!selectedBatchId) return;
    if (!confirm('Khởi chạy tự động phân bổ Hội đồng & Giảng viên phản biện (ràng buộc không trùng GVHD, cân bằng tải)?')) return;

    try {
      setAssigning(true);
      setAssignResult(null);
      const res = await apiClient.post('/admin/reviewers/auto-assign/', {
        batch_id: selectedBatchId,
      });
      setAssignResult(res.data);
      fetchData();
    } catch (err: any) {
      alert('Lỗi phân công phản biện: ' + (err.response?.data?.detail || err.message));
    } finally {
      setAssigning(false);
    }
  };

  const handleRunAutoSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBatchId) return;

    try {
      setScheduling(true);
      const res = await apiClient.post('/admin/defense/auto-schedule/', {
        batch_id: selectedBatchId,
        slot_duration: slotDuration,
        morning_start: morningStart,
        afternoon_start: afternoonStart,
      });
      alert(`Đã tự động xếp lịch thành công cho ${res.data?.scheduled_projects_count} đồ án!`);
      setShowScheduleModal(false);
      setActiveTab('schedule');
      fetchData();
    } catch (err: any) {
      alert('Lỗi xếp lịch: ' + (err.response?.data?.detail || err.message));
    } finally {
      setScheduling(false);
    }
  };

  const handleOpenOverride = (proj: any) => {
    setOverrideProj(proj);
    setOverrideCouncilId(proj.council || '');
    setOverrideReviewerId(proj.reviewer || '');
    setShowOverrideModal(true);
  };

  const handleSaveOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideProj) return;

    try {
      const res = await apiClient.patch('/admin/defense/override-reviewer/', {
        project_id: overrideProj.id,
        council_id: overrideCouncilId ? Number(overrideCouncilId) : null,
        reviewer_id: overrideReviewerId ? Number(overrideReviewerId) : null,
      });
      alert(res.data?.message || 'Đã điều chỉnh thành công!');
      setShowOverrideModal(false);
      setOverrideProj(null);
      fetchData();
    } catch (err: any) {
      alert('Lỗi: ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
    }
  };

  const handleCreateCouncil = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBatchId || !councilName) return;

    try {
      await apiClient.post('/admin/councils/', {
        batch_id: selectedBatchId,
        council_number: councilNumber,
        council_name: councilName,
        defense_room: defenseRoom,
        session_date: sessionDate || null,
        session_time: sessionTime,
        members: selectedMembers,
      });
      setShowCreateModal(false);
      setCouncilName('');
      setDefenseRoom('');
      setSelectedMembers([]);
      fetchData();
    } catch (err: any) {
      alert('Lỗi tạo Hội đồng: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteCouncil = async (councilId: number, councilName: string) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa "${councilName}"? Mọi phân công đồ án vào hội đồng này sẽ được reset.`)) return;
    try {
      await apiClient.delete(`/admin/councils/${councilId}/`);
      alert(`Đã xóa thành công ${councilName}.`);
      fetchData();
    } catch (err: any) {
      alert('Lỗi xóa hội đồng: ' + (err.response?.data?.detail || err.message));
    }
  };

  const addMemberSlot = () => {
    setSelectedMembers([...selectedMembers, { user_id: 0, role: 'MEMBER', external_institution: '' }]);
  };

  const updateMemberSlot = (index: number, field: string, val: any) => {
    const updated = [...selectedMembers];
    (updated[index] as any)[field] = val;
    setSelectedMembers(updated);
  };

  const removeMemberSlot = (index: number) => {
    setSelectedMembers(selectedMembers.filter((_, i) => i !== index));
  };

  return (
    <AdminLayout>
      <div className="utc-councils-portal">
        {/* Navigation Tabs */}
        <div className="utc-subnav-tabs">
          <button
            className={`utc-subnav-btn ${activeTab === 'councils' ? 'active' : ''}`}
            onClick={() => setActiveTab('councils')}
          >
            🏛️ Hội Đồng Bảo Vệ & Phản Biện (1CT-2TK-2UV)
          </button>
          <button
            className={`utc-subnav-btn ${activeTab === 'schedule' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedule')}
          >
            ⏱️ Lịch Bảo Vệ Chi Tiết Từng Sinh Viên (Slot)
          </button>
        </div>

        {/* Header Bar */}
        <div className="utc-councils-header-bar">
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

          <div className="utc-council-actions">
            <button onClick={() => setShowCreateModal(true)} className="utc-btn-primary">
              <span>➕</span> Tạo Hội Đồng Chuẩn (1CT-2TK-2UV)
            </button>
            <button
              onClick={handleAutoAssignReviewers}
              disabled={assigning}
              className="utc-btn-emerald"
              title="Phân bổ đề tài vào HĐ & gán phản biện không trùng GVHD"
            >
              <span>⚖️</span> {assigning ? 'Đang phân bổ...' : 'Tự Động Phân HĐ & Phản Biện'}
            </button>
            <button
              onClick={() => setShowScheduleModal(true)}
              className="utc-btn-violet"
              title="Khoa nhập tham số ca/giờ/thời lượng để tự động xếp lịch"
            >
              <span>⏱️</span> Tự Động Xếp Lịch Bảo Vệ
            </button>
          </div>
        </div>

        {/* TAB 1: COUNCILS */}
        {activeTab === 'councils' && (
          <>
            {/* Auto-Assign Feedback */}
            {assignResult && (
              <div className="utc-assign-feedback">
                <h4>🎉 Kết Quả Phân Bổ Hội Đồng & Phản Biện:</h4>
                <p>
                  Đã gán thành công: <strong>{assignResult.assigned_count}</strong> đề tài | Trùng xung đột: <strong>{assignResult.unassigned_count}</strong>
                </p>
                {assignResult.conflicts && assignResult.conflicts.length > 0 && (
                  <div className="utc-conflicts-box">
                    <strong>Xung đột lợi ích phát hiện:</strong>
                    <ul>
                      {assignResult.conflicts.map((c: any, idx: number) => (
                        <li key={idx}>
                          {c.student_name} ({c.registration_no}): {c.reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Councils Grid */}
            {loading ? (
              <div className="utc-loading-text">Đang tải danh sách Hội đồng...</div>
            ) : councils.length === 0 ? (
              <div className="utc-empty-text">Chưa thành lập Hội đồng nào cho đợt này. Hãy nhấn "Tạo Hội Đồng Chuẩn".</div>
            ) : (
              <div className="utc-councils-grid">
                {councils.map((council) => {
                  const val = council.validity_info;
                  return (
                    <div key={council.id} className="utc-council-card">
                      <div className="utc-council-card-head">
                        <div>
                          <span className="utc-council-tag">HĐ #{council.council_number}</span>
                          <h4>{council.council_name}</h4>
                        </div>
                        <span className={`utc-utc-model-badge ${val?.is_valid ? 'badge-utc-valid' : 'badge-utc-warn'}`}>
                          {val?.is_valid ? '✅ Chuẩn 1CT-2TK-2UV' : `⚠️ Thành phần (${council.members?.length || 0}/5)`}
                        </span>
                      </div>

                      <div className="utc-council-meta">
                        <div>📅 {council.session_date ? council.session_date : 'Chưa xếp ngày'}</div>
                        <div>⏰ {council.session_time === 'AFTERNOON' ? 'Ca Chiều (13:30)' : 'Ca Sáng (08:00)'}</div>
                        <div>🚪 Phòng: <strong>{council.defense_room || 'Chưa gán'}</strong></div>
                        <div>📚 Đề tài: <strong>{council.project_count || 0}</strong> sinh viên</div>
                      </div>

                      <div className="utc-members-list">
                        <h5>Thành phần Hội đồng:</h5>
                        {council.members && council.members.length > 0 ? (
                          council.members.map((m) => (
                            <div key={m.id} className="utc-member-row">
                              <span className="utc-member-role">{m.role === 'CHAIR' ? 'Chủ tịch' : m.role === 'SECRETARY' ? 'Thư ký' : 'Ủy viên'}</span>
                              <span className="utc-member-name">{m.academic_title} {m.lecturer_name}</span>
                            </div>
                          ))
                        ) : (
                          <div className="text-muted text-xs" style={{ color: '#ef4444', fontWeight: 600 }}>⚠️ Chưa có thành viên nào. Hội đồng này sẽ bị bỏ qua khi phân bổ tự động.</div>
                        )}
                      </div>

                      <div style={{ marginTop: '0.85rem', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid #f1f5f9', paddingTop: '0.65rem' }}>
                        <button
                          type="button"
                          onClick={() => handleDeleteCouncil(council.id, council.council_name)}
                          className="utc-btn-cancel"
                          style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem', color: '#dc2626', borderColor: '#fca5a5', background: '#fff' }}
                          title="Xóa hội đồng này"
                        >
                          🗑️ Xóa Hội Đồng
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* TAB 2: DETAILED SCHEDULE (SLOTS) */}
        {activeTab === 'schedule' && (
          <div className="utc-schedule-section">
            <div className="utc-panel-head">
              <h4>⏱️ Lịch Bảo Vệ Chi Tiết Từng Sinh Viên (Theo Khung Giờ & Phòng)</h4>
              <span className="text-muted">Được tính toán tự động dựa trên thời lượng và ca bảo vệ của từng Hội đồng</span>
            </div>

            <div className="utc-table-container">
              <table className="utc-custom-table">
                <thead>
                  <tr>
                    <th>STT</th>
                    <th>Hội Đồng</th>
                    <th>MSSV</th>
                    <th>Sinh Viên</th>
                    <th>Khung Giờ Bảo Vệ</th>
                    <th>Phòng</th>
                    <th>GV Hướng Dẫn</th>
                    <th>GV Phản Biện</th>
                    <th>Hành Động</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((proj, idx) => (
                    <tr key={proj.id}>
                      <td className="text-center font-bold">{proj.schedule_slot_info?.order || idx + 1}</td>
                      <td>
                        <span className="font-semibold text-slate-800">{proj.council_name || 'Chưa gán HĐ'}</span>
                      </td>
                      <td className="font-bold">{proj.student_reg_no}</td>
                      <td>
                        <div className="font-semibold">{proj.student_name}</div>
                        <div className="text-xs text-muted">{proj.topic_title_vi}</div>
                      </td>
                      <td>
                        {proj.schedule_slot_info ? (
                          <span className="utc-time-slot-badge">
                            {proj.schedule_slot_info.start} - {proj.schedule_slot_info.end}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">Chưa xếp slot</span>
                        )}
                      </td>
                      <td>
                        <span className="font-bold text-blue-700">{proj.schedule_slot_info?.room || '—'}</span>
                      </td>
                      <td>{proj.supervisor_name}</td>
                      <td>
                        <span className="font-semibold text-purple-700">{proj.reviewer_name || 'Chưa gán GVPB'}</span>
                      </td>
                      <td>
                        <button onClick={() => handleOpenOverride(proj)} className="utc-btn-override" title="Đổi HĐ hoặc Phản biện">
                          ✏️ Đổi
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* MODAL 1: CREATE COUNCIL (1CT - 2TK - 2UV) */}
        {showCreateModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card" style={{ maxWidth: '650px' }}>
              <div className="utc-modal-head">
                <h4>➕ Thành Lập Hội Đồng Bảo Vệ Chuẩn UTC (1CT-2TK-2UV)</h4>
                <button onClick={() => setShowCreateModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleCreateCouncil}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
                  <div className="utc-form-group">
                    <label>Số Hội Đồng:</label>
                    <input
                      type="number"
                      min={1}
                      value={councilNumber}
                      onChange={(e) => setCouncilNumber(Number(e.target.value))}
                      className="utc-input"
                      required
                    />
                  </div>
                  <div className="utc-form-group">
                    <label>Tên Hội Đồng:</label>
                    <input
                      type="text"
                      placeholder="VD: Hội đồng chấm đồ án tốt nghiệp 1"
                      value={councilName}
                      onChange={(e) => setCouncilName(e.target.value)}
                      className="utc-input"
                      required
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                  <div className="utc-form-group">
                    <label>Phòng Bảo Vệ:</label>
                    <input
                      type="text"
                      placeholder="VD: P.402-A9"
                      value={defenseRoom}
                      onChange={(e) => setDefenseRoom(e.target.value)}
                      className="utc-input"
                    />
                  </div>
                  <div className="utc-form-group">
                    <label>Ngày Bảo Vệ:</label>
                    <input
                      type="date"
                      value={sessionDate}
                      onChange={(e) => setSessionDate(e.target.value)}
                      className="utc-input"
                    />
                  </div>
                  <div className="utc-form-group">
                    <label>Ca Bảo Vệ:</label>
                    <select
                      value={sessionTime}
                      onChange={(e) => setSessionTime(e.target.value)}
                      className="utc-input"
                    >
                      <option value="MORNING">Ca Sáng (08:00)</option>
                      <option value="AFTERNOON">Ca Chiều (13:30)</option>
                    </select>
                  </div>
                </div>

                <div className="utc-form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label>Thành Viên Hội Đồng (Chuẩn: 1 Chủ tịch, 2 Thư ký, 2 Ủy viên):</label>
                    <button type="button" onClick={addMemberSlot} className="utc-btn-sm-add">
                      + Thêm thành viên
                    </button>
                  </div>

                  {selectedMembers.map((m, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
                      <select
                        style={{ flex: 2 }}
                        className="utc-input"
                        value={m.user_id}
                        onChange={(e) => updateMemberSlot(idx, 'user_id', Number(e.target.value))}
                        required
                      >
                        <option value={0}>-- Chọn giảng viên --</option>
                        {users.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.full_name} ({u.username})
                          </option>
                        ))}
                      </select>

                      <select
                        style={{ flex: 1.5 }}
                        className="utc-input"
                        value={m.role}
                        onChange={(e) => updateMemberSlot(idx, 'role', e.target.value)}
                      >
                        <option value="CHAIR">Chủ tịch (CT)</option>
                        <option value="SECRETARY">Ủy viên, Thư ký (TK)</option>
                        <option value="MEMBER">Ủy viên (UV)</option>
                        <option value="EXTERNAL_MEMBER">Ủy viên ngoài trường</option>
                      </select>

                      <button type="button" onClick={() => removeMemberSlot(idx)} className="utc-btn-sm-del">
                        ✕
                      </button>
                    </div>
                  ))}
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowCreateModal(false)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" className="utc-btn-primary">Lưu Hội Đồng</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 2: AUTO SCHEDULE */}
        {showScheduleModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card">
              <div className="utc-modal-head">
                <h4>⏱️ Tự Động Xếp Lịch Bảo Vệ Chi Tiết (Bước 41)</h4>
                <button onClick={() => setShowScheduleModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleRunAutoSchedule}>
                <div className="utc-form-group">
                  <label>Thời lượng mỗi đồ án (phút):</label>
                  <input
                    type="number"
                    min={20}
                    max={90}
                    value={slotDuration}
                    onChange={(e) => setSlotDuration(Number(e.target.value))}
                    className="utc-input"
                    required
                  />
                  <small style={{ color: '#64748b' }}>Tiêu chuẩn UTC: 40 - 45 phút cho mỗi đồ án bảo vệ.</small>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="utc-form-group">
                    <label>Giờ bắt đầu ca sáng:</label>
                    <input
                      type="text"
                      value={morningStart}
                      onChange={(e) => setMorningStart(e.target.value)}
                      className="utc-input"
                      placeholder="08:00"
                      required
                    />
                  </div>
                  <div className="utc-form-group">
                    <label>Giờ bắt đầu ca chiều:</label>
                    <input
                      type="text"
                      value={afternoonStart}
                      onChange={(e) => setAfternoonStart(e.target.value)}
                      className="utc-input"
                      placeholder="13:30"
                      required
                    />
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowScheduleModal(false)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" disabled={scheduling} className="utc-btn-violet">
                    {scheduling ? 'Đang phân slot...' : 'Khởi Chạy Xếp Lịch'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL 3: MANUAL OVERRIDE REVIEWER / COUNCIL */}
        {showOverrideModal && overrideProj && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card">
              <div className="utc-modal-head">
                <h4>✏️ Điều Chỉnh Thủ Công Hội Đồng & Phản Biện</h4>
                <button onClick={() => setShowOverrideModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleSaveOverride}>
                <div className="utc-form-group">
                  <p>Sinh viên: <strong>{overrideProj.student_name}</strong> ({overrideProj.student_reg_no})</p>
                  <p>GVHD: <strong>{overrideProj.supervisor_name}</strong> (Ràng buộc: Không được trùng với GVPB)</p>
                </div>

                <div className="utc-form-group">
                  <label>Chọn Hội Đồng Bảo Vệ:</label>
                  <select
                    className="utc-input"
                    value={overrideCouncilId}
                    onChange={(e) => setOverrideCouncilId(e.target.value ? Number(e.target.value) : '')}
                  >
                    <option value="">-- Chọn Hội Đồng --</option>
                    {councils.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.council_name} ({c.defense_room || 'Phòng ?'})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="utc-form-group">
                  <label>Chọn Giảng Viên Phản Biện (Reviewer):</label>
                  <select
                    className="utc-input"
                    value={overrideReviewerId}
                    onChange={(e) => setOverrideReviewerId(e.target.value ? Number(e.target.value) : '')}
                  >
                    <option value="">-- Chọn Giảng Viên Phản Biện --</option>
                    {users.map((u) => {
                      const sup = u.supervisor_profile;
                      if (!sup) return null;
                      return (
                        <option key={sup.id} value={sup.id}>
                          {sup.academic_title} {u.full_name} ({sup.department_name || 'Khoa CNTT'})
                        </option>
                      );
                    })}
                  </select>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowOverrideModal(false)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" className="utc-btn-primary">Xác Nhận Điều Chỉnh</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
