import * as React from 'react';
import { useSearchParams, useNavigate, useParams } from 'react-router-dom';
import {
  FileText,
  Presentation,
  UploadCloud,
  Trash2,
  Play,
  RotateCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  BookOpen,
  Info,
} from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';

import {
  useCourses,
  useDocuments,
  useUnitDocuments,
  useUploadDocument,
  useDeleteDocument,
  useProcessDocument,
  Course,
  DocumentItem,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { FileUploadZone } from '@/components/shared/FileUploadZone';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export default function UnitUploads() {
  const navigate = useNavigate();
  const params = useParams<{ courseId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  // Selected Course & Unit State
  const initialCourseId = params.courseId || searchParams.get('courseId') || '';
  const initialUnit = searchParams.get('unit') || '1';

  const [selectedCourseId, setSelectedCourseId] = React.useState<string>(initialCourseId);
  const [activeUnit, setActiveUnit] = React.useState<string>(initialUnit);

  // Document to delete modal state
  const [docToDelete, setDocToDelete] = React.useState<DocumentItem | null>(null);

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
      setSearchParams({ courseId: defaultId, unit: activeUnit });
    }
  }, [courses, selectedCourseId, activeUnit, setSearchParams]);

  // Sync state to URL params
  const handleCourseChange = (id: string) => {
    setSelectedCourseId(id);
    setSearchParams({ courseId: id, unit: activeUnit });
  };

  const handleUnitChange = (unit: string) => {
    setActiveUnit(unit);
    if (selectedCourseId) {
      setSearchParams({ courseId: selectedCourseId, unit });
    }
  };

  const numericUnit = parseInt(activeUnit, 10) || 1;

  // Fetch all documents for this course to calculate counts per unit
  const { data: allDocs = [] } = useDocuments(selectedCourseId || undefined);

  // Fetch unit specific documents
  const {
    data: unitDocs = [],
    isLoading: isLoadingDocs,
    isError: isDocsError,
    error: docsError,
    refetch: refetchDocs,
  } = useUnitDocuments(selectedCourseId || undefined, numericUnit);

  // Mutations
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  const processMutation = useProcessDocument();

  // Document count per unit (1 to 5)
  const unitCounts = React.useMemo(() => {
    const counts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    if (Array.isArray(allDocs)) {
      allDocs.forEach((doc) => {
        // unit_id or unit_number
        const u = doc.unit_id || 1;
        if (counts[u] !== undefined) {
          counts[u] += 1;
        }
      });
    }
    return counts;
  }, [allDocs]);

  // Handle file uploads
  const handleFileUpload = async (files: File[]) => {
    if (!selectedCourseId) return;

    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
      formData.append('file', file);
    });

    try {
      await uploadMutation.mutateAsync({
        courseId: selectedCourseId,
        unitNumber: numericUnit,
        formData,
      });
    } catch {
      // Handled by React Query
    }
  };

  const handleProcessDocument = async (docId: number) => {
    if (!selectedCourseId) return;
    try {
      await processMutation.mutateAsync({
        id: docId,
        courseId: selectedCourseId,
      });
    } catch {
      // Handled by React Query
    }
  };

  const handleDeleteConfirm = async () => {
    if (!docToDelete || !selectedCourseId) return;
    try {
      await deleteMutation.mutateAsync({
        id: docToDelete.id,
        courseId: selectedCourseId,
      });
      setDocToDelete(null);
    } catch {
      // Handled by React Query
    }
  };

  if (isLoadingCourses) {
    return <LoadingSpinner text="Loading courses..." fullHeight />;
  }

  if (courses.length === 0) {
    return (
      <div className="space-y-6 pb-12">
        <PageHeader
          title="Document Management"
          description="Upload and index your lecture notes and slide decks for offline semantic search."
        />
        <EmptyState
          icon={BookOpen}
          title="No courses registered yet"
          description="Before uploading documents, please create a course outline to organize your units."
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
        title="Document Management"
        description="Organize lecture slides and PDF notes into curriculum units. Files are chunked and indexed into ChromaDB offline."
        actions={
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Active Course:</span>
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
          </div>
        }
      />

      {/* Info notice about offline parsing */}
      <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50/70 p-4 text-xs text-blue-900 shadow-xs">
        <Info className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-semibold text-blue-950">Local Parsing & Vector Indexing</p>
          <p className="text-blue-800/90 leading-relaxed">
            Uploaded PDFs and PPTX files are processed on your machine with pypdf and python-pptx, then embedded into the local offline Chroma vector database. No data leaves your computer.
          </p>
        </div>
      </div>

      {/* Unit Tabs */}
      <Tabs value={activeUnit} onValueChange={handleUnitChange}>
        <TabsList className="grid grid-cols-5 w-full max-w-2xl bg-gray-100 p-1">
          {[1, 2, 3, 4, 5].map((u) => (
            <TabsTrigger
              key={u}
              value={String(u)}
              className="text-xs py-2 gap-1.5 data-[state=active]:bg-white"
            >
              <span>Unit {u}</span>
              <span
                className={`inline-flex items-center justify-center rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                  unitCounts[u] > 0
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {unitCounts[u]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        {[1, 2, 3, 4, 5].map((unitNum) => (
          <TabsContent key={unitNum} value={String(unitNum)} className="space-y-6 mt-4">
            {/* Upload Zone Card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">Upload Notes for Unit {unitNum}</CardTitle>
                    <CardDescription className="text-xs">
                      Attach lecture presentations (.pptx) or textbook chapters (.pdf) specific to Unit {unitNum}.
                    </CardDescription>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Unit {unitNum}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <FileUploadZone
                  onUpload={handleFileUpload}
                  isLoading={uploadMutation.isPending}
                  acceptText="PDF or PPTX presentation slides up to 50MB"
                />
              </CardContent>
            </Card>

            {/* Document List Card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">
                      Unit {unitNum} Materials ({unitDocs.length})
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Extracted documents and processing status for this unit.
                    </CardDescription>
                  </div>
                  {unitDocs.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => refetchDocs()}
                      className="text-xs h-8"
                    >
                      <RotateCw className="h-3.5 w-3.5 mr-1 text-gray-500" />
                      Refresh
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent>
                {isLoadingDocs ? (
                  <LoadingSpinner text={`Loading Unit ${unitNum} documents...`} />
                ) : isDocsError ? (
                  <ErrorDisplay
                    title="Failed to load documents"
                    error={docsError as Error}
                    onRetry={() => refetchDocs()}
                  />
                ) : unitDocs.length === 0 ? (
                  <EmptyState
                    icon={UploadCloud}
                    title={`No materials uploaded for Unit ${unitNum}`}
                    description="Upload your slides or lecture PDFs above to let SemesTrack analyze syllabus coverage."
                    className="py-12 border-dashed bg-gray-50/50"
                  />
                ) : (
                  <div className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden bg-white">
                    {unitDocs.map((doc) => {
                      const isPptx =
                        doc.file_type?.toLowerCase() === 'pptx' ||
                        doc.original_filename?.toLowerCase().endsWith('.pptx');

                      const formattedDate = doc.created_at
                        ? (() => {
                            try {
                              const parsed = parseISO(doc.created_at);
                              return isValid(parsed)
                                ? format(parsed, 'MMM dd, yyyy HH:mm')
                                : doc.created_at;
                            } catch {
                              return doc.created_at;
                            }
                          })()
                        : 'Recently';

                      const isProcessingThis =
                        processMutation.isPending &&
                        processMutation.variables?.id === doc.id;

                      return (
                        <div
                          key={doc.id}
                          className="flex flex-col sm:flex-row sm:items-center justify-between p-4 gap-4 hover:bg-gray-50/80 transition-colors"
                        >
                          {/* File info */}
                          <div className="flex items-start gap-3.5 min-w-0">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-700 shrink-0 mt-0.5">
                              {isPptx ? (
                                <Presentation className="h-5 w-5 text-amber-600" />
                              ) : (
                                <FileText className="h-5 w-5 text-primary-600" />
                              )}
                            </div>
                            <div className="min-w-0 space-y-1">
                              <p className="font-semibold text-gray-900 text-sm truncate max-w-md">
                                {doc.original_filename || doc.filename}
                              </p>
                              <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                                <span className="uppercase font-medium text-gray-600">
                                  {isPptx ? 'PPTX Slide Deck' : 'PDF Document'}
                                </span>
                                <span>&bull;</span>
                                <span>{formatBytes(doc.file_size)}</span>
                                <span>&bull;</span>
                                <span>{formattedDate}</span>
                              </div>

                              {/* Pages and Chunks badge */}
                              {doc.status === 'completed' && (
                                <div className="flex items-center gap-2 pt-1 text-[11px] text-gray-600">
                                  <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5">
                                    <Layers className="h-3 w-3 text-gray-500" />
                                    <span>
                                      {doc.page_count} {isPptx ? 'slides' : 'pages'}
                                    </span>
                                  </span>
                                  <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5">
                                    <span>{doc.chunk_count} indexed chunks</span>
                                  </span>
                                </div>
                              )}

                              {/* Error message if failed */}
                              {doc.status === 'failed' && doc.error_message && (
                                <p className="text-xs text-red-600 font-medium pt-1">
                                  Error: {doc.error_message}
                                </p>
                              )}
                            </div>
                          </div>

                          {/* Status and Action Buttons */}
                          <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                            <StatusBadge status={doc.status} />

                            {/* Process Button if pending or failed */}
                            {(doc.status === 'pending' || doc.status === 'failed') && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-8 text-xs bg-white text-primary-600 hover:text-primary-700"
                                onClick={() => handleProcessDocument(doc.id)}
                                disabled={isProcessingThis || processMutation.isPending}
                              >
                                {isProcessingThis ? (
                                  <>
                                    <RotateCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                    Indexing...
                                  </>
                                ) : (
                                  <>
                                    <Play className="h-3.5 w-3.5 mr-1.5" />
                                    Process Now
                                  </>
                                )}
                              </Button>
                            )}

                            {/* Delete Button */}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-gray-400 hover:text-red-600 hover:bg-red-50"
                              onClick={() => setDocToDelete(doc)}
                              aria-label="Delete document"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      {/* Delete Confirmation Modal */}
      <Dialog open={Boolean(docToDelete)} onOpenChange={(open) => !open && setDocToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-600 flex items-center gap-2">
              <Trash2 className="h-5 w-5" />
              Remove Document
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete{' '}
              <strong className="text-gray-900">
                {docToDelete?.original_filename || docToDelete?.filename}
              </strong>
              ? This will remove all extracted text chunks and embeddings from the offline index.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDocToDelete(null)}
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
              {deleteMutation.isPending ? 'Removing...' : 'Delete File'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
