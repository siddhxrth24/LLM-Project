import React, { useState } from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { useCourses, useSyllabusTopics, useTopicContent, useGenerateTopicContent } from '@/lib/queries';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Sparkles, BookOpen } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';

export default function TopicsPage() {
  const { data: coursesData } = useCourses();
  const courses = Array.isArray(coursesData) ? coursesData : coursesData?.courses || [];
  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>(
    courses[0]?.id
  );

  const { data: topics = [] } = useSyllabusTopics(selectedCourseId);
  const [selectedTopicId, setSelectedTopicId] = useState<number | undefined>(
    topics[0]?.id
  );

  const { data: topicContent, isLoading: contentLoading } = useTopicContent(selectedTopicId);
  const generateMutation = useGenerateTopicContent();

  const handleGenerate = () => {
    if (selectedTopicId) {
      generateMutation.mutate({ topicId: selectedTopicId, regenerate: true });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Topic Teacher"
        description="Offline conceptual explanations, real-world analogies, and interactive check questions."
        actions={
          <Button
            onClick={handleGenerate}
            disabled={generateMutation.isPending || !selectedTopicId}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {generateMutation.isPending ? 'Teaching...' : 'Teach Topic'}
          </Button>
        }
      />

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full sm:w-64">
          <label className="block text-xs font-medium text-gray-500 mb-1">Course</label>
          <Select
            value={selectedCourseId}
            onChange={(e) => {
              const cid = Number(e.target.value);
              setSelectedCourseId(cid);
            }}
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="w-full sm:w-80">
          <label className="block text-xs font-medium text-gray-500 mb-1">Topic</label>
          <Select
            value={selectedTopicId}
            onChange={(e) => setSelectedTopicId(Number(e.target.value))}
          >
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                Unit {t.unit_number}: {t.topic_name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {contentLoading ? (
        <LoadingSpinner text="Loading lesson material..." fullHeight />
      ) : topicContent ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">{topicContent.topic_name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h4 className="font-semibold text-gray-900 mb-1 text-sm uppercase tracking-wide text-primary-700">
                  Definition
                </h4>
                <p className="text-gray-700 leading-relaxed bg-primary-50/50 p-4 rounded-lg border border-primary-100">
                  {topicContent.content.definition}
                </p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1 text-sm uppercase tracking-wide text-gray-700">
                  Conceptual Explanation
                </h4>
                <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                  {topicContent.content.explanation}
                </p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1 text-sm uppercase tracking-wide text-amber-700">
                  Intuitive Analogy
                </h4>
                <div className="p-4 rounded-lg bg-amber-50/60 border border-amber-200 text-gray-800 italic">
                  "{topicContent.content.analogy}"
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1 text-sm uppercase tracking-wide text-gray-700">
                  Worked Example
                </h4>
                <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 text-gray-800 whitespace-pre-line font-mono text-xs sm:text-sm">
                  {topicContent.content.worked_example}
                </div>
              </div>

              {topicContent.content.practice_questions?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide text-emerald-700">
                    Practice Questions
                  </h4>
                  <div className="space-y-3">
                    {topicContent.content.practice_questions.map((pq, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-lg border border-gray-200 bg-white space-y-2"
                      >
                        <p className="font-medium text-gray-900 text-sm">
                          Q{idx + 1}: {pq.question}
                        </p>
                        <div className="text-xs text-emerald-800 bg-emerald-50/70 p-2.5 rounded border border-emerald-100">
                          <span className="font-semibold">Answer: </span>
                          {pq.answer}
                          <p className="mt-1 text-gray-600">{pq.explanation}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-16 text-sm text-gray-500">
          <BookOpen className="h-10 w-10 mx-auto mb-3 text-gray-400 stroke-1" />
          Choose a topic and click "Teach Topic" to synthesize an offline lesson.
        </div>
      )}
    </div>
  );
}
