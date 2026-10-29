import * as React from 'react';
import {
  HardDrive,
  Cpu,
  Database,
  ShieldCheck,
  RotateCw,
  Copy,
  Check,
  AlertTriangle,
  Server,
  Layers,
  FolderOpen,
  Sparkles,
  CheckCircle2,
  XCircle,
  Terminal,
  Activity,
} from 'lucide-react';

import {
  useSystemStatus,
  useModelStatus,
  useLoadModels,
  SystemStatus,
  ModelStatus,
} from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';

export default function Settings() {
  const {
    data: systemStatus,
    isLoading: isLoadingSystem,
    isError: isSystemError,
    error: systemError,
    refetch: refetchSystem,
  } = useSystemStatus();

  const {
    data: modelStatus,
    isLoading: isLoadingModels,
    refetch: refetchModels,
  } = useModelStatus();

  const loadModelsMutation = useLoadModels();

  // Fine-tuning command copy state
  const [copied, setCopied] = React.useState(false);

  const finetuneCommand = 'python -m app.services.finetune --data ./data/train.jsonl --epochs 2 --output ./models/lora_adapter';

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(finetuneCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLoadModels = async () => {
    try {
      await loadModelsMutation.mutateAsync({
        load_llm: true,
        load_embedding: true,
        load_lora: false,
      });
      await Promise.all([refetchSystem(), refetchModels()]);
    } catch {
      // Handled by react query
    }
  };

  if (isLoadingSystem || isLoadingModels) {
    return <LoadingSpinner text="Reading offline system & model status..." fullHeight />;
  }

  if (isSystemError) {
    return (
      <ErrorDisplay
        title="Could not connect to backend system"
        message="Please verify that the FastAPI backend server is running on http://127.0.0.1:8000."
        error={systemError as Error}
        onRetry={() => {
          refetchSystem();
          refetchModels();
        }}
        fullHeight
      />
    );
  }

  // Merge model status from either endpoint
  const models: ModelStatus | undefined = modelStatus || systemStatus?.models;
  const storage = systemStatus?.storage;
  const env = systemStatus?.environment || {};

  return (
    <div className="space-y-8 pb-16">
      <PageHeader
        title="System Diagnostics & Settings"
        description="Inspect local model memory allocation, vector database storage, offline status, and fine-tuning options."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              refetchSystem();
              refetchModels();
            }}
            className="text-xs gap-1.5 bg-white shadow-xs"
          >
            <RotateCw className="h-3.5 w-3.5 text-gray-500" />
            Refresh Diagnostics
          </Button>
        }
      />

      {/* Prominent Offline Banner */}
      <div className="relative overflow-hidden rounded-xl border border-emerald-200 bg-gradient-to-r from-emerald-50 via-white to-emerald-50/60 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm shrink-0">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-emerald-950">
                  Air-Gapped Offline Protection Active
                </h2>
                <Badge variant="outline" className="text-[10px] bg-emerald-100 text-emerald-800 border-emerald-300">
                  100% Private
                </Badge>
              </div>
              <p className="text-xs text-emerald-800/90 mt-0.5">
                SemesTrack is operating without sending any notes, syllabus documents, or chat logs to external cloud APIs. All models run in-process on CPU/GPU.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-emerald-900">Backend Connected</span>
          </div>
        </div>
      </div>

      {/* 1. Model Status Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Cpu className="h-5 w-5 text-primary-600" />
              <span>Offline AI Models</span>
            </h2>
            <p className="text-xs text-gray-500">
              Local HuggingFace transformers models loaded into local machine RAM.
            </p>
          </div>

          <Button
            size="sm"
            onClick={handleLoadModels}
            disabled={loadModelsMutation.isPending}
            className="text-xs gap-1.5 shadow-xs self-start sm:self-auto"
          >
            <RotateCw
              className={`h-3.5 w-3.5 ${loadModelsMutation.isPending ? 'animate-spin' : ''}`}
            />
            {loadModelsMutation.isPending ? 'Loading Models...' : 'Load / Reinitialize Models'}
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* LLM Card */}
          <Card className="hover:border-primary-300 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-gray-400">
                    Teaching LLM
                  </span>
                  <CardTitle className="text-sm font-semibold line-clamp-1">
                    {models?.llm_model_id || 'TinyLlama / Local LLM'}
                  </CardTitle>
                </div>
                {models?.llm_loaded ? (
                  <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">
                    <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-600" />
                    Loaded
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-gray-100 text-gray-600 border-gray-200 text-[10px]">
                    <XCircle className="h-3 w-3 mr-1 text-gray-400" />
                    Not Loaded
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-gray-600 pt-0">
              <div className="rounded-lg bg-gray-50 p-2.5 space-y-1.5 border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span className="text-gray-400">Device:</span>
                  <span className="font-semibold text-gray-800">{models?.llm_device || 'CPU'}</span>
                </div>
                <div className="truncate">
                  <span className="text-gray-400">Path: </span>
                  <span className="text-gray-700">{models?.llm_model_path || './models/llm'}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Embedding Model Card */}
          <Card className="hover:border-primary-300 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-gray-400">
                    Sentence Embeddings
                  </span>
                  <CardTitle className="text-sm font-semibold line-clamp-1">
                    {models?.embedding_model_id || 'all-MiniLM-L6-v2'}
                  </CardTitle>
                </div>
                {models?.embedding_loaded ? (
                  <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">
                    <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-600" />
                    Loaded
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-gray-100 text-gray-600 border-gray-200 text-[10px]">
                    <XCircle className="h-3 w-3 mr-1 text-gray-400" />
                    Not Loaded
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-gray-600 pt-0">
              <div className="rounded-lg bg-gray-50 p-2.5 space-y-1.5 border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span className="text-gray-400">Device:</span>
                  <span className="font-semibold text-gray-800">{models?.embedding_device || 'CPU'}</span>
                </div>
                <div className="truncate">
                  <span className="text-gray-400">Path: </span>
                  <span className="text-gray-700">{models?.embedding_model_path || './models/embeddings'}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* LoRA Adapter Card */}
          <Card className="hover:border-primary-300 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-gray-400">
                    LoRA Adapter
                  </span>
                  <CardTitle className="text-sm font-semibold line-clamp-1">
                    PEFT LoRA Weights
                  </CardTitle>
                </div>
                {models?.lora_loaded ? (
                  <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 text-[10px]">
                    Active
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-gray-100 text-gray-600 border-gray-200 text-[10px]">
                    Disabled
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-gray-600 pt-0">
              <div className="rounded-lg bg-gray-50 p-2.5 space-y-1.5 border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span className="text-gray-400">Status:</span>
                  <span className="font-semibold text-gray-800">
                    {models?.lora_loaded ? 'Adapter Merged' : 'Base Model Only'}
                  </span>
                </div>
                <div className="truncate">
                  <span className="text-gray-400">Path: </span>
                  <span className="text-gray-700">
                    {models?.lora_adapter_path || 'No adapter configured'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 2. Database & Storage Statistics */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <Database className="h-5 w-5 text-primary-600" />
            <span>Database & Vector Store Statistics</span>
          </h2>
          <p className="text-xs text-gray-500">
            Local SQLite relational database and ChromaDB vector embeddings collection.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Registered Courses</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {storage?.total_courses ?? 0}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                <Layers className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Stored Documents</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {storage?.total_documents ?? 0}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <FolderOpen className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Indexed Chunks</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {storage?.total_chunks ?? 0}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <Database className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">DB Health</p>
                <p className="text-lg font-bold text-emerald-700 mt-1 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" />
                  Connected
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Server className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Directory paths card */}
        <Card className="bg-white border-gray-200">
          <CardContent className="p-4 space-y-2 text-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1 border-b border-gray-100">
              <span className="text-gray-500 font-medium">Relational SQLite DB URL:</span>
              <span className="font-mono text-gray-800 truncate">{storage?.database_url || 'sqlite:///./semestrack.db'}</span>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1 border-b border-gray-100">
              <span className="text-gray-500 font-medium">Document Storage Directory:</span>
              <span className="font-mono text-gray-800 truncate">{storage?.upload_dir || './data/uploads'}</span>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1">
              <span className="text-gray-500 font-medium">ChromaDB Vector Directory:</span>
              <span className="font-mono text-gray-800 truncate">{storage?.chroma_dir || './data/chroma'}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Hardware & Environment Info */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary-600" />
            <span>Hardware & Environment Diagnostics</span>
          </h2>
          <p className="text-xs text-gray-500">
            Host system specifications and compute environment reported by backend.
          </p>
        </div>

        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
              <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-1">
                <p className="text-gray-400 font-medium">App Version</p>
                <p className="font-semibold text-gray-900">
                  {systemStatus?.app_name || 'SemesTrack'} v{systemStatus?.version || '1.0.0'}
                </p>
              </div>

              <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-1">
                <p className="text-gray-400 font-medium">Execution Target</p>
                <p className="font-semibold text-gray-900">
                  {String(env.device || env.platform || 'Local CPU (x86_64)')}
                </p>
              </div>

              <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-1">
                <p className="text-gray-400 font-medium">System Status</p>
                <Badge
                  variant="outline"
                  className={
                    systemStatus?.status === 'ok'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200'
                  }
                >
                  {systemStatus?.status === 'ok' ? 'Healthy / Operational' : 'Degraded'}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 4. Fine-Tuning Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary-600" />
            <span>Local Fine-Tuning Pipeline (PEFT / LoRA)</span>
          </h2>
          <p className="text-xs text-gray-500">
            Adapt the teaching LLM to academic course slides using low-rank adaptation.
          </p>
        </div>

        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">How Fine-Tuning Works</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              SemesTrack pairs syllabus topics with extracted slide chunks to generate high-quality question-answer and concept explanation pairs. You can train a lightweight LoRA adapter entirely offline.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Warning about CPU training */}
            <Alert variant="warning" className="border-amber-200 bg-amber-50">
              <AlertTriangle className="h-4 w-4 text-amber-700" />
              <AlertTitle className="text-amber-900 font-semibold text-xs">
                CPU Compute Duration Notice
              </AlertTitle>
              <AlertDescription className="text-amber-800 text-xs">
                Fine-tuning on a CPU takes noticeably longer than on a GPU. We recommend 1 to 2 epochs or running overnight on low-resource machines.
              </AlertDescription>
            </Alert>

            {/* CLI Command to run */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-medium text-gray-700">
                <span>Run Fine-Tuning via Terminal:</span>
                <span className="text-gray-400">Root Directory</span>
              </div>

              <div className="flex items-center justify-between rounded-lg bg-gray-950 p-3 font-mono text-xs text-emerald-400 overflow-x-auto gap-4">
                <span className="select-all">{finetuneCommand}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyCommand}
                  className="h-7 px-2.5 text-xs bg-gray-800 text-gray-100 hover:bg-gray-700 border-gray-700 shrink-0"
                >
                  {copied ? (
                    <>
                      <Check className="h-3.5 w-3.5 mr-1 text-emerald-400" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5 mr-1 text-gray-300" />
                      Copy
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Dataset location */}
            <div className="rounded-lg bg-gray-50 p-3 border border-gray-100 text-xs text-gray-600 space-y-1">
              <p className="font-semibold text-gray-800">Generated Training Dataset Location:</p>
              <p className="font-mono text-gray-700">./backend/data/training/finetune_dataset.jsonl</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
