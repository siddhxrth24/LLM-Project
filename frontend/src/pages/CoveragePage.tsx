import React, { useState } from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { useCourses, useCoverageData, useAnalyzeCoverage } from '@/lib/queries';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';

export default function CoveragePage() {
  const { data: coursesData } = useCourses();
  const courses = Array.isArray(coursesData) ? coursesData : coursesData?.courses || [];
  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>(
    courses[0]?.id
  );

  const { data: coverage, isLoading } = useCoverageData(selectedCourseId);
  const analyzeMutation = useAnalyzeCoverage();

  const handleRunAnalysis = () => {
    if (selectedCourseId) {
      analyzeMutation.mutate(selectedCourseId);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Syllabus Coverage"
        description="Verify how completely your uploaded slides and notes cover every official syllabus topic."
        actions={
          <Button
            onClick={handleRunAnalysis}
            disabled={analyzeMutation.isPending || !selectedCourseId}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${analyzeMutation.isPending ? 'animate-spin' : ''}`}
            />
            {analyzeMutation.isPending ? 'Analyzing...' : 'Run Coverage Analysis'}
          </Button>
        }
      />

      <div className="w-full sm:w-64">
        <label className="block text-xs font-medium text-gray-500 mb-1">Select Course</label>
        <Select
          value={selectedCourseId}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
        >
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>

      {isLoading ? (
        <LoadingSpinner text="Loading coverage data..." fullHeight />
      ) : coverage ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Overall Coverage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Completion Score</span>
                <span className="text-xl font-bold text-gray-900">
                  {Math.round(coverage.coverage_percentage)}%
                </span>
              </div>
              <Progress value={coverage.coverage_percentage} />

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4 border-t border-gray-100">
                <div className="text-center p-3 rounded-lg bg-emerald-50">
                  <div className="text-lg font-bold text-emerald-700">
                    {coverage.covered_count}
                  </div>
                  <div className="text-xs text-emerald-600">Covered</div>
                </div>
                <div className="text-center p-3 rounded-lg bg-blue-50">
                  <div className="text-lg font-bold text-blue-700">
                    {coverage.partially_covered_count}
                  </div>
                  <div className="text-xs text-blue-600">Partially Covered</div>
                </div>
                <div className="text-center p-3 rounded-lg bg-amber-50">
                  <div className="text-lg font-bold text-amber-700">
                    {coverage.needs_review_count}
                  </div>
                  <div className="text-xs text-amber-600">Needs Review</div>
                </div>
                <div className="text-center p-3 rounded-lg bg-red-50">
                  <div className="text-lg font-bold text-red-700">
                    {coverage.not_found_count}
                  </div>
                  <div className="text-xs text-red-600">Not Found</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Topic Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-gray-100">
                {coverage.topics?.map((topic) => (
                  <div
                    key={topic.id}
                    className="flex items-center justify-between py-3 text-sm"
                  >
                    <div>
                      <p className="font-medium text-gray-900">
                        Unit {topic.unit_number}: {topic.topic_name}
                      </p>
                      <p className="text-xs text-gray-500">
                        Confidence: {Math.round(topic.coverage_confidence * 100)}% · Est:{' '}
                        {topic.estimated_hours} hrs
                      </p>
                    </div>
                    <StatusBadge status={topic.effective_status} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-12 text-sm text-gray-500">
          Select a course and click "Run Coverage Analysis" to inspect syllabus status.
        </div>
      )}
    </div>
  );
}
