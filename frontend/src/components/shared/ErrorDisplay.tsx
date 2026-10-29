import * as React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface ErrorDisplayProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message?: string;
  error?: Error | null;
  onRetry?: () => void;
  fullHeight?: boolean;
}

export function ErrorDisplay({
  title = 'Something went wrong',
  message,
  error,
  onRetry,
  fullHeight = false,
  className,
  ...props
}: ErrorDisplayProps) {
  const displayMessage =
    message || error?.message || 'An unexpected error occurred while loading this data.';

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-8 text-center rounded-xl border border-red-200 bg-red-50/50',
        fullHeight ? 'min-h-[350px] flex-1' : '',
        className
      )}
      {...props}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 mb-3 ring-8 ring-red-50">
        <AlertTriangle className="h-6 w-6 stroke-[1.75]" />
      </div>
      <h3 className="text-base font-semibold text-red-950">{title}</h3>
      <p className="mt-1 text-sm text-red-700/80 max-w-md leading-relaxed">
        {displayMessage}
      </p>
      {onRetry && (
        <div className="mt-5">
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="border-red-300 text-red-700 hover:bg-red-100 bg-white"
          >
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
