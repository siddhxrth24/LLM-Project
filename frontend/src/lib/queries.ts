import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from './api';

// ============================================================================
// TypeScript Types
// ============================================================================

export interface UnitSummary {
  id: number;
  unit_number: number;
  name: string;
  document_count: number;
}

export interface Course {
  id: number;
  name: string;
  syllabus_text?: string | null;
  exam_date?: string | null;
  study_days_per_week: number;
  daily_study_hours: number;
  difficulty_preference: 'easy' | 'balanced' | 'challenging';
  created_at: string;
  updated_at: string;
  unit_count: number;
  document_count: number;
  topic_count: number;
  units: UnitSummary[];
}

export interface CourseCreateInput {
  name: string;
  syllabus_text?: string | null;
  exam_date?: string | null;
  study_days_per_week?: number;
  daily_study_hours?: number;
  difficulty_preference?: 'easy' | 'balanced' | 'challenging';
}

export interface CourseUpdateInput {
  name?: string;
  syllabus_text?: string | null;
  exam_date?: string | null;
  study_days_per_week?: number;
  daily_study_hours?: number;
  difficulty_preference?: 'easy' | 'balanced' | 'challenging';
}

export interface CourseListResponse {
  courses: Course[];
  total: number;
}

export interface ChunkItem {
  id: number;
  document_id: number;
  chunk_index: number;
  page_number?: number | null;
  slide_number?: number | null;
  content: string;
  source_filename: string;
}

export interface DocumentItem {
  id: number;
  unit_id: number;
  course_id: number;
  filename: string;
  original_filename: string;
  file_type: 'pdf' | 'pptx' | string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string | null;
  page_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  chunks?: ChunkItem[] | null;
}

export interface DocumentUploadResponse {
  message: string;
  documents: DocumentItem[];
}

export interface DocumentStatusResponse {
  id: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string | null;
  page_count: number;
  chunk_count: number;
}

export interface SyllabusTopic {
  id: number;
  course_id: number;
  unit_number: number;
  topic_name: string;
  subtopics: string[];
  order_index: number;
  prerequisites: (string | number)[];
  estimated_hours: number;
  difficulty: number;
  coverage_status: 'covered' | 'partially_covered' | 'not_found' | 'needs_review';
  coverage_confidence: number;
  coverage_evidence: Record<string, unknown>;
  user_override_status?: 'covered' | 'partially_covered' | 'not_found' | 'needs_review' | null;
  effective_status: 'covered' | 'partially_covered' | 'not_found' | 'needs_review';
  created_at: string;
  updated_at: string;
}

export interface SyllabusTopicUpdateInput {
  topic_name?: string;
  subtopics?: string[];
  order_index?: number;
  prerequisites?: (string | number)[];
  estimated_hours?: number;
  difficulty?: number;
  coverage_status?: 'covered' | 'partially_covered' | 'not_found' | 'needs_review';
  user_override_status?: 'covered' | 'partially_covered' | 'not_found' | 'needs_review' | null;
}

export interface CoverageData {
  course_id: number;
  total_topics: number;
  covered_count: number;
  partially_covered_count: number;
  not_found_count: number;
  needs_review_count: number;
  coverage_percentage: number;
  topics: SyllabusTopic[];
}

export interface StudySession {
  id: number;
  course_id: number;
  topic_id?: number | null;
  topic_name?: string | null;
  unit_number?: number | null;
  scheduled_date: string;
  duration_hours: number;
  session_type: 'study' | 'revision';
  is_completed: boolean;
  completed_at?: string | null;
  notes?: string | null;
  order_index: number;
}

export interface StudySessionUpdateInput {
  is_completed?: boolean;
  notes?: string | null;
  scheduled_date?: string;
  duration_hours?: number;
}

export interface Schedule {
  course_id: number;
  total_sessions: number;
  total_hours: floatNumber;
  start_date?: string | null;
  exam_date?: string | null;
  is_feasible: boolean;
  conflicts: string[];
  sessions: StudySession[];
}

type floatNumber = number;

export interface ScheduleGenerateInput {
  start_date?: string | null;
  study_days_per_week?: number;
  daily_study_hours?: number;
  revision_ratio?: number;
}

export interface PracticeQuestion {
  question: string;
  answer: string;
  explanation: string;
}

export interface LessonContent {
  definition: string;
  explanation: string;
  analogy: string;
  worked_example: string;
  misconceptions: string[];
  practice_questions: PracticeQuestion[];
  source_supported_points: string[];
  supplemental_notes?: string | null;
}

export interface SourceReference {
  source_filename: string;
  page_number?: number | null;
  slide_number?: number | null;
  excerpt?: string | null;
}

export interface TopicContent {
  id: number;
  topic_id: number;
  topic_name: string;
  content: LessonContent;
  source_refs: SourceReference[];
  generated_at: string;
  model_used: string;
}

export interface ModelStatus {
  llm_model_id: string;
  llm_model_path: string;
  llm_loaded: boolean;
  llm_device: string;
  lora_adapter_path?: string | null;
  lora_loaded: boolean;
  embedding_model_id: string;
  embedding_model_path: string;
  embedding_loaded: boolean;
  embedding_device: string;
}

export interface StorageStatus {
  database_connected: boolean;
  database_url: string;
  upload_dir: string;
  upload_dir_exists: boolean;
  chroma_dir: string;
  chroma_dir_exists: boolean;
  total_courses: number;
  total_documents: number;
  total_chunks: number;
}

export interface SystemStatus {
  app_name: string;
  version: string;
  status: 'ok' | 'degraded';
  models: ModelStatus;
  storage: StorageStatus;
  environment: Record<string, unknown>;
}

export interface ModelLoadInput {
  load_llm?: boolean;
  load_embedding?: boolean;
  load_lora?: boolean;
}

// ============================================================================
// TanStack Query Hooks
// ============================================================================

// --- Courses ---

export function useCourses() {
  return useQuery<CourseListResponse | Course[]>({
    queryKey: ['courses'],
    queryFn: async () => {
      const response = await api.get('/courses');
      return response.data;
    },
  });
}

export function useCourse(id: number | string | undefined) {
  return useQuery<Course>({
    queryKey: ['courses', id],
    queryFn: async () => {
      const response = await api.get(`/courses/${id}`);
      return response.data;
    },
    enabled: Boolean(id),
  });
}

export function useCreateCourse() {
  const queryClient = useQueryClient();
  return useMutation<Course, Error, CourseCreateInput>({
    mutationFn: async (payload) => {
      const response = await api.post('/courses', payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      queryClient.invalidateQueries({ queryKey: ['settings', 'status'] });
    },
  });
}

export function useUpdateCourse() {
  const queryClient = useQueryClient();
  return useMutation<Course, Error, { id: number | string; data: CourseUpdateInput }>({
    mutationFn: async ({ id, data }) => {
      const response = await api.put(`/courses/${id}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      queryClient.invalidateQueries({ queryKey: ['courses', variables.id] });
    },
  });
}

export function useDeleteCourse() {
  const queryClient = useQueryClient();
  return useMutation<{ message: string }, Error, number | string>({
    mutationFn: async (id) => {
      const response = await api.delete(`/courses/${id}`);
      return response.data;
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      queryClient.removeQueries({ queryKey: ['courses', id] });
      queryClient.invalidateQueries({ queryKey: ['settings', 'status'] });
    },
  });
}

// --- Documents ---

export function useDocuments(courseId: number | string | undefined) {
  return useQuery<DocumentItem[]>({
    queryKey: ['documents', 'course', courseId],
    queryFn: async () => {
      const response = await api.get(`/documents/course/${courseId}`);
      return response.data;
    },
    enabled: Boolean(courseId),
  });
}

export function useUnitDocuments(courseId: number | string | undefined, unitNumber: number | undefined) {
  return useQuery<DocumentItem[]>({
    queryKey: ['documents', 'unit', courseId, unitNumber],
    queryFn: async () => {
      const response = await api.get(`/documents/unit/${courseId}/${unitNumber}`);
      return response.data;
    },
    enabled: Boolean(courseId && unitNumber !== undefined),
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation<DocumentUploadResponse, Error, { courseId: number | string; unitNumber: number; formData: FormData }>({
    mutationFn: async ({ courseId, unitNumber, formData }) => {
      const response = await api.post(`/documents/upload/${courseId}/${unitNumber}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['documents', 'course', variables.courseId] });
      queryClient.invalidateQueries({ queryKey: ['documents', 'unit', variables.courseId, variables.unitNumber] });
      queryClient.invalidateQueries({ queryKey: ['courses', variables.courseId] });
      queryClient.invalidateQueries({ queryKey: ['courses'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation<{ message: string }, Error, { id: number | string; courseId?: number | string }>({
    mutationFn: async ({ id }) => {
      const response = await api.delete(`/documents/${id}`);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      if (variables.courseId) {
        queryClient.invalidateQueries({ queryKey: ['courses', variables.courseId] });
      }
      queryClient.invalidateQueries({ queryKey: ['courses'] });
    },
  });
}

export function useProcessDocument() {
  const queryClient = useQueryClient();
  return useMutation<DocumentStatusResponse, Error, { id: number | string; courseId?: number | string }>({
    mutationFn: async ({ id }) => {
      const response = await api.post(`/documents/${id}/process`);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      if (variables.courseId) {
        queryClient.invalidateQueries({ queryKey: ['courses', variables.courseId] });
      }
    },
  });
}

// --- Syllabus & Coverage ---

export function useSyllabusTopics(courseId: number | string | undefined) {
  return useQuery<SyllabusTopic[]>({
    queryKey: ['syllabus', 'topics', courseId],
    queryFn: async () => {
      const response = await api.get(`/syllabus/topics/${courseId}`);
      return response.data;
    },
    enabled: Boolean(courseId),
  });
}

export function useAnalyzeCoverage() {
  const queryClient = useQueryClient();
  return useMutation<CoverageData, Error, number | string>({
    mutationFn: async (courseId) => {
      const response = await api.post(`/syllabus/analyze/${courseId}`);
      return response.data;
    },
    onSuccess: (_, courseId) => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', 'coverage', courseId] });
      queryClient.invalidateQueries({ queryKey: ['syllabus', 'topics', courseId] });
      queryClient.invalidateQueries({ queryKey: ['courses', courseId] });
    },
  });
}

export function useUpdateTopic() {
  const queryClient = useQueryClient();
  return useMutation<SyllabusTopic, Error, { topicId: number | string; courseId?: number | string; data: SyllabusTopicUpdateInput }>({
    mutationFn: async ({ topicId, data }) => {
      const response = await api.put(`/syllabus/topics/${topicId}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', 'topics'] });
      if (variables.courseId) {
        queryClient.invalidateQueries({ queryKey: ['syllabus', 'coverage', variables.courseId] });
      }
    },
  });
}

export function useCoverageData(courseId: number | string | undefined) {
  return useQuery<CoverageData>({
    queryKey: ['syllabus', 'coverage', courseId],
    queryFn: async () => {
      const response = await api.get(`/syllabus/coverage/${courseId}`);
      return response.data;
    },
    enabled: Boolean(courseId),
  });
}

// --- Schedule ---

export function useSchedule(courseId: number | string | undefined) {
  return useQuery<Schedule>({
    queryKey: ['schedule', courseId],
    queryFn: async () => {
      const response = await api.get(`/schedule/${courseId}`);
      return response.data;
    },
    enabled: Boolean(courseId),
  });
}

export function useGenerateSchedule() {
  const queryClient = useQueryClient();
  return useMutation<Schedule, Error, { courseId: number | string; params?: ScheduleGenerateInput }>({
    mutationFn: async ({ courseId, params }) => {
      const response = await api.post(`/schedule/generate/${courseId}`, params || {});
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['schedule', variables.courseId] });
    },
  });
}

export function useUpdateSession() {
  const queryClient = useQueryClient();
  return useMutation<StudySession, Error, { sessionId: number | string; courseId?: number | string; data: StudySessionUpdateInput }>({
    mutationFn: async ({ sessionId, data }) => {
      const response = await api.put(`/schedule/session/${sessionId}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      if (variables.courseId) {
        queryClient.invalidateQueries({ queryKey: ['schedule', variables.courseId] });
      } else {
        queryClient.invalidateQueries({ queryKey: ['schedule'] });
      }
    },
  });
}

export function useRecalculateSchedule() {
  const queryClient = useQueryClient();
  return useMutation<Schedule, Error, { courseId: number | string; params?: ScheduleGenerateInput }>({
    mutationFn: async ({ courseId, params }) => {
      const response = await api.post(`/schedule/recalculate/${courseId}`, params || {});
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['schedule', variables.courseId] });
    },
  });
}

// --- Topic Content / Teaching ---

export function useTopicContent(topicId: number | string | undefined) {
  return useQuery<TopicContent>({
    queryKey: ['topic', 'content', topicId],
    queryFn: async () => {
      const response = await api.get(`/topics/${topicId}/content`);
      return response.data;
    },
    enabled: Boolean(topicId),
  });
}

export function useGenerateTopicContent() {
  const queryClient = useQueryClient();
  return useMutation<TopicContent, Error, { topicId: number | string; regenerate?: boolean }>({
    mutationFn: async ({ topicId, regenerate = false }) => {
      const response = await api.post(`/topics/generate/${topicId}`, { regenerate });
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['topic', 'content', variables.topicId] });
    },
  });
}

// --- Settings & Models ---

export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ['settings', 'status'],
    queryFn: async () => {
      const response = await api.get('/settings/status');
      return response.data;
    },
  });
}

export function useModelStatus() {
  return useQuery<ModelStatus>({
    queryKey: ['settings', 'models'],
    queryFn: async () => {
      const response = await api.get('/settings/models');
      return response.data;
    },
  });
}

export function useLoadModels() {
  const queryClient = useQueryClient();
  return useMutation<{ message: string; models: ModelStatus }, Error, ModelLoadInput | void>({
    mutationFn: async (payload) => {
      const response = await api.post('/settings/models/load', payload || {});
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'models'] });
      queryClient.invalidateQueries({ queryKey: ['settings', 'status'] });
    },
  });
}
