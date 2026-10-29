import * as React from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  BookOpen,
  Calendar,
  Clock,
  Sliders,
  FileText,
  Trash2,
  Edit3,
  Plus,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
  ExternalLink,
  UploadCloud,
} from 'lucide-react';
import { format, isAfter, startOfDay, parseISO, isValid } from 'date-fns';

import {
  useCourses,
  useCourse,
  useCreateCourse,
  useUpdateCourse,
  useDeleteCourse,
  Course,
  CourseCreateInput,
  CourseUpdateInput,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

// ============================================================================
// Course Form Component (Create & Edit)
// ============================================================================

export function CourseForm() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(id);

  // Queries & Mutations
  const { data: existingCourse, isLoading: isFetchingCourse } = useCourse(id);
  const createMutation = useCreateCourse();
  const updateMutation = useUpdateCourse();

  // Form State
  const [name, setName] = React.useState('');
  const [syllabusText, setSyllabusText] = React.useState('');
  const [examDate, setExamDate] = React.useState('');
  const [studyDaysPerWeek, setStudyDaysPerWeek] = React.useState<number>(5);
  const [dailyStudyHours, setDailyStudyHours] = React.useState<number>(2);
  const [difficultyPreference, setDifficultyPreference] = React.useState<'easy' | 'balanced' | 'challenging'>('balanced');

  // Validation & Error State
  const [formErrors, setFormErrors] = React.useState<Record<string, string>>({});
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  // Populate data when editing
  React.useEffect(() => {
    if (existingCourse && isEditing) {
      setName(existingCourse.name || '');
      setSyllabusText(existingCourse.syllabus_text || '');
      setExamDate(existingCourse.exam_date || '');
      setStudyDaysPerWeek(existingCourse.study_days_per_week || 5);
      setDailyStudyHours(existingCourse.daily_study_hours || 2);
      setDifficultyPreference(existingCourse.difficulty_preference || 'balanced');
    }
  }, [existingCourse, isEditing]);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = 'Course name is required.';
    }

    if (examDate) {
      const parsedDate = parseISO(examDate);
      if (!isValid(parsedDate)) {
        errors.examDate = 'Invalid date format.';
      } else if (!isAfter(parsedDate, startOfDay(new Date()))) {
        errors.examDate = 'Exam date must be in the future.';
      }
    }

    if (studyDaysPerWeek < 1 || studyDaysPerWeek > 7) {
      errors.studyDaysPerWeek = 'Study days per week must be between 1 and 7.';
    }

    if (dailyStudyHours < 0.5 || dailyStudyHours > 12) {
      errors.dailyStudyHours = 'Daily study hours must be between 0.5 and 12 hours.';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validate()) {
      return;
    }

    const payload: CourseCreateInput = {
      name: name.trim(),
      syllabus_text: syllabusText.trim() || null,
      exam_date: examDate || null,
      study_days_per_week: Number(studyDaysPerWeek),
      daily_study_hours: Number(dailyStudyHours),
      difficulty_preference: difficultyPreference,
    };

    try {
      if (isEditing && id) {
        await updateMutation.mutateAsync({
          id,
          data: payload as CourseUpdateInput,
        });
      } else {
        await createMutation.mutateAsync(payload);
      }
      navigate('/courses');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save course. Please check inputs.';
      setSubmitError(msg);
    }
  };

  if (isEditing && isFetchingCourse) {
    return <LoadingSpinner text="Loading course details..." fullHeight />;
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/courses')}
          className="text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4 mr-1.5" />
          Back to Courses
        </Button>
      </div>

      <PageHeader
        title={isEditing ? 'Edit Course Settings' : 'Create New Course'}
        description={
          isEditing
            ? `Modify details and syllabus preferences for ${existingCourse?.name || 'this course'}.`
            : 'Register a new subject, paste the syllabus text, and set study schedule parameters.'
        }
      />

      {submitError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Save Error</AlertTitle>
          <AlertDescription>{submitError}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Basic Course Information</CardTitle>
            <CardDescription>
              Essential details used to identify this course throughout the platform.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Course Name */}
            <div className="space-y-1.5">
              <Label htmlFor="courseName" required>
                Course Name
              </Label>
              <Input
                id="courseName"
                placeholder="e.g. Operating Systems, Data Structures & Algorithms"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={formErrors.name ? 'border-red-500' : ''}
              />
              {formErrors.name && (
                <p className="text-xs text-red-600">{formErrors.name}</p>
              )}
            </div>

            {/* Exam Date */}
            <div className="space-y-1.5">
              <Label htmlFor="examDate">Final Exam Date</Label>
              <Input
                id="examDate"
                type="date"
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                className={formErrors.examDate ? 'border-red-500' : ''}
              />
              {formErrors.examDate ? (
                <p className="text-xs text-red-600">{formErrors.examDate}</p>
              ) : (
                <p className="text-xs text-gray-500">
                  Target date for the final exam. Used to distribute units and revision sessions.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Syllabus Text Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Syllabus Outline</CardTitle>
                <CardDescription>
                  Paste your raw syllabus with Unit headers. The offline AI will parse topics and prerequisites.
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-xs font-normal text-gray-600">
                Optional (Can add later)
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <Textarea
              id="syllabusText"
              rows={9}
              placeholder={`Unit 1: Introduction to Operating Systems\n- OS Structures and System Calls\n- Process Concept and Scheduling\n\nUnit 2: Memory Management\n- Paging and Segmentation\n- Virtual Memory and Page Replacement Algorithms`}
              value={syllabusText}
              onChange={(e) => setSyllabusText(e.target.value)}
              className="font-mono text-xs leading-relaxed"
            />
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Sparkles className="h-3.5 w-3.5 text-primary-600 shrink-0" />
              <span>
                Tip: Standard unit headings like "Unit 1: Title" work best for automatic topic division.
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Study Preferences Section */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Study Pacing & Schedule Parameters</CardTitle>
            <CardDescription>
              Define your availability so SemesTrack can balance lesson workload and revision.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Study Days per Week */}
            <div className="space-y-1.5">
              <Label htmlFor="studyDays" required>
                Study Days / Week
              </Label>
              <Input
                id="studyDays"
                type="number"
                min={1}
                max={7}
                value={studyDaysPerWeek}
                onChange={(e) => setStudyDaysPerWeek(Number(e.target.value))}
                className={formErrors.studyDaysPerWeek ? 'border-red-500' : ''}
              />
              {formErrors.studyDaysPerWeek ? (
                <p className="text-xs text-red-600">{formErrors.studyDaysPerWeek}</p>
              ) : (
                <p className="text-[11px] text-gray-500">1 to 7 days per week</p>
              )}
            </div>

            {/* Daily Study Hours */}
            <div className="space-y-1.5">
              <Label htmlFor="dailyHours" required>
                Daily Study Hours
              </Label>
              <Input
                id="dailyHours"
                type="number"
                step="0.5"
                min={0.5}
                max={12}
                value={dailyStudyHours}
                onChange={(e) => setDailyStudyHours(Number(e.target.value))}
                className={formErrors.dailyStudyHours ? 'border-red-500' : ''}
              />
              {formErrors.dailyStudyHours ? (
                <p className="text-xs text-red-600">{formErrors.dailyStudyHours}</p>
              ) : (
                <p className="text-[11px] text-gray-500">0.5 to 12.0 hours</p>
              )}
            </div>

            {/* Difficulty Preference */}
            <div className="space-y-1.5">
              <Label htmlFor="difficulty" required>
                Pacing Preference
              </Label>
              <Select
                id="difficulty"
                value={difficultyPreference}
                onChange={(e) =>
                  setDifficultyPreference(e.target.value as 'easy' | 'balanced' | 'challenging')
                }
              >
                <option value="easy">Easy (Relaxed pace)</option>
                <option value="balanced">Balanced (Recommended)</option>
                <option value="challenging">Challenging (Intensive)</option>
              </Select>
              <p className="text-[11px] text-gray-500">Controls buffer days</p>
            </div>
          </CardContent>
          <CardFooter className="bg-gray-50/70 border-t border-gray-100 flex items-center justify-between py-3 rounded-b-xl">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => navigate('/courses')}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting}>
              {isSubmitting
                ? 'Saving...'
                : isEditing
                ? 'Save Changes'
                : 'Create Course & Continue'}
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}

// ============================================================================
// Course List Component
// ============================================================================

export function CourseList() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useCourses();
  const deleteMutation = useDeleteCourse();

  // State for delete modal
  const [courseToDelete, setCourseToDelete] = React.useState<Course | null>(null);

  const courses: Course[] = React.useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if ('courses' in data && Array.isArray(data.courses)) return data.courses;
    return [];
  }, [data]);

  const handleDeleteConfirm = async () => {
    if (!courseToDelete) return;
    try {
      await deleteMutation.mutateAsync(courseToDelete.id);
      setCourseToDelete(null);
    } catch {
      // Error handled by TanStack query
    }
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading courses..." fullHeight />;
  }

  if (isError) {
    return (
      <ErrorDisplay
        title="Could not load course list"
        error={error as Error}
        onRetry={() => refetch()}
        fullHeight
      />
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Courses Management"
        description="View and organize all your registered academic courses, uploaded documents, and syllabus outlines."
        actions={
          <Button onClick={() => navigate('/courses/new')} className="gap-2 shadow-sm">
            <Plus className="h-4 w-4" />
            Add Course
          </Button>
        }
      />

      {courses.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No courses yet"
          description="Create your first academic course to upload notes, parse your syllabus, and track study progress."
          actionLabel="Add your first course"
          onAction={() => navigate('/courses/new')}
          className="py-16 bg-white border-dashed border-gray-300"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course) => {
            const formattedExam = course.exam_date
              ? (() => {
                  try {
                    const parsed = parseISO(course.exam_date);
                    return isValid(parsed) ? format(parsed, 'MMM dd, yyyy') : course.exam_date;
                  } catch {
                    return course.exam_date;
                  }
                })()
              : 'Not set';

            return (
              <Card
                key={course.id}
                className="flex flex-col justify-between hover:border-primary-300 hover:shadow-md transition-all duration-200"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle className="text-base line-clamp-1">{course.name}</CardTitle>
                      <CardDescription className="text-xs">
                        Created {format(parseISO(course.created_at || new Date().toISOString()), 'MMM dd, yyyy')}
                      </CardDescription>
                    </div>
                    <Badge variant="secondary" className="capitalize text-[11px]">
                      {course.difficulty_preference}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3.5 pb-4 text-xs">
                  {/* Details Grid */}
                  <div className="space-y-2 rounded-lg bg-gray-50 p-3 border border-gray-100">
                    <div className="flex items-center justify-between text-gray-600">
                      <span className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-gray-400" />
                        <span>Exam Date:</span>
                      </span>
                      <span className="font-semibold text-gray-900">{formattedExam}</span>
                    </div>

                    <div className="flex items-center justify-between text-gray-600">
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-gray-400" />
                        <span>Pacing:</span>
                      </span>
                      <span className="font-medium text-gray-900">
                        {course.study_days_per_week} days/wk &bull; {course.daily_study_hours} hrs/day
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-gray-600">
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-gray-400" />
                        <span>Materials:</span>
                      </span>
                      <span className="font-medium text-gray-900">
                        {course.document_count || 0} docs &bull; {course.topic_count || 0} topics
                      </span>
                    </div>
                  </div>

                  {/* Quick Shortcuts */}
                  <div className="grid grid-cols-3 gap-1.5 text-center pt-1">
                    <button
                      type="button"
                      onClick={() => navigate(`/documents?courseId=${course.id}`)}
                      className="rounded-md bg-white border border-gray-200 py-1.5 px-2 hover:bg-gray-50 hover:text-primary-600 transition-colors cursor-pointer"
                    >
                      <UploadCloud className="h-3.5 w-3.5 mx-auto mb-1 text-gray-500" />
                      <span className="text-[10px] font-medium block">Uploads</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate(`/coverage?courseId=${course.id}`)}
                      className="rounded-md bg-white border border-gray-200 py-1.5 px-2 hover:bg-gray-50 hover:text-primary-600 transition-colors cursor-pointer"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 mx-auto mb-1 text-gray-500" />
                      <span className="text-[10px] font-medium block">Coverage</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate(`/schedule?courseId=${course.id}`)}
                      className="rounded-md bg-white border border-gray-200 py-1.5 px-2 hover:bg-gray-50 hover:text-primary-600 transition-colors cursor-pointer"
                    >
                      <Calendar className="h-3.5 w-3.5 mx-auto mb-1 text-gray-500" />
                      <span className="text-[10px] font-medium block">Schedule</span>
                    </button>
                  </div>
                </CardContent>

                <CardFooter className="pt-2 border-t border-gray-100 flex items-center justify-between bg-gray-50/50 rounded-b-xl">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                    onClick={() => setCourseToDelete(course)}
                  >
                    <Trash2 className="h-3.5 w-3.5 mr-1" />
                    Delete
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs bg-white"
                    onClick={() => navigate(`/courses/${course.id}/edit`)}
                  >
                    <Edit3 className="h-3.5 w-3.5 mr-1" />
                    Edit
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={Boolean(courseToDelete)} onOpenChange={(open) => !open && setCourseToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-600 flex items-center gap-2">
              <Trash2 className="h-5 w-5" />
              Delete Course
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong className="text-gray-900">{courseToDelete?.name}</strong>?
              This will permanently remove all associated units, uploaded documents, syllabus topics, and study schedules.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCourseToDelete(null)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Permanently'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================================
// Default Router Wrapper
// ============================================================================

export default function CourseSetup() {
  const { id } = useParams<{ id?: string }>();
  const location = useLocation();

  // If path is /courses/new or /courses/:id/edit, show form. Otherwise show list.
  const isFormRoute =
    location.pathname.endsWith('/new') ||
    location.pathname.includes('/edit') ||
    Boolean(id);

  if (isFormRoute) {
    return <CourseForm />;
  }

  return <CourseList />;
}
