import * as React from 'react';
import { useSearchParams, useNavigate, useParams } from 'react-router-dom';
import {
  Calendar,
  CheckCircle2,
  Clock,
  RotateCw,
  Sparkles,
  AlertTriangle,
  BookOpen,
  ArrowRight,
  Flag,
  CheckSquare,
  Square,
  Layers,
  ChevronDown,
  ChevronRight,
  Info,
} from 'lucide-react';
import {
  format,
  parseISO,
  isValid,
  differenceInCalendarDays,
  startOfWeek,
  endOfWeek,
} from 'date-fns';

import {
  useCourses,
  useSchedule,
  useGenerateSchedule,
  useRecalculateSchedule,
  useUpdateSession,
  Course,
  Schedule,
  StudySession,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

export default function StudyTimeline() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Selected Course state
  const initialCourseId = searchParams.get('courseId') || '';
  const [selectedCourseId, setSelectedCourseId] = React.useState<string>(initialCourseId);

  // Queries
  const { data: coursesData, isLoading: isLoadingCourses } = useCourses();
  const courses: Course[] = React.useMemo(() => {
    if (!coursesData) return [];
    if (Array.isArray(coursesData)) return coursesData;
    if ('courses' in coursesData && Array.isArray(coursesData.courses)) return coursesData.courses;
    return [];
  }, [coursesData]);

  // Set default course if none selected
  React.useEffect(() => {
    if (!selectedCourseId && courses.length > 0) {
      const defaultId = String(courses[0].id);
      setSelectedCourseId(defaultId);
      setSearchParams({ courseId: defaultId });
    }
  }, [courses, selectedCourseId, setSearchParams]);

  const handleCourseChange = (id: string) => {
    setSelectedCourseId(id);
    setSearchParams({ courseId: id });
  };

  // Schedule query & mutations
  const {
    data: schedule,
    isLoading: isLoadingSchedule,
    isError: isScheduleError,
    error: scheduleError,
    refetch: refetchSchedule,
  } = useSchedule(selectedCourseId || undefined);

  const generateMutation = useGenerateSchedule();
  const recalculateMutation = useRecalculateSchedule();
  const updateSessionMutation = useUpdateSession();

  const handleGenerate = async () => {
    if (!selectedCourseId) return;
    try {
      await generateMutation.mutateAsync({ courseId: selectedCourseId });
      refetchSchedule();
    } catch {
      // Handled by react query
    }
  };

  const handleRecalculate = async () => {
    if (!selectedCourseId) return;
    try {
      await recalculateMutation.mutateAsync({ courseId: selectedCourseId });
      refetchSchedule();
    } catch {
      // Handled by react query
    }
  };

  const handleToggleComplete = async (session: StudySession) => {
    if (!selectedCourseId) return;
    try {
      await updateSessionMutation.mutateAsync({
        sessionId: session.id,
        courseId: selectedCourseId,
        data: {
          is_completed: !session.is_completed,
        },
      });
    } catch {
      // Handled
    }
  };

  const currentCourse = courses.find((c) => String(c.id) === selectedCourseId) || courses[0];

  // Calculate schedule stats
  const sessions = schedule?.sessions || [];
  const completedSessions = sessions.filter((s) => s.is_completed).length;
  const totalSessions = sessions.length;
  const progressPct = totalSessions > 0 ? Math.round((completedSessions / totalSessions) * 100) : 0;
  const totalHours = schedule?.total_hours || sessions.reduce((acc, s) => acc + (s.duration_hours || 0), 0);

  // Group sessions by week
  const groupedSessions = React.useMemo(() => {
    const groups: Array<{ weekLabel: string; sessions: StudySession[] }> = [];
    if (sessions.length === 0) return groups;

    // Map each session to a week start
    const map = new Map<string, StudySession[]>();

    sessions.forEach((session) => {
      let key = 'Upcoming';
      try {
        const parsed = parseISO(session.scheduled_date);
        if (isValid(parsed)) {
          const start = startOfWeek(parsed, { weekStartsOn: 1 });
          const end = endOfWeek(parsed, { weekStartsOn: 1 });
          key = `${format(start, 'MMM dd')} - ${format(end, 'MMM dd, yyyy')}`;
        }
      } catch {
        key = 'Scheduled Sessions';
      }

      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)!.push(session);
    });

    let weekIndex = 1;
    map.forEach((items, label) => {
      groups.push({
        weekLabel: `Week ${weekIndex} (${label})`,
        sessions: items,
      });
      weekIndex++;
    });

    return groups;
  }, [sessions]);

  // Exam info
  const examInfo = React.useMemo(() => {
    const rawDate = schedule?.exam_date || currentCourse?.exam_date;
    if (!rawDate) return null;
    try {
      const parsed = parseISO(rawDate);
      if (!isValid(parsed)) return null;
      const daysLeft = differenceInCalendarDays(parsed, new Date());
      return {
        dateStr: format(parsed, 'EEEE, MMMM dd, yyyy'),
        daysLeft,
      };
    } catch {
      return null;
    }
  }, [schedule?.exam_date, currentCourse?.exam_date]);

  if (isLoadingCourses) {
    return <LoadingSpinner text="Loading courses..." fullHeight />;
  }

  if (courses.length === 0) {
    return (
      <div className="space-y-6 pb-12">
        <PageHeader
          title="Study Schedule & Timeline"
          description="Build a topological study schedule that spaces out syllabus concepts before your exam date."
        />
        <EmptyState
          icon={BookOpen}
          title="No courses registered"
          description="Create a course with target exam date to generate an optimized study calendar."
          actionLabel="Create Course"
          onAction={() => navigate('/courses/new')}
          className="py-16 bg-white"
        />
      </div>
    );
  }

  const isGenerating = generateMutation.isPending || recalculateMutation.isPending;

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Study Schedule & Timeline"
        description="Topologically sorted syllabus progression with spaced revision buffers leading up to your final exam."
        actions={
          <div className="flex items-center gap-3">
            <div className="w-56">
              <Select
                value={selectedCourseId}
                onChange={(e) => handleCourseChange(e.target.value)}
                className="text-xs font-semibold"
              >
                {courses.map((course) => (
                  <option key={course.id} value={String(course.id)}>
                    {course.name}
                  </option>
                ))}
              </Select>
            </div>

            {totalSessions > 0 ? (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRecalculate}
                disabled={isGenerating}
                className="gap-2 text-xs bg-white shadow-xs"
              >
                <RotateCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                Recalculate
              </Button>
            ) : null}

            <Button
              size="sm"
              onClick={handleGenerate}
              disabled={isGenerating}
              className="gap-2 text-xs shadow-sm"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-300" />
              {totalSessions > 0 ? 'Regenerate Plan' : 'Generate Schedule'}
            </Button>
          </div>
        }
      />

      {/* Conflicts & Constraint Warning */}
      {schedule && !schedule.is_feasible && (
        <Alert variant="warning" className="border-amber-300 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-700" />
          <AlertTitle className="text-amber-900 font-semibold">
            Pacing Constraint Warning
          </AlertTitle>
          <AlertDescription className="text-amber-800 text-xs space-y-1">
            <p>
              The required syllabus topic hours exceed your available study time before the scheduled exam date.
            </p>
            {schedule.conflicts && schedule.conflicts.length > 0 && (
              <ul className="list-disc pl-4 mt-2 space-y-0.5">
                {schedule.conflicts.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[11px] font-medium text-amber-900">
              Consider increasing your daily study hours or study days per week in course settings.
            </p>
          </AlertDescription>
        </Alert>
      )}

      {/* Progress & Overview Card */}
      {totalSessions > 0 && (
        <Card className="bg-white border-gray-200 shadow-xs">
          <CardContent className="p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Study Plan Completion
                </span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-gray-900">{progressPct}%</span>
                  <span className="text-xs text-gray-500">
                    ({completedSessions} of {totalSessions} sessions completed)
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-6 text-xs text-gray-600">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-primary-600 shrink-0" />
                  <div>
                    <p className="font-semibold text-gray-900">{totalHours} Hours</p>
                    <p className="text-[11px] text-gray-500">Total duration</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-primary-600 shrink-0" />
                  <div>
                    <p className="font-semibold text-gray-900">
                      {currentCourse?.study_days_per_week || 5} d/wk &bull; {currentCourse?.daily_study_hours || 2}h
                    </p>
                    <p className="text-[11px] text-gray-500">Availability</p>
                  </div>
                </div>
              </div>
            </div>

            <Progress
              value={progressPct}
              className="h-2.5"
              indicatorClassName="bg-emerald-600"
            />
          </CardContent>
        </Card>
      )}

      {/* Timeline Sessions List */}
      {isLoadingSchedule ? (
        <LoadingSpinner text="Computing schedule..." fullHeight />
      ) : isScheduleError ? (
        <ErrorDisplay
          title="Could not load study schedule"
          error={scheduleError as Error}
          onRetry={() => refetchSchedule()}
        />
      ) : totalSessions === 0 ? (
        <EmptyState
          icon={Calendar}
          title="No study schedule generated yet"
          description="Click 'Generate Schedule' to calculate an optimized timeline that orders topics based on prerequisites and schedules revision blocks."
          actionLabel="Generate Schedule Now"
          onAction={handleGenerate}
          className="py-16 bg-white"
        />
      ) : (
        <div className="space-y-8">
          {groupedSessions.map((group, groupIdx) => (
            <div key={groupIdx} className="space-y-3">
              <div className="flex items-center gap-2.5">
                <div className="h-2 w-2 rounded-full bg-primary-600" />
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                  {group.weekLabel}
                </h3>
              </div>

              <div className="space-y-2 pl-3 border-l-2 border-gray-200">
                {group.sessions.map((session) => {
                  const isCompleted = session.is_completed;
                  const isRevision = session.session_type === 'revision';

                  const dateFormatted = (() => {
                    try {
                      const p = parseISO(session.scheduled_date);
                      return isValid(p) ? format(p, 'EEE, MMM dd') : session.scheduled_date;
                    } catch {
                      return session.scheduled_date;
                    }
                  })();

                  return (
                    <div
                      key={session.id}
                      className={`relative flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-xl border transition-all duration-150 ${
                        isCompleted
                          ? 'bg-emerald-50/40 border-emerald-200/70 text-gray-600'
                          : isRevision
                          ? 'bg-amber-50/40 border-amber-200/80 text-gray-900'
                          : 'bg-white border-gray-200/90 text-gray-900 hover:border-primary-300 hover:shadow-xs'
                      }`}
                    >
                      {/* Checkbox & Topic Info */}
                      <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                        <button
                          type="button"
                          onClick={() => handleToggleComplete(session)}
                          className={`mt-0.5 sm:mt-0 p-1 rounded-md transition-colors cursor-pointer shrink-0 ${
                            isCompleted
                              ? 'text-emerald-600 hover:text-emerald-700'
                              : 'text-gray-400 hover:text-gray-600'
                          }`}
                          aria-label={isCompleted ? 'Mark incomplete' : 'Mark completed'}
                        >
                          {isCompleted ? (
                            <CheckSquare className="h-5 w-5" />
                          ) : (
                            <Square className="h-5 w-5" />
                          )}
                        </button>

                        <div className="min-w-0 space-y-0.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`text-sm font-semibold truncate ${
                                isCompleted ? 'line-through text-gray-500' : 'text-gray-900'
                              }`}
                            >
                              {session.topic_name || `Session #${session.order_index + 1}`}
                            </span>

                            {session.unit_number && (
                              <Badge
                                variant="outline"
                                className="text-[10px] px-1.5 py-0 bg-gray-50 text-gray-600"
                              >
                                Unit {session.unit_number}
                              </Badge>
                            )}

                            <Badge
                              variant={isRevision ? 'warning' : 'secondary'}
                              className={`capitalize text-[10px] px-1.5 py-0 ${
                                isRevision
                                  ? 'bg-amber-100 text-amber-800 border-amber-200 font-semibold'
                                  : 'bg-blue-50 text-blue-700 border-blue-200'
                              }`}
                            >
                              {session.session_type}
                            </Badge>
                          </div>

                          {session.notes && (
                            <p className="text-xs text-gray-500 italic">{session.notes}</p>
                          )}
                        </div>
                      </div>

                      {/* Date & Duration */}
                      <div className="flex items-center gap-3 shrink-0 mt-2 sm:mt-0 pl-9 sm:pl-0 text-xs">
                        <span className="flex items-center gap-1.5 font-medium text-gray-600">
                          <Calendar className="h-3.5 w-3.5 text-gray-400" />
                          <span>{dateFormatted}</span>
                        </span>

                        <span className="rounded-md bg-gray-100 px-2 py-0.5 font-semibold text-gray-700 text-[11px]">
                          {session.duration_hours} hr{session.duration_hours !== 1 ? 's' : ''}
                        </span>

                        {session.topic_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-primary-600 hover:text-primary-700"
                            onClick={() =>
                              navigate(
                                `/topics?courseId=${selectedCourseId}&topicId=${session.topic_id}`
                              )
                            }
                          >
                            Study Topic
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Exam Milestone Card at Timeline Finish */}
          {examInfo && (
            <div className="pt-4">
              <div className="flex items-center gap-4 rounded-xl border-2 border-dashed border-red-300 bg-red-50/50 p-5 shadow-xs">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 shrink-0 ring-8 ring-red-50">
                  <Flag className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-red-950 text-base">Final Exam Target</h4>
                    <Badge variant="destructive" className="text-xs font-semibold">
                      {examInfo.daysLeft < 0
                        ? 'Completed'
                        : examInfo.daysLeft === 0
                        ? 'Today!'
                        : `${examInfo.daysLeft} days remaining`}
                    </Badge>
                  </div>
                  <p className="text-xs text-red-800 mt-1">
                    Scheduled for <strong>{examInfo.dateStr}</strong>. Keep following your daily study plan to finish all revision cycles.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
