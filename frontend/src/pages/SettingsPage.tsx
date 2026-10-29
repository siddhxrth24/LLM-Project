import React from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { useSystemStatus, useModelStatus, useLoadModels } from '@/lib/queries';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { HardDrive, Cpu, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';

export default function SettingsPage() {
  const { data: status, isLoading, refetch } = useSystemStatus();
  const { data: modelStatus } = useModelStatus();
  const loadMutation = useLoadModels();

  const handleLoadModels = async () => {
    await loadMutation.mutateAsync({
      load_llm: true,
      load_embedding: true,
      load_lora: false,
    });
    refetch();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & System Status"
        description="Monitor local LLM models, vector storage, and offline inference parameters."
        actions={
          <Button
            onClick={handleLoadModels}
            disabled={loadMutation.isPending}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${loadMutation.isPending ? 'animate-spin' : ''}`}
            />
            {loadMutation.isPending ? 'Loading Models...' : 'Reload ML Models'}
          </Button>
        }
      />

      {isLoading ? (
        <LoadingSpinner text="Checking local offline components..." fullHeight />
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Models */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-indigo-600" />
                  Local AI Models
                </CardTitle>
                <CardDescription>Offline language and embedding checkpoints</CardDescription>
              </div>
              <Badge variant={status?.models?.llm_loaded ? 'success' : 'warning'}>
                {status?.models?.llm_loaded ? 'Online (Offline-Mode)' : 'Not Loaded'}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">LLM Model:</span>
                <span className="font-mono text-xs font-semibold text-gray-800">
                  {status?.models?.llm_model_id || 'qwen2.5-1.5b-instruct'}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">LLM Device:</span>
                <span className="font-medium text-gray-800">
                  {status?.models?.llm_device || 'cpu/cuda'}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">Embedding Model:</span>
                <span className="font-mono text-xs font-semibold text-gray-800">
                  {status?.models?.embedding_model_id || 'all-MiniLM-L6-v2'}
                </span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-500">Embedding Loaded:</span>
                <span className="flex items-center gap-1 font-medium">
                  {status?.models?.embedding_loaded ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Yes
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-gray-400" /> No
                    </>
                  )}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Storage & Persistence */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HardDrive className="h-5 w-5 text-emerald-600" />
                Local Storage & Database
              </CardTitle>
              <CardDescription>SQLite and ChromaDB vector persistence</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">Database Status:</span>
                <span className="font-medium text-emerald-600">
                  {status?.storage?.database_connected ? 'Connected' : 'Offline'}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">Total Courses:</span>
                <span className="font-semibold text-gray-800">
                  {status?.storage?.total_courses ?? 0}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-500">Total Documents:</span>
                <span className="font-semibold text-gray-800">
                  {status?.storage?.total_documents ?? 0}
                </span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-500">Vector Chunks:</span>
                <span className="font-semibold text-gray-800">
                  {status?.storage?.total_chunks ?? 0}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
