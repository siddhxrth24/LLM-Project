import * as React from 'react';
import { useSearchParams, useNavigate, useParams, Link } from 'react-router-dom';
import {
  CheckCircle2,
  AlertCircle,
  XCircle,
  HelpCircle,
  Play,
  RotateCw,
  ChevronDown,
  ChevronRight,
  BookOpen,
  FileText,
  FileCheck,
  Search,
  Filter,
  Sparkles,
  ExternalLink,
  Layers,
} from 'lucide-react';

import {
  useCourses,
  useSyllabusTopics,
  useCoverageData,
  useAnalyzeCoverage,
  useUpdateTopic,
  Course,
  SyllabusTopic,
  CoverageData,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge, StatusType } from '@/components/shared/StatusBadge';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

export default function CoverageAnalysis() {
  const navigate = useNavigate();
  const params = useParams<{ courseId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  // Course selection state
  const initialCourseId = params.courseId || searchParams.get('courseId') || '';
  const [selectedCourseId, setSelectedCourseId] = React.useState<string>(initialCourseId);

  // Filter & Search state
  const [statusFilter, setStatusFilter] = React.useState<string>('all');
  const [searchQuery, setSearchQuery] = React.useState<string>('');

  // Expanded sections state
  const [expandedUnits, setExpandedUnits] = React.useState<Record<number, boolean>>({
    1: true,
    2: true,
    3: true,
    4: true,
    5: true,
  });
  const [expandedTopics, setExpandedTopics] = React.useState<Record<number, boolean>>({});

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

  // Queries for topics and coverage summary
  const {
    data: topicsData = [],
    isLoading: isLoadingTopics,
    isError: isTopicsError,
    error: topicsError,
    refetch: refetchTopics,
  } = useSyllabusTopics(selectedCourseId || undefined);

  const {
    data: coverageSummary,
    isLoading: isLoadingCoverage,
    refetch: refetchCoverage,
  } = useCoverageData(selectedCourseId || undefined);

  // Mutations
  const analyzeMutation = useAnalyzeCoverage();
  const updateTopicMutation = useUpdateTopic();

  // Run full coverage analysis
  const handleRunAnalysis = async () => {
    if (!selectedCourseId) return;
    try {
      await analyzeMutation.mutateAsync(selectedCourseId);
      await Promise.all([refetchTopics(), refetchCoverage()]);
    } catch {
      // TanStack query handles mutation error state
    }
  };

  // Handle status override
  const handleStatusOverride = async (topicId: number, newStatus: string) => {
    if (!selectedCourseId) return;
    try {
      const overrideVal =
        newStatus === 'auto'
          ? null
          : (newStatus as 'covered' | 'partially_covered' | 'not_found' | 'needs_review');

      await updateTopicMutation.mutateAsync({
        topicId,
        courseId: selectedCourseId,
        data: {
          user_override_status: overrideVal,
        },
      });
    } catch {
      // Error handled
    }
  };

  const toggleUnitExpand = (unitNum: number) => {
    setExpandedUnits((prev) => ({ ...prev, [unitNum]: !prev[unitNum] }));
  };

  const toggleTopicExpand = (topicId: number) => {
    setExpandedTopics((prev) => ({ ...prev, [topicId]: !prev[topicId] }));
  };

  // Combine topics from either topics query or coverageSummary
  const allTopics: SyllabusTopic[] = React.useMemo(() => {
    if (coverageSummary?.topics && coverageSummary.topics.length > 0) {
      return coverageSummary.topics;
    }
    return Array.isArray(topicsData) ? topicsData : [];
  }, [topicsData, coverageSummary]);

  // Filter topics
  const filteredTopics = React.useMemo(() => {
    return allTopics.filter((t) => {
      const currentStatus = t.effective_status || t.user_override_status || t.coverage_status;
      const matchesStatus =
        statusFilter === 'all' || currentStatus?.toLowerCase() === statusFilter.toLowerCase();
      const matchesSearch =
        !searchQuery ||
        t.topic_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.subtopics && t.subtopics.some((st) => String(st).toLowerCase().includes(searchQuery.toLowerCase())));
      return matchesStatus && matchesSearch;
    });
  }, [allTopics, statusFilter, searchQuery]);

  // Group filtered topics by unit
  const topicsByUnit = React.useMemo(() => {
    const map: Record<number, SyllabusTopic[]> = {};
    filteredTopics.forEach((topic) => {
      const u = topic.unit_number || 1;
      if (!map[u]) map[u] = [];
      map[u].push(topic);
    });
    // Sort each unit by order_index
    Object.keys(map).forEach((u) => {
      map[Number(u)].sort((a, b) => a.order_index - b.order_index);
    });
    return map;
  }, [filteredTopics]);

  // Summary counts
  const stats = React.useMemo(() => {
    const covered = allTopics.filter(
      (t) => (t.effective_status || t.coverage_status) === 'covered'
    ).length;
    const partially = allTopics.filter(
      (t) => (t.effective_status || t.coverage_status) === 'partially_covered'
    ).length;
    const notFound = allTopics.filter(
      (t) => (t.effective_status || t.coverage_status) === 'not_found'
    ).length;
    const needsReview = allTopics.filter(
      (t) => (t.effective_status || t.coverage_status) === 'needs_review'
    ).length;
    const total = allTopics.length;
    const percentage =
      total > 0 ? Math.round(((covered + partially * 0.5) / total) * 100) : 0;

    return {
      total,
      covered: coverageSummary?.covered_count ?? covered,
      partially: coverageSummary?.partially_covered_count ?? partially,
      notFound: coverageSummary?.not_found_count ?? notFound,
      needsReview: coverageSummary?.needs_review_count ?? needsReview,
      percentage: coverageSummary?.coverage_percentage ?? percentage,
    };
  }, [allTopics, coverageSummary]);

  if (isLoadingCourses) {
    return <LoadingSpinner text="Loading courses..." fullHeight />;
  }

  if (courses.length === 0) {
    return (
      <div className="space-y-6 pb-12">
        <PageHeader
          title="Coverage Analysis"
          description="Cross-reference syllabus topics against your uploaded lecture notes and slides."
        />
        <EmptyState
          icon={BookOpen}
          title="No courses registered"
          description="Create a course with syllabus text first, then analyze topic coverage."
          actionLabel="Create Course"
          onAction={() => navigate('/courses/new')}
          className="py-16 bg-white"
        />
      </div>
    );
  }

  const currentCourse = courses.find((c) => String(c.id) === selectedCourseId) || courses[0];

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Syllabus Coverage Analysis"
        description="Verify whether every syllabus exam concept is thoroughly addressed in your slide decks or textbook notes."
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

            <Button
              onClick={handleRunAnalysis}
              disabled={analyzeMutation.isPending || !selectedCourseId}
              className="gap-2 shadow-sm text-xs"
            >
              {analyzeMutation.isPending ? (
                <>
                  <RotateCw className="h-4 w-4 animate-spin" />
                  Running Analysis...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 text-amber-300" />
                  Run Analysis
                </>
              )}
            </Button>
          </div>
        }
      />

      {/* Summary Stats Bar */}
      <Card className="bg-white border-gray-200 shadow-xs">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-6">
            {/* Overall Percentage Progress */}
            <div className="space-y-2 lg:w-1/3 border-b lg:border-b-0 lg:border-r border-gray-100 pb-4 lg:pb-0 lg:pr-6">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Total Syllabus Coverage
                </span>
                <span className="text-xl font-bold text-gray-900">{stats.percentage}%</span>
              </div>
              <Progress
                value={stats.percentage}
                className="h-2.5"
                indicatorClassName={
                  stats.percentage >= 80
                    ? 'bg-emerald-600'
                    : stats.percentage >= 50
                    ? 'bg-blue-600'
                    : 'bg-amber-600'
                }
              />
              <p className="text-[11px] text-gray-500">
                {stats.covered} of {stats.total} topics fully identified in uploaded notes
              </p>
            </div>

            {/* Breakdown Counts */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 flex-1">
              <div className="rounded-lg bg-emerald-50/70 p-3 border border-emerald-100 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 shrink-0">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-emerald-800">Covered</p>
                  <p className="text-xl font-bold text-emerald-950">{stats.covered}</p>
                </div>
              </div>

              <div className="rounded-lg bg-blue-50/70 p-3 border border-blue-100 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-blue-100 text-blue-700 shrink-0">
                  <AlertCircle className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-blue-800">Partially</p>
                  <p className="text-xl font-bold text-blue-950">{stats.partially}</p>
                </div>
              </div>

              <div className="rounded-lg bg-red-50/70 p-3 border border-red-100 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-red-100 text-red-700 shrink-0">
                  <XCircle className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-red-800">Not Found</p>
                  <p className="text-xl font-bold text-red-950">{stats.notFound}</p>
                </div>
              </div>

              <div className="rounded-lg bg-amber-50/70 p-3 border border-amber-100 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-100 text-amber-700 shrink-0">
                  <HelpCircle className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-amber-800">Needs Review</p>
                  <p className="text-xl font-bold text-amber-950">{stats.needsReview}</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search topic or keywords..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-gray-300 bg-white pl-8 pr-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-medium">Filter Status:</span>
          <div className="w-40">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs h-9"
            >
              <option value="all">All Topics ({allTopics.length})</option>
              <option value="covered">Covered Only</option>
              <option value="partially_covered">Partially Covered</option>
              <option value="not_found">Not Found</option>
              <option value="needs_review">Needs Review</option>
            </Select>
          </div>
        </div>
      </div>

      {/* Analysis Running Notice */}
      {analyzeMutation.isPending && (
        <Alert variant="info" className="border-primary-200 bg-primary-50/80">
          <Sparkles className="h-4 w-4 text-primary-600 animate-spin" />
          <AlertTitle>Semantic Vector Matching in Progress</AlertTitle>
          <AlertDescription>
            The offline sentence embedding model is scanning your document chunks to compute confidence scores and highlight excerpts for each syllabus topic...
          </AlertDescription>
        </Alert>
      )}

      {/* Main Topics List Grouped by Unit */}
      {isLoadingTopics ? (
        <LoadingSpinner text="Retrieving syllabus topics..." fullHeight />
      ) : isTopicsError ? (
        <ErrorDisplay
          title="Failed to load topics"
          error={topicsError as Error}
          onRetry={() => refetchTopics()}
        />
      ) : allTopics.length === 0 ? (
        <EmptyState
          icon={FileCheck}
          title="No topics extracted yet"
          description="Your syllabus text has not been parsed or is empty. Add syllabus content in course settings, or click 'Run Analysis'."
          actionLabel="Edit Course Syllabus"
          onAction={() => navigate(`/courses/${selectedCourseId}/edit`)}
          className="py-16 bg-white"
        />
      ) : (
        <div className="space-y-5">
          {Object.keys(topicsByUnit).length === 0 ? (
            <div className="text-center py-12 text-gray-500 text-sm bg-white rounded-xl border border-gray-200">
              No topics match your current filter and search query.
            </div>
          ) : (
            Object.keys(topicsByUnit)
              .map(Number)
              .sort((a, b) => a - b)
              .map((unitNum) => {
                const unitTopics = topicsByUnit[unitNum] || [];
                const isExpanded = expandedUnits[unitNum] ?? true;

                return (
                  <div
                    key={unitNum}
                    className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-xs"
                  >
                    {/* Unit Header Bar */}
                    <button
                      type="button"
                      onClick={() => toggleUnitExpand(unitNum)}
                      className="w-full flex items-center justify-between p-4 bg-gray-50/90 hover:bg-gray-100 transition-colors text-left cursor-pointer border-b border-gray-200"
                    >
                      <div className="flex items-center gap-3">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-500" />
                        )}
                        <div>
                          <span className="font-bold text-gray-900 text-sm sm:text-base">
                            Unit {unitNum}
                          </span>
                          <span className="text-xs text-gray-500 ml-2">
                            ({unitTopics.length} topics)
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs bg-white text-gray-700">
                          Unit {unitNum}
                        </Badge>
                      </div>
                    </button>

                    {/* Unit Topics Table / Rows */}
                    {isExpanded && (
                      <div className="divide-y divide-gray-100">
                        {unitTopics.map((topic) => {
                          const currentStatus =
                            topic.user_override_status ||
                            topic.effective_status ||
                            topic.coverage_status;

                          const confidencePct = Math.round(
                            (topic.coverage_confidence || 0) * 100
                          );

                          const isTopicExpanded = Boolean(expandedTopics[topic.id]);

                          // Parse evidence safely
                          const evidenceObj = topic.coverage_evidence || {};
                          const evidenceList: Array<{
                            source_file?: string;
                            page_number?: number;
                            slide_number?: number;
                            excerpt?: string;
                            score?: number;
                          }> = Array.isArray(evidenceObj)
                            ? evidenceObj
                            : Array.isArray(evidenceObj.matches)
                            ? evidenceObj.matches
                            : Array.isArray(evidenceObj.snippets)
                            ? evidenceObj.snippets
                            : Array.isArray(evidenceObj.chunks)
                            ? evidenceObj.chunks
                            : [];

                          return (
                            <div key={topic.id} className="p-4 transition-colors hover:bg-gray-50/50">
                              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                                {/* Topic Info */}
                                <div className="space-y-1.5 flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => toggleTopicExpand(topic.id)}
                                      className="font-semibold text-sm text-gray-900 hover:text-primary-600 flex items-center gap-1.5 text-left cursor-pointer"
                                    >
                                      {isTopicExpanded ? (
                                        <ChevronDown className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                                      ) : (
                                        <ChevronRight className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                                      )}
                                      <span>{topic.topic_name}</span>
                                    </button>

                                    {topic.user_override_status && (
                                      <Badge variant="secondary" className="text-[10px] bg-purple-50 text-purple-700 border-purple-200">
                                        Manual Override
                                      </Badge>
                                    )}
                                  </div>

                                  {/* Subtopics bullet list preview */}
                                  {topic.subtopics && topic.subtopics.length > 0 && (
                                    <div className="pl-5 text-xs text-gray-500 flex flex-wrap gap-1.5">
                                      {topic.subtopics.map((sub, i) => (
                                        <span
                                          key={i}
                                          className="inline-flex items-center rounded-sm bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600"
                                        >
                                          {String(sub)}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>

                                {/* Confidence Bar & Status Badge & Override */}
                                <div className="flex items-center gap-4 shrink-0 flex-wrap sm:flex-nowrap">
                                  {/* Confidence Bar */}
                                  <div className="w-24 space-y-1">
                                    <div className="flex justify-between text-[10px] text-gray-500 font-medium">
                                      <span>Match</span>
                                      <span>{confidencePct}%</span>
                                    </div>
                                    <Progress
                                      value={confidencePct}
                                      className="h-1.5"
                                      indicatorClassName={
                                        confidencePct >= 70
                                          ? 'bg-emerald-600'
                                          : confidencePct >= 40
                                          ? 'bg-blue-600'
                                          : 'bg-amber-500'
                                      }
                                    />
                                  </div>

                                  {/* Status Badge */}
                                  <StatusBadge status={currentStatus} />

                                  {/* Override Selector */}
                                  <div className="w-36">
                                    <Select
                                      value={topic.user_override_status || 'auto'}
                                      onChange={(e) =>
                                        handleStatusOverride(topic.id, e.target.value)
                                      }
                                      disabled={updateTopicMutation.isPending}
                                      className="text-[11px] h-8 bg-white"
                                    >
                                      <option value="auto">Auto (Detected)</option>
                                      <option value="covered">Set: Covered</option>
                                      <option value="partially_covered">Set: Partial</option>
                                      <option value="not_found">Set: Not Found</option>
                                      <option value="needs_review">Set: Needs Review</option>
                                    </Select>
                                  </div>

                                  {/* Link to AI Tutor for this topic */}
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 text-xs text-primary-600 hover:text-primary-700"
                                    onClick={() =>
                                      navigate(
                                        `/topics?courseId=${selectedCourseId}&topicId=${topic.id}`
                                      )
                                    }
                                  >
                                    <Sparkles className="h-3.5 w-3.5 mr-1" />
                                    Learn
                                  </Button>
                                </div>
                              </div>

                              {/* Expanded Evidence View */}
                              {isTopicExpanded && (
                                <div className="mt-4 pt-3 border-t border-gray-100 pl-4 space-y-3 animate-in fade-in-50 duration-150">
                                  <div className="flex items-center justify-between">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                                      Matching Text Evidence & References
                                    </p>
                                    <span className="text-[11px] text-gray-400">
                                      {evidenceList.length} evidence snippet{evidenceList.length !== 1 ? 's' : ''}
                                    </span>
                                  </div>

                                  {evidenceList.length === 0 ? (
                                    <p className="text-xs text-gray-500 italic bg-gray-50 p-3 rounded-lg border border-gray-100">
                                      No direct evidence snippets extracted yet. Try uploading more lecture slides or running coverage analysis.
                                    </p>
                                  ) : (
                                    <div className="space-y-2">
                                      {evidenceList.map((item, idx) => (
                                        <div
                                          key={idx}
                                          className="p-3 rounded-lg bg-gray-50 border border-gray-200/80 text-xs space-y-1.5"
                                        >
                                          <div className="flex items-center justify-between text-gray-600 font-medium">
                                            <span className="flex items-center gap-1.5 text-primary-700 font-semibold truncate max-w-sm">
                                              <FileText className="h-3.5 w-3.5 shrink-0" />
                                              <span>{item.source_file || 'Document excerpt'}</span>
                                            </span>
                                            <span className="text-gray-500 text-[11px]">
                                              {item.slide_number
                                                ? `Slide ${item.slide_number}`
                                                : item.page_number
                                                ? `Page ${item.page_number}`
                                                : ''}
                                            </span>
                                          </div>
                                          {item.excerpt && (
                                            <p className="text-gray-700 leading-relaxed italic bg-white p-2 rounded border border-gray-100">
                                              "{item.excerpt}"
                                            </p>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })
          )}
        </div>
      )}
    </div>
  );
}
