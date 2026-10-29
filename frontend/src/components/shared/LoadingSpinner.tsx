import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface LoadingSpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  text?: string;
  size?: 'sm' | 'md' | 'lg';
  fullHeight?: boolean;
}

export function LoadingSpinner({
  text = 'Loading...',
  size = 'md',
  fullHeight = false,
  className,
  ...props
}: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  };

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-6 text-center',
        fullHeight ? 'min-h-[350px] flex-1' : '',
        className
      )}
      {...props}
    >
      <Loader2
        className={cn(
          'animate-spin text-primary-600',
          sizeMap[size]
        )}
      />
      {text && (
        <p className="mt-3 text-sm font-medium text-gray-500 animate-pulse">
          {text}
        </p>
      )}
    </div>
  );
}
