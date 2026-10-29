import * as React from 'react';
import { UploadCloud, FileText, Presentation, X, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface FileUploadZoneProps {
  onUpload: (files: File[]) => void | Promise<void>;
  isLoading?: boolean;
  maxFiles?: number;
  className?: string;
  acceptText?: string;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.pptx'];
const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.ms-powerpoint',
];

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function FileUploadZone({
  onUpload,
  isLoading = false,
  maxFiles = 10,
  className,
  acceptText = 'PDF or PPTX up to 50MB each',
}: FileUploadZoneProps) {
  const [isDragOver, setIsDragOver] = React.useState(false);
  const [selectedFiles, setSelectedFiles] = React.useState<File[]>([]);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  const isValidFile = (file: File): boolean => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    const matchesExt = ALLOWED_EXTENSIONS.includes(ext);
    const matchesType = ALLOWED_TYPES.includes(file.type);
    return matchesExt || matchesType;
  };

  const handleFiles = (incomingFiles: FileList | File[]) => {
    setErrorMessage(null);
    const filesArray = Array.from(incomingFiles);
    const valid: File[] = [];
    const invalid: string[] = [];

    filesArray.forEach((file) => {
      if (isValidFile(file)) {
        valid.push(file);
      } else {
        invalid.push(file.name);
      }
    });

    if (invalid.length > 0) {
      setErrorMessage(
        `Unsupported file type for: ${invalid.join(', ')}. Only PDF and PPTX files are supported.`
      );
    }

    if (valid.length > 0) {
      setSelectedFiles((prev) => {
        // Filter out duplicate filenames
        const prevNames = new Set(prev.map((f) => f.name));
        const newFiles = valid.filter((f) => !prevNames.has(f.name));
        const combined = [...prev, ...newFiles];
        if (combined.length > maxFiles) {
          setErrorMessage(`You can select at most ${maxFiles} files at once.`);
          return combined.slice(0, maxFiles);
        }
        return combined;
      });
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  const handleUploadClick = async () => {
    if (selectedFiles.length === 0 || isLoading) return;
    await onUpload(selectedFiles);
    setSelectedFiles([]);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  const getFileIcon = (file: File) => {
    const isPptx = file.name.toLowerCase().endsWith('.pptx');
    if (isPptx) {
      return <Presentation className="h-5 w-5 text-amber-600 shrink-0" />;
    }
    return <FileText className="h-5 w-5 text-primary-600 shrink-0" />;
  };

  return (
    <div className={cn('w-full space-y-4', className)}>
      {/* Drop Zone Box */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-200 select-none',
          isDragOver
            ? 'border-primary-500 bg-primary-50/60 scale-[1.005]'
            : 'border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50/80',
          isLoading && 'pointer-events-none opacity-60'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
          }}
          disabled={isLoading}
        />

        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-600 mb-3">
          <UploadCloud className="h-6 w-6 stroke-[1.75]" />
        </div>

        <div className="text-sm font-semibold text-gray-900">
          <span>Click to upload</span> or drag and drop
        </div>
        <p className="mt-1 text-xs text-gray-500">{acceptText}</p>
      </div>

      {/* Error message */}
      {errorMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>Selected Files ({selectedFiles.length})</span>
            <button
              type="button"
              onClick={() => setSelectedFiles([])}
              className="text-xs text-red-600 hover:underline cursor-pointer"
              disabled={isLoading}
            >
              Clear all
            </button>
          </div>

          <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
            {selectedFiles.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                className="flex items-center justify-between px-3 py-2.5 text-sm"
              >
                <div className="flex items-center space-x-3 overflow-hidden">
                  {getFileIcon(file)}
                  <div className="min-w-0">
                    <p className="truncate font-medium text-gray-800 text-xs sm:text-sm">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-400">{formatFileSize(file.size)}</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRemoveFile(idx)}
                  disabled={isLoading}
                  className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50 cursor-pointer"
                  aria-label={`Remove ${file.name}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Upload Button */}
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={handleUploadClick}
              disabled={isLoading || selectedFiles.length === 0}
              className="w-full sm:w-auto"
            >
              {isLoading ? (
                'Uploading...'
              ) : (
                `Upload ${selectedFiles.length} File${selectedFiles.length > 1 ? 's' : ''}`
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
