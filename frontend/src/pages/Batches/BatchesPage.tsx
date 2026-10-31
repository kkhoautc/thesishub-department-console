import React, { useState, useEffect, useRef } from 'react';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { apiClient } from '../../api/client';
import './BatchesPage.css';
import '../../components/common/Modal.css';

interface AcademicBatch {
  id: number;
  batch_code: string;
  batch_name: string;
  program_type: 'BACHELOR' | 'ENGINEER' | 'BOTH';
  current_stage: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  is_closed: boolean;
  student_count: number;
  project_count: number;
  classes: Array<{
    id: number;
    class_code: string;
    class_name: string;
    program_type: string;
    education_program: string;
    class_group: string;
    student_count: number;
  }>;
}

interface Department {
  id: number;
  code: string;
  name: string;
  description: string;
  supervisor_count: number;
}

interface SupervisorItem {
  id: number;
  supervisor_id: string;
  academic_title: string;
  department_name: string;
  department_obj: number | null;
  department_code?: string;
  academic_rank_multiplier: number;
  phone_number: string;
  research_interest: string;
  user_full_name?: string;
  username?: string;
}

interface StudentItem {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  phone_number?: string;
  is_active: boolean;
  student_profile?: {
    id?: number;
    registration_no?: string;
    department?: string;
    batch_no?: string;
    education_program?: string;
    degree_program?: string;
    phone_number?: string;
    academic_batch?: number;
    major?: string;
    course_class?: {
      id?: number;
      class_code?: string;
      class_name?: string;
      program_type?: string;
      education_program?: string;
    };
  };
}

export const BatchesPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'batches' | 'departments' | 'supervisors'>('batches');
  const [batches, setBatches] = useState<AcademicBatch[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [supervisors, setSupervisors] = useState<SupervisorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);

  // Subtabs inside selected batch: 'students' or 'classes'
  const [batchDetailTab, setBatchDetailTab] = useState<'students' | 'classes'>('students');
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');
  const [filterEduProgram, setFilterEduProgram] = useState<'ALL' | 'BACHELOR' | 'ENGINEER'>('ALL');
  const [filterMajor, setFilterMajor] = useState<'ALL' | 'CNTT' | 'KHMT'>('ALL');

  // Toast Notification State
  const [toast, setToast] = useState<{ show: boolean; type: 'success' | 'error' | 'info'; message: string } | null>(null);
  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
    setToast({ show: true, type, message });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  // Helper for extracting clean DRF error message
  const extractErrorMessage = (err: any, fallback: string): string => {
    const data = err.response?.data;
    if (!data) return err.message || fallback;
    if (typeof data === 'string') return data;
    if (data.detail && typeof data.detail === 'string') return data.detail;
    if (data.error && typeof data.error === 'string') return data.error;
    if (data.message && typeof data.message === 'string') return data.message;
    if (typeof data === 'object') {
      const firstKey = Object.keys(data)[0];
      const val = data[firstKey];
      if (Array.isArray(val) && val.length > 0) {
        return `${firstKey !== 'non_field_errors' ? firstKey + ': ' : ''}${val[0]}`;
      }
      if (typeof val === 'string') return val;
    }
    return err.message || fallback;
  };

  // -------------------------------------------------------------
  // MODAL 1: Create New Batch State
  // -------------------------------------------------------------
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newBatchCode, setNewBatchCode] = useState('');
  const [newBatchName, setNewBatchName] = useState('');
  const [newProgramType, setNewProgramType] = useState<'BACHELOR' | 'ENGINEER' | 'BOTH'>('BACHELOR');
  const [newStartDate, setNewStartDate] = useState('');
  const [newEndDate, setNewEndDate] = useState('');
  const [newIsActive, setNewIsActive] = useState(true);
  const [createBatchLoading, setCreateBatchLoading] = useState(false);
  const [createBatchError, setCreateBatchError] = useState<string | null>(null);

  // Quick suggestion for batch code
  const generateBatchCodeSuggestion = (type: 'DOT1' | 'DOT2') => {
    const year = new Date().getFullYear();
    const code = `${year}-${type}-CNTT`;
    const name = `Đồ án tốt nghiệp ${type === 'DOT1' ? 'Học kỳ 1' : 'Học kỳ 2'} Năm học ${year}-${year + 1}`;
    setNewBatchCode(code);
    setNewBatchName(name);
  };

  // -------------------------------------------------------------
  // MODAL 1.5: Edit Batch State
  // -------------------------------------------------------------
  const [editingBatch, setEditingBatch] = useState<AcademicBatch | null>(null);
  const [editBatchName, setEditBatchName] = useState('');
  const [editBatchProg, setEditBatchProg] = useState<'BACHELOR' | 'ENGINEER' | 'BOTH'>('BACHELOR');
  const [editBatchStart, setEditBatchStart] = useState('');
  const [editBatchEnd, setEditBatchEnd] = useState('');
  const [editBatchIsActive, setEditBatchIsActive] = useState(true);
  const [editBatchLoading, setEditBatchLoading] = useState(false);

  const handleOpenEditBatch = (b: AcademicBatch) => {
    setEditingBatch(b);
    setEditBatchName(b.batch_name);
    setEditBatchProg(b.program_type);
    setEditBatchStart(b.start_date || '');
    setEditBatchEnd(b.end_date || '');
    setEditBatchIsActive(b.is_active);
  };

  const handleSaveEditBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBatch) return;
    try {
      setEditBatchLoading(true);
      await apiClient.patch(`/admin/batches/${editingBatch.id}/`, {
        batch_name: editBatchName,
        program_type: editBatchProg,
        start_date: editBatchStart || null,
        end_date: editBatchEnd || null,
        is_active: editBatchIsActive,
      });
      showToast(`✓ Cập nhật đợt "${editingBatch.batch_code}" thành công!`, 'success');
      setEditingBatch(null);
      fetchBatches();
    } catch (err: any) {
      showToast('❌ Lỗi cập nhật đợt: ' + extractErrorMessage(err, 'Không thể cập nhật đợt'), 'error');
    } finally {
      setEditBatchLoading(false);
    }
  };

  const handleDeleteBatch = async (batch: AcademicBatch) => {
    if (batch.student_count > 0 || batch.project_count > 0) {
      alert(`Đợt "${batch.batch_name}" hiện có ${batch.student_count} sinh viên và ${batch.project_count} đề tài. Bạn không thể xóa đợt khi đang có dữ liệu!`);
      return;
    }
    if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn đợt đồ án "${batch.batch_name}" (${batch.batch_code})?`)) return;
    try {
      await apiClient.delete(`/admin/batches/${batch.id}/`);
      showToast(`✓ Đã xóa đợt "${batch.batch_code}" thành công!`, 'success');
      if (selectedBatchId === batch.id) {
        setSelectedBatchId(null);
      }
      fetchBatches();
    } catch (err: any) {
      showToast('❌ Lỗi xóa đợt: ' + extractErrorMessage(err, 'Không thể xóa đợt'), 'error');
    }
  };

  // -------------------------------------------------------------
  // MODAL 2: Import Excel State
  // -------------------------------------------------------------
  const [showImportModal, setShowImportModal] = useState(false);
  const [importBatchId, setImportBatchId] = useState<number | ''>('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importDefaultMajor, setImportDefaultMajor] = useState<'CNTT' | 'KHMT'>('CNTT');
  const [importPasswordStrategy, setImportPasswordStrategy] = useState<'MSSV' | 'FIXED' | 'RANDOM'>('MSSV');
  const [importFixedPassword, setImportFixedPassword] = useState('Sv@123456');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // -------------------------------------------------------------
  // MODAL 3: Manual Add Student State
  // -------------------------------------------------------------
  const [showAddStudentModal, setShowAddStudentModal] = useState(false);
  const [addBatchId, setAddBatchId] = useState<number | ''>('');
  const [addMssv, setAddMssv] = useState('');
  const [addFullName, setAddFullName] = useState('');
  const [addClassId, setAddClassId] = useState<number | ''>('');
  const [addClassName, setAddClassName] = useState('');
  const [addEduProgram, setAddEduProgram] = useState<'BACHELOR' | 'ENGINEER'>('BACHELOR');
  const [addMajor, setAddMajor] = useState<'CNTT' | 'KHMT'>('CNTT');
  const [addEmail, setAddEmail] = useState('');
  const [addPhone, setAddPhone] = useState('');
  const [addPasswordStrategy, setAddPasswordStrategy] = useState<'MSSV' | 'FIXED' | 'CUSTOM'>('MSSV');
  const [addCustomPassword, setAddCustomPassword] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // -------------------------------------------------------------
  // MODAL 4: Edit Student State
  // -------------------------------------------------------------
  const [editStudent, setEditStudent] = useState<StudentItem | null>(null);
  const [editFullName, setEditFullName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editClassName, setEditClassName] = useState('');
  const [editClassId, setEditClassId] = useState<number | ''>('');
  const [editEduProgram, setEditEduProgram] = useState<'BACHELOR' | 'ENGINEER'>('BACHELOR');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editLoading, setEditLoading] = useState(false);

  const handleOpenEditStudent = (st: StudentItem) => {
    setEditStudent(st);
    const prof = st.student_profile || {};
    setEditFullName(st.full_name || `${st.last_name || ''} ${st.first_name || ''}`.trim() || st.username);
    setEditEmail(st.email || '');
    setEditPhone(prof.phone_number || st.phone_number || '');
    setEditClassName(prof.course_class?.class_name || prof.department || prof.batch_no || '');
    setEditClassId(prof.course_class?.id || '');
    const edu = (prof.education_program || prof.degree_program || prof.course_class?.education_program || 'BACHELOR') as 'BACHELOR' | 'ENGINEER';
    setEditEduProgram(edu === 'ENGINEER' ? 'ENGINEER' : 'BACHELOR');
    setEditIsActive(st.is_active);
  };

  const handleSaveEditStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editStudent) return;
    try {
      setEditLoading(true);
      const parts = editFullName.trim().split(' ');
      const firstName = parts.length > 1 ? parts.pop()! : parts[0];
      const lastName = parts.join(' ');

      const payload: any = {
        first_name: firstName,
        last_name: lastName,
        email: editEmail.trim(),
        phone_number: editPhone.trim(),
        is_active: editIsActive,
        class_name: editClassName.trim(),
        education_program: editEduProgram,
      };
      if (editClassId) {
        payload.course_class_id = Number(editClassId);
      }

      await apiClient.patch(`/admin/users/${editStudent.id}/`, payload);
      showToast(`✓ Cập nhật thông tin sinh viên ${editStudent.username} thành công!`, 'success');
      setEditStudent(null);
      if (selectedBatchId) fetchStudents(selectedBatchId);
      fetchBatches();
    } catch (err: any) {
      showToast('❌ Lỗi cập nhật sinh viên: ' + extractErrorMessage(err, 'Không thể cập nhật thông tin'), 'error');
    } finally {
      setEditLoading(false);
    }
  };

  // -------------------------------------------------------------
  // MODAL 5: Reset Password State
  // -------------------------------------------------------------
  const [resetStudent, setResetStudent] = useState<StudentItem | null>(null);
  const [resetStrategy, setResetStrategy] = useState<'MSSV' | 'FIXED' | 'CUSTOM'>('MSSV');
  const [resetCustomPassword, setResetCustomPassword] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetStudent) return;
    try {
      setResetLoading(true);
      const res = await apiClient.post(`/admin/users/${resetStudent.id}/reset-password/`, {
        password_strategy: resetStrategy,
        custom_password: resetCustomPassword,
      });
      const newPass = res.data?.new_password || resetCustomPassword || 'MSSV';
      showToast(`✓ Đã đặt lại mật khẩu cho sinh viên ${resetStudent.username}! Mật khẩu mới: ${newPass}`, 'success');
      setResetStudent(null);
      setResetCustomPassword('');
    } catch (err: any) {
      showToast('❌ Lỗi đặt lại mật khẩu: ' + extractErrorMessage(err, 'Không thể đặt lại mật khẩu'), 'error');
    } finally {
      setResetLoading(false);
    }
  };

  const handleDeleteStudent = async (studentId: number, studentName: string) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa sinh viên "${studentName}" khỏi đợt đồ án này?`)) return;
    try {
      await apiClient.delete(`/admin/users/${studentId}/`);
      showToast(`✓ Đã xóa sinh viên "${studentName}" thành công!`, 'success');
      if (selectedBatchId) fetchStudents(selectedBatchId);
      fetchBatches();
    } catch (err: any) {
      showToast('❌ Lỗi xóa sinh viên: ' + extractErrorMessage(err, 'Không thể xóa sinh viên'), 'error');
    }
  };

  // -------------------------------------------------------------
  // MODAL 6: Department & Supervisor Management (Tabs 2 & 3)
  // -------------------------------------------------------------
  const [showDeptModal, setShowDeptModal] = useState(false);
  const [deptCode, setDeptCode] = useState('');
  const [deptName, setDeptName] = useState('');
  const [deptDesc, setDeptDesc] = useState('');

  const [editingSupervisor, setEditingSupervisor] = useState<SupervisorItem | null>(null);
  const [supTitle, setSupTitle] = useState('');
  const [supDeptId, setSupDeptId] = useState<number | ''>('');
  const [supMultiplier, setSupMultiplier] = useState(1.0);
  const [supInterest, setSupInterest] = useState('');

  // -------------------------------------------------------------
  // Fetch Functions
  // -------------------------------------------------------------
  const fetchBatches = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/batches/');
      const list: AcademicBatch[] = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setBatches(list);
      if (list.length > 0 && !selectedBatchId) {
        setSelectedBatchId(list[0].id);
      }
    } catch (err) {
      console.error('Error fetching batches:', err);
      setBatches([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      const res = await apiClient.get('/admin/departments/');
      setDepartments(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Error fetching departments:', err);
    }
  };

  const fetchSupervisors = async () => {
    try {
      const res = await apiClient.get('/admin/users/?user_type=supervisor');
      const users = Array.isArray(res.data) ? res.data : (res.data?.users || res.data?.results || []);
      const supList: SupervisorItem[] = [];
      users.forEach((u: any) => {
        if (u.supervisor_profile) {
          supList.push({
            ...u.supervisor_profile,
            user_full_name: u.full_name || u.username,
            username: u.username
          });
        }
      });
      setSupervisors(supList);
    } catch (err) {
      console.error('Error fetching supervisors:', err);
    }
  };

  const fetchStudents = async (batchId: number) => {
    try {
      setStudentsLoading(true);
      const res = await apiClient.get(`/admin/users/?user_type=student&batch_id=${batchId}`);
      const list = Array.isArray(res.data) ? res.data : (res.data?.users || res.data?.results || []);
      setStudents(list);
    } catch (err) {
      console.error('Error fetching students of batch:', err);
      setStudents([]);
    } finally {
      setStudentsLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
    fetchDepartments();
    fetchSupervisors();
  }, []);

  useEffect(() => {
    if (selectedBatchId) {
      fetchStudents(selectedBatchId);
      const curr = batches.find((b) => b.id === selectedBatchId);
      if (curr) {
        if (curr.program_type === 'ENGINEER') {
          setAddEduProgram('ENGINEER');
        } else {
          setAddEduProgram('BACHELOR');
        }
      }
    }
  }, [selectedBatchId, batches]);

  // -------------------------------------------------------------
  // Actions: Create Batch
  // -------------------------------------------------------------
  const handleCreateBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBatchCode.trim() || !newBatchName.trim()) {
      setCreateBatchError('Mã đợt và Tên đợt là các trường bắt buộc.');
      return;
    }

    try {
      setCreateBatchLoading(true);
      setCreateBatchError(null);
      const payload = {
        batch_code: newBatchCode.trim().toUpperCase(),
        batch_name: newBatchName.trim(),
        program_type: newProgramType,
        start_date: newStartDate || null,
        end_date: newEndDate || null,
        is_active: newIsActive,
      };

      const res = await apiClient.post('/admin/batches/', payload);
      setShowCreateModal(false);
      setNewBatchCode('');
      setNewBatchName('');
      setNewProgramType('BACHELOR');
      setNewStartDate('');
      setNewEndDate('');
      setNewIsActive(true);
      showToast('✓ Khởi tạo đợt đồ án tốt nghiệp mới thành công!', 'success');

      // Auto-select newly created batch
      if (res.data && res.data.id) {
        setSelectedBatchId(res.data.id);
      }
      fetchBatches();
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Lỗi tạo đợt đồ án');
      setCreateBatchError(msg);
      showToast(`❌ ${msg}`, 'error');
    } finally {
      setCreateBatchLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Actions: Download Template & Import Excel
  // -------------------------------------------------------------
  const handleDownloadTemplate = async () => {
    try {
      showToast('Đang tạo và kết xuất file Excel mẫu chuẩn UTC...', 'info');
      const res = await apiClient.get('/admin/users/template/?type=student', {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Mau_Import_Sinh_Vien_UTC.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('✓ Tải file mẫu Excel chuẩn UTC thành công!', 'success');
    } catch (err: any) {
      showToast('❌ Không thể tải file mẫu: ' + extractErrorMessage(err, 'Lỗi kết nối máy chủ'), 'error');
    }
  };

  const handleImportExcel = async (e: React.FormEvent) => {
    e.preventDefault();
    const targetBatch = importBatchId || selectedBatchId;
    if (!importFile) {
      showToast('Vui lòng chọn file Excel để import!', 'error');
      return;
    }
    if (!targetBatch) {
      showToast('Vui lòng chọn Đợt Đồ Án áp dụng!', 'error');
      return;
    }

    try {
      setImporting(true);
      setImportResult(null);
      const formData = new FormData();
      formData.append('file', importFile);
      formData.append('batch_id', targetBatch.toString());
      formData.append('default_major', importDefaultMajor);
      formData.append('password_strategy', importPasswordStrategy);
      if (importPasswordStrategy === 'FIXED') {
        formData.append('custom_fixed_password', importFixedPassword);
      }

      const res = await apiClient.post('/admin/students/import-excel/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportResult(res.data);
      showToast(`✓ Import hoàn tất! Đã tạo ${res.data?.created || 0} sinh viên mới.`, 'success');
      fetchBatches();
      fetchStudents(Number(targetBatch));
    } catch (err: any) {
      const msg = extractErrorMessage(err, 'Lỗi khi import file Excel sinh viên');
      showToast(`❌ ${msg}`, 'error');
    } finally {
      setImporting(false);
    }
  };

  // Export Students in standard Excel format
  const handleExportStudents = async () => {
    if (!selectedBatchId) {
      showToast('Vui lòng chọn một đợt đồ án để xuất danh sách sinh viên!', 'info');
      return;
    }
    const currBatch = batches.find((b) => b.id === selectedBatchId);
    try {
      showToast('Đang kết xuất file Excel sinh viên chuẩn định dạng UTC...', 'info');
      const res = await apiClient.get(`/admin/students/export-excel/?batch_id=${selectedBatchId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Danh_Sach_Sinh_Vien_Dot_${currBatch?.batch_code || selectedBatchId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('✓ Đã xuất file Excel sinh viên thành công!', 'success');
    } catch (err: any) {
      showToast('❌ Lỗi xuất file Excel: ' + extractErrorMessage(err, 'Không thể tải file'), 'error');
    }
  };

  // -------------------------------------------------------------
  // Actions: Add Student Manually
  // -------------------------------------------------------------
  const handleAddStudentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const targetBatchId = addBatchId || selectedBatchId;
    if (!addMssv.trim() || !addFullName.trim()) {
      setAddError('Mã sinh viên và Họ tên là các trường bắt buộc!');
      return;
    }
    if (!targetBatchId) {
      setAddError('Vui lòng chọn Đợt Đồ Án áp dụng cho sinh viên!');
      return;
    }

    setAddLoading(true);
    setAddError(null);

    const parts = addFullName.trim().split(' ');
    const firstName = parts.length > 1 ? parts.pop()! : parts[0];
    const lastName = parts.join(' ');

    let plainPass = 'Sv@123456';
    if (addPasswordStrategy === 'MSSV') {
      plainPass = addMssv.trim();
    } else if (addPasswordStrategy === 'CUSTOM' && addCustomPassword.trim()) {
      plainPass = addCustomPassword.trim();
    }

    const payload: any = {
      user_type: 'student',
      username: addMssv.trim(),
      registration_no: addMssv.trim(),
      first_name: firstName,
      last_name: lastName,
      academic_batch_id: Number(targetBatchId),
      education_program: addEduProgram,
      major: addMajor,
      program_type: addMajor === 'KHMT' ? 'KHMT' : 'DAI_TRA',
      email: addEmail.trim() || `${addMssv.trim().toLowerCase()}@sv.utc.edu.vn`,
      phone_number: addPhone.trim(),
      password_strategy: addPasswordStrategy,
      password: plainPass,
    };

    if (addClassId) {
      payload.course_class_id = Number(addClassId);
    }
    if (addClassName.trim()) {
      payload.class_name = addClassName.trim();
    }

    try {
      await apiClient.post('/admin/users/', payload);
      setShowAddStudentModal(false);
      setAddMssv('');
      setAddFullName('');
      setAddClassId('');
      setAddClassName('');
      setAddEmail('');
      setAddPhone('');
      setAddCustomPassword('');
      showToast(`✓ Đã thêm sinh viên ${addMssv.trim()} - ${addFullName.trim()} thành công!`, 'success');
      fetchBatches();
      fetchStudents(Number(targetBatchId));
    } catch (err: any) {
      const errMsg = extractErrorMessage(err, 'Không thể thêm sinh viên');
      setAddError(errMsg);
      showToast(`❌ Thêm sinh viên thất bại: ${errMsg}`, 'error');
    } finally {
      setAddLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Actions: Department & Supervisor Management
  // -------------------------------------------------------------
  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deptCode || !deptName) return;
    try {
      await apiClient.post('/admin/departments/', {
        code: deptCode.trim().toUpperCase(),
        name: deptName.trim(),
        description: deptDesc.trim(),
      });
      setShowDeptModal(false);
      setDeptCode('');
      setDeptName('');
      setDeptDesc('');
      showToast('✓ Thêm bộ môn mới thành công!', 'success');
      fetchDepartments();
    } catch (err: any) {
      showToast('❌ Lỗi tạo bộ môn: ' + extractErrorMessage(err, 'Không thể tạo bộ môn'), 'error');
    }
  };

  const handleOpenEditSupervisor = (sup: SupervisorItem) => {
    setEditingSupervisor(sup);
    setSupTitle(sup.academic_title || 'ThS');
    setSupDeptId(sup.department_obj || '');
    setSupMultiplier(sup.academic_rank_multiplier || 1.0);
    setSupInterest(sup.research_interest || '');
  };

  const handleSaveSupervisor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSupervisor) return;
    try {
      await apiClient.patch(`/admin/supervisors/${editingSupervisor.id}/profile/`, {
        academic_title: supTitle,
        department_id: supDeptId ? Number(supDeptId) : null,
        academic_rank_multiplier: supMultiplier,
        research_interest: supInterest,
      });
      setEditingSupervisor(null);
      fetchSupervisors();
      showToast('✓ Đã cập nhật học vị & hệ số định mức Giảng viên thành công!', 'success');
    } catch (err: any) {
      showToast('❌ Lỗi cập nhật giảng viên: ' + extractErrorMessage(err, 'Không thể lưu'), 'error');
    }
  };

  const handleCloseBatch = async (batchId: number) => {
    if (!confirm('Bạn có chắc chắn muốn KẾT THÚC đợt đồ án này? Sau khi kết thúc, trạng thái đợt sẽ hoàn tất và chuyển sang lưu trữ.')) return;
    try {
      await apiClient.post(`/admin/batches/${batchId}/close/`);
      showToast('✓ Đã kết thúc đợt đồ án thành công!', 'success');
      fetchBatches();
    } catch (err: any) {
      showToast('❌ Lỗi kết thúc đợt: ' + extractErrorMessage(err, 'Không thể kết thúc đợt'), 'error');
    }
  };

  // -------------------------------------------------------------
  // Filter students for table display
  // -------------------------------------------------------------
  const filteredStudents = students.filter((s) => {
    const stdProf = s.student_profile || {};
    // Text search
    if (studentSearch.trim()) {
      const q = studentSearch.trim().toLowerCase();
      const fullName = (s.full_name || `${s.last_name || ''} ${s.first_name || ''}`).toLowerCase();
      const regNo = (stdProf.registration_no || s.username || '').toLowerCase();
      const cls = (stdProf.course_class?.class_name || stdProf.department || stdProf.batch_no || '').toLowerCase();
      const eml = (s.email || '').toLowerCase();
      if (!fullName.includes(q) && !regNo.includes(q) && !cls.includes(q) && !eml.includes(q)) {
        return false;
      }
    }
    // Program filter
    if (filterEduProgram !== 'ALL') {
      const eduProg = stdProf.education_program || stdProf.degree_program || stdProf.course_class?.education_program || 'BACHELOR';
      if (eduProg !== filterEduProgram) return false;
    }
    // Major filter
    if (filterMajor !== 'ALL') {
      const maj = stdProf.major || (stdProf.course_class?.program_type === 'KHMT' ? 'KHMT' : 'CNTT');
      if (maj !== filterMajor) return false;
    }
    return true;
  });

  const currBatch = batches.find((b) => b.id === selectedBatchId);

  return (
    <AdminLayout>
      <div className="utc-batches-portal">
        {/* Navigation Tabs */}
        <div className="utc-subnav-tabs">
          <button
            className={`utc-subnav-btn ${activeTab === 'batches' ? 'active' : ''}`}
            onClick={() => setActiveTab('batches')}
          >
            📅 Đợt Đồ Án & Sinh Viên Thuộc Đợt
          </button>
          <button
            className={`utc-subnav-btn ${activeTab === 'departments' ? 'active' : ''}`}
            onClick={() => setActiveTab('departments')}
          >
            🏢 Danh Mục Bộ Môn Khoa CNTT
          </button>
          <button
            className={`utc-subnav-btn ${activeTab === 'supervisors' ? 'active' : ''}`}
            onClick={() => setActiveTab('supervisors')}
          >
            👨‍🏫 Học Vị & Hướng Nghiên Cứu GV
          </button>
        </div>

        {/* ========================================================= */}
        {/* TAB 1: BATCHES & STUDENTS */}
        {/* ========================================================= */}
        {activeTab === 'batches' && (
          <>
            <div className="utc-batches-header-bar">
              <div className="utc-batches-header-info">
                <h3>Giai Đoạn 1: Khởi Tạo Đợt Đồ Án & Quản Lý Sinh Viên UTC</h3>
                <p>Khởi tạo đợt làm đồ án, thêm sinh viên thủ công hoặc import/export danh sách Excel chuẩn format đào tạo UTC</p>
              </div>
              <div className="utc-batches-actions">
                <button
                  type="button"
                  onClick={() => {
                    setAddError(null);
                    setAddBatchId(selectedBatchId || (batches[0]?.id || ''));
                    if (currBatch && currBatch.program_type !== 'BOTH') {
                      setAddEduProgram(currBatch.program_type);
                    }
                    setShowAddStudentModal(true);
                  }}
                  className="utc-btn-primary"
                  title="Thêm sinh viên thủ công vào đợt ĐATN"
                >
                  <span>👤➕</span> Thêm Sinh Viên
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setImportBatchId(selectedBatchId || (batches[0]?.id || ''));
                    setImportResult(null);
                    setImportFile(null);
                    setShowImportModal(true);
                  }}
                  className="utc-btn-emerald"
                  title="Import sinh viên từ file Excel UTC"
                >
                  <span>📊</span> Import Sinh Viên (Excel)
                </button>

                <button
                  type="button"
                  onClick={handleDownloadTemplate}
                  className="utc-btn-outline"
                  title="Tải file Excel mẫu chuẩn đào tạo UTC (.xlsx)"
                >
                  <span>📥</span> File Mẫu Excel
                </button>

                <button
                  type="button"
                  onClick={handleExportStudents}
                  className="utc-btn-outline"
                  title="Xuất danh sách sinh viên đợt này ra file Excel đúng định dạng file mẫu import"
                >
                  <span>📤</span> Export Sinh Viên (.xlsx)
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setCreateBatchError(null);
                    generateBatchCodeSuggestion('DOT1');
                    setShowCreateModal(true);
                  }}
                  className="utc-btn-primary"
                  style={{ background: '#003366' }}
                  title="Tạo đợt làm đồ án tốt nghiệp mới"
                >
                  <span>➕</span> Tạo Đợt ĐATN Mới
                </button>
              </div>
            </div>

            {loading ? (
              <div className="utc-loading-box">Đang tải danh sách đợt đồ án...</div>
            ) : batches.length === 0 ? (
              <div className="utc-empty-box">
                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📅</div>
                <h4>Chưa có đợt làm ĐATN nào trong hệ thống!</h4>
                <p>Hãy nhấn nút <strong>"Tạo Đợt ĐATN Mới"</strong> phía trên để khởi tạo đợt làm đồ án tốt nghiệp đầu tiên.</p>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(true)}
                  className="utc-btn-primary"
                  style={{ marginTop: '1rem' }}
                >
                  ➕ Tạo Đợt ĐATN Mới Ngay
                </button>
              </div>
            ) : (
              <div className="utc-batches-grid">
                {batches.map((batch) => (
                  <div
                    key={batch.id}
                    onClick={() => setSelectedBatchId(batch.id)}
                    className={`utc-batch-card ${selectedBatchId === batch.id ? 'selected' : ''}`}
                  >
                    <div className="utc-batch-card-head">
                      <div>
                        <span className="utc-batch-code-tag">{batch.batch_code}</span>
                        <span className={`utc-prog-tag prog-${batch.program_type.toLowerCase()}`}>
                          {batch.program_type === 'ENGINEER' ? '⚙️ Kỹ Sư' : batch.program_type === 'BACHELOR' ? '🎓 Cử Nhân' : '🔄 Cả Hai'}
                        </span>
                      </div>
                      <div className="utc-batch-card-actions">
                        <span className={`utc-status-pill ${batch.is_closed ? 'pill-gray' : 'pill-green'}`}>
                          {batch.is_closed ? '🔒 Đã kết thúc' : '🟢 Đang mở'}
                        </span>
                        <button
                          type="button"
                          className="utc-batch-action-icon"
                          title="Chỉnh sửa thông tin đợt"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenEditBatch(batch);
                          }}
                        >
                          ✏️
                        </button>
                        {batch.student_count === 0 && batch.project_count === 0 && (
                          <button
                            type="button"
                            className="utc-batch-action-icon danger"
                            title="Xóa đợt trống này"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteBatch(batch);
                            }}
                          >
                            🗑️
                          </button>
                        )}
                      </div>
                    </div>

                    <h4 className="utc-batch-name">{batch.batch_name}</h4>
                    <div className="utc-batch-stage-text">
                      <strong>Vòng đời:</strong> {batch.current_stage}
                    </div>

                    {(batch.start_date || batch.end_date) && (
                      <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <span>📅 Thời gian:</span>
                        <strong>{batch.start_date || '—'}</strong> đến <strong>{batch.end_date || '—'}</strong>
                      </div>
                    )}

                    <div className="utc-batch-stats">
                      <div className="utc-stat-item">
                        <span className="utc-stat-label">Sinh viên</span>
                        <span className="utc-stat-value">{batch.student_count || 0}</span>
                      </div>
                      <div className="utc-stat-item">
                        <span className="utc-stat-label">Lớp học phần</span>
                        <span className="utc-stat-value">{batch.classes?.length || 0}</span>
                      </div>
                      <div className="utc-stat-item">
                        <span className="utc-stat-label">Đề tài đồ án</span>
                        <span className="utc-stat-value">{batch.project_count || 0}</span>
                      </div>
                    </div>

                    <div className="utc-batch-footer">
                      <span>{batch.is_closed ? 'Đợt đã lưu trữ' : 'Nhấp để xem sinh viên & lớp học'}</span>
                      {!batch.is_closed && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCloseBatch(batch.id);
                          }}
                          className="utc-btn-close-batch"
                          title="Kết thúc đợt đồ án"
                        >
                          Kết thúc đợt
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Selected Batch Details */}
            {selectedBatchId && (
              <div className="utc-classes-section">
                <div className="utc-classes-header">
                  <h4>Quản lý Dữ liệu Đợt ĐATN: #{selectedBatchId} - {currBatch?.batch_name}</h4>
                  <span className="utc-classes-subtitle">
                    Mã đợt: <strong>{currBatch?.batch_code}</strong> | Chương trình: <strong>{currBatch?.program_type}</strong> | Trạng thái: {currBatch?.is_closed ? 'Đã đóng' : 'Đang mở tiếp nhận'}
                  </span>
                </div>

                <div className="utc-batch-subtabs">
                  <button
                    type="button"
                    className={`utc-batch-subtab-btn ${batchDetailTab === 'students' ? 'active' : ''}`}
                    onClick={() => setBatchDetailTab('students')}
                  >
                    <span>🎓</span> Danh Sách Sinh Viên Thuộc Đợt
                    <span className="utc-batch-subtab-badge">{students.length}</span>
                  </button>
                  <button
                    type="button"
                    className={`utc-batch-subtab-btn ${batchDetailTab === 'classes' ? 'active' : ''}`}
                    onClick={() => setBatchDetailTab('classes')}
                  >
                    <span>🏫</span> Danh Sách Lớp Học Phần
                    <span className="utc-batch-subtab-badge">{currBatch?.classes?.length || 0}</span>
                  </button>
                </div>

                {/* Subtab Content: Students */}
                {batchDetailTab === 'students' && (
                  <div>
                    <div className="utc-student-search-bar">
                      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                        <input
                          type="text"
                          placeholder="🔍 Tìm kiếm sinh viên theo MSSV, Họ tên, Lớp..."
                          value={studentSearch}
                          onChange={(e) => setStudentSearch(e.target.value)}
                          className="utc-search-input"
                        />

                        {/* Program Filter */}
                        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Hệ:</span>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterEduProgram === 'ALL' ? 'active' : ''}`}
                            onClick={() => setFilterEduProgram('ALL')}
                          >
                            Tất cả
                          </button>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterEduProgram === 'BACHELOR' ? 'active' : ''}`}
                            onClick={() => setFilterEduProgram('BACHELOR')}
                          >
                            🎓 Cử nhân
                          </button>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterEduProgram === 'ENGINEER' ? 'active' : ''}`}
                            onClick={() => setFilterEduProgram('ENGINEER')}
                          >
                            ⚙️ Kỹ sư
                          </button>
                        </div>

                        {/* Major Filter */}
                        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Ngành:</span>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterMajor === 'ALL' ? 'active' : ''}`}
                            onClick={() => setFilterMajor('ALL')}
                          >
                            Tất cả
                          </button>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterMajor === 'CNTT' ? 'active' : ''}`}
                            onClick={() => setFilterMajor('CNTT')}
                          >
                            💻 CNTT
                          </button>
                          <button
                            type="button"
                            className={`utc-filter-pill ${filterMajor === 'KHMT' ? 'active' : ''}`}
                            onClick={() => setFilterMajor('KHMT')}
                          >
                            🧠 KHMT
                          </button>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                          Hiển thị <strong>{filteredStudents.length}</strong> / {students.length} sinh viên
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setAddError(null);
                            setAddBatchId(selectedBatchId);
                            setShowAddStudentModal(true);
                          }}
                          className="utc-btn-sm-edit"
                          style={{ background: '#0284c7', color: '#fff', borderColor: '#0284c7', padding: '0.45rem 0.85rem' }}
                        >
                          ➕ Thêm Sinh Viên Mới
                        </button>
                      </div>
                    </div>

                    {studentsLoading ? (
                      <div className="utc-loading-box">Đang tải danh sách sinh viên...</div>
                    ) : filteredStudents.length === 0 ? (
                      <div className="utc-empty-classes">
                        {students.length === 0
                          ? 'Đợt này chưa có sinh viên nào. Bạn có thể nhấn nút "Thêm Sinh Viên" hoặc "Import Sinh Viên (Excel)" phía trên để nạp danh sách.'
                          : 'Không tìm thấy sinh viên nào khớp với bộ lọc tìm kiếm.'}
                      </div>
                    ) : (
                      <div className="utc-classes-table-wrapper">
                        <table className="utc-classes-table">
                          <thead>
                            <tr>
                              <th style={{ width: '45px' }}>STT</th>
                              <th>Mã Sinh Viên (MSSV)</th>
                              <th>Họ và Tên</th>
                              <th>Lớp Sinh Hoạt / HP</th>
                              <th>Hệ Đào Tạo</th>
                              <th>Ngành</th>
                              <th>Email</th>
                              <th>Số Điện Thoại</th>
                              <th>Trạng Thái</th>
                              <th style={{ textAlign: 'center', width: '130px' }}>Hành Động</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredStudents.map((st, idx) => {
                              const stdProf = st.student_profile || {};
                              const regNo = stdProf.registration_no || st.username;
                              const fullName = st.full_name || `${st.last_name || ''} ${st.first_name || ''}`.trim() || st.username;
                              const className = stdProf.course_class?.class_name || stdProf.department || stdProf.batch_no || '—';
                              const eduProg = stdProf.education_program || stdProf.degree_program || stdProf.course_class?.education_program || 'BACHELOR';
                              const major = stdProf.major || (stdProf.course_class?.program_type === 'KHMT' ? 'KHMT' : 'CNTT');
                              const phone = stdProf.phone_number || st.phone_number || '—';
                              const email = st.email || `${regNo}@sv.utc.edu.vn`;

                              return (
                                <tr key={st.id || idx}>
                                  <td className="text-center font-bold text-gray-500">{idx + 1}</td>
                                  <td className="font-bold text-blue-700">
                                    <span style={{ fontFamily: 'monospace', letterSpacing: '0.5px' }}>{regNo}</span>
                                  </td>
                                  <td className="font-semibold">{fullName}</td>
                                  <td>{className}</td>
                                  <td>
                                    <span className={`utc-badge-edu ${eduProg === 'ENGINEER' ? 'edu-ks' : 'edu-cn'}`}>
                                      {eduProg === 'ENGINEER' ? '⚙️ Kỹ sư' : '🎓 Cử nhân'}
                                    </span>
                                  </td>
                                  <td>
                                    <span style={{ fontSize: '0.78rem', fontWeight: 600, color: major === 'KHMT' ? '#7c3aed' : '#0369a1' }}>
                                      {major === 'KHMT' ? '🧠 KHMT' : '💻 CNTT'}
                                    </span>
                                  </td>
                                  <td style={{ fontSize: '0.85rem' }}>{email}</td>
                                  <td style={{ fontSize: '0.85rem' }}>{phone}</td>
                                  <td>
                                    <span className="utc-badge-active" style={{ background: st.is_active ? '#dcfce7' : '#fee2e2', color: st.is_active ? '#15803d' : '#b91c1c' }}>
                                      {st.is_active ? '🟢 Hoạt động' : '🔴 Khóa'}
                                    </span>
                                  </td>
                                  <td style={{ textAlign: 'center' }}>
                                    <div className="utc-action-btn-group">
                                      <button
                                        type="button"
                                        className="utc-action-btn edit"
                                        title="Chỉnh sửa thông tin sinh viên"
                                        onClick={() => handleOpenEditStudent(st)}
                                      >
                                        ✏️
                                      </button>
                                      <button
                                        type="button"
                                        className="utc-action-btn key"
                                        title="Đặt lại mật khẩu"
                                        onClick={() => {
                                          setResetStudent(st);
                                          setResetStrategy('MSSV');
                                          setResetCustomPassword('');
                                        }}
                                      >
                                        🔑
                                      </button>
                                      <button
                                        type="button"
                                        className="utc-action-btn delete"
                                        title="Xóa sinh viên khỏi đợt"
                                        onClick={() => handleDeleteStudent(st.id, fullName)}
                                      >
                                        🗑️
                                      </button>
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
                )}

                {/* Subtab Content: Classes */}
                {batchDetailTab === 'classes' && (
                  <div>
                    {(!currBatch || !currBatch.classes || currBatch.classes.length === 0) ? (
                      <div className="utc-empty-classes">
                        Đợt này chưa có dữ liệu lớp học phần. Hãy nhấn nút <strong>Import Sinh Viên (Excel)</strong> để hệ thống tự động nhận diện và tạo các lớp học phần từ từng Sheet/Mã học phần.
                      </div>
                    ) : (
                      <div className="utc-classes-table-wrapper">
                        <table className="utc-classes-table">
                          <thead>
                            <tr>
                              <th>Mã Lớp HP</th>
                              <th>Tên Lớp Học Phần</th>
                              <th>Chương trình</th>
                              <th>Hệ đào tạo</th>
                              <th>Nhóm</th>
                              <th>Số Sinh Viên</th>
                            </tr>
                          </thead>
                          <tbody>
                            {currBatch.classes.map((cls) => (
                              <tr key={cls.id}>
                                <td className="font-bold">{cls.class_code}</td>
                                <td>{cls.class_name}</td>
                                <td>
                                  <span className="utc-badge-prog">{cls.program_type}</span>
                                </td>
                                <td>
                                  <span className={`utc-badge-edu ${cls.education_program === 'ENGINEER' ? 'edu-ks' : 'edu-cn'}`}>
                                    {cls.education_program === 'ENGINEER' ? '⚙️ Kỹ sư' : '🎓 Cử nhân'}
                                  </span>
                                </td>
                                <td>{cls.class_group || '—'}</td>
                                <td className="text-center font-bold text-blue-600">{cls.student_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ========================================================= */}
        {/* TAB 2: DEPARTMENTS */}
        {/* ========================================================= */}
        {activeTab === 'departments' && (
          <div className="utc-dept-section">
            <div className="utc-batches-header-bar">
              <div className="utc-batches-header-info">
                <h3>Thiết Lập Quan Hệ Khoa – Bộ Môn – Giảng Viên (Bước 6)</h3>
                <p>Quản lý các bộ môn chuyên môn trực thuộc Khoa CNTT phục vụ phân chia đề tài & hội đồng</p>
              </div>
              <button onClick={() => setShowDeptModal(true)} className="utc-btn-primary">
                <span>➕</span> Thêm Bộ Môn Mới
              </button>
            </div>

            <div className="utc-dept-grid">
              {departments.length === 0 ? (
                <div className="utc-empty-box">Chưa có bộ môn nào. Hãy thêm bộ môn mới.</div>
              ) : (
                departments.map((dept) => (
                  <div key={dept.id} className="utc-dept-card">
                    <div className="utc-dept-head">
                      <span className="utc-dept-code">{dept.code}</span>
                      <span className="utc-dept-count">👨‍🏫 {dept.supervisor_count || 0} Giảng viên</span>
                    </div>
                    <h4>{dept.name}</h4>
                    <p>{dept.description || 'Chuyên ngành kỹ thuật thuộc Khoa CNTT UTC.'}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 3: SUPERVISORS */}
        {/* ========================================================= */}
        {activeTab === 'supervisors' && (
          <div className="utc-sup-section">
            <div className="utc-batches-header-bar">
              <div className="utc-batches-header-info">
                <h3>Cập Nhật Hướng Nghiên Cứu, Học Vị & Hệ Số Capacity GV (Bước 7)</h3>
                <p>Khoa thiết lập học vị (GS/PGS/TS/ThS), hệ số định mức và bộ môn chuyên môn cho từng giảng viên</p>
              </div>
            </div>

            <div className="utc-classes-table-wrapper">
              <table className="utc-classes-table">
                <thead>
                  <tr>
                    <th>Mã GV</th>
                    <th>Họ và Tên Giảng Viên</th>
                    <th>Học Vị / Chức Danh</th>
                    <th>Bộ Môn</th>
                    <th>Hệ Số Capacity</th>
                    <th>Hướng Nghiên Cứu</th>
                    <th>Hành Động</th>
                  </tr>
                </thead>
                <tbody>
                  {supervisors.map((s) => (
                    <tr key={s.id}>
                      <td className="font-bold">{s.supervisor_id || s.username}</td>
                      <td>{s.user_full_name}</td>
                      <td>
                        <span className={`utc-title-badge title-${(s.academic_title || '').toLowerCase()}`}>
                          {s.academic_title || 'ThS'}
                        </span>
                      </td>
                      <td>{s.department_name || 'Khoa CNTT'}</td>
                      <td className="text-center font-bold text-emerald-600">x{s.academic_rank_multiplier || 1.0}</td>
                      <td style={{ maxWidth: '250px' }}>{s.research_interest || 'Chưa cập nhật'}</td>
                      <td>
                        <button onClick={() => handleOpenEditSupervisor(s)} className="utc-btn-sm-edit">
                          ✏️ Chỉnh sửa
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 1: CREATE BATCH */}
        {/* ========================================================= */}
        {showCreateModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>➕ Khởi Tạo Đợt Đồ Án Tốt Nghiệp Mới</h4>
                <button onClick={() => setShowCreateModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleCreateBatch}>
                <div className="utc-modal-body">
                  {createBatchError && (
                    <div style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #f87171', padding: '0.65rem 0.9rem', borderRadius: 8, marginBottom: '1rem', fontSize: '0.88rem' }}>
                      ❌ {createBatchError}
                    </div>
                  )}

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">
                        Mã Đợt (Batch Code) <span className="utc-label-required">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="VD: 2026-DOT1-CNTT"
                        value={newBatchCode}
                        onChange={(e) => setNewBatchCode(e.target.value.toUpperCase())}
                        className="utc-input"
                        autoFocus
                      />
                      <div style={{ marginTop: '0.35rem' }}>
                        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Gợi ý nhanh: </span>
                        <span className="utc-quick-tag" onClick={() => generateBatchCodeSuggestion('DOT1')}>
                          Đợt 1 HK1
                        </span>
                        <span className="utc-quick-tag" onClick={() => generateBatchCodeSuggestion('DOT2')}>
                          Đợt 2 HK2
                        </span>
                      </div>
                    </div>

                    <div>
                      <label className="utc-label">
                        Tên Đợt Đồ Án <span className="utc-label-required">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="VD: Đồ án tốt nghiệp Học kỳ 2 Năm 2025-2026"
                        value={newBatchName}
                        onChange={(e) => setNewBatchName(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  <div style={{ marginBottom: '1.25rem' }}>
                    <label className="utc-label">
                      Chương Trình Đào Tạo Áp Dụng <span className="utc-label-required">*</span>
                    </label>
                    <div className="utc-radio-group">
                      <label className={`utc-radio-card ${newProgramType === 'BACHELOR' ? 'active' : ''}`}>
                        <input
                          type="radio"
                          name="prog"
                          value="BACHELOR"
                          checked={newProgramType === 'BACHELOR'}
                          onChange={() => setNewProgramType('BACHELOR')}
                        />
                        <div>
                          <strong>🎓 Cử Nhân (Bachelor)</strong>
                          <p>Quy chuẩn đồ án cử nhân, không bắt buộc GVHD phải có học vị Tiến sĩ (TS).</p>
                        </div>
                      </label>

                      <label className={`utc-radio-card ${newProgramType === 'ENGINEER' ? 'active' : ''}`}>
                        <input
                          type="radio"
                          name="prog"
                          value="ENGINEER"
                          checked={newProgramType === 'ENGINEER'}
                          onChange={() => setNewProgramType('ENGINEER')}
                        />
                        <div>
                          <strong>⚙️ Kỹ Sư (Engineer)</strong>
                          <p>Ràng buộc cứng theo quy chế UTC: GVHD bắt buộc phải đạt học vị Tiến sĩ (TS) trở lên.</p>
                        </div>
                      </label>

                      <label className={`utc-radio-card ${newProgramType === 'BOTH' ? 'active' : ''}`}>
                        <input
                          type="radio"
                          name="prog"
                          value="BOTH"
                          checked={newProgramType === 'BOTH'}
                          onChange={() => setNewProgramType('BOTH')}
                        />
                        <div>
                          <strong>🔄 Cả Hai (Hỗn hợp Cử nhân & Kỹ sư)</strong>
                          <p>Hệ thống tự động kiểm tra ràng buộc học vị theo từng lớp học phần của sinh viên.</p>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">Ngày Bắt Đầu Dự Kiến:</label>
                      <input
                        type="date"
                        value={newStartDate}
                        onChange={(e) => setNewStartDate(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                    <div>
                      <label className="utc-label">Ngày Kết Thúc Dự Kiến:</label>
                      <input
                        type="date"
                        value={newEndDate}
                        onChange={(e) => setNewEndDate(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <input
                      type="checkbox"
                      id="batchIsActive"
                      checked={newIsActive}
                      onChange={(e) => setNewIsActive(e.target.checked)}
                      style={{ width: 18, height: 18, cursor: 'pointer' }}
                    />
                    <label htmlFor="batchIsActive" style={{ cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                      Mở đợt làm đồ án ngay (Trạng thái đang hoạt động)
                    </label>
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowCreateModal(false)} className="utc-btn-cancel" disabled={createBatchLoading}>
                    Hủy
                  </button>
                  <button type="submit" className="utc-btn-primary" disabled={createBatchLoading}>
                    {createBatchLoading ? 'Đang khởi tạo...' : 'Khởi Tạo Đợt ĐATN'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 1.5: EDIT BATCH */}
        {/* ========================================================= */}
        {editingBatch && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>✏️ Chỉnh Sửa Đợt Đồ Án: {editingBatch.batch_code}</h4>
                <button onClick={() => setEditingBatch(null)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleSaveEditBatch}>
                <div className="utc-modal-body">
                  <div style={{ marginBottom: '1rem' }}>
                    <label className="utc-label">Tên Đợt Đồ Án:</label>
                    <input
                      type="text"
                      required
                      value={editBatchName}
                      onChange={(e) => setEditBatchName(e.target.value)}
                      className="utc-input"
                    />
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label className="utc-label">Chương Trình Đào Tạo:</label>
                    <select
                      className="utc-input"
                      value={editBatchProg}
                      onChange={(e) => setEditBatchProg(e.target.value as any)}
                    >
                      <option value="BACHELOR">🎓 Cử Nhân (Bachelor)</option>
                      <option value="ENGINEER">⚙️ Kỹ Sư (Engineer - bắt buộc GVHD học vị TS)</option>
                      <option value="BOTH">🔄 Cả Hai (Hỗn hợp)</option>
                    </select>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">Ngày Bắt Đầu:</label>
                      <input
                        type="date"
                        value={editBatchStart}
                        onChange={(e) => setEditBatchStart(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                    <div>
                      <label className="utc-label">Ngày Kết Thúc:</label>
                      <input
                        type="date"
                        value={editBatchEnd}
                        onChange={(e) => setEditBatchEnd(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      id="editBatchActive"
                      checked={editBatchIsActive}
                      onChange={(e) => setEditBatchIsActive(e.target.checked)}
                      style={{ width: 18, height: 18 }}
                    />
                    <label htmlFor="editBatchActive" style={{ cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                      Đang mở tiếp nhận sinh viên & phân công GVHD
                    </label>
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setEditingBatch(null)} className="utc-btn-cancel" disabled={editBatchLoading}>
                    Hủy
                  </button>
                  <button type="submit" className="utc-btn-primary" disabled={editBatchLoading}>
                    {editBatchLoading ? 'Đang lưu...' : 'Lưu Thay Đổi'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 2: IMPORT EXCEL */}
        {/* ========================================================= */}
        {showImportModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>📊 Import Danh Sách Sinh Viên Theo File Excel UTC</h4>
                <button onClick={() => setShowImportModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleImportExcel}>
                <div className="utc-modal-body">
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">
                        Chọn Đợt Đồ Án Áp Dụng <span className="utc-label-required">*</span>
                      </label>
                      <select
                        className="utc-input"
                        value={importBatchId || ''}
                        onChange={(e) => setImportBatchId(Number(e.target.value))}
                        required
                      >
                        <option value="">-- Chọn đợt đồ án --</option>
                        {batches.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.batch_code} - {b.batch_name} ({b.program_type === 'ENGINEER' ? 'Kỹ sư' : b.program_type === 'BACHELOR' ? 'Cử nhân' : 'Cả hai'})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="utc-label">Ngành Đào Tạo Mặc Định:</label>
                      <select
                        className="utc-input"
                        value={importDefaultMajor}
                        onChange={(e) => setImportDefaultMajor(e.target.value as any)}
                      >
                        <option value="CNTT">💻 Công nghệ thông tin (CNTT)</option>
                        <option value="KHMT">🧠 Khoa học máy tính (KHMT)</option>
                      </select>
                    </div>
                  </div>

                  {/* Password Strategy Options */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
                    <div>
                      <label className="utc-label">Chiến Lược Khởi Tạo Mật Khẩu:</label>
                      <select
                        className="utc-input"
                        value={importPasswordStrategy}
                        onChange={(e) => setImportPasswordStrategy(e.target.value as any)}
                      >
                        <option value="MSSV">Theo Mã Sinh Viên (Khuyên dùng - SV dễ nhớ)</option>
                        <option value="FIXED">Mật khẩu cố định chung</option>
                        <option value="RANDOM">Mật khẩu ngẫu nhiên an toàn</option>
                      </select>
                    </div>

                    {importPasswordStrategy === 'FIXED' && (
                      <div>
                        <label className="utc-label">Mật khẩu cố định:</label>
                        <input
                          type="text"
                          value={importFixedPassword}
                          onChange={(e) => setImportFixedPassword(e.target.value)}
                          className="utc-input"
                          placeholder="VD: Sv@123456"
                        />
                      </div>
                    )}
                  </div>

                  {/* Template Download Prompt */}
                  <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 10, padding: '0.85rem 1rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#0369a1' }}>
                        📥 Cần file mẫu đúng chuẩn định dạng đào tạo UTC?
                      </div>
                      <div style={{ fontSize: '0.78rem', color: '#0284c7', marginTop: '0.15rem' }}>
                        Bao gồm các cột: STT, Mã SV, Họ và tên, Lớp học phần, Ngành, Email, SĐT.
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleDownloadTemplate}
                      className="utc-btn-outline"
                      style={{ fontSize: '0.82rem', padding: '0.45rem 0.9rem', whiteSpace: 'nowrap' }}
                    >
                      Tải File Mẫu (.xlsx)
                    </button>
                  </div>

                  {/* Drag and Drop Zone */}
                  <div>
                    <label className="utc-label">
                      Chọn File Excel Dữ Liệu (.xlsx, .xls) <span className="utc-label-required">*</span>
                    </label>

                    <input
                      type="file"
                      ref={fileInputRef}
                      accept=".xlsx, .xls"
                      style={{ display: 'none' }}
                      onChange={(e) => setImportFile(e.target.files ? e.target.files[0] : null)}
                    />

                    {!importFile ? (
                      <div
                        className={`utc-dropzone ${isDragging ? 'active' : ''}`}
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setIsDragging(true);
                        }}
                        onDragLeave={() => setIsDragging(false)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setIsDragging(false);
                          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                            setImportFile(e.dataTransfer.files[0]);
                          }
                        }}
                      >
                        <span className="utc-dropzone-icon">📁</span>
                        <div className="utc-dropzone-title">Kéo & thả file Excel vào đây, hoặc nhấn để duyệt file</div>
                        <div className="utc-dropzone-desc">Hỗ trợ định dạng .xlsx, .xls xuất từ Cổng đào tạo UTC</div>
                      </div>
                    ) : (
                      <div className="utc-file-preview-card">
                        <div className="utc-file-info">
                          <span className="utc-file-icon">📊</span>
                          <div>
                            <div className="utc-file-name">{importFile.name}</div>
                            <div className="utc-file-size">{(importFile.size / 1024).toFixed(1)} KB</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="utc-btn-close"
                          onClick={() => setImportFile(null)}
                          title="Hủy file đã chọn"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Result Box */}
                  {importResult && (
                    <div style={{ background: importResult.success ? '#ecfdf5' : '#fef2f2', border: `1.5px solid ${importResult.success ? '#a7f3d0' : '#fecaca'}`, padding: '1rem', borderRadius: 10, marginTop: '1.25rem' }}>
                      <strong style={{ color: importResult.success ? '#065f46' : '#991b1b', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.95rem' }}>
                        {importResult.success ? '✅ Kết quả import Excel thành công:' : '❌ Kết quả import thất bại:'}
                      </strong>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginTop: '0.75rem', textAlign: 'center' }}>
                        <div style={{ background: '#fff', padding: '0.5rem', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Tổng số dòng</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: 800 }}>{importResult.total || 0}</div>
                        </div>
                        <div style={{ background: '#fff', padding: '0.5rem', borderRadius: 6, border: '1px solid #a7f3d0' }}>
                          <div style={{ fontSize: '0.72rem', color: '#059669' }}>Tạo mới</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#059669' }}>{importResult.created || 0}</div>
                        </div>
                        <div style={{ background: '#fff', padding: '0.5rem', borderRadius: 6, border: '1px solid #bfdbfe' }}>
                          <div style={{ fontSize: '0.72rem', color: '#2563eb' }}>Cập nhật</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#2563eb' }}>{importResult.updated || 0}</div>
                        </div>
                        <div style={{ background: '#fff', padding: '0.5rem', borderRadius: 6, border: '1px solid #fde68a' }}>
                          <div style={{ fontSize: '0.72rem', color: '#d97706' }}>Bỏ qua / Lỗi</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#d97706' }}>{importResult.skipped || 0}</div>
                        </div>
                      </div>

                      {/* Display Row Errors if any */}
                      {importResult.errors && importResult.errors.length > 0 && (
                        <div className="utc-error-table-container">
                          <table className="utc-error-table">
                            <thead>
                              <tr>
                                <th style={{ width: '40px' }}>#</th>
                                <th>Chi tiết lỗi các dòng bị bỏ qua</th>
                              </tr>
                            </thead>
                            <tbody>
                              {importResult.errors.map((errItem: any, eIdx: number) => (
                                <tr key={eIdx}>
                                  <td>{eIdx + 1}</td>
                                  <td>{typeof errItem === 'string' ? errItem : JSON.stringify(errItem)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      <div style={{ marginTop: '0.85rem', display: 'flex', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          className="utc-btn-primary"
                          style={{ fontSize: '0.85rem', padding: '0.45rem 1rem' }}
                          onClick={() => {
                            setShowImportModal(false);
                            setBatchDetailTab('students');
                            if (importBatchId) setSelectedBatchId(Number(importBatchId));
                          }}
                        >
                          👥 Xem Danh Sách Sinh Viên Đợt Ngay
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowImportModal(false)} className="utc-btn-cancel" disabled={importing}>
                    Đóng
                  </button>
                  <button type="submit" disabled={importing || !importFile} className="utc-btn-emerald">
                    {importing ? 'Đang phân tích & import...' : 'Bắt Đầu Import'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 3: MANUAL ADD STUDENT FORM */}
        {/* ========================================================= */}
        {showAddStudentModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>👤➕ Thêm Sinh Viên Thủ Công Vào Đợt ĐATN</h4>
                <button
                  type="button"
                  onClick={() => setShowAddStudentModal(false)}
                  className="utc-btn-close"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleAddStudentSubmit}>
                <div className="utc-modal-body">
                  {addError && (
                    <div style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #f87171', padding: '0.65rem 0.9rem', borderRadius: 8, marginBottom: '1rem', fontSize: '0.88rem' }}>
                      ❌ {addError}
                    </div>
                  )}

                  {/* Batch Selection */}
                  <div style={{ marginBottom: '1rem' }}>
                    <label className="utc-label">
                      Đợt Đồ Án Tốt Nghiệp Áp Dụng <span className="utc-label-required">*</span>
                    </label>
                    <select
                      className="utc-input"
                      value={addBatchId || ''}
                      onChange={(e) => {
                        const bid = Number(e.target.value);
                        setAddBatchId(bid);
                        const b = batches.find((x) => x.id === bid);
                        if (b && b.program_type !== 'BOTH') {
                          setAddEduProgram(b.program_type);
                        }
                      }}
                      required
                    >
                      <option value="">-- Chọn đợt đồ án --</option>
                      {batches.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.batch_code} - {b.batch_name} ({b.program_type === 'ENGINEER' ? 'Kỹ sư' : b.program_type === 'BACHELOR' ? 'Cử nhân' : 'Cả hai'})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Required Fields: MSSV & Họ và Tên */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '0.85rem', marginBottom: '0.9rem' }}>
                    <div>
                      <label className="utc-label">
                        Mã Sinh Viên (MSSV) <span className="utc-label-required">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="VD: 201200021"
                        value={addMssv}
                        onChange={(e) => {
                          const val = e.target.value.trim();
                          setAddMssv(val);
                          if (!addEmail || addEmail.endsWith('@sv.utc.edu.vn')) {
                            setAddEmail(val ? `${val.toLowerCase()}@sv.utc.edu.vn` : '');
                          }
                        }}
                        className="utc-input"
                        autoFocus
                      />
                    </div>

                    <div>
                      <label className="utc-label">
                        Họ và Tên Sinh Viên <span className="utc-label-required">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="VD: Nguyễn Hoàng Minh"
                        value={addFullName}
                        onChange={(e) => setAddFullName(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  {/* Program & Major Selection */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.9rem' }}>
                    <div>
                      <label className="utc-label">
                        Hệ đào tạo <span className="utc-label-required">*</span>
                      </label>
                      <select
                        className="utc-input"
                        value={addEduProgram}
                        onChange={(e) => setAddEduProgram(e.target.value as 'BACHELOR' | 'ENGINEER')}
                      >
                        <option value="BACHELOR">🎓 Cử nhân (Bachelor)</option>
                        <option value="ENGINEER">⚙️ Kỹ sư (Engineer - Yêu cầu GVHD học vị TS)</option>
                      </select>
                    </div>

                    <div>
                      <label className="utc-label">
                        Ngành đào tạo
                      </label>
                      <select
                        className="utc-input"
                        value={addMajor}
                        onChange={(e) => setAddMajor(e.target.value as 'CNTT' | 'KHMT')}
                      >
                        <option value="CNTT">💻 Công nghệ thông tin</option>
                        <option value="KHMT">🧠 Khoa học máy tính</option>
                      </select>
                    </div>
                  </div>

                  {/* Class Selection */}
                  <div style={{ marginBottom: '0.9rem' }}>
                    <label className="utc-label">
                      Lớp sinh hoạt / Lớp học phần
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: currBatch?.classes?.length ? '1.2fr 1fr' : '1fr', gap: '0.5rem' }}>
                      {currBatch?.classes && currBatch.classes.length > 0 && (
                        <select
                          className="utc-input"
                          value={addClassId}
                          onChange={(e) => {
                            const cid = e.target.value ? Number(e.target.value) : '';
                            setAddClassId(cid);
                            const found = currBatch.classes.find((c) => c.id === cid);
                            if (found) {
                              setAddClassName(found.class_name);
                              setAddEduProgram(found.education_program as any || addEduProgram);
                            }
                          }}
                        >
                          <option value="">-- Chọn lớp có sẵn trong đợt --</option>
                          {currBatch.classes.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.class_code} - {c.class_name} ({c.education_program})
                            </option>
                          ))}
                        </select>
                      )}
                      <input
                        type="text"
                        placeholder="Hoặc nhập tên lớp (vd: CNTT1-K62)"
                        value={addClassName}
                        onChange={(e) => setAddClassName(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  {/* Email & Phone */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '0.85rem', marginBottom: '0.9rem' }}>
                    <div>
                      <label className="utc-label">Email sinh viên</label>
                      <input
                        type="email"
                        placeholder="vd: 201200021@sv.utc.edu.vn"
                        value={addEmail}
                        onChange={(e) => setAddEmail(e.target.value)}
                        className="utc-input"
                      />
                    </div>

                    <div>
                      <label className="utc-label">Số điện thoại</label>
                      <input
                        type="text"
                        placeholder="vd: 0912345678"
                        value={addPhone}
                        onChange={(e) => setAddPhone(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  {/* Password Strategy */}
                  <div style={{ display: 'grid', gridTemplateColumns: addPasswordStrategy === 'CUSTOM' ? '1fr 1fr' : '1fr', gap: '0.85rem', marginBottom: '0.5rem' }}>
                    <div>
                      <label className="utc-label">Thiết lập mật khẩu đăng nhập:</label>
                      <select
                        className="utc-input"
                        value={addPasswordStrategy}
                        onChange={(e) => setAddPasswordStrategy(e.target.value as any)}
                      >
                        <option value="MSSV">Mặc định theo MSSV (Khuyên dùng)</option>
                        <option value="FIXED">Mặc định chung: Sv@123456</option>
                        <option value="CUSTOM">Tùy chỉnh mật khẩu</option>
                      </select>
                    </div>

                    {addPasswordStrategy === 'CUSTOM' && (
                      <div>
                        <label className="utc-label">Nhập mật khẩu:</label>
                        <input
                          type="text"
                          required
                          placeholder="Mật khẩu tùy chọn..."
                          value={addCustomPassword}
                          onChange={(e) => setAddCustomPassword(e.target.value)}
                          className="utc-input"
                        />
                      </div>
                    )}
                  </div>

                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: 8, fontSize: '0.8rem', color: '#64748b', marginTop: '0.75rem' }}>
                    💡 <strong>Ghi chú:</strong> Sinh viên có thể đăng nhập vào Cổng sinh viên (Port 3000) bằng MSSV và mật khẩu này để khảo sát nguyện vọng và làm đồ án.
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button
                    type="button"
                    onClick={() => setShowAddStudentModal(false)}
                    className="utc-btn-cancel"
                    disabled={addLoading}
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    className="utc-btn-primary"
                    disabled={addLoading}
                  >
                    {addLoading ? 'Đang lưu...' : 'Lưu Sinh Viên'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 4: EDIT STUDENT MODAL */}
        {/* ========================================================= */}
        {editStudent && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>✏️ Chỉnh Sửa Sinh Viên: {editStudent.username}</h4>
                <button onClick={() => setEditStudent(null)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleSaveEditStudent}>
                <div className="utc-modal-body">
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">Mã Sinh Viên (Không thể đổi):</label>
                      <input
                        type="text"
                        disabled
                        value={editStudent.username}
                        className="utc-input"
                      />
                    </div>
                    <div>
                      <label className="utc-label">Họ và Tên:</label>
                      <input
                        type="text"
                        required
                        value={editFullName}
                        onChange={(e) => setEditFullName(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">Hệ đào tạo:</label>
                      <select
                        className="utc-input"
                        value={editEduProgram}
                        onChange={(e) => setEditEduProgram(e.target.value as any)}
                      >
                        <option value="BACHELOR">🎓 Cử nhân (Bachelor)</option>
                        <option value="ENGINEER">⚙️ Kỹ sư (Engineer)</option>
                      </select>
                    </div>

                    <div>
                      <label className="utc-label">Lớp sinh hoạt / HP:</label>
                      <input
                        type="text"
                        value={editClassName}
                        onChange={(e) => setEditClassName(e.target.value)}
                        className="utc-input"
                        placeholder="VD: CNTT2-K62"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                      <label className="utc-label">Email:</label>
                      <input
                        type="email"
                        value={editEmail}
                        onChange={(e) => setEditEmail(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                    <div>
                      <label className="utc-label">Số điện thoại:</label>
                      <input
                        type="text"
                        value={editPhone}
                        onChange={(e) => setEditPhone(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      id="editStudentActive"
                      checked={editIsActive}
                      onChange={(e) => setEditIsActive(e.target.checked)}
                      style={{ width: 18, height: 18 }}
                    />
                    <label htmlFor="editStudentActive" style={{ cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                      Tài khoản sinh viên đang hoạt động (Được phép đăng nhập)
                    </label>
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setEditStudent(null)} className="utc-btn-cancel" disabled={editLoading}>
                    Hủy
                  </button>
                  <button type="submit" className="utc-btn-primary" disabled={editLoading}>
                    {editLoading ? 'Đang lưu...' : 'Lưu Cập Nhật'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 5: RESET PASSWORD MODAL */}
        {/* ========================================================= */}
        {resetStudent && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card medium">
              <div className="utc-modal-head">
                <h4>🔑 Đặt Lại Mật Khẩu: {resetStudent.username}</h4>
                <button onClick={() => setResetStudent(null)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleResetPassword}>
                <div className="utc-modal-body">
                  <p style={{ fontSize: '0.88rem', color: '#64748b', marginBottom: '1rem' }}>
                    Đặt lại mật khẩu cho sinh viên <strong>{resetStudent.full_name || resetStudent.username}</strong> ({resetStudent.username}).
                  </p>

                  <div style={{ marginBottom: '1rem' }}>
                    <label className="utc-label">Chọn phương thức đặt lại:</label>
                    <select
                      className="utc-input"
                      value={resetStrategy}
                      onChange={(e) => setResetStrategy(e.target.value as any)}
                    >
                      <option value="MSSV">Đặt lại về Mã Sinh Viên ({resetStudent.username})</option>
                      <option value="FIXED">Đặt lại về mật khẩu mặc định: Sv@123456</option>
                      <option value="CUSTOM">Đặt mật khẩu tùy chọn mới</option>
                    </select>
                  </div>

                  {resetStrategy === 'CUSTOM' && (
                    <div style={{ marginBottom: '1rem' }}>
                      <label className="utc-label">Mật khẩu mới:</label>
                      <input
                        type="text"
                        required
                        placeholder="Nhập mật khẩu mới..."
                        value={resetCustomPassword}
                        onChange={(e) => setResetCustomPassword(e.target.value)}
                        className="utc-input"
                      />
                    </div>
                  )}
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setResetStudent(null)} className="utc-btn-cancel" disabled={resetLoading}>
                    Hủy
                  </button>
                  <button type="submit" className="utc-btn-primary" disabled={resetLoading}>
                    {resetLoading ? 'Đang xử lý...' : 'Xác Nhận Đặt Lại'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 6: CREATE DEPARTMENT */}
        {/* ========================================================= */}
        {showDeptModal && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card medium">
              <div className="utc-modal-head">
                <h4>🏢 Thêm Bộ Môn Chuyên Môn Trực Thuộc Khoa CNTT</h4>
                <button onClick={() => setShowDeptModal(false)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleCreateDepartment}>
                <div className="utc-modal-body">
                  <div className="utc-form-group">
                    <label className="utc-label">Mã Bộ Môn:</label>
                    <input
                      type="text"
                      required
                      placeholder="VD: CNPM, MHTTT, KHMT, HTTT"
                      value={deptCode}
                      onChange={(e) => setDeptCode(e.target.value)}
                      className="utc-input"
                    />
                  </div>
                  <div className="utc-form-group">
                    <label className="utc-label">Tên Bộ Môn:</label>
                    <input
                      type="text"
                      required
                      placeholder="VD: Bộ môn Công nghệ Phần mềm"
                      value={deptName}
                      onChange={(e) => setDeptName(e.target.value)}
                      className="utc-input"
                    />
                  </div>
                  <div className="utc-form-group">
                    <label className="utc-label">Mô tả chuyên môn:</label>
                    <textarea
                      rows={3}
                      placeholder="Mô tả các hướng nghiên cứu trọng tâm..."
                      value={deptDesc}
                      onChange={(e) => setDeptDesc(e.target.value)}
                      className="utc-input"
                    />
                  </div>
                </div>
                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setShowDeptModal(false)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" className="utc-btn-primary">Lưu Bộ Môn</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL 7: EDIT SUPERVISOR */}
        {/* ========================================================= */}
        {editingSupervisor && (
          <div className="utc-modal-backdrop">
            <div className="utc-modal-card wide">
              <div className="utc-modal-head">
                <h4>✏️ Cập Nhật Hồ Sơ Giảng Viên: {editingSupervisor.user_full_name}</h4>
                <button onClick={() => setEditingSupervisor(null)} className="utc-btn-close">✕</button>
              </div>
              <form onSubmit={handleSaveSupervisor}>
                <div className="utc-modal-body">
                  <div className="utc-form-group">
                    <label className="utc-label">Học vị / Học hàm:</label>
                    <select
                      className="utc-input"
                      value={supTitle}
                      onChange={(e) => {
                        const t = e.target.value;
                        setSupTitle(t);
                        if (t === 'GS.TS') setSupMultiplier(2.0);
                        else if (t === 'PGS.TS') setSupMultiplier(1.5);
                        else if (t === 'TS') setSupMultiplier(1.2);
                        else setSupMultiplier(1.0);
                      }}
                    >
                      <option value="ThS">ThS - Thạc sĩ (Hệ số x1.0)</option>
                      <option value="TS">TS - Tiến sĩ (Hệ số x1.2 - Đủ chuẩn Kỹ sư)</option>
                      <option value="PGS.TS">PGS.TS - Phó Giáo sư (Hệ số x1.5 - Đủ chuẩn Kỹ sư)</option>
                      <option value="GS.TS">GS.TS - Giáo sư (Hệ số x2.0 - Đủ chuẩn Kỹ sư)</option>
                    </select>
                  </div>

                  <div className="utc-form-group">
                    <label className="utc-label">Bộ Môn Chuyên Môn:</label>
                    <select
                      className="utc-input"
                      value={supDeptId}
                      onChange={(e) => setSupDeptId(e.target.value ? Number(e.target.value) : '')}
                    >
                      <option value="">-- Chưa gán bộ môn --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                      ))}
                    </select>
                  </div>

                  <div className="utc-form-group">
                    <label className="utc-label">Hệ số Capacity (Tự động nhân với chỉ tiêu cơ sở):</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.5"
                      max="5.0"
                      value={supMultiplier}
                      onChange={(e) => setSupMultiplier(parseFloat(e.target.value) || 1.0)}
                      className="utc-input"
                    />
                    <small style={{ color: '#64748b' }}>
                      Chỉ tiêu tối đa của GV = Base Quota * Hệ số ({supMultiplier}).
                    </small>
                  </div>

                  <div className="utc-form-group">
                    <label className="utc-label">Hướng nghiên cứu chuyên sâu:</label>
                    <textarea
                      rows={3}
                      value={supInterest}
                      onChange={(e) => setSupInterest(e.target.value)}
                      placeholder="VD: Trí tuệ nhân tạo, Big Data, Phát triển phần mềm doanh nghiệp..."
                      className="utc-input"
                    />
                  </div>
                </div>

                <div className="utc-modal-foot">
                  <button type="button" onClick={() => setEditingSupervisor(null)} className="utc-btn-cancel">Hủy</button>
                  <button type="submit" className="utc-btn-primary">Lưu Thay Đổi</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TOAST NOTIFICATION POPUP */}
        {/* ========================================================= */}
        {toast && (
          <div className="utc-toast-container">
            <div className={`utc-toast-item ${toast.type}`}>
              <span>{toast.message}</span>
              <button
                type="button"
                onClick={() => setToast(null)}
                className="utc-toast-close"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};

export default BatchesPage;
