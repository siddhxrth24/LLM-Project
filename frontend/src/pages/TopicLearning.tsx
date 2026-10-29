import * as React from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  BookOpen,
  Lightbulb,
  Code2,
  AlertTriangle,
  HelpCircle,
  FileText,
  RotateCw,
  CheckCircle2,
  Eye,
  EyeOff,
  ChevronRight,
  ChevronDown,
  Layers,
  GraduationCap,
  Quote,
  ShieldCheck,
  Search,
  Cpu,
} from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';

import {
  useCourses,
  useSyllabusTopics,
  useTopicContent,
  useGenerateTopicContent,
  Course,
  SyllabusTopic,
  TopicContent,
  PracticeQuestion,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';

export default function TopicLearning() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Selected Course and Topic
  const initialCourseId = searchParams.get('courseId') || '';
  const initialTopicId = searchParams.get('topicId') || '';

  const [selectedCourseId, setSelectedCourseId] = React.useState<string>(initialCourseId);
  const [selectedTopicId, setSelectedTopicId] = React.useState<string>(initialTopicId);
  const [topicSearch, setTopicSearch] = React.useState<string>('');

  // Practice questions revealed state { [questionIdx]: boolean }
  const [revealedAnswers, setRevealedAnswers] = React.useState<Record<number, boolean>>({});

  // Queries
  const { data: coursesData, isLoading: isLoadingCourses } = useCourses();
  const courses: Course[] = React.useMemo(() => {
    if (!coursesData) return [];
    if (Array.isArray(coursesData)) return coursesData;
    if ('courses' in coursesData && Array.isArray(coursesData.courses)) return coursesData.courses;
    return [];
  }, [coursesData]);

  // Set default course
  React.useEffect(() => {
    if (!selectedCourseId && courses.length > 0) {
      const defaultCourseId = String(courses[0].id);
      setSelectedCourseId(defaultCourseId);
      setSearchParams({ courseId: defaultCourseId });
    }
  }, [courses, selectedCourseId, setSearchParams]);

  // Fetch topics for current course
  const {
    data: topics = [],
    isLoading: isLoadingTopics,
    refetch: refetchTopics,
  } = useSyllabusTopics(selectedCourseId || undefined);

  // Set default topic when topics load
  React.useEffect(() => {
    if (topics.length > 0 && !selectedTopicId) {
      const defaultTopicId = String(topics[0].id);
      setSelectedTopicId(defaultTopicId);
      setSearchParams({ courseId: selectedCourseId, topicId: defaultTopicId });
    }
  }, [topics, selectedTopicId, selectedCourseId, setSearchParams]);

  const handleCourseChange = (id: string) => {
    setSelectedCourseId(id);
    setSelectedTopicId('');
    setSearchParams({ courseId: id });
  };

  const handleSelectTopic = (id: string) => {
    setSelectedTopicId(id);
    setRevealedAnswers({});
    setSearchParams({ courseId: selectedCourseId, topicId: id });
  };

  // Topic Content query
  const {
    data: topicContent,
    isLoading: isLoadingContent,
    isError: isContentError,
    error: contentError,
    refetch: refetchContent,
  } = useTopicContent(selectedTopicId || undefined);

  // Generate content mutation
  const generateMutation = useGenerateTopicContent();

  const handleGenerateContent = async (regenerate = false) => {
    if (!selectedTopicId) return;
    try {
      await generateMutation.mutateAsync({
        topicId: selectedTopicId,
        regenerate,
      });
      refetchContent();
    } catch {
      // Handled
    }
  };

  const toggleAnswerReveal = (idx: number) => {
    setRevealedAnswers((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const currentTopic = topics.find((t) => String(t.id) === selectedTopicId);

  // Group topics by unit for sidebar
  const topicsByUnit = React.useMemo(() => {
    const map: Record<number, SyllabusTopic[]> = {};
    const filtered = topics.filter(
      (t) => !topicSearch || t.topic_name.toLowerCase().includes(topicSearch.toLowerCase())
    );
    filtered.forEach((t) => {
      const u = t.unit_number || 1;
      if (!map[u]) map[u] = [];
      map[u].push(t);
    });
    return map;
  }, [topics, topicSearch]);

  if (isLoadingCourses) {
    return <LoadingSpinner text="Loading courses..." fullHeight />;
  }

  if (courses.length === 0) {
    return (
      <div className="space-y-6 pb-12">
        <PageHeader
          title="Interactive Topic Learning"
          description="Master syllabus concepts with structured definitions, analogies, and practice questions."
        />
        <EmptyState
          icon={BookOpen}
          title="No courses registered"
          description="Create a course and import your syllabus to begin interactive topic tutoring."
          actionLabel="Create Course"
          onAction={() => navigate('/courses/new')}
          className="py-16 bg-white"
        />
      </div>
    );
  }

  const isGenerating = generateMutation.isPending;

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Interactive Topic Tutor"
        description="Structured pedagogical lessons generated locally by your offline LLM, grounded in your lecture slides."
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

            {selectedTopicId && (
              <Button
                size="sm"
                onClick={() => handleGenerateContent(Boolean(topicContent))}
                disabled={isGenerating}
                className="gap-2 text-xs shadow-sm"
              >
                {isGenerating ? (
                  <>
                    <RotateCw className="h-3.5 w-3.5 animate-spin" />
                    Generating with LLM...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                    {topicContent ? 'Regenerate Content' : 'Generate Content'}
                  </>
                )}
              </Button>
            )}
          </div>
        }
      />

      {/* Main 2-column Layout: Topics Sidebar + Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Sidebar: Topics Selector */}
        <div className="lg:col-span-4 space-y-3">
          <Card className="bg-white border-gray-200">
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold text-gray-900">Syllabus Topics</CardTitle>
                <Badge variant="outline" className="text-[10px] text-gray-500">
                  {topics.length} Total
                </Badge>
              </div>

              {/* Topic search */}
              <div className="pt-2">
                <input
                  type="text"
                  placeholder="Filter topics..."
                  value={topicSearch}
                  onChange={(e) => setTopicSearch(e.target.value)}
                  className="h-8 w-full rounded-md border border-gray-200 bg-gray-50 px-2.5 text-xs focus:bg-white focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>
            </CardHeader>

            <CardContent className="p-2 pt-0">
              <ScrollArea maxHeight="calc(100vh - 280px)" className="pr-1">
                {isLoadingTopics ? (
                  <div className="py-8">
                    <LoadingSpinner size="sm" text="Loading topics..." />
                  </div>
                ) : topics.length === 0 ? (
                  <div className="p-4 text-center text-xs text-gray-500">
                    No topics found for this course. Add topics in course setup or run analysis.
                  </div>
                ) : (
                  <div className="space-y-4 pt-2">
                    {Object.keys(topicsByUnit)
                      .map(Number)
                      .sort((a, b) => a - b)
                      .map((unitNum) => (
                        <div key={unitNum} className="space-y-1">
                          <div className="px-2 py-1 text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                            Unit {unitNum}
                          </div>
                          <div className="space-y-1">
                            {topicsByUnit[unitNum].map((t) => {
                              const isSelected = String(t.id) === selectedTopicId;
                              return (
                                <button
                                  key={t.id}
                                  type="button"
                                  onClick={() => handleSelectTopic(String(t.id))}
                                  className={`w-full flex items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium text-left transition-colors cursor-pointer ${
                                    isSelected
                                      ? 'bg-primary-50 text-primary-900 font-semibold border border-primary-200/80 shadow-xs'
                                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                                  }`}
                                >
                                  <span className="truncate pr-2">{t.topic_name}</span>
                                  <StatusBadge
                                    status={t.effective_status || t.coverage_status}
                                    showIcon={false}
                                    className="text-[10px] px-1.5 py-0 shrink-0"
                                  />
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Right Content Area: Detailed Lesson */}
        <div className="lg:col-span-8 space-y-6">
          {/* Active Topic Banner */}
          {currentTopic && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-white border border-gray-200 shadow-xs">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs font-semibold bg-gray-50 text-gray-700">
                    Unit {currentTopic.unit_number}
                  </Badge>
                  <StatusBadge status={currentTopic.effective_status || currentTopic.coverage_status} />
                </div>
                <h2 className="text-xl font-bold text-gray-900 mt-1">{currentTopic.topic_name}</h2>
              </div>

              {topicContent?.model_used && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 px-2.5 py-1 rounded-md border border-gray-100 shrink-0">
                  <Cpu className="h-3.5 w-3.5 text-primary-600" />
                  <span>Model: {topicContent.model_used}</span>
                </div>
              )}
            </div>
          )}

          {/* Generating Banner */}
          {isGenerating && (
            <Alert variant="info" className="border-primary-200 bg-primary-50">
              <Sparkles className="h-4 w-4 text-primary-600 animate-spin" />
              <AlertTitle className="text-primary-950 font-semibold">
                Synthesizing Pedagogical Lesson (Offline CPU LLM)
              </AlertTitle>
              <AlertDescription className="text-primary-800 text-xs">
                Generating definitions, intuition, real-world analogies, step-by-step worked examples, and check-for-understanding practice questions. This may take 15–30 seconds.
              </AlertDescription>
            </Alert>
          )}

          {/* Lesson Content Sections */}
          {isLoadingContent ? (
            <LoadingSpinner text="Retrieving lesson content..." fullHeight />
          ) : isContentError ? (
            <ErrorDisplay
              title="Failed to load lesson content"
              error={contentError as Error}
              onRetry={() => refetchContent()}
            />
          ) : !topicContent ? (
            <EmptyState
              icon={Sparkles}
              title="No content generated yet for this topic"
              description="Click 'Generate Content' above to use your offline LLM to produce structured teaching material grounded in your uploaded slide decks."
              actionLabel="Generate Lesson Content"
              onAction={() => handleGenerateContent(false)}
              className="py-16 bg-white"
            />
          ) : (
            <div className="space-y-6">
              {/* 1. Formal Definition */}
              <Card className="border-primary-200/80 bg-gradient-to-br from-primary-50/50 via-white to-primary-50/20">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2 text-primary-800 font-semibold text-sm">
                    <BookOpen className="h-4 w-4" />
                    <span>Formal Academic Definition</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-900 text-sm sm:text-base font-medium leading-relaxed">
                    {topicContent.content.definition}
                  </p>
                </CardContent>
              </Card>

              {/* 2. Step-by-Step Explanation */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2 text-gray-900 font-semibold text-sm">
                    <GraduationCap className="h-4 w-4 text-primary-600" />
                    <span>In-Depth Conceptual Explanation</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed space-y-3 whitespace-pre-line text-sm">
                    {topicContent.content.explanation}
                  </div>
                </CardContent>
              </Card>

              {/* 3. Real-World Analogy */}
              {topicContent.content.analogy && (
                <Card className="border-blue-200 bg-blue-50/40">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2 text-blue-900 font-semibold text-sm">
                      <Lightbulb className="h-4 w-4 text-blue-600" />
                      <span>Intuition & Real-World Analogy</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-blue-950 text-sm leading-relaxed italic">
                      "{topicContent.content.analogy}"
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 4. Worked Example */}
              {topicContent.content.worked_example && (
                <Card className="border-gray-300">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2 text-gray-900 font-semibold text-sm">
                      <Code2 className="h-4 w-4 text-indigo-600" />
                      <span>Worked Example & Walkthrough</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="rounded-lg bg-gray-900 p-4 text-gray-100 font-mono text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap">
                      {topicContent.content.worked_example}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 5. Common Misconceptions */}
              {topicContent.content.misconceptions &&
                topicContent.content.misconceptions.length > 0 && (
                  <Card className="border-amber-200 bg-amber-50/40">
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2 text-amber-900 font-semibold text-sm">
                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                        <span>Common Student Misconceptions & Traps</span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2 text-xs sm:text-sm text-amber-950">
                        {topicContent.content.misconceptions.map((misc, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className="font-bold text-amber-600 shrink-0">&times;</span>
                            <span>{misc}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

              {/* 6. Source-Supported Points vs Supplemental Notes */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Source supported */}
                <Card className="border-emerald-200 bg-emerald-50/30">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2 text-emerald-900 font-semibold text-xs uppercase tracking-wider">
                      <ShieldCheck className="h-4 w-4 text-emerald-600" />
                      <span>Directly From Your Course Material</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {topicContent.content.source_supported_points &&
                    topicContent.content.source_supported_points.length > 0 ? (
                      <ul className="space-y-1.5 text-xs text-emerald-950">
                        {topicContent.content.source_supported_points.map((pt, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                            <span>{pt}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-gray-500 italic">
                        No direct points identified from current slides.
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* Supplemental */}
                <Card className="border-gray-200 bg-gray-50/50">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2 text-gray-700 font-semibold text-xs uppercase tracking-wider">
                      <Quote className="h-4 w-4 text-gray-500" />
                      <span>Supplemental Context (LLM Augmented)</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      {topicContent.content.supplemental_notes ||
                        'Standard academic background knowledge provided by the offline model to enrich understanding.'}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* 7. Practice Questions (Expandable Q&A) */}
              {topicContent.content.practice_questions &&
                topicContent.content.practice_questions.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
                      <HelpCircle className="h-5 w-5 text-primary-600" />
                      <span>Check Your Understanding Practice Questions</span>
                    </h3>

                    <div className="space-y-3">
                      {topicContent.content.practice_questions.map((q, qIdx) => {
                        const isRevealed = Boolean(revealedAnswers[qIdx]);
                        return (
                          <Card key={qIdx} className="border-gray-200">
                            <CardContent className="p-4 space-y-3">
                              <div className="flex items-start justify-between gap-4">
                                <div className="space-y-1 flex-1">
                                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary-600">
                                    Question {qIdx + 1}
                                  </span>
                                  <p className="text-sm font-semibold text-gray-900">
                                    {q.question}
                                  </p>
                                </div>

                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs h-8 shrink-0 bg-white"
                                  onClick={() => toggleAnswerReveal(qIdx)}
                                >
                                  {isRevealed ? (
                                    <>
                                      <EyeOff className="h-3.5 w-3.5 mr-1 text-gray-500" />
                                      Hide Solution
                                    </>
                                  ) : (
                                    <>
                                      <Eye className="h-3.5 w-3.5 mr-1 text-primary-600" />
                                      Reveal Answer
                                    </>
                                  )}
                                </Button>
                              </div>

                              {isRevealed && (
                                <div className="mt-3 pt-3 border-t border-gray-100 space-y-2 rounded-lg bg-gray-50 p-3 text-xs animate-in fade-in-50 duration-150">
                                  <div>
                                    <span className="font-bold text-gray-900 block mb-1">
                                      Answer:
                                    </span>
                                    <p className="text-gray-800">{q.answer}</p>
                                  </div>
                                  {q.explanation && (
                                    <div className="pt-1 border-t border-gray-200/60">
                                      <span className="font-bold text-gray-700 block mb-0.5">
                                        Explanation:
                                      </span>
                                      <p className="text-gray-600 leading-relaxed">
                                        {q.explanation}
                                      </p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* 8. Source References (Citations) */}
              {topicContent.source_refs && topicContent.source_refs.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
                    <FileText className="h-4 w-4 text-gray-400" />
                    <span>Citations & Slide References</span>
                  </h3>

                  <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
                    {topicContent.source_refs.map((ref, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col sm:flex-row sm:items-center justify-between p-3 gap-2 text-xs"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="h-4 w-4 text-primary-600 shrink-0" />
                          <span className="font-semibold text-gray-800 truncate">
                            {ref.source_filename}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 shrink-0 text-gray-500">
                          {ref.slide_number && (
                            <Badge variant="secondary" className="text-[10px]">
                              Slide {ref.slide_number}
                            </Badge>
                          )}
                          {ref.page_number && (
                            <Badge variant="secondary" className="text-[10px]">
                              Page {ref.page_number}
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
